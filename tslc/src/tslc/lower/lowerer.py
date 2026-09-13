"""Lower a selected implementation into a backend-ready function.

Pieces, each with one job:

- :class:`LoweringSession` (in ``context.py``) groups immutable selected facts,
  body-local aliases, diagnostics, and the ``unsafe`` flag.
- :class:`ExpressionRenderer` walks a body's segment sequence: raw text passes
  through, regions dispatch to per-keyword :class:`RegionLowerer` handlers.
- :class:`ImplementationBodyLowerer` scans and lowers default/variant bodies,
  collecting their safety, diagnostics, implementation state, and dependencies.
- :class:`Lowerer` orchestrates signature/type resolution, body lowering, and
  delegates final validation/assembly to ``specialization_assembly`` (a
  not-yet-lowerable construct skips the specialization rather than failing).

Growth is by registering more region lowerers / query functions, not by editing
this file.
"""

from __future__ import annotations

from dataclasses import replace

from tslc.backend import translation_common
from tslc.backend.translation import BackendDialect
from tslc.catalog.arithmetic import ArithmeticOperandRole, ArithmeticOperation
from tslc.catalog.model import (
    Catalog,
    ImmediateParam,
    ImmediateRangeUpperKind,
    ImmediateValueRange,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS, scalar_bit_width_or_default
from tslc.catalog.signatures import SignatureShape, parse_signature
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.ir.segments import Segment
from tslc.lower.body_rendering import body_context
from tslc.lower.context import (
    LaneListParameter,
    LoweringEnv,
    LoweringScope,
)
from tslc.lower.catalog_facts import LowererCatalogFacts as _LowererCatalogFacts
from tslc.lower._diagnostics import (
    implementation_source as _implementation_source,
    lowering_error_diagnostic,
    lowering_skip_diagnostic,
    primitive_signature_source as _primitive_signature_source,
)
from tslc.lower.implementation_bodies import ImplementationBodyLowerer
from tslc.lower.model import (
    LoweredArithmeticPrecondition,
    LoweredArithmeticPreconditionKind,
    LoweredSpecialization,
    LoweredTypeParam,
    LoweringResult,
)
from tslc.lower.param_types import (
    effective_param_types,
    param_type_overrides as _param_type_overrides,
)
from tslc.lower.region_handlers import (
    DEFAULT_REGION_LOWERERS,
    RegionLowerer,
)
from tslc.lower.specialization_assembly import (
    ResolvedSpecializationSignature,
    assemble_specialization,
)
from tslc.lower.target_vectors import TargetVector, resolve_target_vector
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
        self._body_lowerer = ImplementationBodyLowerer(region_lowerers)
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
        deferred_kinds = self._support.fixed_shape_kinds_for_extension(
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
        (
            immediate,
            immediate_dispatch,
            immediate_range,
            immediate_valid_range,
        ) = resolved_immediate
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
            current_primitive_contract=selected.primitive,
            current_parameters=parameters,
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
        context = body_context(env, scope)

        param_context = (
            body_context(
                replace(env, simd_type_param_base_bindings={}),
                scope,
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

        bodies, body_diagnostics = self._body_lowerer.lower(
            selected=selected,
            shape=shape,
            context=context,
            scope=scope,
            current_register_spelling=register_spelling,
            target=target,
            body_segments=body_segments,
        )
        if bodies is None:
            return LoweringResult(
                specialization=None,
                diagnostics=body_diagnostics,
            )
        resolved_signature = ResolvedSpecializationSignature(
            shape=shape,
            parameters=parameters,
            base_type_spelling=base_type_spelling,
            register_spelling=register_spelling,
            param_type_overrides=param_type_overrides,
            vector_spelling=vector_spelling,
            index_register_spelling=index_register_spelling,
            native_register_spelling=native_register_spelling,
            uses_sized_vector=uses_sized_vector,
            lane_parameter=lane_parameter,
            target=target,
            immediate=immediate,
            immediate_range=immediate_range,
            immediate_valid_range=immediate_valid_range,
            arithmetic_preconditions=arithmetic_preconditions,
        )
        return assemble_specialization(
            selected=selected,
            env=context.env,
            resolved=resolved_signature,
            bodies=bodies,
            primitive_type_param_bounds=(
                catalog_facts.primitive_type_param_bounds
            ),
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
    if not contract.operations.intersection(
        {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
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
    value_range: ImmediateValueRange,
    selected: SelectedImplementation,
) -> tuple[int, int, bool] | None:
    """Resolve a typed source interval for one concrete source/target slot."""

    upper = value_range.upper
    if upper.kind is ImmediateRangeUpperKind.LITERAL:
        assert upper.literal is not None
        hi = upper.literal
    elif upper.kind is ImmediateRangeUpperKind.SOURCE_BASE_BIT_WIDTH:
        hi = scalar_bit_width_or_default(selected.type_tag)
    else:
        if selected.to_target is None:
            return None
        source_bits = scalar_bit_width_or_default(selected.type_tag)
        target_bits = scalar_bit_width_or_default(selected.to_target)
        narrower, wider = sorted((source_bits, target_bits))
        if narrower <= 0 or wider % narrower:
            return None
        hi = wider // narrower
    return (value_range.lower, hi, value_range.inclusive)


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
) -> tuple[
    tuple[str, str] | None,
    str | None,
    tuple[int, int, bool] | None,
    tuple[int, int, bool] | None,
] | LoweringResult:
    """Resolve an `sImm` operand and its dispatch/validity intervals.

    ``operand`` is the ``(name, backend type spelling)`` the backend emits as a
    template/const-generic param (NOT a runtime arg); ``dispatch``/``value_range`` are the
    per-backend forwarding facts. All come from the `params:` block (`immediate_param`);
    absent metadata defaults to `ui32` with positional forwarding. Returns four ``None``
    values when the signature has no `sImm`, or a :class:`LoweringResult` error when the
    immediate type or a declared static interval cannot be resolved.
    """

    if not support.has_immediate_operand(shape):
        return (None, None, None, None)
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
        return ((imm_name, imm_spelling), None, None, None)
    value_range = (
        _resolve_immediate_range(imm_param.value_range, selected)
        if imm_param.value_range is not None
        else None
    )
    valid_range = (
        _resolve_immediate_range(imm_param.valid_range, selected)
        if imm_param.valid_range is not None
        else None
    )
    if imm_param.valid_range is not None and valid_range is None:
        return _error(
            "TSL-LOWER-INVALID-IMMEDIATE-RANGE",
            f"could not resolve the static immediate range of "
            f"{selected.primitive.name!r} for {selected.type_tag!r}",
            source=imm_param.source or _implementation_source(selected),
        )
    return (
        (imm_name, imm_spelling),
        imm_param.dispatch_for(backend.backend_id),
        value_range,
        valid_range,
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
