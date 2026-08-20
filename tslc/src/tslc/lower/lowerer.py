"""Lower a selected implementation into a backend-ready function.

Pieces, each with one job:

- :class:`LoweringSession` (in ``context.py``) groups immutable selected facts,
  body-local aliases, diagnostics, and the ``unsafe`` flag.
- :class:`ExpressionRenderer` walks a body's segment sequence: raw text passes
  through, regions dispatch to per-keyword :class:`RegionLowerer` handlers.
- :class:`Lowerer` is the orchestrator: read the signature kinds, locate the
  return statement, render the body, and assemble a :class:`LoweredSpecialization`
  (a not-yet-lowerable construct skips the specialization rather than failing).

Growth is by registering more region lowerers / query functions, not by editing
this file.
"""

from __future__ import annotations

from dataclasses import replace

from tslc.backend import translation_common
from tslc.backend.translation import BackendDialect
from tslc.catalog.arithmetic import ArithmeticGuarantee, ArithmeticOperandRole
from tslc.catalog.memory import resolve_memory_alignment
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    Catalog,
    ImmediateParam,
    Primitive,
    RESULT_DIM_VECTOR,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS, scalar_bit_width_or_default
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan, sort_diagnostics
from tslc.documentation import primitive_documentation
from tslc.ir.scan import scan
from tslc.ir.segments import Segment
from tslc.lower.body_rendering import body_context, render_body
from tslc.lower.context import (
    LaneListParameter,
    LoweringEnv,
    LoweringScope,
    LoweringSession,
)
from tslc.lower.catalog_facts import (
    LowererCatalogFacts as _LowererCatalogFacts,
    type_param_bounds as _type_param_bounds,
)
from tslc.lower._diagnostics import (
    implementation_source as _implementation_source,
    lowering_error_diagnostic,
    lowering_skip_diagnostic,
    primitive_signature_source as _primitive_signature_source,
)
from tslc.lower.dependencies import origin_sort_key, symbolic_call_dependency_error
from tslc.lower.fixed_native import lower_preferred_fixed_native
from tslc.lower.region_handlers import (
    DEFAULT_REGION_LOWERERS,
    RegionLowerer,
)
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.model import (
    LoweredArithmeticPrecondition,
    LoweredArithmeticPreconditionKind,
    LoweredImplementationVariant,
    LoweredSpecialization,
    LoweredTypeParam,
    LoweringResult,
)
from tslc.lower.primitive_semantics import (
    LoweredMemoryAlignment,
    LoweredPrimitiveSemantics,
)
from tslc.lower.param_types import (
    effective_param_types,
    param_type_overrides as _param_type_overrides,
)
from tslc.lower.target_vectors import TargetVector, resolve_target_vector
from tslc.target_text import LoweredBody
from tslc.select.selector import SelectedImplementation
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy

POLICY_DEFERRED_SIGNATURE_CODE = "TSL-LOWER-POLICY-DEFERRED-SIGNATURE"


