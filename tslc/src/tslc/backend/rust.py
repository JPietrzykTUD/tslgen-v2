"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tslc.backend.primitive_rendering import body_for as _body_for
from tslc.backend.primitive_rendering import variant_names as _variant_names
from tslc.backend.rust_direct_calls import (
    any_caller_unsafe as _any_caller_unsafe,
    free_function as _free_function,
    free_variant_functions as _free_variant_functions,
    implementation_lint_allowance as _implementation_lint_allowance,
    implementation_trait_name as _implementation_trait_name,
    indent as _indent,
    primitive_module as _primitive_module,
    rust_implementation_state as _rust_implementation_state,
    specialization_implementation_state as _spec_implementation_state,
    variant_primitive_name as _variant_primitive_name,
)
from tslc.backend.rust_documentation_api import (
    documentation_free_function as _documentation_free_function,
    documentation_overloaded_wrapper as _documentation_overloaded_wrapper,
    documentation_wrapper as _documentation_wrapper,
)
from tslc.backend.rust_implementation_state import (
    render_implementation_state_queries as _implementation_state_queries,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelection,
    RustPolicySelectionProfile,
    rust_policy_selection_shape_reason,
)
from tslc.backend.rust_signatures import (
    arithmetic_preconditions as _rust_arithmetic_preconditions,
    axis_name as _axis_name,
    concrete_param_type as _rust_concrete_param,
    concrete_result_type as _rust_concrete_result,
    concrete_type as _rust_concrete,
    generic_decls as _generic_decls,
    impl_generic_parts as _impl_generic_parts,
    kind_type as _kind_type,
    param_kind_type as _param_kind_type,
    params as _params,
    runtime_names as _runtime_names,
    trait_args_by_name as _trait_args_by_name,
    trait_args_by_value as _trait_args_by_value,
    unsafe_call as _unsafe_call,
    unsafe_prefix as _unsafe_prefix,
    vector_type as _vector_type,
)
from tslc.backend.rust_documentation import rust_doc as _rust_doc
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_type_params import (
    index_where as _index_where,
    rust_base_dispatch_key_tag as _rust_base_dispatch_key_tag,
    type_param_base_key_args as _type_param_base_key_args,
    type_param_base_key_decls as _type_param_base_key_decls,
    type_param_decls as _type_param_decls,
    type_param_names as _type_param_names,
    with_consistent_type_param_bounds as _with_consistent_type_param_bounds,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.benchmark.model import SpecializationKey
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)
from tslc.target_text import LoweredBody, RenderContext
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_PRIMITIVE_TRAIT_PREFIX = "detail::primitives::"


def _qualified_primitive_trait_prefix(module_prefix: str) -> str:
    module = module_prefix.removesuffix("::")
    if not module:
        return _PRIMITIVE_TRAIT_PREFIX
    return f"{module}::{_PRIMITIVE_TRAIT_PREFIX}"


