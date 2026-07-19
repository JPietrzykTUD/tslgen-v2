"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tslc.backend.primitive_rendering import body_for as _body_for
from tslc.backend.primitive_rendering import variant_names as _variant_names
from tslc.backend.rust_implementation_state import (
    render_implementation_state_queries as _implementation_state_queries,
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
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES, rust_free_type
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.target_capability import rust_extension_tag
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)
from tslc.lower.implementation_state import ImplementationState
from tslc.target_text import LoweredBody, RenderContext
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_PRIMITIVE_TRAIT_PREFIX = "detail::primitives::"


class RustBackend:
    backend_id = "rust"

    def __init__(
        self,
        *,
        feature_spellings: Mapping[str, str] | None = None,
        emit_target_features: bool = True,
    ) -> None:
        self._feature_spellings = dict(feature_spellings or {})
        self._emit_target_features = emit_target_features

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        internal = self.render_primitive_internal(primitive_name, specializations)
        public = self.render_primitive_public(primitive_name, specializations)
        if not internal:
            return public
        return "\n\n".join([_primitive_module(internal), public])

    def render_primitive_module(self, internal: str) -> str:
        return _primitive_module(internal) if internal.strip() else ""

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
            self._impl(spec, caller_unsafe=caller_unsafe) for spec in specializations
        ]
        parts = [trait, *impls]
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
            vec = _vector_type(spec)
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
                f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_impl}) -> {ret_impl} {{\n"
                f"{_indent(method_body, 8)}\n"
                f"    }}\n"
                f"}}"
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
        vt_type: str | None = None
        # A representation-change primitive takes the target vector as a first generic `ToVec`
        # and returns (and may take, via a `vt` param) its register type.
        if shape.target is not None:
            decls = ["ToVec: StaticSimdVector", *decls]
            ret = "ToVec::RegisterType"
            vt_type = "ToVec::RegisterType"
        # Free SIMD type params (gather's `IndicesType`) — a `vidx` param projects through one.
        decls = _type_param_decls(shape) + _type_param_base_key_decls(shape) + decls
        vidx_type = f"{shape.type_params[0].name}::RegisterType" if shape.type_params else None
        params = _params(shape, "Self", vt_type=vt_type, vidx_type=vidx_type)
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
    ) -> str:
        body_ref = _body_for(spec, variant_name)
        if body_ref is None:
            return ""
        # A sized vector's impl is parameterized by its lane const generic; an `sImm` immediate
        # is a further free const generic. A monomorphized slot (numeric `lane_parameter`) is over
        # a concrete `Generic<N>` instead, so it declares no lane generic.
        impl_parts, impl_generic_names = _impl_generic_parts(spec)
        key = _vector_type(spec)
        impl_generics = f"<{', '.join(impl_parts)}>" if impl_parts else ""
        targs = _trait_args_by_value(spec)
        ret = _kind_type(spec.result_kind, "Self")
        vt_type: str | None = None
        # The target vector is concrete in the impl's trait args; the result (and any `vt`
        # param) is its concrete register.
        if spec.target is not None:
            targs = [spec.target.vector_spelling, *targs]
            ret = spec.target.register_spelling
            vt_type = spec.target.register_spelling
        targs = [
            *_type_param_names(spec),
            *_type_param_base_key_args(spec, mode="concrete"),
            *targs,
        ]
        vidx_type = f"{spec.type_params[0].name}::RegisterType" if spec.type_params else None
        params = _params(spec, "Self", vt_type=vt_type, vidx_type=vidx_type)
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
                vt_type=vt_type,
                vidx_type=vidx_type,
            ),
            args=_runtime_names(spec),
            return_type=(
                spec.target.register_spelling
                if spec.target is not None
                else _kind_type(spec.result_kind, concrete_owner)
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
        trait_primitive = _variant_primitive_name(spec.primitive_name, variant_name)
        return (
            (f"{doc}\n" if doc else "")
            + f"impl{impl_generics} {rust_primitive_trait_name(trait_primitive)}"
            + f"{trait_args} for {key}"
            f"{_index_where(spec, impl_register=impl_register, base_dispatch='concrete')} {{\n"
            f"    const IMPLEMENTATION_STATE: ImplementationState = "
            f"{_rust_implementation_state(_spec_implementation_state(spec, variant_name))};\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret} {{\n"
            f"{_indent(body, 8)}\n"
            f"    }}\n"
            f"}}"
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
        vt_type: str | None = None
        # A representation-change primitive takes the target vector `T` as a generic, bounds `S`
        # on `…Impl<T, …>`, and returns (and may take, via a `vt` param) `T`'s register; the
        # call is qualified to pin the target.
        if shape.target is not None:
            targs = ["T", *targs]
            decl_list = ["T: StaticSimdVector", *decl_list]
            ret = "T::RegisterType"
            vt_type = "T::RegisterType"
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
        else:
            vidx_type = None
        params = _params(shape, "S", vt_type=vt_type, vidx_type=vidx_type)
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


def _free_function(spec: LoweredSpecialization, *, backend: RustBackend) -> str:
    """A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module, with
    concrete pointer/size types (no `SimdVector` projection). The body's `unsafe` framing is
    already applied by the lowered body (raw pointer / allocation access)."""

    params = ", ".join(
        f"{name}: {_free_kind_type(kind, spec)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    ret_clause = (
        ""
        if spec.result_kind == "void"
        else f" -> {_free_kind_type(spec.result_kind, spec)}"
    )
    ret_type = (
        "()"
        if spec.result_kind == "void"
        else _free_kind_type(spec.result_kind, spec)
    )
    unsafe_prefix = _unsafe_prefix(spec.safety.caller_unsafe)
    function_name = rust_raw_identifier(spec.primitive_name)
    body = backend._target_feature_body(
        spec,
        spec.body,
        params=params,
        args=_runtime_names(spec),
        return_type=ret_type,
    )
    doc = _rust_doc(spec, context="Rust free function")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix}fn {function_name}({params}){ret_clause} {{\n"
        f"{_indent(body, 4)}\n"
        f"}}"
    )


def _documentation_wrapper(
    primitive_name: str,
    shape: LoweredSpecialization,
    *,
    caller_unsafe: bool,
) -> str:
    declarations = _generic_decls(shape)
    result_type = _kind_type(shape.result_kind, "S")
    target_type: str | None = None
    if shape.target is not None:
        declarations = ["T: StaticSimdVector", *declarations]
        result_type = "T::RegisterType"
        target_type = "T::RegisterType"
    index_type: str | None = None
    if shape.type_params:
        declarations = [
            *(f"{param.name}: StaticSimdVector" for param in shape.type_params),
            *declarations,
        ]
        index_type = f"{shape.type_params[0].name}::RegisterType"
    generics = ", ".join(("S: StaticSimdVector", *declarations))
    params = _params(
        shape,
        "S",
        vt_type=target_type,
        vidx_type=index_type,
    )
    doc = _rust_doc(shape, context="Rust documentation facade", concrete=False)
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {_unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
        f"<{generics}>({params}) -> {result_type}"
        f"{_index_where(shape, base_dispatch='projection')} {{\n"
        "    unimplemented!()\n"
        "}"
    )


def _documentation_overloaded_wrapper(
    primitive_name: str,
    specs: tuple[LoweredSpecialization, ...],
    *,
    caller_unsafe: bool,
) -> str:
    shape = specs[0]
    varying_index = varying_positions(specs)[0]
    declarations = [
        "S: StaticSimdVector",
        *_generic_decls(shape),
        "V",
    ]
    params = ", ".join(
        (
            f"{name}: V"
            if index == varying_index
            else f"{name}: {_param_kind_type(kind, 'S')}"
        )
        for index, (name, kind) in enumerate(
            zip(shape.param_names, shape.param_kinds)
        )
    )
    result_type = _kind_type(shape.result_kind, "S")
    doc = _rust_doc(shape, context="Rust documentation facade", concrete=False)
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {_unsafe_prefix(caller_unsafe)}fn {rust_raw_identifier(primitive_name)}"
        f"<{', '.join(declarations)}>({params}) -> {result_type} {{\n"
        "    unimplemented!()\n"
        "}"
    )


def _documentation_free_function(spec: LoweredSpecialization) -> str:
    params = ", ".join(
        f"{name}: {_free_kind_type(kind, spec)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    result = (
        ""
        if spec.result_kind == "void"
        else f" -> {_free_kind_type(spec.result_kind, spec)}"
    )
    doc = _rust_doc(spec, context="Rust documentation facade")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {_unsafe_prefix(spec.safety.caller_unsafe)}fn "
        f"{rust_raw_identifier(spec.primitive_name)}({params}){result} {{\n"
        "    unimplemented!()\n"
        "}"
    )