class Lowerer:
    def __init__(
        self,
        region_lowerers: tuple[RegionLowerer, ...] = DEFAULT_REGION_LOWERERS,
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
    ) -> None:
        self._region_lowerers = region_lowerers
        self._support = support
        self._catalog_facts_catalog: Catalog | None = None
        self._catalog_facts: _LowererCatalogFacts | None = None

    def lower(
        self,
        selected: SelectedImplementation,
        catalog: Catalog,
        backend: BackendDialect,
        *,
        body_segments: tuple[Segment, ...] | None = None,
    ) -> LoweringResult:
        shape = parse_signature(selected.primitive.signature)
        if shape is None:
            return _error(
                "TSL-LOWER-BAD-SIGNATURE",
                f"could not parse signature {selected.primitive.signature!r}",
                source=_primitive_signature_source(selected),
            )
        if not selected.extension.supports_backend(backend.backend_id):
            return _skip(
                "TSL-LOWER-BACKEND-UNSUPPORTED",
                f"extension {selected.extension.isa_name!r} is not supported on "
                f"{backend.backend_id}",
                source=_implementation_source(selected),
            )
        deferred_kinds = self._support.deferred_signature_kinds_for_extension(
            shape, selected.extension
        )
        unsupported_kinds = self._support.unsupported_signature_kinds_for_extension(
            shape, selected.extension
        )
        if unsupported_kinds:
            if unsupported_kinds == deferred_kinds:
                return _skip(
                    POLICY_DEFERRED_SIGNATURE_CODE,
                    f"signature {selected.primitive.signature!r} is policy-deferred for "
                    f"scalable vector extension {selected.extension.name!r} "
                    f"(deferred kinds: {', '.join(sorted(deferred_kinds))})",
                    source=_primitive_signature_source(selected),
                )
            # A not-yet-supported signature kind (e.g. s[], ptr) is a coverage gap,
            # not a failure — skip the specialization (info), don't fail generation.
            return _skip(
                "TSL-LOWER-UNSUPPORTED-KIND",
                f"signature {selected.primitive.signature!r} uses an unsupported kind "
                f"(supported: {', '.join(sorted(self._support.supported_signature_kinds))})",
                source=_primitive_signature_source(selected),
            )
        parameters = tuple(selected.primitive.parameters)
        if len(parameters) != len(shape.param_kinds):
            return _error(
                "TSL-LOWER-SIGNATURE-ARITY",
                f"primitive {selected.primitive.name!r} has {len(parameters)} parameters "
                f"but signature {selected.primitive.signature!r} has {len(shape.param_kinds)}",
                source=_primitive_signature_source(selected),
            )

        base_type_spelling = backend.types.scalar_spelling(selected.type_tag)
        if base_type_spelling is None:
            return _error(
                "TSL-LOWER-NO-BASE-TYPE",
                f"no {backend.backend_id} base-type spelling for {selected.type_tag!r}",
                source=_implementation_source(selected),
            )
        uses_sized_vector = self._support.uses_sized_vector(selected.extension)
        lane_parameter = (
            str(selected.concrete_lanes)
            if selected.concrete_lanes is not None
            else self._support.size_parameter_name(selected.extension)
        ) if uses_sized_vector else None
        is_free_function = self._support.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        )
        register_spelling = (
            base_type_spelling
            if is_free_function
            else backend.types.target_register_spelling(
                selected.type_tag,
                selected.extension.isa_name,
                uses_sized_vector=uses_sized_vector,
                lane_parameter=lane_parameter,
            )
        )
        if register_spelling is None:
            return _error(
                "TSL-LOWER-NO-REGISTER-TYPE",
                f"no {backend.backend_id} register-type spelling for "
                f"{selected.extension.isa_name!r} / {selected.type_tag!r}",
                source=_implementation_source(selected),
            )

        vector_spelling = (
            None
            if is_free_function
            else (
                backend.types.sized_vector_spelling(
                    base_type_spelling,
                    selected.extension.isa_name,
                    lane_parameter,
                )
                if uses_sized_vector and lane_parameter is not None
                else backend.types.vector_type_spelling(
                    base_type_spelling, selected.extension.isa_name
                )
            )
        )
        native_register_spelling = (
            None
            if is_free_function
            else translation_common.vector_register_type(
                catalog,
                backend.backend_id,
                selected.extension.isa_name,
                selected.type_tag,
            )
        )
        index_register_spelling = (
            backend.types.target_register_spelling("si32", selected.extension.isa_name)
            if (
                self._support.index_vector_kind in shape.param_kinds
                and selected.extension_family_capability.index_vector_register
            )
            else None
        )

        # A representation-change primitive produces a TARGET vector; resolve it (and bind
        # its declared target alias into the scope), or propagate the skip/error it returns.
        scope = LoweringScope()
        target = resolve_target_vector(
            selected, catalog, backend, base_type_spelling, scope, self._support
        )
        if isinstance(target, Diagnostic):
            return LoweringResult(specialization=None, diagnostics=(target,))

        # Resolve the `sImm` compile-time immediate, if any (operand + forwarding facts).
        resolved_immediate = _resolve_immediate(selected, shape, backend, self._support)
        if isinstance(resolved_immediate, LoweringResult):
            return resolved_immediate
        immediate, immediate_dispatch, immediate_range = resolved_immediate
        immediate_name = immediate[0] if immediate is not None else None
        arithmetic_preconditions = _arithmetic_preconditions(selected, immediate)

        catalog_facts = self._facts_for(catalog)
        env = LoweringEnv(
            catalog=catalog,
            backend=backend,
            extension=selected.extension,
            type_tag=selected.type_tag,
            support=self._support,
            fixed_fallback_extension=selected.fixed_fallback_extension,
            fixed_native_fallback_extension=(
                selected.fixed_native_fallback_extension
            ),
            attributes=dict(selected.primitive.attributes),
            primitive_axes=catalog_facts.primitive_axes,
            primitive_arg_generics=catalog_facts.primitive_arg_generics,
            primitive_caller_unsafe=catalog_facts.primitive_caller_unsafe,
            primitive_borrowed_arg_positions=(
                catalog_facts.primitive_borrowed_arg_positions
            ),
            policy_split_names=catalog_facts.policy_split_names,
            explicit_mask_split_names=(
                catalog_facts.explicit_mask_split_names
            ),
            immediate_split_names=catalog_facts.immediate_split_names,
            current_primitive=selected.primitive.name,
            immediate_name=immediate_name,
            immediate_dispatch=immediate_dispatch,
            immediate_range=immediate_range,
            generic_param_names=tuple(
                gp.name for gp in selected.primitive.generic_params
            ),
            simd_type_param_names=frozenset(
                gp.name
                for gp in selected.primitive.generic_params
                if gp.kind == "simd_type"
            ),
            simd_type_param_base_bindings={
                binding.param_name: binding.base_tag
                for binding in selected.simd_type_base_bindings
            },
            lane_list_params=_lane_list_param_map(
                parameters,
                shape,
                selected,
                self._support,
            ),
            concrete_lanes=selected.concrete_lanes,
        )
        context = body_context(env, scope, shape, self._support)

        param_context = (
            body_context(
                replace(env, simd_type_param_base_bindings={}),
                scope,
                shape,
                self._support,
            )
            if selected.simd_type_base_bindings
            else context
        )
        param_type_overrides = _param_type_overrides(
            selected,
            parameters,
            param_context,
            self._region_lowerers,
        )

        segments = (
            body_segments
            if body_segments is not None
            else scan(
                selected.implementation.body_text,
                source=selected.implementation.body_source,
            )
        )

        default_body = lower_preferred_fixed_native(
            selected,
            shape,
            context,
            current_register_spelling=register_spelling,
            target=target,
        )
        if default_body is None:
            default_body = render_body(
                selected=selected,
                shape=shape,
                context=context,
                segments=segments,
                region_lowerers=self._region_lowerers,
            )
        if default_body.rendered is None:
            return LoweringResult(
                specialization=None,
                diagnostics=sort_diagnostics(default_body.diagnostics),
            )
        safety = selected.implementation.safety.merge(default_body.safety)
        body = LoweredBody.from_render_text(
            default_body.rendered,
            unsafe_block_renderer=backend.syntax.render_unsafe_block,
            requires_unsafe=safety.internal_unsafe,
        )

        variant_sources = tuple(
            (
                variant,
                scan(variant.body_text, source=variant.body_source),
            )
            for variant in selected.implementation.variants
        )
        variant_bodies: list[LoweredImplementationVariant] = []
        effective_safety = safety
        diagnostics = [*default_body.diagnostics]
        call_dependency_origins = set(context.effects.call_dependency_origins)
        for variant, variant_segments in variant_sources:
            variant_context = body_context(
                replace(
                    env,
                    dependency_origin=f"implementation variant {variant.name!r}",
                ),
                scope,
                shape,
                self._support,
            )
            rendered_variant = render_body(
                selected=selected,
                shape=shape,
                context=variant_context,
                segments=variant_segments,
                region_lowerers=self._region_lowerers,
                variant_name=variant.name,
                variant_source=variant.body_source,
            )
            if rendered_variant.rendered is None:
                return LoweringResult(
                    specialization=None,
                    diagnostics=sort_diagnostics(rendered_variant.diagnostics),
                )
            variant_safety = (
                selected.implementation.safety
                .merge(variant.safety)
                .merge(rendered_variant.safety)
            )
            effective_safety = effective_safety.merge(variant_safety)
            diagnostics.extend(rendered_variant.diagnostics)
            call_dependency_origins.update(
                variant_context.effects.call_dependency_origins
            )
            variant_bodies.append(
                LoweredImplementationVariant(
                    name=variant.name,
                    body=LoweredBody.from_render_text(
                        rendered_variant.rendered,
                        unsafe_block_renderer=backend.syntax.render_unsafe_block,
                        requires_unsafe=variant_safety.internal_unsafe,
                    ),
                    implementation_state=rendered_variant.implementation_state,
                    safety=variant_safety,
                )
            )

        type_param_segments = (segments, *(item[1] for item in variant_sources))
        type_params = tuple(
            LoweredTypeParam(
                name=gp.name,
                bounds=tuple(
                    sorted(
                        {
                            bound
                            for body in type_param_segments
                            for bound in _type_param_bounds(
                                body,
                                gp.name,
                                catalog_facts.primitive_type_param_bounds,
                                selected.extension.name,
                            )
                        }
                    )
                ),
                base_type_constraints=gp.base_type_constraints,
                specialize_base=gp.specialize_base,
                base_type_binding=context.env.simd_type_param_base_bindings.get(
                    gp.name
                ),
                base_type_binding_spelling=(
                    backend.types.scalar_spelling(binding)
                    if (
                        binding := context.env.simd_type_param_base_bindings.get(
                            gp.name
                        )
                    )
                    is not None
                    else None
                ),
            )
            for gp in selected.primitive.generic_params
            if gp.kind == "simd_type"
        )
        type_param_bounds = {
            type_param.name: type_param.bounds for type_param in type_params
        }
        ordered_dependency_origins = tuple(
            sorted(call_dependency_origins, key=origin_sort_key)
        )
        for origin in ordered_dependency_origins:
            if (
                message := symbolic_call_dependency_error(
                    origin.dependency,
                    type_param_bounds,
                )
            ) is not None:
                return _error(
                    "TSL-LOWER-INVALID-SYMBOLIC-CALL-DEPENDENCY",
                    message,
                    source=_implementation_source(selected),
                )

        specialization = LoweredSpecialization(
            backend_id=backend.backend_id,
            primitive_name=selected.primitive.name,
            source_primitive_name=selected.primitive.name,
            # Emit the ISA name (avx2), not the internal block name (avx2_vl):
            # the `_vl` distinction only steers selection, never the generated type.
            extension_name=context.env.extension.isa_name,
            type_tag=context.env.type_tag,
            base_type_spelling=base_type_spelling,
            register_spelling=register_spelling,
            result_kind=shape.result_kind,
            param_names=parameters,
            param_kinds=shape.param_kinds,
            body=body,
            primitive_semantics=LoweredPrimitiveSemantics(
                overload=catalog.resolve_primitive_overload(selected.primitive),
                arithmetic=selected.primitive.arithmetic,
                operation=selected.primitive.operation,
                memory=selected.primitive.memory,
                memory_alignment=_lowered_memory_alignment(
                    selected.primitive
                ),
                conversion=selected.primitive.conversion,
                shift=selected.primitive.shift,
            ),
            param_identity_tokens=tuple(
                self._support.overload_identity_token(
                    kind,
                    register_is_base=self._support.register_is_base(
                        context.env.extension
                    ),
                )
                for kind in shape.param_kinds
            ),
            param_type_overrides=param_type_overrides,
            vector_spelling=vector_spelling,
            index_register_spelling=index_register_spelling,
            native_register_spelling=native_register_spelling,
            uses_sized_vector=uses_sized_vector,
            lane_parameter=lane_parameter,
            axis=tuple(
                (key, selected.primitive.attributes[key])
                for key in sorted(selected.primitive.attributes)
                if key in BOOLEAN_WILDCARD_ATTRIBUTES
            ),
            immediate=immediate,
            arithmetic_preconditions=arithmetic_preconditions,
            # `generic_params` split by kind: `bool`/`int` are non-type (const) params; a
            # `simd_type` is a free type param (see `type_params`).
            generic_params=tuple(
                (gp.name, backend.types.const_param_type(gp.kind), gp.default)
                for gp in selected.primitive.generic_params
                if gp.kind != "simd_type"
            ),
            type_params=type_params,
            result_vector_param=(
                selected.primitive.result_target[1]
                if selected.primitive.result_target is not None
                and selected.primitive.result_target[0] == RESULT_DIM_VECTOR
                else None
            ),
            # True only when the extension declares its register type as the base type.
            # Other zero-width/sized vectors may still use array-backed registers, so this is
            # a source capability, not a vector_bits shortcut.
            register_is_base=self._support.register_is_base(context.env.extension),
            target=target,
            mask_policy=selected.primitive.mask_mode,
            lane_list_params=tuple(context.env.lane_list_params.values()),
            required_features=selected.required_features,
            required_compiler_capabilities=(
                selected.required_compiler_capabilities
            ),
            call_dependency_origins=ordered_dependency_origins,
            implementation_state=default_body.implementation_state,
            safety=effective_safety,
            variant_bodies=tuple(variant_bodies),
            documentation=primitive_documentation(
                brief=selected.primitive.brief_description,
                detailed=selected.primitive.detailed_description,
                semantics=selected.primitive.semantics,
            ),
            source=_implementation_source(selected),
        )
        return LoweringResult(
            specialization=specialization,
            diagnostics=sort_diagnostics(diagnostics),
        )

    def _facts_for(self, catalog: Catalog) -> _LowererCatalogFacts:
        if self._catalog_facts_catalog is not catalog or self._catalog_facts is None:
            self._catalog_facts = _LowererCatalogFacts.build(catalog, self._support)
            self._catalog_facts_catalog = catalog
        return self._catalog_facts