class RustBackend:
    backend_id = "rust"

    def __init__(
        self,
        *,
        feature_spellings: Mapping[str, str] | None = None,
        emit_target_features: bool = True,
        policy_selection: RustPolicySelectionProfile | None = None,
        deferred_policy_mapping_file: str | None = None,
    ) -> None:
        self._feature_spellings = dict(feature_spellings or {})
        self._emit_target_features = emit_target_features
        self._policy_selection = policy_selection
        if deferred_policy_mapping_file is not None and policy_selection is None:
            raise ValueError(
                "deferred Rust policy selection requires a typed selection profile"
            )
        self._deferred_policy_mapping_file = deferred_policy_mapping_file

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        internal = self.render_primitive_internal(primitive_name, specializations)
        public = self.render_primitive_public(primitive_name, specializations)
        if not internal:
            return public
        return "\n\n".join([self.render_primitive_module(internal), public])

    def render_primitive_module(self, internal: str) -> str:
        if not internal.strip():
            return ""
        if (
            self._deferred_policy_mapping_file is not None
            and self._policy_selection is not None
            and self._policy_selection.selections
        ):
            internal = (
                f"{internal}\n\n"
                "include!(concat!(env!(\"OUT_DIR\"), "
                f'"/{self._deferred_policy_mapping_file}"));'
            )
        return _primitive_module(internal)

    def render_policy_selection_impl(
        self,
        selection: RustPolicySelection,
    ) -> str:
        """Render one trusted mapping fragment from typed backend facts."""

        if self._policy_selection is None:
            raise ValueError("Rust policy mapping rendering requires a selection profile")
        expected = next(
            (
                candidate
                for candidate in self._policy_selection.selections
                if candidate.key == selection.key
            ),
            None,
        )
        if expected is None or (
            expected.specialization != selection.specialization
            or expected.candidate_ids != selection.candidate_ids
        ):
            raise ValueError(
                "Rust policy mapping selection is foreign or stale for this profile"
            )
        return self._selection_impl(
            selection,
            caller_unsafe=selection.specialization.safety.caller_unsafe,
        )

    def render_primitive_internal(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _free_variant_functions(specializations, backend=self)
        # Rust has no fn overloading: a primitive with several signatures (e.g. store's
        # `(ptr,v)`/`(ptr,s)`) dispatches on the varying argument's type via a trait
        # implemented for that type. Single-signature primitives keep the simple trait.
        if varying_positions(specializations):
            parts = [self._render_overloaded_internal(primitive_name, specializations)]
            parts.extend(
                rendered
                for name in _variant_names(specializations)
                if (
                    rendered := self._render_overloaded_internal(
                        primitive_name,
                        specializations,
                        variant_name=name,
                    )
                )
            )
            return "\n\n".join(parts)
        caller_unsafe = _any_caller_unsafe(specializations)
        trait = self._trait(primitive_name, shape, caller_unsafe=caller_unsafe)
        impls = [
            self._impl(spec, caller_unsafe=caller_unsafe)
            for spec in specializations
            if self._selection_for(spec) is None
        ]
        parts = [trait, *impls]
        selections = tuple(
            selection
            for spec in specializations
            if (selection := self._selection_for(spec)) is not None
        )
        if selections:
            default_primitive = _variant_primitive_name(primitive_name, "default")
            parts.append(
                self._trait(
                    default_primitive,
                    shape,
                    caller_unsafe=caller_unsafe,
                )
            )
            parts.extend(
                self._impl(
                    selection.specialization,
                    caller_unsafe=caller_unsafe,
                    implementation_trait_variant="default",
                )
                for selection in selections
            )
        for name in _variant_names(specializations):
            variant_primitive = _variant_primitive_name(primitive_name, name)
            variant_impls = [
                rendered
                for spec in specializations
                if (rendered := self._impl(
                    spec,
                    caller_unsafe=caller_unsafe,
                    variant_name=name,
                ))
            ]
            if variant_impls:
                parts.append(
                    self._trait(
                        variant_primitive,
                        shape,
                        caller_unsafe=caller_unsafe,
                    )
                )
                parts.extend(variant_impls)
        if self._deferred_policy_mapping_file is None:
            parts.extend(
                self._selection_impl(selection, caller_unsafe=caller_unsafe)
                for selection in selections
            )
        return "\n\n".join(parts)

    def render_primitive_public(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            # A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module,
            # not a `SimdVector`-bound trait/impl/wrapper.
            return _free_function(shape, backend=self)
        caller_unsafe = _any_caller_unsafe(specializations)
        if varying_positions(specializations):
            return self._render_overloaded_wrapper(
                primitive_name, specializations, caller_unsafe=caller_unsafe
            )
        return self._wrapper(primitive_name, shape, caller_unsafe=caller_unsafe)

    def render_documentation_api(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render one profile-neutral public API stub for rustdoc.

        The generated function preserves the public parameter, result, generic,
        safety, and documentation shape without depending on a profile-local
        dispatch trait or implementation body.
        """

        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _documentation_free_function(shape)
        caller_unsafe = _any_caller_unsafe(specializations)
        if varying_positions(specializations):
            return _documentation_overloaded_wrapper(
                primitive_name,
                specializations,
                caller_unsafe=caller_unsafe,
            )
        return _documentation_wrapper(
            primitive_name,
            shape,
            caller_unsafe=caller_unsafe,
        )

    def render_implementation_state_queries(
        self,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> str:
        return _implementation_state_queries(
            {
                primitive_name: _with_consistent_type_param_bounds(specializations)
                for primitive_name, specializations in by_primitive.items()
            }
        )

    def concrete_vector_type(self, spec: LoweredSpecialization) -> str:
        """Spell the concrete Rust SIMD type selected for one specialization."""

        return _vector_type(spec)

    def render_direct_implementation_call(
        self,
        spec: LoweredSpecialization,
        variant_name: str | None,
        arguments: tuple[str, ...],
        *,
        module_prefix: str = "",
        immediate_value: str | None = None,
        overload_parameter_positions: tuple[int, ...] = (),
        selection_key: SpecializationKey | None = None,
    ) -> str:
        """Render a direct call to one already-emitted implementation trait.

        This is the backend-owned call boundary for projections such as the
        generated benchmark harness.  It deliberately bypasses the public
        wrapper without duplicating Rust trait naming, const-argument order,
        concrete vector spelling, or caller-unsafe framing.
        """

        if _body_for(spec, variant_name) is None:
            candidate = "default" if variant_name is None else variant_name
            raise ValueError(
                f"Rust implementation candidate {candidate!r} is not available for "
                f"{spec.primitive_name!r}"
            )
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            spec.result_kind,
            spec.param_kinds,
        ):
            raise ValueError("direct Rust implementation trait calls require a SIMD shape")
        expected_arguments = sum(
            kind != DEFAULT_SUPPORT_POLICY.immediate_kind for kind in spec.param_kinds
        )
        if len(arguments) != expected_arguments:
            raise ValueError(
                f"Rust implementation call for {spec.primitive_name!r} requires "
                f"{expected_arguments} runtime arguments, got {len(arguments)}"
            )
        if immediate_value is not None and spec.immediate is None:
            raise ValueError(
                f"Rust implementation call for {spec.primitive_name!r} has no immediate"
            )
        if spec.type_params:
            raise ValueError(
                "direct Rust implementation calls with SIMD type parameters require "
                "concrete type arguments"
            )
        trait_prefix = _qualified_primitive_trait_prefix(module_prefix)

        if overload_parameter_positions:
            if len(overload_parameter_positions) != 1:
                raise ValueError(
                    "direct Rust implementation calls support one overload parameter"
                )
            if spec.immediate is not None or spec.target is not None:
                raise ValueError(
                    "direct overloaded Rust implementation calls do not support "
                    "immediate or target-vector shapes"
                )
            varying = overload_parameter_positions[0]
            if not 0 <= varying < len(arguments):
                raise ValueError("Rust overload parameter position is out of range")
            overload_trait_arguments = [
                self.concrete_vector_type(spec),
                *(value for _name, value in spec.axis),
                *(default for _name, _type, default in spec.generic_params),
            ]
            trait_name = _implementation_trait_name(
                spec.primitive_name, variant_name
            )
            fixed_arguments = [
                argument
                for position, argument in enumerate(arguments)
                if position != varying
            ]
            call_arguments = ", ".join(
                (arguments[varying], *fixed_arguments)
            )
            receiver_type = _rust_concrete(spec, spec.param_kinds[varying])
            call = (
                f"<{receiver_type} as {trait_prefix}{trait_name}Arg"
                f"<{', '.join(overload_trait_arguments)}>>::apply({call_arguments})"
            )
            return _unsafe_call(call, spec.safety.caller_unsafe)

        trait_arguments: list[str] = []
        if spec.target is not None:
            trait_arguments.append(spec.target.vector_spelling)
        trait_arguments.extend(value for _name, value in spec.axis)
        if spec.immediate is not None:
            trait_arguments.append(immediate_value or spec.immediate[0])
        trait_arguments.extend(default for _name, _type, default in spec.generic_params)
        generic_args = (
            f"<{', '.join(trait_arguments)}>" if trait_arguments else ""
        )
        direct_variant = variant_name
        if (
            variant_name is None
            and selection_key is not None
            and rust_policy_selection_shape_reason(selection_key, spec) is None
        ):
            direct_variant = "default"
        trait_name = _implementation_trait_name(spec.primitive_name, direct_variant)
        call = (
            f"<{self.concrete_vector_type(spec)} as {trait_prefix}{trait_name}"
            f"{generic_args}>::apply({', '.join(arguments)})"
        )
        return _unsafe_call(call, spec.safety.caller_unsafe)

    def _render_overloaded_internal(
        self,
        primitive_name: str,
        specs: tuple[LoweredSpecialization, ...],
        *,
        variant_name: str | None = None,
    ) -> str:
        shape = specs[0]
        internal_name = _variant_primitive_name(primitive_name, variant_name)
        caller_unsafe = _any_caller_unsafe(specs)
        # Exactly one varying position: wider overloads were rejected by
        # validate_rust_profiles (TSL-BACKEND-RUST-UNSUPPORTED-MULTI-POSITION-OVERLOAD).
        vi = varying_positions(specs)[0]
        arg_trait = f"{rust_primitive_trait_name(internal_name)}Arg"
        fixed = [
            (name, kind)
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
            if i != vi
        ]
        # In the arg-trait `Self` is the *argument* type, not the vector — a vector-typed
        # result (e.g. shift's `v` -> register) must project through the vector param `S`.
        ret = _kind_type(shape.result_kind, "S")
        axis_decl = "".join(f", const {_axis_name(k)}: bool" for k, _ in shape.axis)
        # `generic_params` (e.g. `PreserveSign`) are free const generics on the arg-trait too.
        gp_decl = "".join(f", const {name}: {typ}" for name, typ, _ in shape.generic_params)
        gp_names = [name for name, _, _ in shape.generic_params]
        fixed_trait = "".join(f", {n}: {_param_kind_type(k, 'S')}" for n, k in fixed)
        doc = _rust_doc(
            shape, context="Rust overload dispatch trait", concrete=False
        )
        trait = (
            (f"{doc}\n" if doc else "")
            + f"pub trait {arg_trait}<S: StaticSimdVector{axis_decl}{gp_decl}> {{\n"
            "    const IMPLEMENTATION_STATE: ImplementationState;\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_trait}) -> {ret};\n"
            f"}}"
        )

        # Dedup is per (Vec, axis) group — one impl per distinct argument type *within*
        # a group (scalar's register==base collapses its two overloads to one).
        impls: list[str] = []
        seen: set[tuple[str, str, tuple, tuple[str, ...]]] = set()
        for spec in specs:
            body_ref = _body_for(spec, variant_name)
            if body_ref is None:
                continue
            signature = (
                spec.base_type_spelling,
                spec.extension_name,
                spec.axis,
                effective_param_types(spec),
            )
            if signature in seen:
                continue
            seen.add(signature)
            # A sized vector's overloaded impls are parameterized by its lane parameter — UNLESS
            # the slot is monomorphized at a concrete lane count (a numeric `lane_parameter` like
            # "16"), in which case the impl is over a concrete `Generic<16>` with no lane generic.
            lane_parameter = spec.lane_parameter
            has_lane_generic = (
                spec.uses_sized_vector
                and lane_parameter is not None
                and not lane_parameter.isdigit()
            )
            impl_generics = (
                [f"const {lane_parameter}: usize"]
                if has_lane_generic
                else []
            ) + [
                f"const {name}: {typ}" for name, typ, _ in spec.generic_params
            ]
            impl_generic_names = (
                [lane_parameter]
                if has_lane_generic and lane_parameter is not None
                else []
            ) + [name for name, _, _ in spec.generic_params]
            vec = self.concrete_vector_type(spec)
            impl_prefix = f"impl<{', '.join(impl_generics)}>" if impl_generics else "impl"
            self_ty = _rust_concrete(spec, spec.param_kinds[vi])
            trait_args = (
                "<"
                + vec
                + "".join(f", {value}" for _, value in spec.axis)
                + "".join(f", {name}" for name in gp_names)
                + ">"
            )
            fixed_impl = "".join(
                f", {n}: {_rust_concrete_param(spec, k)}" for n, k in fixed
            )
            ret_impl = _rust_concrete_result(spec)
            body_context = RenderContext(
                current_owner=f"<{vec} as SimdVector>",
                current_vector=vec,
                current_register=spec.register_spelling,
                current_base=spec.base_type_spelling,
                current_mask=f"<{vec} as SimdVector>::MaskType",
                current_imask=f"<{vec} as SimdVector>::ImaskType",
            )
            helper_params = ", ".join(
                (
                    f"{spec.param_names[vi]}: {self_ty}",
                    *(f"{n}: {_rust_concrete_param(spec, k)}" for n, k in fixed),
                )
            )
            helper_args = ", ".join((spec.param_names[vi], *[n for n, _ in fixed]))
            method_body = "\n".join(
                (
                    f"let {spec.param_names[vi]} = self;",
                    self._target_feature_body(
                        spec,
                        body_ref,
                        render_context=body_context,
                        params=helper_params,
                        args=helper_args,
                        return_type=ret_impl,
                        generic_decls=impl_generics,
                        generic_names=impl_generic_names,
                        receiver_type=vec,
                    ),
                )
            )
            doc_context = (
                "Rust specialization"
                if variant_name is None
                else f"Rust specialization variant {variant_name}"
            )
            doc = _rust_doc(spec, context=doc_context)
            impls.append(
                (f"{doc}\n" if doc else "")
                + f"{impl_prefix} {arg_trait}{trait_args} for {self_ty} {{\n"
                f"    const IMPLEMENTATION_STATE: ImplementationState = "
                f"{_rust_implementation_state(_spec_implementation_state(spec, variant_name))};\n"
                f"{_indent(_implementation_lint_allowance(spec), 4)}\n"
                f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_impl}) -> {ret_impl} {{\n"
                f"{_indent(method_body, 8)}\n"
                f"    }}\n"
                f"}}"
            )
            shift = spec.primitive_semantics.shift
            if shift is not None and spec.param_kinds[vi] == "s":
                forwarded_args = ", ".join(name for name, _kind in fixed)
                for count_tag in shift.scalar_count_types:
                    count_type = SCALAR_TYPE_INFOS[
                        count_tag
                    ].documentation_short_label
                    if count_type == self_ty:
                        continue
                    call = (
                        f"<{self_ty} as {arg_trait}{trait_args}>::apply("
                        f"self as {self_ty}"
                        + (f", {forwarded_args}" if forwarded_args else "")
                        + ")"
                    )
                    if caller_unsafe:
                        call = f"unsafe {{ {call} }}"
                    impls.append(
                        f"{impl_prefix} {arg_trait}{trait_args} for {count_type} {{\n"
                        "    const IMPLEMENTATION_STATE: ImplementationState = "
                        f"<{self_ty} as {arg_trait}{trait_args}>::"
                        "IMPLEMENTATION_STATE;\n"
                        f"    {_unsafe_prefix(caller_unsafe)}fn apply("
                        f"self{fixed_impl}) -> {ret_impl} {{\n"
                        f"        {call}\n"
                        "    }\n"
                        "}"
                    )

        return "\n\n".join([trait, *impls]) if impls else ""

    def _render_overloaded_wrapper(
        self,
        primitive_name: str,
        specs: tuple[LoweredSpecialization, ...],
        *,
        caller_unsafe: bool,
    ) -> str:
        shape = specs[0]
        vi = varying_positions(specs)[0]
        arg_trait = (
            f"{_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
        )
        fixed = [
            (name, kind)
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
            if i != vi
        ]
        axis_wrap = "".join(f"const {_axis_name(k)}: bool, " for k, _ in shape.axis)
        axis_args = "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        gp_wrap = "".join(f"const {name}: {typ}, " for name, typ, _ in shape.generic_params)
        gp_names = [name for name, _, _ in shape.generic_params]
        gp_args = "".join(f", {name}" for name in gp_names)
        wrap_params = ", ".join(
            (f"{name}: V" if i == vi else f"{name}: {_param_kind_type(kind, 'S')}")
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        )
        fixed_names = [n for n, _ in fixed]
        call_args = ", ".join((shape.param_names[vi], *fixed_names))
        call = f"<V as {arg_trait}<S{axis_args}{gp_args}>>::apply({call_args})"
        call = _unsafe_call(call, caller_unsafe)
        unsafe_prefix = _unsafe_prefix(caller_unsafe)
        ret_type = _kind_type(shape.result_kind, "S")
        doc = _rust_doc(shape, context="Rust wrapper", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"pub {unsafe_prefix}fn {primitive_name}"
            f"<S: StaticSimdVector, {axis_wrap}{gp_wrap}"
            f"V: {arg_trait}<S{axis_args}{gp_args}>>"
            f"({wrap_params}) -> {ret_type} {{\n"
            f"    {call}\n"
            f"}}"
        )

    def _trait(
        self,
        primitive_name: str,
        shape: LoweredSpecialization,
        *,
        caller_unsafe: bool,
    ) -> str:
        # Boolean-wildcard axes and an `sImm` immediate become const-generics on the trait,
        # so the `[aligned=*]` variants are distinct impls (`StoreImpl<false>`/`StoreImpl<true>`)
        # and the immediate is a free param (`MulImmImpl<const factor: u32>`).
        decls = _generic_decls(shape)
        ret = _kind_type(shape.result_kind, "Self")
        target_owner: str | None = None
        # A representation-change primitive takes the target vector as a first generic
        # `ToVec`; its result and target-owned parameters project through that vector.
        if shape.target is not None:
            decls = ["ToVec: StaticSimdVector", *decls]
            ret = _kind_type(shape.result_kind, "ToVec")
            target_owner = "ToVec"
        elif shape.result_vector_param is not None:
            ret = _kind_type(shape.result_kind, shape.result_vector_param)
        # Free SIMD type params (gather's `IndicesType`) — a `vidx` param projects through one.
        decls = _type_param_decls(shape) + _type_param_base_key_decls(shape) + decls
        vidx_type = f"{shape.type_params[0].name}::RegisterType" if shape.type_params else None
        params = _params(
            shape,
            "Self",
            target_owner=target_owner,
            vidx_type=vidx_type,
        )
        generics = f"<{', '.join(decls)}>" if decls else ""
        trait_header = (
            f"pub trait {rust_primitive_trait_name(primitive_name)}{generics}: "
            f"StaticSimdVector{_index_where(shape, base_dispatch='hidden')}"
        )
        doc = _rust_doc(shape, context="Rust dispatch trait", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"{trait_header} {{\n"
            "    const IMPLEMENTATION_STATE: ImplementationState;\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret};\n"
            f"}}"
        )

    def _impl(
        self,
        spec: LoweredSpecialization,
        *,
        caller_unsafe: bool,
        variant_name: str | None = None,
        implementation_trait_variant: str | None = None,
    ) -> str:
        body_ref = _body_for(spec, variant_name)
        if body_ref is None:
            return ""
        # A sized vector's impl is parameterized by its lane const generic; an `sImm` immediate
        # is a further free const generic. A monomorphized slot (numeric `lane_parameter`) is over
        # a concrete `Generic<N>` instead, so it declares no lane generic.
        impl_parts, impl_generic_names = _impl_generic_parts(spec)
        key = self.concrete_vector_type(spec)
        impl_generics = f"<{', '.join(impl_parts)}>" if impl_parts else ""
        targs = _trait_args_by_value(spec)
        ret = _kind_type(spec.result_kind, "Self")
        target_owner: str | None = None
        # The target vector is concrete in the impl's trait args; the result and
        # target-owned parameters project through that concrete vector.
        if spec.target is not None:
            targs = [spec.target.vector_spelling, *targs]
            target_owner = f"<{spec.target.vector_spelling} as SimdVector>"
            ret = _kind_type(spec.result_kind, target_owner)
        elif spec.result_vector_param is not None:
            ret = _kind_type(spec.result_kind, spec.result_vector_param)
        targs = [
            *_type_param_names(spec),
            *_type_param_base_key_args(spec, mode="concrete"),
            *targs,
        ]
        vidx_type = f"{spec.type_params[0].name}::RegisterType" if spec.type_params else None
        params = _params(
            spec,
            "Self",
            target_owner=target_owner,
            vidx_type=vidx_type,
        )
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        # Native index intrinsics take the concrete integer-register type for the selected ISA.
        # Lowering resolves it from source extension metadata; scalar/generic stay opaque.
        impl_register = spec.index_register_spelling
        body_context = RenderContext(
            current_vector=key,
            current_register=spec.register_spelling,
            current_base=spec.base_type_spelling,
            current_mask=f"<{key} as SimdVector>::MaskType",
            current_imask=f"<{key} as SimdVector>::ImaskType",
        )
        concrete_owner = f"<{key} as SimdVector>"
        body = self._target_feature_body(
            spec,
            body_ref,
            render_context=body_context,
            params=_params(
                spec,
                concrete_owner,
                target_owner=target_owner,
                vidx_type=vidx_type,
            ),
            args=_runtime_names(spec),
            return_type=_kind_type(
                spec.result_kind,
                target_owner or spec.result_vector_param or concrete_owner,
            ),
            generic_decls=impl_parts,
            generic_names=impl_generic_names,
            where_clause=_index_where(
                spec,
                impl_register=impl_register,
                base_dispatch="concrete",
            ),
            receiver_type=key,
        )
        doc_context = (
            "Rust specialization"
            if variant_name is None
            else f"Rust specialization variant {variant_name}"
        )
        doc = _rust_doc(spec, context=doc_context)
        trait_name = _implementation_trait_name(
            spec.primitive_name,
            implementation_trait_variant
            if implementation_trait_variant is not None
            else variant_name,
        )
        preconditions = _rust_arithmetic_preconditions(spec)
        return (
            (f"{doc}\n" if doc else "")
            + f"impl{impl_generics} {trait_name}"
            + f"{trait_args} for {key}"
            f"{_index_where(spec, impl_register=impl_register, base_dispatch='concrete')} {{\n"
            f"    const IMPLEMENTATION_STATE: ImplementationState = "
            f"{_rust_implementation_state(_spec_implementation_state(spec, variant_name))};\n"
            f"{_indent(_implementation_lint_allowance(spec), 4)}\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret} {{\n"
            f"{preconditions}"
            f"{_indent(body, 8)}\n"
            f"    }}\n"
            f"}}"
        )

    def _selection_for(
        self,
        spec: LoweredSpecialization,
    ) -> RustPolicySelection | None:
        if self._policy_selection is None:
            return None
        return next(
            (
                selection
                for selection in self._policy_selection.selections
                if selection.specialization == spec
            ),
            None,
        )

    def _selection_impl(
        self,
        selection: RustPolicySelection,
        *,
        caller_unsafe: bool,
    ) -> str:
        spec = selection.specialization
        reason = rust_policy_selection_shape_reason(selection.key, spec)
        if reason is not None:
            raise ValueError(
                f"Rust policy selection renderer received an unsupported shape: {reason}"
            )
        selected_variant = (
            "default"
            if selection.selected_candidate == "default"
            else selection.selected_candidate
        )
        trait_name = _implementation_trait_name(spec.primitive_name)
        selected_trait_name = _implementation_trait_name(
            spec.primitive_name, selected_variant
        )
        key = self.concrete_vector_type(spec)
        params = _params(spec, "Self")
        result = _kind_type(spec.result_kind, "Self")
        call = (
            f"<Self as {selected_trait_name}>::apply({_runtime_names(spec)})"
        )
        call = _unsafe_call(call, caller_unsafe)
        return (
            f"impl {trait_name} for {key} {{\n"
            f"    const IMPLEMENTATION_STATE: ImplementationState = "
            f"<Self as {selected_trait_name}>::IMPLEMENTATION_STATE;\n"
            "    #[inline(always)]\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {result} {{\n"
            f"        {call}\n"
            "    }\n"
            "}"
        )

    def _wrapper(
        self,
        primitive_name: str,
        shape: LoweredSpecialization,
        *,
        caller_unsafe: bool,
    ) -> str:
        names = _runtime_names(shape)
        # `S` comes first, then the const-generic axis/immediate params — the same turbofish
        # order as the overloaded wrapper (`S, ALIGNED, V`), so a call site can spell
        # `name::<Self, …>` uniformly. The trait bound carries them (`S: MulImmImpl<factor>`);
        # Rust allows referencing a const-generic in the bound before it is declared.
        targs = _trait_args_by_name(shape)
        decl_list = _generic_decls(shape)
        ret = _kind_type(shape.result_kind, "S")
        call = ""
        target_owner: str | None = None
        # A representation-change primitive takes the target vector `T` as a generic, bounds `S`
        # on `…Impl<T, …>`, and projects the result and target-owned parameters through `T`;
        # the call is qualified to pin the target.
        if shape.target is not None:
            targs = ["T", *targs]
            decl_list = ["T: StaticSimdVector", *decl_list]
            ret = _kind_type(shape.result_kind, "T")
            target_owner = "T"
            call = (
                f"<S as {_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}"
                f"<{', '.join(targs)}>>::apply({names})"
            )
        # Free SIMD type params: declare them (bounded) and pass them as trait args. The call is
        # qualified — `IndicesType::RegisterType` is non-injective, so it can't be inferred from
        # the `vidx` argument; pinning `IndicesType` in the trait path resolves `apply`.
        if shape.type_params:
            targs = [
                *_type_param_names(shape),
                *_type_param_base_key_args(shape, mode="projection"),
                *targs,
            ]
            decl_list = _type_param_decls(
                shape, trait_prefix=_PRIMITIVE_TRAIT_PREFIX
            ) + decl_list
            vidx_type = f"{shape.type_params[0].name}::RegisterType"
            call = (
                f"<S as {_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}"
                f"<{', '.join(targs)}>>::apply({names})"
            )
            if shape.result_vector_param is not None:
                ret = _kind_type(shape.result_kind, shape.result_vector_param)
        else:
            vidx_type = None
        params = _params(
            shape,
            "S",
            target_owner=target_owner,
            vidx_type=vidx_type,
        )
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        decls = "".join(f", {d}" for d in decl_list)
        call = (
            f"<S as {_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}"
            f"{trait_args}>::apply({names})"
        )
        call = _unsafe_call(call, caller_unsafe)
        doc = _rust_doc(shape, context="Rust wrapper", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"pub {_unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
            f"<S: {_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}"
            f"{trait_args}{decls}>"
            f"({params}) -> {ret}{_index_where(shape, base_dispatch='projection')} {{\n"
            f"    {call}\n"
            f"}}"
        )

    def _target_feature_body(
        self,
        spec: LoweredSpecialization,
        body: LoweredBody,
        *,
        render_context: RenderContext | None = None,
        params: str,
        args: str,
        return_type: str,
        generic_decls: list[str] | tuple[str, ...] = (),
        generic_names: list[str] | tuple[str, ...] = (),
        where_clause: str = "",
        receiver_type: str | None = None,
    ) -> str:
        attrs = self._target_feature_attrs(spec)
        active_context = render_context or RenderContext()
        if attrs and receiver_type is not None:
            active_context = replace(
                active_context,
                current_owner=f"<{receiver_type} as SimdVector>",
            )
        rendered_body = body.render(active_context)
        if not attrs:
            return rendered_body
        decls = f"<{', '.join(generic_decls)}>" if generic_decls else ""
        call_generics = f"::<{', '.join(generic_names)}>" if generic_names else ""
        attr_lines = "\n".join(attrs)
        return (
            f"{attr_lines}\n"
            f"unsafe fn __tsl_target_feature_body{decls}({params}) -> {return_type}"
            f"{where_clause} {{\n"
            f"{_indent(rendered_body, 4)}\n"
            f"}}\n"
            f"unsafe {{ __tsl_target_feature_body{call_generics}({args}) }}"
        )

    def _target_feature_attrs(self, spec: LoweredSpecialization) -> tuple[str, ...]:
        if not self._emit_target_features or not spec.required_features:
            return ()
        return tuple(
            f'#[target_feature(enable = "{self._feature_spellings.get(feature, feature)}")]'
            for feature in sorted(spec.required_features)
        )