def _spec_implementation_state(
    spec: LoweredSpecialization,
    variant_name: str | None,
) -> ImplementationState:
    if variant_name is None:
        return spec.implementation_state
    for variant in spec.variant_bodies:
        if variant.name == variant_name:
            return variant.implementation_state
    return ImplementationState.UNKNOWN


def _rust_implementation_state(state: ImplementationState) -> str:
    return {
        ImplementationState.NATIVE: "ImplementationState::Native",
        ImplementationState.COMPOSED: "ImplementationState::Composed",
        ImplementationState.FALLBACK: "ImplementationState::Fallback",
        ImplementationState.UNKNOWN: "ImplementationState::Unknown",
    }[state]


def _free_variant_functions(
    specializations: tuple[LoweredSpecialization, ...],
    *,
    backend: RustBackend,
) -> str:
    rendered: list[str] = []
    for spec in specializations:
        for variant in spec.variant_bodies:
            rendered.append(_free_function_variant(spec, variant.name, backend=backend))
    return "\n\n".join(rendered)


def _free_function_variant(
    spec: LoweredSpecialization,
    variant_name: str,
    *,
    backend: RustBackend,
) -> str:
    body = _body_for(spec, variant_name)
    if body is None:
        return ""
    params = ", ".join(
        f"{name}: {_free_kind_type(kind, spec)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    ret_clause = (
        ""
        if spec.result_kind == "void"
        else f" -> {_free_kind_type(spec.result_kind, spec)}"
    )
    ret_type = (
        "()"
        if spec.result_kind == "void"
        else _free_kind_type(spec.result_kind, spec)
    )
    unsafe_prefix = _unsafe_prefix(spec.safety.caller_unsafe)
    function_name = rust_raw_identifier(
        _variant_primitive_name(spec.primitive_name, variant_name)
    )
    body_text = backend._target_feature_body(
        spec,
        body,
        params=params,
        args=_runtime_names(spec),
        return_type=ret_type,
    )
    doc = _rust_doc(spec, context=f"Rust free function variant {variant_name}")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix}fn {function_name}({params}){ret_clause} {{\n"
        f"{_indent(body_text, 4)}\n"
        f"}}"
    )


def _variant_primitive_name(
    primitive_name: str, variant_name: str | None = None
) -> str:
    if variant_name is None:
        return primitive_name
    return f"{primitive_name}_{variant_name}"


def _primitive_module(internal: str) -> str:
    return (
        "#[doc(hidden)]\n"
        "pub mod detail {\n"
        "    pub mod primitives {\n"
        "        use super::super::*;\n\n"
        f"{_indent(internal, 8)}\n"
        "    }\n"
        "}"
    )


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _any_caller_unsafe(specs: tuple[LoweredSpecialization, ...]) -> bool:
    return any(spec.safety.caller_unsafe for spec in specs)


def _unsafe_prefix(enabled: bool) -> str:
    return "unsafe " if enabled else ""


def _unsafe_call(call: str, enabled: bool) -> str:
    return f"unsafe {{ {call} }}" if enabled else call


def _free_kind_type(kind: str, spec: LoweredSpecialization) -> str:
    """A free function's kind -> concrete Rust type (no `Self` projection). Pointer spellings
    carry their own mutability; `usize` is a size; `void` is unit."""

    return rust_free_type(
        kind,
        spec.base_type_spelling,
        base_type_tag=spec.type_tag,
    )


def _impl_generic_parts(shape: LoweredSpecialization) -> tuple[list[str], list[str]]:
    """Rust impl generic declarations and the matching turbofish names."""

    const_decls: list[str] = []
    const_names: list[str] = []
    lane_parameter = shape.lane_parameter
    if (
        shape.uses_sized_vector
        and lane_parameter is not None
        and not lane_parameter.isdigit()
    ):
        const_decls.append(f"const {lane_parameter}: usize")
        const_names.append(lane_parameter)
    if shape.immediate is not None:
        const_decls.append(f"const {shape.immediate[0]}: {shape.immediate[1]}")
        const_names.append(shape.immediate[0])
    for name, typ, _default in shape.generic_params:
        const_decls.append(f"const {name}: {typ}")
        const_names.append(name)
    # Free SIMD type params stay generic in the impl; Rust requires type params
    # before const params, and the helper call uses the same order.
    return (
        [*_type_param_decls(shape), *const_decls],
        [*_type_param_names(shape), *const_names],
    )


def _axis_name(key: str) -> str:
    """An axis attribute key as a Rust const-generic name (`aligned` -> `ALIGNED`)."""

    return key.upper()


def _ext_tag(extension_name: str) -> str:
    return rust_extension_tag(extension_name)


def _rust_concrete(spec: LoweredSpecialization, kind: str) -> str:
    """Concrete (non-associated) type for an overloaded impl's `for`/params: the impl is
    written for a concrete arg type, so associated-type projections won't do."""

    return RUST_SIGNATURE_TYPES.concrete_type(
        kind,
        base=spec.base_type_spelling,
        register=spec.register_spelling,
        array=_rust_concrete_array(spec),
    )


def _rust_concrete_param(spec: LoweredSpecialization, kind: str) -> str:
    if DEFAULT_SUPPORT_POLICY.is_borrowed_parameter_kind(kind):
        return f"&{_rust_concrete_array(spec)}"
    return _rust_concrete(spec, kind)


def _rust_concrete_result(spec: LoweredSpecialization) -> str:
    return _rust_concrete(spec, spec.result_kind)


def _rust_concrete_array(spec: LoweredSpecialization) -> str:
    lane_parameter = spec.lane_parameter
    return f"array_type<{spec.base_type_spelling}, {lane_parameter}>"


def _vector_type(spec: LoweredSpecialization) -> str:
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    if spec.uses_sized_vector:
        lane_parameter = spec.lane_parameter
        return (
            f"Simd<{spec.base_type_spelling}, "
            f"{_ext_tag(spec.extension_name)}<{lane_parameter}>>"
        )
    return f"Simd<{spec.base_type_spelling}, {_ext_tag(spec.extension_name)}>"


def _kind_type(kind: str, owner: str) -> str:
    return RUST_SIGNATURE_TYPES.owner_type(kind, owner=owner)


def _param_kind_type(kind: str, owner: str) -> str:
    return RUST_SIGNATURE_TYPES.parameter_type(kind, owner=owner)


def _params(
    shape: LoweredSpecialization,
    owner: str,
    *,
    vt_type: str | None = None,
    vidx_type: str | None = None,
) -> str:
    # A body that needs a mutable `s[]` borrow should introduce a mutable local explicitly
    # in source (`var<infer>(local, data)`), keeping read-only array parameters const in
    # generated Rust. A `vt` (target-axis vector) param uses `vt_type` —
    # the per-context target register spelling (trait `ToVec::RegisterType` / impl concrete /
    # wrapper `T::RegisterType`); a `vidx` (index vector) param uses `vidx_type`
    # (`IndicesType::RegisterType` — the generic name is the same in every context).
    parts: list[str] = []
    for index, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds)):
        if kind == DEFAULT_SUPPORT_POLICY.immediate_kind:
            continue
        override = shape.effective_param_type_overrides[index]
        if override is not None:
            typ = override
        elif kind == "vt":
            assert vt_type is not None
            typ = vt_type
        elif kind == DEFAULT_SUPPORT_POLICY.index_vector_kind:
            assert vidx_type is not None
            typ = vidx_type
        else:
            typ = _param_kind_type(kind, owner)
        parts.append(f"{name}: {typ}")
    return ", ".join(parts)