def _arithmetic_preconditions(
    selected: SelectedImplementation,
    immediate: tuple[str, str] | None,
) -> tuple[LoweredArithmeticPrecondition, ...]:
    contract = selected.primitive.arithmetic
    info = SCALAR_TYPE_INFOS.get(selected.type_tag)
    if contract is None or info is None or info.floating or immediate is None:
        return ()
    if not contract.has_guarantee(
        ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS
    ):
        return ()
    binding = contract.binding(ArithmeticOperandRole.DIVISOR)
    if (
        binding is None
        or binding.parameter_kind != "sImm"
        or binding.parameter_name != immediate[0]
    ):
        return ()
    return (
        LoweredArithmeticPrecondition(
            kind=LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO,
            parameter_name=binding.parameter_name,
            lane_bit_width=info.bit_width,
        ),
    )


def _resolve_immediate_range(
    imm_param: ImmediateParam, type_tag: str
) -> tuple[int, int, bool] | None:
    """Resolve an `ImmediateParam.value_range` to concrete `(lo, hi, inclusive)` for the
    selected type. `hi_expr` is an int literal or the symbolic `base_bit_width(data)` (the
    selected type's bit width, from its tag's digits, e.g. `si32` -> 32). None when undeclared
    or unresolvable — the literal-match bridge then has no range and falls back to positional."""

    if imm_param.value_range is None:
        return None
    lo, hi_expr, inclusive = imm_param.value_range
    if hi_expr == "base_bit_width(data)":
        hi = scalar_bit_width_or_default(type_tag)
    elif hi_expr.lstrip("-").isdigit():
        hi = int(hi_expr)
    else:
        return None
    return (lo, hi, inclusive)


