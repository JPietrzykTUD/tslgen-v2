"""Plan the ordinary Rust facade from finalized lowering and target facts."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustCuratedTraitImplementation,
    RustFacadeBitConversion,
    RustFacadeCoverageEntry,
    RustFacadeCoverageStatus,
    RustFacadeConstParameter,
    RustFacadeConstParameterSource,
    RustFacadeCoreDelegate,
    RustFacadeCoreOperationRequirement,
    RustFacadeDelegate,
    RustFacadeDelegateVector,
    RustFacadeInvocation,
    RustFacadeOperationBinding,
    RustFacadeParameter,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeReceiverKind,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustFacadeTargetSelection,
    RustFacadeTraitRhsKind,
    RustFacadeTypeParameter,
    RustFacadeTypeParameterRole,
    RustNativeAlias,
    RustNativeAliasSelection,
    RustOperationValue,
)
from tslc.backend.rust_static_selection import RustStaticSelectionPlan
from tslc.catalog.arithmetic import (
    ArithmeticGuarantee,
    ArithmeticOperandRole,
    ArithmeticOperation,
)
from tslc.catalog.conversion import (
    ConversionKind,
    LaneCountRelation,
    NumericConversionMode,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.model import Catalog
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic, diagnostic_at, sort_diagnostics
from tslc.lower.lowerer import LoweredSpecialization, varying_positions


_FacadeOperandRole = OperandRole | ArithmeticOperandRole
_PublicOperand = tuple[_FacadeOperandRole, str]
_RoleBinding = tuple[_FacadeOperandRole, int, str]


@dataclass(frozen=True, slots=True)
class _CandidateKey:
    source_name: str
    result_kind: str
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    axis_names: tuple[str, ...]
    immediate: tuple[str, str] | None
    generic_params: tuple[tuple[str, str, str], ...]
    type_param_names: tuple[str, ...]
    result_vector_param: str | None
    conversion: tuple[
        ConversionKind, LaneCountRelation, NumericConversionMode | None
    ] | None
    has_concrete_target: bool
    mask_policy: str | None
    overload: tuple[str, str, bool] | None
    operation: PrimitiveOperation | None
    operation_roles: tuple[tuple[OperandRole, int, str], ...]
    arithmetic_operations: tuple[ArithmeticOperation, ...]
    arithmetic_roles: tuple[tuple[ArithmeticOperandRole, int, str], ...]
    param_type_overrides: tuple[str | None, ...]

    @property
    def signature(self) -> str:
        return f"{self.result_kind}:=({','.join(self.param_kinds)})"


@dataclass(slots=True)
class _Candidate:
    key: _CandidateKey
    specs: list[tuple[str | None, LoweredSpecialization]]
    overload_positions: dict[tuple[str | None, str], tuple[int, ...]]

    @property
    def representative(self) -> LoweredSpecialization:
        return self.specs[0][1]

    @property
    def type_tags(self) -> tuple[str, ...]:
        return tuple(sorted({spec.type_tag for _profile, spec in self.specs}))

    @property
    def result_type_tags(self) -> tuple[str, ...]:
        result_param = self.key.result_vector_param
        if result_param is None:
            return ()
        return tuple(
            sorted(
                {
                    param.base_type_binding
                    for _profile, spec in self.specs
                    for param in spec.type_params
                    if param.name == result_param
                    and param.base_type_binding is not None
                }
            )
        )


@dataclass(frozen=True, slots=True)
class _CoreDelegateMatch:
    delegate: RustFacadeDelegate
    invocation: RustFacadeInvocation


class RustFacadePlanningError(ValueError):
    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(item.message for item in diagnostics))


def plan_rust_facade(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> RustFacadePlan:
    plan, diagnostics = _plan_rust_facade(
        profiles, static_selection, require_core=False
    )
    if diagnostics:
        raise RustFacadePlanningError(diagnostics)
    assert plan is not None
    return plan


def validate_rust_facade(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> tuple[Diagnostic, ...]:
    _plan, diagnostics = _plan_rust_facade(
        profiles, static_selection, require_core=True
    )
    return diagnostics


def validate_rust_facade_plan(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    plan: RustFacadePlan,
) -> None:
    if plan != plan_rust_facade(profiles, static_selection):
        raise ValueError("Rust facade plan does not match the lowered profile inventory")


def rust_facade_closure_seed_primitives(catalog: Catalog) -> tuple[str, ...]:
    """Source primitives needed by the logical value boundary.

    Selection uses semantic operation identities and typed signatures. Primitive
    names remain outputs of this projection, never its classifier.
    """

    names = {
        primitive.name
        for primitive in catalog.primitives
        if primitive.operation is not None
        and (shape := parse_signature(primitive.signature)) is not None
        and any(
            primitive.operation.kind is requirement.operation
            and shape.result_kind == requirement.result_kind
            and _invocation_from_roles(
                shape.param_kinds,
                tuple(
                    (
                        binding.role,
                        binding.parameter_index,
                        binding.parameter_kind,
                    )
                    for binding in primitive.operation.operand_bindings
                ),
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
            is not None
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
        )
    }
    return tuple(sorted(names))


def _plan_rust_facade(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    *,
    require_core: bool,
) -> tuple[RustFacadePlan | None, tuple[Diagnostic, ...]]:
    candidates = _candidates(profiles, static_selection)
    baseline_keys = {
        _candidate_key(spec)
        for _name, specs in static_selection.fallback_module.primitive_specializations
        for spec in specs
    }
    diagnostics: list[Diagnostic] = []
    methods: list[RustComprehensiveMethod] = []
    coverage: list[RustFacadeCoverageEntry] = []

    for candidate in sorted(candidates.values(), key=_candidate_sort_key):
        key = candidate.key
        if key not in baseline_keys:
            coverage.append(_excluded(candidate, "missing generic baseline"))
            continue
        method, reason, candidate_diagnostics = _comprehensive_method(candidate)
        diagnostics.extend(candidate_diagnostics)
        if candidate_diagnostics:
            continue
        if method is None:
            coverage.append(_excluded(candidate, reason or "not representable"))
            continue
        methods.append(method)
        coverage.append(
            RustFacadeCoverageEntry(
                key.source_name,
                key.signature,
                key.mask_policy,
                RustFacadeCoverageStatus.ADMITTED,
                public_name=method.public_name,
            )
        )

    curated_methods, curated_diagnostics = _curated_methods(methods, candidates)
    traits, trait_diagnostics = _curated_traits(methods, candidates)
    bit_conversions, bit_conversion_diagnostics = _bit_conversions(candidates)
    operation_bindings, operation_binding_diagnostics = _operation_bindings(
        candidates, baseline_keys
    )
    diagnostics.extend(curated_diagnostics)
    diagnostics.extend(trait_diagnostics)
    diagnostics.extend(bit_conversion_diagnostics)
    diagnostics.extend(operation_binding_diagnostics)
    ordered_diagnostics = sort_diagnostics(diagnostics)
    if ordered_diagnostics:
        return None, ordered_diagnostics

    facade_type_tags = _core_facade_type_tags(operation_bindings)
    has_core_inventory = facade_type_tags is not None
    if facade_type_tags is None:
        facade_type_tags = {
            spec.type_tag
            for _primitive_name, specs in (
                static_selection.fallback_module.primitive_specializations
            )
            for spec in specs
        }
    shapes = _logical_shapes(
        static_selection,
        facade_type_tags,
        operation_bindings,
    )
    methods = _finalize_comprehensive_shapes(methods, shapes)
    coverage = _finalize_comprehensive_coverage(coverage, methods)
    curated_methods = _finalize_curated_shapes(curated_methods, shapes)
    traits = _finalize_trait_shapes(traits, shapes)
    diagnostics.extend(_method_collision_diagnostics(methods, curated_methods))
    diagnostics.extend(_trait_collision_diagnostics(traits, candidates))
    if diagnostics:
        return None, sort_diagnostics(diagnostics)
    operation_values = _operation_values(traits)
    core_delegates, core_diagnostics = _core_delegates(
        shapes,
        operation_bindings,
        require_complete=require_core and has_core_inventory,
    )
    if core_diagnostics:
        return None, sort_diagnostics(core_diagnostics)
    return (
        RustFacadePlan(
            shapes=shapes,
            operation_bindings=operation_bindings,
            core_delegates=core_delegates,
            comprehensive_methods=tuple(sorted(methods, key=_method_sort_key)),
            curated_methods=tuple(sorted(curated_methods, key=_curated_method_sort_key)),
            bit_conversions=_finalize_bit_conversions(bit_conversions, shapes),
            trait_implementations=tuple(sorted(traits, key=_trait_sort_key)),
            native_aliases=_native_aliases(
                profiles,
                static_selection,
                facade_type_tags,
                shapes,
            ),
            operation_values=operation_values,
            coverage=tuple(sorted(coverage, key=_coverage_sort_key)),
        ),
        (),
    )


def _candidates(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> dict[_CandidateKey, _Candidate]:
    grouped: dict[_CandidateKey, _Candidate] = {}
    inputs: list[tuple[str | None, LoweredSpecialization]] = [
        (None, spec)
        for _name, specs in sorted(
            static_selection.fallback_module.primitive_specializations
        )
        for spec in sorted(specs, key=_specialization_sort_key)
    ]
    inputs.extend(
        (profile.profile.name, spec)
        for profile in sorted(profiles, key=lambda item: item.profile.name)
        for _name, specs in sorted(profile.specializations("rust").items())
        for spec in sorted(specs, key=_specialization_sort_key)
    )
    seen: set[
        tuple[
            str | None,
            _CandidateKey,
            str,
            str,
            str,
            tuple[tuple[str, str | None], ...],
            tuple[str, str] | None,
            tuple[tuple[str, str], ...],
            bool,
        ]
    ] = set()
    for profile_name, spec in inputs:
        key = _candidate_key(spec)
        identity = (
            profile_name,
            key,
            spec.primitive_name,
            spec.extension_name,
            spec.type_tag,
            tuple((param.name, param.base_type_binding) for param in spec.type_params),
            (
                (spec.target.extension_isa, spec.target.base_tag)
                if spec.target is not None
                else None
            ),
            spec.axis,
            spec.safety.caller_unsafe,
        )
        if identity in seen:
            continue
        seen.add(identity)
        candidate = grouped.setdefault(key, _Candidate(key, [], {}))
        candidate.specs.append((profile_name, spec))
    by_delegate: dict[
        tuple[str | None, str], list[LoweredSpecialization]
    ] = defaultdict(list)
    for profile_name, spec in inputs:
        by_delegate[(profile_name, spec.primitive_name)].append(spec)
    overload_positions = {
        key: varying_positions(tuple(specs))
        for key, specs in by_delegate.items()
    }
    for candidate in grouped.values():
        candidate.overload_positions.update(overload_positions)
    return grouped


def _candidate_key(spec: LoweredSpecialization) -> _CandidateKey:
    semantics = spec.primitive_semantics
    operation = semantics.operation
    arithmetic = semantics.arithmetic
    overload = semantics.overload
    conversion = semantics.conversion
    return _CandidateKey(
        source_name=spec.source_primitive_name,
        result_kind=spec.result_kind,
        param_names=spec.param_names,
        param_kinds=spec.param_kinds,
        axis_names=tuple(name for name, _value in spec.axis),
        immediate=spec.immediate,
        generic_params=spec.generic_params,
        type_param_names=tuple(param.name for param in spec.type_params),
        result_vector_param=spec.result_vector_param,
        conversion=(
            (conversion.kind, conversion.lane_count, conversion.numeric_mode)
            if conversion is not None
            else None
        ),
        has_concrete_target=spec.target is not None,
        mask_policy=spec.mask_policy,
        overload=(
            (overload.axis, overload.value, overload.is_primary_value)
            if overload is not None
            else None
        ),
        operation=operation.kind if operation is not None else None,
        operation_roles=tuple(
            sorted(
                (
                    (binding.role, binding.parameter_index, binding.parameter_kind)
                    for binding in operation.operand_bindings
                ),
                key=lambda item: item[0].value,
            )
        )
        if operation is not None
        else (),
        arithmetic_operations=arithmetic.ordered_operations if arithmetic else (),
        arithmetic_roles=tuple(
            sorted(
                (
                    (binding.role, binding.parameter_index, binding.parameter_kind)
                    for binding in arithmetic.operand_bindings
                ),
                key=lambda item: item[0].value,
            )
        )
        if arithmetic is not None
        else (),
        param_type_overrides=spec.effective_param_type_overrides,
    )


def _comprehensive_method(
    candidate: _Candidate,
) -> tuple[RustComprehensiveMethod | None, str | None, tuple[Diagnostic, ...]]:
    key = candidate.key
    representative = candidate.representative
    safety_values = {spec.safety.caller_unsafe for _profile, spec in candidate.specs}
    if len(safety_values) != 1:
        return None, None, (
            _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-SAFETY-MISMATCH",
                "has inconsistent caller safety across generated implementations",
            ),
        )
    delegate_diagnostic = _delegate_diagnostic(candidate)
    if delegate_diagnostic is not None:
        return None, None, (delegate_diagnostic,)
    if key.has_concrete_target:
        return None, "concrete target-vector shape is lower-level only", ()
    if key.type_param_names and key.type_param_names != (key.result_vector_param,):
        return None, "additional SIMD type parameters are not facade-representable", ()
    if key.result_vector_param is not None and (
        key.conversion is None
        or key.conversion[1] is not LaneCountRelation.PRESERVE_LANE_COUNT
        or not candidate.result_type_tags
    ):
        return None, "result vector is not a closed lane-preserving shape", ()
    if any(item is not None for item in key.param_type_overrides):
        return None, "backend-specific parameter spelling is lower-level only", ()
    if key.result_kind not in _REPRESENTABLE_KINDS or any(
        kind not in _REPRESENTABLE_KINDS for kind in key.param_kinds
    ):
        return None, "signature kind is not facade-representable", ()
    role_diagnostic = _role_signature_diagnostic(candidate)
    if role_diagnostic is not None:
        return None, None, (role_diagnostic,)
    curated_memory_reason = _curated_memory_exclusion(key)
    if curated_memory_reason is not None:
        return None, curated_memory_reason, ()

    primary_indices = _primary_indices(key)
    if not primary_indices:
        primary_indices = tuple(
            sorted(
                {
                    index
                    for role, index, kind in key.operation_roles
                    if role is OperandRole.VALUE and kind in {"v", "m"}
                }
            )
        )
    if len(primary_indices) > 1:
        return None, None, (
            _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-PRIMARY-MISMATCH",
                "has contradictory primary operand bindings",
            ),
        )
    primary_index = primary_indices[0] if primary_indices else None
    receiver_kind = RustFacadeReceiverKind.FREE
    if primary_index is not None and primary_index < len(key.param_kinds):
        if key.param_kinds[primary_index] == "v":
            receiver_kind = RustFacadeReceiverKind.VECTOR
        elif key.param_kinds[primary_index] == "m":
            receiver_kind = RustFacadeReceiverKind.MASK

    public_name, name_diagnostic = _public_name(candidate)
    if name_diagnostic is not None:
        return None, None, (name_diagnostic,)
    assert public_name is not None
    roles = _roles_by_index(key)
    parameters = tuple(
        RustFacadeParameter(
            name,
            _rust_const_name(name) if kind == "sImm" else name,
            kind,
            index,
            (
                RustFacadeParameterPlacement.RECEIVER
                if receiver_kind is not RustFacadeReceiverKind.FREE
                and index == primary_index
                else RustFacadeParameterPlacement.CONST_GENERIC
                if kind == "sImm"
                else RustFacadeParameterPlacement.ARGUMENT
            ),
            roles.get(index),
        )
        for index, (name, kind) in enumerate(zip(key.param_names, key.param_kinds))
    )
    const_parameters = tuple(
        RustFacadeConstParameter(
            name,
            _rust_const_name(name),
            "bool",
            RustFacadeConstParameterSource.ATTRIBUTE,
        )
        for name in key.axis_names
    ) + (
        (
            RustFacadeConstParameter(
                key.immediate[0],
                _rust_const_name(key.immediate[0]),
                key.immediate[1],
                RustFacadeConstParameterSource.IMMEDIATE,
            ),
        )
        if key.immediate is not None
        else ()
    ) + tuple(
        RustFacadeConstParameter(
            name,
            _rust_const_name(name),
            type_spelling,
            RustFacadeConstParameterSource.GENERIC,
            default,
        )
        for name, type_spelling, default in key.generic_params
    )
    type_parameters = (
        (
            RustFacadeTypeParameter(
                key.result_vector_param,
                "U",
                RustFacadeTypeParameterRole.RESULT_ELEMENT,
                candidate.result_type_tags,
            ),
        )
        if key.result_vector_param is not None
        else ()
    )
    return (
        RustComprehensiveMethod(
            public_name=public_name,
            source_primitive_name=key.source_name,
            signature=key.signature,
            mask_policy=key.mask_policy,
            receiver_kind=receiver_kind,
            parameters=parameters,
            const_parameters=const_parameters,
            type_parameters=type_parameters,
            result_kind=key.result_kind,
            type_tags=candidate.type_tags,
            shape_keys=(),
            caller_unsafe=next(iter(safety_values)),
            safety_requirements=_safety_requirements(candidate),
            panic_conditions=_panic_conditions(candidate),
            bounds_checked_parameters=_bounds_checked_parameters(candidate),
            must_use=key.result_kind != "void",
            documentation=representative.documentation,
            delegates=_delegates(candidate),
        ),
        None,
        (),
    )


def _curated_memory_exclusion(key: _CandidateKey) -> str | None:
    if (
        key.operation is PrimitiveOperation.LOAD
        and key.result_kind == "v"
        and key.param_kinds == ("cptr",)
        and key.mask_policy is None
    ):
        return "unmasked vector load is exposed by the curated memory boundary"
    if (
        key.operation is PrimitiveOperation.STORE
        and key.result_kind == "void"
        and sorted(key.param_kinds) == ["ptr", "v"]
        and key.mask_policy is None
        and key.overload == ("payload_extent", "vector", True)
    ):
        return "unmasked vector store is exposed by the curated memory boundary"
    return None


def _public_name(
    candidate: _Candidate,
) -> tuple[str | None, Diagnostic | None]:
    key = candidate.key
    name = key.source_name
    if key.overload is not None:
        axis, value, primary = key.overload
        if axis == "count_distribution" and value == "per_lane":
            name = _append_component(name, "_each")
        elif axis == "count_distribution" and value == "uniform":
            if not primary and key.immediate is None:
                return None, _diagnostic(
                    candidate,
                    "TSL-BACKEND-RUST-FACADE-UNRESOLVED-OVERLOAD",
                    "has a non-primary uniform overload without an immediate discriminator",
                )
        elif axis == "payload_extent" and value in {"vector", "scalar"}:
            pass
        else:
            return None, _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-UNKNOWN-OVERLOAD",
                f"uses unsupported overload {axis}={value}",
            )
    if key.immediate is not None or "sImm" in key.param_kinds:
        name = _append_component(name, "_imm")
    if key.mask_policy == "pass_through":
        name = _append_component(name, "_masked")
    elif key.mask_policy == "zero":
        name = _append_component(name, "_masked_zero")
    elif key.mask_policy is not None:
        return None, _diagnostic(
            candidate,
            "TSL-BACKEND-RUST-FACADE-UNKNOWN-MASK-POLICY",
            f"uses unsupported mask policy {key.mask_policy!r}",
        )
    elif any(role is OperandRole.CONTROL_MASK for role, _index, _kind in key.operation_roles):
        name = _append_component(name, "_masked")
    return name, None


def _curated_methods(
    methods: list[RustComprehensiveMethod],
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[list[RustCuratedMethod], tuple[Diagnostic, ...]]:
    planned: list[RustCuratedMethod] = []
    diagnostics: list[Diagnostic] = []
    names = {
        PrimitiveOperation.COMPARE_EQUAL: "simd_eq",
        PrimitiveOperation.COMPARE_NOT_EQUAL: "simd_ne",
        PrimitiveOperation.COMPARE_LESS: "simd_lt",
        PrimitiveOperation.COMPARE_LESS_EQUAL: "simd_le",
        PrimitiveOperation.COMPARE_GREATER: "simd_gt",
        PrimitiveOperation.COMPARE_GREATER_EQUAL: "simd_ge",
    }
    for candidate in candidates.values():
        operation = candidate.key.operation
        if (
            operation is PrimitiveOperation.SELECT
            and candidate.key.mask_policy in {None, "pass_through"}
            and candidate.key.result_kind == "v"
            and sorted(candidate.key.param_kinds) == ["m", "v", "v"]
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                invocation = _candidate_invocation(
                    candidate,
                    (
                        (OperandRole.CONTROL_MASK, "m"),
                        (OperandRole.PRIMARY, "v"),
                        (OperandRole.PASS_THROUGH, "v"),
                    ),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                planned.append(
                    RustCuratedMethod(
                        public_name="select",
                        receiver_kind=RustFacadeReceiverKind.MASK,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=method.type_tags,
                        target_type_tags=(),
                        shape_keys=(),
                        caller_unsafe=False,
                        invocation=invocation,
                        delegates=method.delegates,
                    )
                )
        if (
            operation in names
            and candidate.key.mask_policy is None
            and candidate.key.result_kind == "m"
            and sorted(candidate.key.param_kinds) == ["v", "v"]
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                invocation = _candidate_invocation(
                    candidate,
                    (
                        (OperandRole.PRIMARY, "v"),
                        (OperandRole.SECONDARY, "v"),
                    ),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                planned.append(
                    RustCuratedMethod(
                        public_name=names[operation],
                        receiver_kind=RustFacadeReceiverKind.VECTOR,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=method.type_tags,
                        target_type_tags=(),
                        shape_keys=(),
                        caller_unsafe=False,
                        invocation=invocation,
                        delegates=method.delegates,
                    )
                )
        conversion = candidate.representative.primitive_semantics.conversion
        if (
            operation is PrimitiveOperation.CONVERT
            and conversion is not None
            and conversion.kind is ConversionKind.NUMERIC
            and conversion.lane_count is LaneCountRelation.PRESERVE_LANE_COUNT
            and candidate.key.result_vector_param is not None
            and candidate.key.result_kind == "v"
            and sorted(candidate.key.param_kinds) == ["v"]
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                invocation = _candidate_invocation(
                    candidate,
                    ((OperandRole.PRIMARY, "v"),),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                planned.append(
                    RustCuratedMethod(
                        public_name="cast",
                        receiver_kind=RustFacadeReceiverKind.VECTOR,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=method.type_tags,
                        target_type_tags=candidate.result_type_tags,
                        shape_keys=(),
                        caller_unsafe=False,
                        invocation=invocation,
                        delegates=method.delegates,
                    )
                )
    return _deduplicate_curated_methods(planned), tuple(diagnostics)


def _bit_conversions(
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[tuple[RustFacadeBitConversion, ...], tuple[Diagnostic, ...]]:
    conversions: list[RustFacadeBitConversion] = []
    diagnostics: list[Diagnostic] = []
    for candidate in candidates.values():
        conversion = candidate.representative.primitive_semantics.conversion
        if (
            candidate.key.operation is not PrimitiveOperation.REINTERPRET
            or conversion is None
            or conversion.kind is not ConversionKind.BIT_PATTERN
            or conversion.lane_count is not LaneCountRelation.PRESERVE_REGISTER_WIDTH
            or candidate.key.result_kind != "v"
            or candidate.key.param_kinds != ("v",)
        ):
            continue
        safety_values = {
            spec.safety.caller_unsafe for _profile, spec in candidate.specs
        }
        if safety_values != {False}:
            continue
        fallback_pairs = {
            (spec.type_tag, spec.target.base_tag)
            for profile_name, spec in candidate.specs
            if profile_name is None and spec.target is not None
        }
        for float_tag, bits_tag in (("f32", "ui32"), ("f64", "ui64")):
            if {
                (float_tag, bits_tag),
                (bits_tag, float_tag),
            } <= fallback_pairs:
                invocation = _candidate_invocation(
                    candidate,
                    ((OperandRole.PRIMARY, "v"),),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    break
                conversions.append(
                    RustFacadeBitConversion(
                        float_type_tag=float_tag,
                        bits_type_tag=bits_tag,
                        source_primitive_name=candidate.key.source_name,
                        shape_keys=(),
                        invocation=invocation,
                        delegates=_delegates(candidate),
                    )
                )
    return (
        tuple(
            sorted(
                conversions,
                key=lambda item: (item.float_type_tag, item.bits_type_tag),
            )
        ),
        tuple(diagnostics),
    )


def _finalize_bit_conversions(
    conversions: tuple[RustFacadeBitConversion, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustFacadeBitConversion, ...]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    finalized: list[RustFacadeBitConversion] = []
    for conversion in conversions:
        lanes = sorted(
            {
                shape.lanes
                for shape in shapes
                if shape.type_tag == conversion.float_type_tag
                and (conversion.bits_type_tag, shape.lanes) in by_key
            }
        )
        shape_keys = tuple(
            (conversion.float_type_tag, lane_count)
            for lane_count in lanes
            if _bit_conversion_shape_is_complete(
                conversion,
                by_key[(conversion.float_type_tag, lane_count)],
                by_key[(conversion.bits_type_tag, lane_count)],
            )
        )
        if shape_keys:
            finalized.append(replace(conversion, shape_keys=shape_keys))
    return tuple(finalized)


def _bit_conversion_shape_is_complete(
    conversion: RustFacadeBitConversion,
    float_shape: RustFacadeShape,
    bits_shape: RustFacadeShape,
) -> bool:
    profile_names = {
        representation.profile_name
        for shape in (float_shape, bits_shape)
        for representation in shape.representations
    }
    for profile_name in profile_names:
        float_representation = _representation_for_profile(
            float_shape,
            profile_name,
        )
        bits_representation = _representation_for_profile(
            bits_shape,
            profile_name,
        )
        if not (
            _has_active_surface_delegate(
                conversion.delegates,
                float_shape,
                float_representation,
                profile_name,
            )
            and _has_active_surface_delegate(
                conversion.delegates,
                bits_shape,
                bits_representation,
                profile_name,
            )
        ):
            return False
    return True


def _representation_for_profile(
    shape: RustFacadeShape,
    profile_name: str | None,
) -> RustFacadeRepresentation:
    representation = next(
        (
            item
            for item in shape.representations
            if item.profile_name == profile_name
        ),
        None,
    )
    if representation is not None:
        return representation
    return next(
        item for item in shape.representations if item.profile_name is None
    )


def _has_active_surface_delegate(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    profile_name: str | None,
) -> bool:
    expected_extension = representation.mapping.extension_name or (
        "scalar" if shape.lanes == 1 else "generic"
    )
    return (
        sum(
            delegate.profile_name == profile_name
            and any(
                vector.extension_name == expected_extension
                and vector.type_tag == shape.type_tag
                for vector in delegate.vectors
            )
            for delegate in delegates
        )
        == 1
    )


def _curated_traits(
    methods: list[RustComprehensiveMethod],
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[list[RustCuratedTraitImplementation], tuple[Diagnostic, ...]]:
    traits: list[RustCuratedTraitImplementation] = []
    diagnostics: list[Diagnostic] = []
    for candidate in candidates.values():
        if candidate.key.mask_policy is not None:
            continue
        method = _method_for_candidate(methods, candidate)
        if method is None or method.caller_unsafe:
            continue
        trait_facts = _trait_facts(candidate)
        for (
            trait_path,
            method_name,
            operation,
            type_tags,
            rhs_kind,
            rhs_types,
            public_operands,
        ) in trait_facts:
            if type_tags:
                invocation = _candidate_invocation(candidate, public_operands)
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                traits.append(
                    RustCuratedTraitImplementation(
                        trait_path=trait_path,
                        method_name=method_name,
                        receiver_kind=method.receiver_kind,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=type_tags,
                        rhs_kind=rhs_kind,
                        rhs_type_tags=rhs_types,
                        shape_keys=(),
                        invocation=invocation,
                        delegates=method.delegates,
                    )
                )
    return _deduplicate_traits(traits), tuple(diagnostics)


def _trait_facts(
    candidate: _Candidate,
) -> tuple[
    tuple[
        str,
        str,
        ArithmeticOperation | PrimitiveOperation,
        tuple[str, ...],
        RustFacadeTraitRhsKind | None,
        tuple[str, ...],
        tuple[_PublicOperand, ...],
    ],
    ...,
]:
    spec = candidate.representative
    arithmetic = spec.primitive_semantics.arithmetic
    facts: list[
        tuple[
            str,
            str,
            ArithmeticOperation | PrimitiveOperation,
            tuple[str, ...],
            RustFacadeTraitRhsKind | None,
            tuple[str, ...],
            tuple[_PublicOperand, ...],
        ]
    ] = []
    if arithmetic is not None:
        mapping = {
            ArithmeticOperation.ADDITION: ("core::ops::Add", "add"),
            ArithmeticOperation.SUBTRACTION: ("core::ops::Sub", "sub"),
            ArithmeticOperation.MULTIPLICATION: ("core::ops::Mul", "mul"),
            ArithmeticOperation.DIVISION: ("core::ops::Div", "div"),
            ArithmeticOperation.REMAINDER: ("core::ops::Rem", "rem"),
            ArithmeticOperation.NEGATION: ("core::ops::Neg", "neg"),
        }
        for operation in arithmetic.ordered_operations:
            spelling = mapping.get(operation)
            if spelling is None or not _arithmetic_guarantees_admit(
                operation, arithmetic.guarantees
            ):
                continue
            rhs_kind = _arithmetic_rhs_kind(candidate, operation)
            if operation is not ArithmeticOperation.NEGATION and rhs_kind is None:
                continue
            if operation is ArithmeticOperation.NEGATION and (
                candidate.key.result_kind != "v"
                or candidate.key.param_kinds != ("v",)
            ):
                continue
            type_tags = candidate.type_tags
            if operation is ArithmeticOperation.NEGATION:
                type_tags = tuple(
                    type_tag
                    for type_tag in type_tags
                    if type_tag in SCALAR_TYPE_INFOS
                    and SCALAR_TYPE_INFOS[type_tag].signed
                )
            facts.append(
                (
                    *spelling,
                    operation,
                    type_tags,
                    rhs_kind,
                    (),
                    _arithmetic_public_operands(operation),
                )
            )
    primitive_operation = candidate.key.operation
    integer_tags = tuple(
        tag
        for tag in candidate.type_tags
        if tag in SCALAR_TYPE_INFOS and not SCALAR_TYPE_INFOS[tag].floating
    )
    primitive_mapping = {
        PrimitiveOperation.BIT_AND: ("core::ops::BitAnd", "bitand"),
        PrimitiveOperation.BIT_OR: ("core::ops::BitOr", "bitor"),
        PrimitiveOperation.BIT_XOR: ("core::ops::BitXor", "bitxor"),
        PrimitiveOperation.BIT_NOT: ("core::ops::Not", "not"),
        PrimitiveOperation.MASK_AND: ("core::ops::BitAnd", "bitand"),
        PrimitiveOperation.MASK_OR: ("core::ops::BitOr", "bitor"),
        PrimitiveOperation.MASK_XOR: ("core::ops::BitXor", "bitxor"),
        PrimitiveOperation.MASK_NOT: ("core::ops::Not", "not"),
        PrimitiveOperation.SHIFT_LEFT_WRAPPING: ("core::ops::Shl", "shl"),
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING: ("core::ops::Shr", "shr"),
    }
    spelling = (
        None
        if primitive_operation is None
        else primitive_mapping.get(primitive_operation)
    )
    admitted, rhs_kind = _primitive_trait_shape(candidate, primitive_operation)
    if spelling is not None and primitive_operation is not None and admitted:
        type_tags = (
            candidate.type_tags
            if primitive_operation in _MASK_OPERATIONS
            else integer_tags
        )
        rhs_types = (
            spec.primitive_semantics.shift.scalar_count_types
            if primitive_operation
            in {
                PrimitiveOperation.SHIFT_LEFT_WRAPPING,
                PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
            }
            and spec.primitive_semantics.shift is not None
            else ()
        )
        facts.append(
            (
                *spelling,
                primitive_operation,
                type_tags,
                rhs_kind,
                rhs_types,
                _primitive_public_operands(primitive_operation, rhs_kind),
            )
        )
    return tuple(facts)


def _arithmetic_rhs_kind(
    candidate: _Candidate,
    operation: ArithmeticOperation,
) -> RustFacadeTraitRhsKind | None:
    if operation is ArithmeticOperation.NEGATION:
        return None
    if (
        candidate.key.result_kind != "v"
        or sorted(candidate.key.param_kinds) != ["v", "v"]
    ):
        return None
    return RustFacadeTraitRhsKind.SAME_TYPE


def _arithmetic_public_operands(
    operation: ArithmeticOperation,
) -> tuple[_PublicOperand, ...]:
    if operation is ArithmeticOperation.NEGATION:
        return ((ArithmeticOperandRole.PRIMARY, "v"),)
    rhs_role = (
        ArithmeticOperandRole.DIVISOR
        if operation in {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
        else ArithmeticOperandRole.SECONDARY
    )
    return (
        (ArithmeticOperandRole.PRIMARY, "v"),
        (rhs_role, "v"),
    )


def _primitive_public_operands(
    operation: PrimitiveOperation,
    rhs_kind: RustFacadeTraitRhsKind | None,
) -> tuple[_PublicOperand, ...]:
    if operation in {PrimitiveOperation.BIT_NOT, PrimitiveOperation.MASK_NOT}:
        kind = "m" if operation is PrimitiveOperation.MASK_NOT else "v"
        return ((OperandRole.PRIMARY, kind),)
    if operation in {
        PrimitiveOperation.SHIFT_LEFT_WRAPPING,
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
    }:
        return (
            (OperandRole.PRIMARY, "v"),
            (
                OperandRole.COUNT,
                "s" if rhs_kind is RustFacadeTraitRhsKind.SCALAR else "v",
            ),
        )
    kind = "m" if operation in _MASK_OPERATIONS else "v"
    return (
        (OperandRole.PRIMARY, kind),
        (OperandRole.SECONDARY, kind),
    )


def _primitive_trait_shape(
    candidate: _Candidate,
    operation: PrimitiveOperation | None,
) -> tuple[bool, RustFacadeTraitRhsKind | None]:
    key = candidate.key
    unary = {
        PrimitiveOperation.BIT_NOT,
        PrimitiveOperation.MASK_NOT,
    }
    binary_vectors = {
        PrimitiveOperation.BIT_AND,
        PrimitiveOperation.BIT_OR,
        PrimitiveOperation.BIT_XOR,
    }
    binary_masks = {
        PrimitiveOperation.MASK_AND,
        PrimitiveOperation.MASK_OR,
        PrimitiveOperation.MASK_XOR,
    }
    shifts = {
        PrimitiveOperation.SHIFT_LEFT_WRAPPING,
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
    }
    if operation in unary:
        expected = ("m",) if operation is PrimitiveOperation.MASK_NOT else ("v",)
        expected_result = "m" if operation is PrimitiveOperation.MASK_NOT else "v"
        return (key.param_kinds == expected and key.result_kind == expected_result, None)
    if (
        operation in binary_vectors
        and key.result_kind == "v"
        and sorted(key.param_kinds) == ["v", "v"]
    ):
        return True, RustFacadeTraitRhsKind.SAME_TYPE
    if (
        operation in binary_masks
        and key.result_kind == "m"
        and sorted(key.param_kinds) == ["m", "m"]
    ):
        return True, RustFacadeTraitRhsKind.SAME_TYPE
    if operation in shifts and key.result_kind == "v":
        if sorted(key.param_kinds) == ["v", "v"]:
            return True, RustFacadeTraitRhsKind.SAME_TYPE
        if sorted(key.param_kinds) == ["s", "v"]:
            return True, RustFacadeTraitRhsKind.SCALAR
    return False, None


def _arithmetic_guarantees_admit(
    operation: ArithmeticOperation,
    guarantees: frozenset[ArithmeticGuarantee],
) -> bool:
    required = {
        ArithmeticOperation.ADDITION: {ArithmeticGuarantee.INTEGER_WRAPPING},
        ArithmeticOperation.SUBTRACTION: {ArithmeticGuarantee.INTEGER_WRAPPING},
        ArithmeticOperation.MULTIPLICATION: {ArithmeticGuarantee.INTEGER_WRAPPING},
        ArithmeticOperation.NEGATION: {
            ArithmeticGuarantee.INTEGER_WRAPPING,
            ArithmeticGuarantee.FLOATING_SIGN_BIT_TOGGLE,
        },
        ArithmeticOperation.DIVISION: {
            ArithmeticGuarantee.INTEGER_QUOTIENT_TOWARD_ZERO,
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
            ArithmeticGuarantee.SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN,
            ArithmeticGuarantee.FLOATING_DIVISION_IEEE754_VALUES,
        },
        ArithmeticOperation.REMAINDER: {
            ArithmeticGuarantee.INTEGER_REMAINDER_HAS_DIVIDEND_SIGN,
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
            ArithmeticGuarantee.SIGNED_MIN_REM_NEG_ONE_RETURNS_ZERO,
            ArithmeticGuarantee.FLOATING_REMAINDER_TRUNCATING,
        },
    }[operation]
    return required <= guarantees


def _logical_shapes(
    plan: RustStaticSelectionPlan,
    admitted_type_tags: set[str],
    bindings: tuple[RustFacadeOperationBinding, ...],
) -> tuple[RustFacadeShape, ...]:
    profiles = {profile.profile_name: profile for profile in plan.profiles}
    shapes: list[RustFacadeShape] = []
    for fallback in plan.fallback_mappings:
        if fallback.type_tag not in admitted_type_tags:
            continue
        if fallback.lanes != 1 and fallback.total_bits not in _FACADE_FIXED_WIDTHS:
            continue
        representations: list[RustFacadeRepresentation] = []
        for profile_name, profile in sorted(profiles.items()):
            mapping = next(
                (
                    item
                    for item in profile.mappings
                    if (item.type_tag, item.lanes) == (fallback.type_tag, fallback.lanes)
                ),
                None,
            )
            if mapping is not None and mapping.uses_hardware:
                representation = RustFacadeRepresentation(
                    profile_name,
                    profile.requirement,
                    profile.stronger_requirements,
                    mapping,
                )
                if all(
                    len(
                        _matching_core_delegates(
                            fallback.type_tag,
                            fallback.lanes,
                            representation,
                            requirement,
                            bindings,
                        )
                    )
                    == 1
                    for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
                ):
                    representations.append(representation)
        fallback_exclusions = tuple(
            sorted(
                {
                    RustFacadeTargetSelection(
                        representation.requirement,
                        representation.stronger_requirements,
                    )
                    for representation in representations
                    if representation.requirement is not None
                },
                key=lambda item: (
                    item.requirement.target_arch,
                    item.requirement.target_features,
                ),
            )
        )
        representations.insert(
            0,
            RustFacadeRepresentation(
                None,
                None,
                (),
                fallback,
                fallback_exclusions,
            ),
        )
        shapes.append(
            RustFacadeShape(
                fallback.type_tag,
                fallback.base_spelling,
                fallback.lanes,
                fallback.total_bits,
                tuple(representations),
            )
        )
    return tuple(sorted(shapes, key=lambda item: (item.type_tag, item.lanes)))


def _native_aliases(
    emitted_profiles: tuple[EmittedProfile, ...],
    plan: RustStaticSelectionPlan,
    admitted_type_tags: set[str],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustNativeAlias, ...]:
    emitted = {profile.profile.name: profile for profile in emitted_profiles}
    aliases: dict[str, list[RustNativeAliasSelection]] = defaultdict(list)
    spellings = {mapping.type_tag: mapping.base_spelling for mapping in plan.fallback_mappings}
    fallback_by_type: dict[str, list] = defaultdict(list)
    for mapping in plan.fallback_mappings:
        if (
            mapping.type_tag in admitted_type_tags
            and (
                mapping.lanes == 1
                or mapping.total_bits in _FACADE_FIXED_WIDTHS
            )
        ):
            fallback_by_type[mapping.type_tag].append(mapping)
    fallback_lanes: dict[str, int] = {}
    admitted_hardware_shapes = {
        (representation.profile_name, shape.type_tag, shape.lanes)
        for shape in shapes
        for representation in shape.representations
        if representation.profile_name is not None
    }
    for type_tag, mappings in fallback_by_type.items():
        fixed_mappings = tuple(mapping for mapping in mappings if mapping.lanes > 1)
        best_fallback = min(
            fixed_mappings or tuple(mappings),
            key=lambda item: (item.total_bits, item.lanes),
        )
        fallback_lanes[type_tag] = best_fallback.lanes
        aliases[type_tag].append(
            RustNativeAliasSelection(None, None, (), best_fallback.lanes)
        )
    for profile in plan.profiles:
        source_profile = emitted.get(profile.profile_name)
        if source_profile is None:
            continue
        by_type: dict[str, list] = defaultdict(list)
        for mapping in profile.mappings:
            if (
                mapping.uses_hardware
                and mapping.total_bits in _FACADE_FIXED_WIDTHS
                and (profile.profile_name, mapping.type_tag, mapping.lanes)
                in admitted_hardware_shapes
            ):
                by_type[mapping.type_tag].append(mapping)
        for type_tag, fallback_lane_count in fallback_lanes.items():
            mappings = by_type.get(type_tag, [])
            best = (
                max(
                    mappings,
                    key=lambda item: (
                        source_profile.extensions[
                            item.extension_name
                        ].metadata.native_sort_order
                        if item.extension_name in source_profile.extensions
                        and source_profile.extensions[
                            item.extension_name
                        ].metadata.native_sort_order
                        is not None
                        else 0,
                        item.total_bits,
                        item.lanes,
                    ),
                )
                if mappings
                else None
            )
            aliases[type_tag].append(
                RustNativeAliasSelection(
                    profile.profile_name,
                    profile.requirement,
                    profile.stronger_requirements,
                    best.lanes if best is not None else fallback_lane_count,
                )
            )
    for type_tag, selections in aliases.items():
        hardware_requirements = tuple(
            sorted(
                {
                    selection.requirement
                    for selection in selections
                    if selection.requirement is not None
                },
                key=lambda item: (item.target_arch, item.target_features),
            )
        )
        aliases[type_tag] = [
            (
                RustNativeAliasSelection(
                    selection.profile_name,
                    selection.requirement,
                    hardware_requirements,
                    selection.lanes,
                )
                if selection.requirement is None
                else selection
            )
            for selection in selections
        ]
    return tuple(
        RustNativeAlias(
            type_tag,
            spellings[type_tag],
            tuple(
                sorted(
                    selections,
                    key=lambda item: (item.profile_name is not None, item.profile_name or ""),
                )
            ),
        )
        for type_tag, selections in sorted(aliases.items())
    )


def _operation_values(
    traits: list[RustCuratedTraitImplementation],
) -> tuple[RustOperationValue, ...]:
    values: dict[ArithmeticOperation | PrimitiveOperation, RustOperationValue] = {}
    for trait in sorted(traits, key=_trait_sort_key):
        public_name = trait.trait_path.rsplit("::", 1)[-1]
        values.setdefault(
            trait.operation,
            RustOperationValue(
                public_name,
                trait.operation,
                trait.source_primitive_name,
                trait.type_tags,
            ),
        )
    return tuple(sorted(values.values(), key=lambda item: item.public_name))


def _primary_indices(key: _CandidateKey) -> tuple[int, ...]:
    indices = {
        index
        for role, index, _kind in key.operation_roles
        if role is OperandRole.PRIMARY
    }
    indices.update(
        index
        for role, index, _kind in key.arithmetic_roles
        if role is ArithmeticOperandRole.PRIMARY
    )
    return tuple(sorted(indices))


def _role_signature_diagnostic(candidate: _Candidate) -> Diagnostic | None:
    key = candidate.key
    roles = (*key.operation_roles, *key.arithmetic_roles)
    for role, index, declared_kind in roles:
        if (
            index < 0
            or index >= len(key.param_kinds)
            or key.param_kinds[index] != declared_kind
        ):
            return _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-ROLE-MISMATCH",
                f"binds {role.value!r} to a parameter that does not match "
                f"signature kind {declared_kind!r}",
            )
    return None


def _candidate_invocation(
    candidate: _Candidate,
    public_operands: tuple[_PublicOperand, ...],
) -> RustFacadeInvocation | None:
    bindings: tuple[_RoleBinding, ...]
    if public_operands and isinstance(
        public_operands[0][0], ArithmeticOperandRole
    ):
        bindings = candidate.key.arithmetic_roles
    else:
        bindings = candidate.key.operation_roles
    return _invocation_from_roles(
        candidate.key.param_kinds,
        bindings,
        public_operands,
    )


def _invocation_from_roles(
    parameter_kinds: tuple[str, ...],
    role_bindings: tuple[_RoleBinding, ...],
    public_operands: tuple[_PublicOperand, ...],
) -> RustFacadeInvocation | None:
    if len(parameter_kinds) != len(public_operands):
        return None
    public_roles = tuple(role for role, _kind in public_operands)
    if len(set(public_roles)) != len(public_roles):
        return None
    if len(role_bindings) != len(parameter_kinds):
        return None
    if {role for role, _index, _kind in role_bindings} != set(public_roles):
        return None
    source_indices = tuple(index for _role, index, _kind in role_bindings)
    if tuple(sorted(source_indices)) != tuple(range(len(parameter_kinds))):
        return None

    public_index_by_role = {
        role: public_index
        for public_index, (role, _kind) in enumerate(public_operands)
    }
    public_kind_by_role = dict(public_operands)
    public_index_by_source_index = [-1] * len(parameter_kinds)
    for role, source_index, declared_kind in role_bindings:
        if (
            parameter_kinds[source_index] != declared_kind
            or public_kind_by_role[role] != declared_kind
        ):
            return None
        public_index_by_source_index[source_index] = public_index_by_role[role]
    return RustFacadeInvocation(tuple(public_index_by_source_index))


def _invocation_diagnostic(candidate: _Candidate) -> Diagnostic:
    return _diagnostic(
        candidate,
        "TSL-BACKEND-RUST-FACADE-INVOCATION-MISMATCH",
        "does not provide one complete, kind-compatible source index for every "
        "public operand role",
    )


def _roles_by_index(
    key: _CandidateKey,
) -> dict[int, OperandRole | ArithmeticOperandRole]:
    roles: dict[int, OperandRole | ArithmeticOperandRole] = {}
    for operation_role, index, _kind in key.operation_roles:
        roles.setdefault(index, operation_role)
    for arithmetic_role, index, _kind in key.arithmetic_roles:
        roles.setdefault(index, arithmetic_role)
    return roles


def _bounds_checked_parameters(candidate: _Candidate) -> tuple[str, ...]:
    if candidate.key.operation not in {
        PrimitiveOperation.EXTRACT_LANE,
        PrimitiveOperation.INSERT_LANE,
        PrimitiveOperation.INTEGRAL_MASK_TEST,
        PrimitiveOperation.MASK_SET_LANE,
    }:
        return ()
    return tuple(
        candidate.key.param_names[index]
        for role, index, _kind in candidate.key.operation_roles
        if role is OperandRole.INDEX and 0 <= index < len(candidate.key.param_names)
    )


def _safety_requirements(candidate: _Candidate) -> tuple[str, ...]:
    if not candidate.representative.safety.caller_unsafe:
        return ()
    reasons = frozenset(
        reason
        for _profile_name, spec in candidate.specs
        for reason in spec.safety.reasons
    )
    requirements: list[str] = []
    if "raw_pointer" in reasons:
        requirements.append(
            "Every raw pointer argument must satisfy the source primitive's "
            "validity, initialization, aliasing, extent, and applicable alignment "
            "requirements for the duration of the call."
        )
    elif "raw_memory" in reasons:
        requirements.append(
            "Every memory argument must satisfy the source primitive's validity, "
            "initialization, aliasing, and extent requirements."
        )
    requirements.append(
        "The caller must uphold every remaining source-declared safety precondition "
        "for this primitive."
    )
    return tuple(requirements)


def _panic_conditions(candidate: _Candidate) -> tuple[str, ...]:
    conditions = [
        f"Panics when `{name}` is not less than `N`."
        for name in _bounds_checked_parameters(candidate)
    ]
    arithmetic = candidate.representative.primitive_semantics.arithmetic
    divisor = (
        arithmetic.binding(ArithmeticOperandRole.DIVISOR)
        if arithmetic is not None
        else None
    )
    if (
        arithmetic is not None
        and arithmetic.has_guarantee(
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS
        )
        and divisor is not None
        and divisor.parameter_kind != "sImm"
        and any(
            type_tag in SCALAR_TYPE_INFOS
            and not SCALAR_TYPE_INFOS[type_tag].floating
            for type_tag in candidate.type_tags
        )
    ):
        conditions.append(
            "For integer element types, panics when an active divisor lane is zero."
        )
    return tuple(conditions)


def _delegates(candidate: _Candidate) -> tuple[RustFacadeDelegate, ...]:
    by_profile: dict[
        str | None,
        dict[
            str,
            dict[tuple[str, str], set[tuple[tuple[str, str], ...]]],
        ],
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for profile_name, spec in candidate.specs:
        by_profile[profile_name][spec.primitive_name][
            (spec.extension_name, spec.type_tag)
        ].add(spec.axis)
    return tuple(
        RustFacadeDelegate(
            profile_name,
            primitive_name,
            tuple(
                sorted(
                    (
                        RustFacadeDelegateVector(
                            extension_name,
                            type_tag,
                            tuple(sorted(attribute_combinations)),
                        )
                        for (
                            extension_name,
                            type_tag,
                        ), attribute_combinations in by_name[
                            primitive_name
                        ].items()
                    ),
                    key=lambda item: (item.extension_name, item.type_tag),
                )
            ),
            candidate.overload_positions.get(
                (profile_name, primitive_name),
                (),
            ),
        )
        for profile_name, by_name in sorted(
            by_profile.items(), key=lambda item: (item[0] is not None, item[0] or "")
        )
        if len(by_name) == 1
        for primitive_name in by_name
    )


def _delegate_diagnostic(candidate: _Candidate) -> Diagnostic | None:
    by_profile: dict[str | None, set[str]] = defaultdict(set)
    for profile_name, spec in candidate.specs:
        by_profile[profile_name].add(spec.primitive_name)
    ambiguous = tuple(
        (profile_name, tuple(sorted(names)))
        for profile_name, names in by_profile.items()
        if len(names) > 1
    )
    if not ambiguous:
        return None
    rendered = "; ".join(
        f"{profile_name or 'fallback'}: {', '.join(names)}"
        for profile_name, names in sorted(
            ambiguous, key=lambda item: (item[0] is not None, item[0] or "")
        )
    )
    return _diagnostic(
        candidate,
        "TSL-BACKEND-RUST-FACADE-DELEGATE-MISMATCH",
        f"has multiple lower-level delegates for one profile ({rendered})",
    )


def _operation_bindings(
    candidates: dict[_CandidateKey, _Candidate],
    baseline_keys: set[_CandidateKey],
) -> tuple[tuple[RustFacadeOperationBinding, ...], tuple[Diagnostic, ...]]:
    bindings: list[RustFacadeOperationBinding] = []
    diagnostics: list[Diagnostic] = []
    for candidate in candidates.values():
        key = candidate.key
        if key not in baseline_keys or key.operation is None:
            continue
        safety_values = {
            spec.safety.caller_unsafe for _profile, spec in candidate.specs
        }
        if len(safety_values) != 1 or _delegate_diagnostic(candidate) is not None:
            continue
        core_requirements = tuple(
            requirement
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
            if key.operation is requirement.operation
            and key.result_kind == requirement.result_kind
            and sorted(key.param_kinds) == sorted(requirement.parameter_kinds)
            and key.axis_names == requirement.axis_names
            and key.mask_policy is None
            and key.overload == requirement.overload
            and next(iter(safety_values))
            == (
                requirement.operation
                in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
            )
        )
        if any(
            _invocation_from_roles(
                key.param_kinds,
                key.operation_roles,
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
            is None
            for requirement in core_requirements
        ):
            diagnostics.append(_invocation_diagnostic(candidate))
            continue
        bindings.append(
            RustFacadeOperationBinding(
                operation=key.operation,
                source_primitive_name=key.source_name,
                result_kind=key.result_kind,
                parameter_kinds=key.param_kinds,
                operand_roles=key.operation_roles,
                axis_names=key.axis_names,
                mask_policy=key.mask_policy,
                overload=key.overload,
                type_tags=candidate.type_tags,
                caller_unsafe=next(iter(safety_values)),
                delegates=_delegates(candidate),
            )
        )
    return (
        tuple(sorted(bindings, key=_operation_binding_sort_key)),
        tuple(diagnostics),
    )


def _core_delegates(
    shapes: tuple[RustFacadeShape, ...],
    bindings: tuple[RustFacadeOperationBinding, ...],
    *,
    require_complete: bool,
) -> tuple[tuple[RustFacadeCoreDelegate, ...], tuple[Diagnostic, ...]]:
    delegates: list[RustFacadeCoreDelegate] = []
    diagnostics: list[Diagnostic] = []
    for shape in shapes:
        for representation in shape.representations:
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS:
                candidates = _matching_core_delegates(
                    shape.type_tag,
                    shape.lanes,
                    representation,
                    requirement,
                    bindings,
                )
                if len(candidates) != 1:
                    if require_complete:
                        diagnostics.append(
                            Diagnostic(
                                severity="error",
                                code="TSL-BACKEND-RUST-FACADE-MISSING-CORE-DELEGATE",
                                message=(
                                    f"Rust facade role {requirement.role!r} has "
                                    f"{len(candidates)} delegates for "
                                    f"{shape.type_tag}x{shape.lanes} under "
                                    f"{representation.profile_name or 'fallback'}"
                                ),
                            )
                        )
                    continue
                delegates.append(
                    RustFacadeCoreDelegate(
                        role=requirement.role,
                        type_tag=shape.type_tag,
                        lanes=shape.lanes,
                        profile_name=representation.profile_name,
                        source_primitive_name=candidates[0].delegate.primitive_name,
                        invocation=candidates[0].invocation,
                    )
                )
    return (
        tuple(
            sorted(
                delegates,
                key=lambda item: (
                    item.type_tag,
                    item.lanes,
                    item.profile_name is not None,
                    item.profile_name or "",
                    item.role,
                ),
            )
        ),
        tuple(diagnostics),
    )


def _matching_core_delegates(
    type_tag: str,
    lanes: int,
    representation: RustFacadeRepresentation,
    requirement: RustFacadeCoreOperationRequirement,
    bindings: tuple[RustFacadeOperationBinding, ...],
) -> tuple[_CoreDelegateMatch, ...]:
    expected_extension = representation.mapping.extension_name or (
        "scalar" if lanes == 1 else "generic"
    )
    return tuple(
        _CoreDelegateMatch(delegate, invocation)
        for binding in bindings
        if binding.operation is requirement.operation
        and binding.result_kind == requirement.result_kind
        and (
            invocation := _invocation_from_roles(
                binding.parameter_kinds,
                binding.operand_roles,
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
        )
        is not None
        and binding.axis_names == requirement.axis_names
        and binding.mask_policy is None
        and binding.overload == requirement.overload
        and type_tag in binding.type_tags
        and binding.caller_unsafe
        == (requirement.operation in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE})
        for delegate in binding.delegates
        if delegate.profile_name == representation.profile_name
        and any(
            vector.extension_name == expected_extension
            and vector.type_tag == type_tag
            for vector in delegate.vectors
        )
    )


def _core_facade_type_tags(
    bindings: tuple[RustFacadeOperationBinding, ...],
) -> set[str] | None:
    supported_by_role: list[set[str]] = []
    for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS:
        type_tags = {
            type_tag
            for binding in bindings
            if binding.operation is requirement.operation
            and binding.result_kind == requirement.result_kind
            and _invocation_from_roles(
                binding.parameter_kinds,
                binding.operand_roles,
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
            is not None
            and binding.axis_names == requirement.axis_names
            and binding.mask_policy is None
            and binding.overload == requirement.overload
            and binding.caller_unsafe
            == (
                requirement.operation
                in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
            )
            and any(delegate.profile_name is None for delegate in binding.delegates)
            for type_tag in binding.type_tags
        }
        if not type_tags:
            return None
        supported_by_role.append(type_tags)
    return set.intersection(*supported_by_role)


def _finalize_curated_shapes(
    methods: list[RustCuratedMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustCuratedMethod]:
    return [
        replace(method, shape_keys=shape_keys)
        for method in methods
        if (
            shape_keys := _surface_shape_keys(
                method.delegates, method.type_tags, shapes
            )
        )
    ]


def _finalize_comprehensive_shapes(
    methods: list[RustComprehensiveMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustComprehensiveMethod]:
    return [
        replace(method, shape_keys=shape_keys)
        for method in methods
        if (
            shape_keys := _surface_shape_keys(
                method.delegates, method.type_tags, shapes
            )
        )
    ]


def _finalize_comprehensive_coverage(
    coverage: list[RustFacadeCoverageEntry],
    methods: list[RustComprehensiveMethod],
) -> list[RustFacadeCoverageEntry]:
    admitted = {
        (
            method.source_primitive_name,
            method.signature,
            method.mask_policy,
            method.public_name,
        )
        for method in methods
    }
    return [
        (
            entry
            if entry.status is RustFacadeCoverageStatus.EXCLUDED
            or (
                entry.source_primitive_name,
                entry.signature,
                entry.mask_policy,
                entry.public_name,
            )
            in admitted
            else replace(
                entry,
                status=RustFacadeCoverageStatus.EXCLUDED,
                public_name=None,
                reason="no admitted logical shape",
            )
        )
        for entry in coverage
    ]


def _finalize_trait_shapes(
    traits: list[RustCuratedTraitImplementation],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustCuratedTraitImplementation]:
    return [
        replace(trait, shape_keys=shape_keys)
        for trait in traits
        if (
            shape_keys := _surface_shape_keys(
                trait.delegates, trait.type_tags, shapes
            )
        )
    ]


def _surface_shape_keys(
    delegates: tuple[RustFacadeDelegate, ...],
    type_tags: tuple[str, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[tuple[str, int], ...]:
    return tuple(
        (shape.type_tag, shape.lanes)
        for shape in shapes
        if shape.type_tag in type_tags
        and all(
            _has_surface_delegate(delegates, shape, representation)
            for representation in shape.representations
        )
    )


def _has_surface_delegate(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> bool:
    expected_extension = (
        representation.mapping.extension_name
        or ("scalar" if shape.lanes == 1 else "generic")
    )
    return (
        sum(
            delegate.profile_name == representation.profile_name
            and any(
                vector.extension_name == expected_extension
                and vector.type_tag == shape.type_tag
                for vector in delegate.vectors
            )
            for delegate in delegates
        )
        == 1
    )


def _method_for_candidate(
    methods: list[RustComprehensiveMethod],
    candidate: _Candidate,
) -> RustComprehensiveMethod | None:
    public_name, diagnostic = _public_name(candidate)
    if diagnostic is not None or public_name is None:
        return None
    return next(
        (
            method
            for method in methods
            if method.source_primitive_name == candidate.key.source_name
            and method.public_name == public_name
            and method.type_tags == candidate.type_tags
        ),
        None,
    )


def _method_collision_diagnostics(
    comprehensive: list[RustComprehensiveMethod],
    curated: list[RustCuratedMethod],
) -> tuple[Diagnostic, ...]:
    grouped: dict[tuple[RustFacadeReceiverKind, str], list[str]] = defaultdict(list)
    for comprehensive_method in comprehensive:
        grouped[(comprehensive_method.receiver_kind, comprehensive_method.public_name)].append(
            comprehensive_method.source_primitive_name
        )
    for curated_method in curated:
        grouped[(curated_method.receiver_kind, curated_method.public_name)].append(
            curated_method.source_primitive_name
        )
    return tuple(
        Diagnostic(
            severity="error",
            code="TSL-BACKEND-RUST-FACADE-NAME-COLLISION",
            message=(
                f"Rust facade {receiver.value} method {name!r} is claimed by: "
                + ", ".join(sorted(sources))
            ),
        )
        for (receiver, name), sources in sorted(
            grouped.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
        if len(sources) > 1
    )


def _trait_collision_diagnostics(
    traits: list[RustCuratedTraitImplementation],
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[Diagnostic, ...]:
    del candidates
    grouped: dict[
        tuple[RustFacadeReceiverKind, str, RustFacadeTraitRhsKind | None], set[str]
    ] = defaultdict(set)
    for trait in traits:
        grouped[(trait.receiver_kind, trait.trait_path, trait.rhs_kind)].add(
            trait.source_primitive_name
        )
    return tuple(
        Diagnostic(
            severity="error",
            code="TSL-BACKEND-RUST-FACADE-TRAIT-COLLISION",
            message=(
                f"Rust facade trait {trait_path!r} for {receiver.value} values is "
                "provided by multiple primitives: " + ", ".join(sorted(sources))
            ),
        )
        for (receiver, trait_path, _rhs_kind), sources in sorted(
            grouped.items(),
            key=lambda item: (
                item[0][0].value,
                item[0][1],
                item[0][2].value if item[0][2] is not None else "",
            ),
        )
        if len(sources) > 1
    )


def _deduplicate_curated_methods(
    methods: list[RustCuratedMethod],
) -> list[RustCuratedMethod]:
    return list(
        {
            (method.receiver_kind, method.public_name, method.source_primitive_name): method
            for method in methods
        }.values()
    )


def _deduplicate_traits(
    traits: list[RustCuratedTraitImplementation],
) -> list[RustCuratedTraitImplementation]:
    return list(
        {
            (
                trait.receiver_kind,
                trait.trait_path,
                trait.source_primitive_name,
                trait.type_tags,
                trait.rhs_kind,
                trait.rhs_type_tags,
            ): trait
            for trait in traits
        }.values()
    )


def _excluded(candidate: _Candidate, reason: str) -> RustFacadeCoverageEntry:
    return RustFacadeCoverageEntry(
        candidate.key.source_name,
        candidate.key.signature,
        candidate.key.mask_policy,
        RustFacadeCoverageStatus.EXCLUDED,
        reason=reason,
    )


def _diagnostic(
    candidate: _Candidate,
    code: str,
    detail: str,
) -> Diagnostic:
    return diagnostic_at(
        severity="error",
        code=code,
        message=f"Rust facade candidate {candidate.key.source_name!r} {detail}",
        source=candidate.representative.source,
    )


def _append_component(name: str, component: str) -> str:
    return name if name.endswith(component) else f"{name}{component}"


def _rust_const_name(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


def _candidate_sort_key(candidate: _Candidate) -> tuple[object, ...]:
    key = candidate.key
    return (key.source_name, key.signature, key.mask_policy or "", key.overload or ())


def _specialization_sort_key(spec: LoweredSpecialization) -> tuple[object, ...]:
    return (
        spec.source_primitive_name,
        spec.primitive_name,
        spec.extension_name,
        spec.type_tag,
        tuple(
            (param.name, param.base_type_binding or "") for param in spec.type_params
        ),
        spec.axis,
    )


def _method_sort_key(method: RustComprehensiveMethod) -> tuple[str, str, str]:
    return (method.receiver_kind.value, method.public_name, method.source_primitive_name)


def _curated_method_sort_key(method: RustCuratedMethod) -> tuple[str, str, str]:
    return (method.receiver_kind.value, method.public_name, method.source_primitive_name)


def _operation_binding_sort_key(
    binding: RustFacadeOperationBinding,
) -> tuple[object, ...]:
    return (
        binding.operation.value,
        binding.source_primitive_name,
        binding.result_kind,
        binding.parameter_kinds,
        tuple(
            (role.value, index, kind)
            for role, index, kind in binding.operand_roles
        ),
        binding.axis_names,
        binding.mask_policy or "",
        binding.overload or ("", "", False),
    )


def _trait_sort_key(
    trait: RustCuratedTraitImplementation,
) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        trait.receiver_kind.value,
        trait.trait_path,
        trait.source_primitive_name,
        trait.type_tags,
    )


def _coverage_sort_key(
    entry: RustFacadeCoverageEntry,
) -> tuple[str, str, str, str]:
    return (
        entry.source_primitive_name,
        entry.signature,
        entry.mask_policy or "",
        entry.public_name or "",
    )


RUST_FACADE_CORE_OPERATION_REQUIREMENTS = (
    RustFacadeCoreOperationRequirement(
        "vector_splat",
        PrimitiveOperation.VECTOR_SPLAT,
        "v",
        ("s",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_from_array",
        PrimitiveOperation.VECTOR_FROM_ARRAY,
        "v",
        ("s[]",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_to_array",
        PrimitiveOperation.VECTOR_TO_ARRAY,
        "s[]",
        ("v",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_zero", PrimitiveOperation.VECTOR_ZERO, "v", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "extract_lane",
        PrimitiveOperation.EXTRACT_LANE,
        "s",
        ("v", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX),
    ),
    RustFacadeCoreOperationRequirement(
        "insert_lane",
        PrimitiveOperation.INSERT_LANE,
        "v",
        ("v", "usize", "s"),
        (OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE),
    ),
    RustFacadeCoreOperationRequirement(
        "load",
        PrimitiveOperation.LOAD,
        "v",
        ("cptr",),
        (OperandRole.MEMORY_SOURCE,),
        axis_names=("aligned",),
    ),
    RustFacadeCoreOperationRequirement(
        "store",
        PrimitiveOperation.STORE,
        "void",
        ("ptr", "v"),
        (OperandRole.MEMORY_DESTINATION, OperandRole.VALUE),
        axis_names=("aligned",),
        overload=("payload_extent", "vector", True),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_false", PrimitiveOperation.MASK_ALL_FALSE, "m", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_true", PrimitiveOperation.MASK_ALL_TRUE, "m", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_to_integral",
        PrimitiveOperation.MASK_TO_INTEGRAL,
        "im",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_from_integral",
        PrimitiveOperation.MASK_FROM_INTEGRAL,
        "m",
        ("im",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "integral_mask_test",
        PrimitiveOperation.INTEGRAL_MASK_TEST,
        "im",
        ("im", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_set_lane",
        PrimitiveOperation.MASK_SET_LANE,
        "m",
        ("m", "usize", "im"),
        (OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_population_count",
        PrimitiveOperation.MASK_POPULATION_COUNT,
        "usize",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_and",
        PrimitiveOperation.MASK_AND,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_or",
        PrimitiveOperation.MASK_OR,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_xor",
        PrimitiveOperation.MASK_XOR,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_not",
        PrimitiveOperation.MASK_NOT,
        "m",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
)

_REPRESENTABLE_KINDS = frozenset(
    {"void", "v", "m", "im", "imt", "s", "sImm", "usize", "ptr", "cptr"}
)
_FACADE_FIXED_WIDTHS = frozenset({128, 256, 512})
_MASK_OPERATIONS = frozenset(
    {
        PrimitiveOperation.MASK_AND,
        PrimitiveOperation.MASK_OR,
        PrimitiveOperation.MASK_XOR,
        PrimitiveOperation.MASK_NOT,
    }
)


__all__ = (
    "RUST_FACADE_CORE_OPERATION_REQUIREMENTS",
    "RustFacadePlanningError",
    "plan_rust_facade",
    "rust_facade_closure_seed_primitives",
    "validate_rust_facade",
    "validate_rust_facade_plan",
)