def _runtime_names(shape: LoweredSpecialization) -> str:
    """The call-through argument names, excluding the `sImm` immediate (a const generic)."""

    return ", ".join(
        name
        for name, kind in zip(shape.param_names, shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )


def _generic_decls(shape: LoweredSpecialization) -> list[str]:
    """Const-generic parameter declarations for a trait/wrapper: the boolean axes plus an
    `sImm` immediate, e.g. ``["const ALIGNED: bool", "const factor: u32"]``."""

    decls = [f"const {_axis_name(k)}: bool" for k, _ in shape.axis]
    if shape.immediate is not None:
        decls.append(f"const {shape.immediate[0]}: {shape.immediate[1]}")
    # `generic_params` (e.g. `PreserveSign`) — const generics with no default (Rust const-generic
    # defaults are unstable, so callers pass them).
    decls += [f"const {name}: {typ}" for name, typ, _ in shape.generic_params]
    return decls


def _trait_args_by_name(shape: LoweredSpecialization) -> list[str]:
    """Trait generic ARGS spelled by name (wrapper side): axis names + immediate + generic_params."""

    args = [_axis_name(k) for k, _ in shape.axis]
    if shape.immediate is not None:
        args.append(shape.immediate[0])
    args += [name for name, _, _ in shape.generic_params]
    return args


def _trait_args_by_value(spec: LoweredSpecialization) -> list[str]:
    """Trait generic ARGS for a concrete impl: axis literal values + immediate + generic_params
    (the immediate and generic_params stay free const generics on the impl)."""

    args = [value for _, value in spec.axis]
    if spec.immediate is not None:
        args.append(spec.immediate[0])
    args += [name for name, _, _ in spec.generic_params]
    return args