def _lane_list_param_map(
    parameters: tuple[str, ...],
    shape: SignatureShape,
    selected: SelectedImplementation,
    support: SupportPolicy,
) -> dict[str, LaneListParameter]:
    result: dict[str, LaneListParameter] = {}
    concrete_lanes = selected.concrete_lanes
    lane_count = (
        concrete_lanes
        if concrete_lanes is not None
        else support.lane_count(selected.extension, selected.type_tag)
    )
    lane_expression = (
        str(concrete_lanes)
        if concrete_lanes is not None
        else support.lane_expression(selected.extension, selected.type_tag)
    )
    for name, term in zip(parameters, shape.param_terms):
        if not term.is_lane_list:
            continue
        result[name] = LaneListParameter(
            name=name,
            element_kind=term.lane_element_kind or "",
            lane_count=lane_count,
            lane_expression=lane_expression,
        )
    return result


def _resolve_immediate(
    selected: SelectedImplementation,
    shape: SignatureShape,
    backend: BackendDialect,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> tuple[tuple[str, str] | None, str | None, tuple[int, int, bool] | None] | LoweringResult:
    """Resolve an `sImm` operand into ``(operand, dispatch, value_range)``.

    ``operand`` is the ``(name, backend type spelling)`` the backend emits as a
    template/const-generic param (NOT a runtime arg); ``dispatch``/``value_range`` are the
    per-backend forwarding facts. All come from the `params:` block (`immediate_param`);
    absent metadata defaults to `ui32` with positional forwarding. Returns ``(None, None,
    None)`` when the signature has no `sImm`, or a :class:`LoweringResult` error when the
    immediate type has no backend spelling.
    """

    if not support.has_immediate_operand(shape):
        return (None, None, None)
    imm_name = selected.primitive.parameters[
        shape.param_kinds.index(support.immediate_kind)
    ]
    imm_param = selected.primitive.immediate_param(imm_name)
    imm_type = imm_param.type_tag if imm_param is not None else "ui32"
    imm_spelling = backend.types.scalar_spelling(imm_type)
    if imm_spelling is None:
        return _error(
            "TSL-LOWER-NO-IMMEDIATE-TYPE",
            f"no {backend.backend_id} spelling for the immediate type of "
            f"{selected.primitive.name!r}",
            source=(
                imm_param.source
                if imm_param is not None and imm_param.source is not None
                else _implementation_source(selected)
            ),
        )
    if imm_param is None:
        return ((imm_name, imm_spelling), None, None)
    return (
        (imm_name, imm_spelling),
        imm_param.dispatch_for(backend.backend_id),
        _resolve_immediate_range(imm_param, selected.type_tag),
    )


def varying_positions(specs: tuple[LoweredSpecialization, ...]) -> tuple[int, ...]:
    """Parameter positions whose kind differs across a primitive's signatures — the
    dispatch points of an overload (e.g. store's `(ptr,v)`/`(ptr,s)` vary at position 1).
    Shared by both backends."""

    if not specs:
        return ()
    arity = len(specs[0].param_kinds)
    return tuple(
        i for i in range(arity) if len({spec.param_kinds[i] for spec in specs}) > 1
    )


def _lowered_memory_alignment(
    primitive: Primitive,
) -> LoweredMemoryAlignment | None:
    if primitive.memory is None:
        return None
    resolved = resolve_memory_alignment(primitive.attributes)
    return (
        None
        if resolved is None
        else LoweredMemoryAlignment(axis_name=resolved[0], mode=resolved[1])
    )


def _error(code: str, message: str, *, source: SourceSpan | None = None) -> LoweringResult:
    return LoweringResult(
        specialization=None,
        diagnostics=(lowering_error_diagnostic(code, message, source=source),),
    )


def _skip(code: str, message: str, *, source: SourceSpan | None = None) -> LoweringResult:
    """A not-yet-lowerable specialization: recorded as a coverage gap, not a failure."""

    return LoweringResult(
        specialization=None,
        diagnostics=(lowering_skip_diagnostic(code, message, source=source),),
    )
