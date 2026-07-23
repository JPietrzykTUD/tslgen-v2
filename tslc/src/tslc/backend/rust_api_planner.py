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
    RustFacadeOperationBinding,
    RustFacadeParameter,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeReceiverKind,
    RustFacadeRepresentation,
    RustFacadeShape,
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
from tslc.lower.lowerer import LoweredSpecialization


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

    required_shapes = {
        (
            requirement.operation,
            requirement.result_kind,
            requirement.parameter_kinds,
        )
        for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
    }
    names = {
        primitive.name
        for primitive in catalog.primitives
        if primitive.operation is not None
        and (shape := parse_signature(primitive.signature)) is not None
        and (
            primitive.operation.kind,
            shape.result_kind,
            shape.param_kinds,
        )
        in required_shapes
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

    curated_methods = _curated_methods(methods, candidates)
    traits = _curated_traits(methods, candidates)
    ordered_diagnostics = sort_diagnostics(diagnostics)
    if ordered_diagnostics:
        return None, ordered_diagnostics

    operation_bindings = _operation_bindings(candidates, baseline_keys)
    facade_type_tags = _core_facade_type_tags(operation_bindings)
    if facade_type_tags is None:
        facade_type_tags = {
            spec.type_tag
            for _primitive_name, specs in (
                static_selection.fallback_module.primitive_specializations
            )
            for spec in specs
        }
    shapes = _logical_shapes(static_selection, facade_type_tags)
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
        require_complete=require_core,
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
            bit_conversions=_bit_conversions(candidates),
            trait_implementations=tuple(sorted(traits, key=_trait_sort_key)),
            native_aliases=_native_aliases(
                profiles, static_selection, facade_type_tags
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
            spec.safety.caller_unsafe,
        )
        if identity in seen:
            continue
        seen.add(identity)
        candidate = grouped.setdefault(key, _Candidate(key, []))
        candidate.specs.append((profile_name, spec))
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

    primary_indices = _primary_indices(key)
    if len(primary_indices) > 1:
        return None, None, (
            _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-PRIMARY-MISMATCH",
                "has contradictory primary operand bindings",
            ),
        )
    if not primary_indices:
        return None, "no source-authored primary receiver", ()
    primary_index = primary_indices[0]
    if primary_index >= len(key.param_kinds) or key.param_kinds[primary_index] not in {
        "v",
        "m",
    }:
        return None, "source-authored primary has no coherent vector or mask receiver", ()

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
                if index == primary_index
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
            receiver_kind=(
                RustFacadeReceiverKind.VECTOR
                if key.param_kinds[primary_index] == "v"
                else RustFacadeReceiverKind.MASK
            ),
            parameters=parameters,
            const_parameters=const_parameters,
            type_parameters=type_parameters,
            result_kind=key.result_kind,
            type_tags=candidate.type_tags,
            caller_unsafe=next(iter(safety_values)),
            must_use=key.result_kind != "void",
            documentation=representative.documentation,
            delegates=_delegates(candidate),
        ),
        None,
        (),
    )


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
) -> list[RustCuratedMethod]:
    planned: list[RustCuratedMethod] = []
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
            and candidate.key.param_kinds == ("m", "v", "v")
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                planned.append(
                    RustCuratedMethod(
                        "select",
                        RustFacadeReceiverKind.MASK,
                        operation,
                        candidate.key.source_name,
                        method.type_tags,
                        (),
                        (),
                        False,
                        method.delegates,
                    )
                )
        if (
            operation in names
            and candidate.key.mask_policy is None
            and candidate.key.result_kind == "m"
            and candidate.key.param_kinds == ("v", "v")
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                planned.append(
                    RustCuratedMethod(
                        names[operation],
                        RustFacadeReceiverKind.VECTOR,
                        operation,
                        candidate.key.source_name,
                        method.type_tags,
                        (),
                        (),
                        False,
                        method.delegates,
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
            and candidate.key.param_kinds == ("v",)
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                planned.append(
                    RustCuratedMethod(
                        "cast",
                        RustFacadeReceiverKind.VECTOR,
                        operation,
                        candidate.key.source_name,
                        method.type_tags,
                        candidate.result_type_tags,
                        (),
                        False,
                        method.delegates,
                    )
                )
    return _deduplicate_curated_methods(planned)


def _bit_conversions(
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[RustFacadeBitConversion, ...]:
    conversions: list[RustFacadeBitConversion] = []
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
                conversions.append(
                    RustFacadeBitConversion(
                        float_tag,
                        bits_tag,
                        candidate.key.source_name,
                        _delegates(candidate),
                    )
                )
    return tuple(
        sorted(conversions, key=lambda item: (item.float_type_tag, item.bits_type_tag))
    )


def _curated_traits(
    methods: list[RustComprehensiveMethod],
    candidates: dict[_CandidateKey, _Candidate],
) -> list[RustCuratedTraitImplementation]:
    traits: list[RustCuratedTraitImplementation] = []
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
        ) in trait_facts:
            if type_tags:
                traits.append(
                    RustCuratedTraitImplementation(
                        trait_path,
                        method_name,
                        method.receiver_kind,
                        operation,
                        candidate.key.source_name,
                        type_tags,
                        rhs_kind,
                        rhs_types,
                        (),
                        method.delegates,
                    )
                )
    return _deduplicate_traits(traits)


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
            facts.append((*spelling, operation, type_tags, rhs_kind, ()))
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
            (*spelling, primitive_operation, type_tags, rhs_kind, rhs_types)
        )
    return tuple(facts)


def _arithmetic_rhs_kind(
    candidate: _Candidate,
    operation: ArithmeticOperation,
) -> RustFacadeTraitRhsKind | None:
    if operation is ArithmeticOperation.NEGATION:
        return None
    if candidate.key.result_kind != "v" or candidate.key.param_kinds != ("v", "v"):
        return None
    return RustFacadeTraitRhsKind.SAME_TYPE


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
    if operation in binary_vectors and key.result_kind == "v" and key.param_kinds == (
        "v",
        "v",
    ):
        return True, RustFacadeTraitRhsKind.SAME_TYPE
    if operation in binary_masks and key.result_kind == "m" and key.param_kinds == (
        "m",
        "m",
    ):
        return True, RustFacadeTraitRhsKind.SAME_TYPE
    if operation in shifts and key.result_kind == "v":
        if key.param_kinds == ("v", "v"):
            return True, RustFacadeTraitRhsKind.SAME_TYPE
        if key.param_kinds == ("v", "s"):
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
                representations.append(
                    RustFacadeRepresentation(
                        profile_name,
                        profile.requirement,
                        profile.stronger_requirements,
                        mapping,
                    )
                )
        fallback_exclusions = tuple(
            sorted(
                {
                    representation.requirement
                    for representation in representations
                    if representation.requirement is not None
                },
                key=lambda item: (item.target_arch, item.target_features),
            )
        )
        representations.insert(
            0,
            RustFacadeRepresentation(None, None, fallback_exclusions, fallback),
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
) -> tuple[RustNativeAlias, ...]:
    emitted = {profile.profile.name: profile for profile in emitted_profiles}
    aliases: dict[str, list[RustNativeAliasSelection]] = defaultdict(list)
    spellings = {mapping.type_tag: mapping.base_spelling for mapping in plan.fallback_mappings}
    fallback_by_type: dict[str, list] = defaultdict(list)
    for mapping in plan.fallback_mappings:
        if (
            mapping.type_tag in admitted_type_tags
            and mapping.lanes > 1
            and mapping.total_bits in _FACADE_FIXED_WIDTHS
        ):
            fallback_by_type[mapping.type_tag].append(mapping)
    fallback_lanes: dict[str, int] = {}
    for type_tag, mappings in fallback_by_type.items():
        best_fallback = min(mappings, key=lambda item: (item.total_bits, item.lanes))
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
            if mapping.uses_hardware and mapping.total_bits in _FACADE_FIXED_WIDTHS:
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


def _roles_by_index(
    key: _CandidateKey,
) -> dict[int, OperandRole | ArithmeticOperandRole]:
    roles: dict[int, OperandRole | ArithmeticOperandRole] = {}
    for operation_role, index, _kind in key.operation_roles:
        roles.setdefault(index, operation_role)
    for arithmetic_role, index, _kind in key.arithmetic_roles:
        roles.setdefault(index, arithmetic_role)
    return roles


def _delegates(candidate: _Candidate) -> tuple[RustFacadeDelegate, ...]:
    by_profile: dict[
        str | None, dict[str, set[RustFacadeDelegateVector]]
    ] = defaultdict(lambda: defaultdict(set))
    for profile_name, spec in candidate.specs:
        by_profile[profile_name][spec.primitive_name].add(
            RustFacadeDelegateVector(spec.extension_name, spec.type_tag)
        )
    return tuple(
        RustFacadeDelegate(
            profile_name,
            next(iter(by_name)),
            tuple(
                sorted(
                    next(iter(by_name.values())),
                    key=lambda item: (item.extension_name, item.type_tag),
                )
            ),
        )
        for profile_name, by_name in sorted(
            by_profile.items(), key=lambda item: (item[0] is not None, item[0] or "")
        )
        if len(by_name) == 1
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
) -> tuple[RustFacadeOperationBinding, ...]:
    bindings: list[RustFacadeOperationBinding] = []
    for candidate in candidates.values():
        key = candidate.key
        if key not in baseline_keys or key.operation is None:
            continue
        safety_values = {
            spec.safety.caller_unsafe for _profile, spec in candidate.specs
        }
        if len(safety_values) != 1 or _delegate_diagnostic(candidate) is not None:
            continue
        bindings.append(
            RustFacadeOperationBinding(
                operation=key.operation,
                source_primitive_name=key.source_name,
                result_kind=key.result_kind,
                parameter_kinds=key.param_kinds,
                axis_names=key.axis_names,
                mask_policy=key.mask_policy,
                overload=key.overload,
                type_tags=candidate.type_tags,
                caller_unsafe=next(iter(safety_values)),
                delegates=_delegates(candidate),
            )
        )
    return tuple(sorted(bindings, key=_operation_binding_sort_key))


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
            expected_extension = (
                representation.mapping.extension_name
                or ("scalar" if shape.lanes == 1 else "generic")
            )
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS:
                candidates = tuple(
                    delegate
                    for binding in bindings
                    if binding.operation is requirement.operation
                    and binding.result_kind == requirement.result_kind
                    and binding.parameter_kinds == requirement.parameter_kinds
                    and binding.axis_names == requirement.axis_names
                    and binding.mask_policy is None
                    and binding.overload == requirement.overload
                    and shape.type_tag in binding.type_tags
                    and binding.caller_unsafe
                    == (
                        requirement.operation
                        in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
                    )
                    for delegate in binding.delegates
                    if delegate.profile_name == representation.profile_name
                    and any(
                        vector.extension_name == expected_extension
                        and vector.type_tag == shape.type_tag
                        for vector in delegate.vectors
                    )
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
                        source_primitive_name=candidates[0].primitive_name,
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
            and binding.parameter_kinds == requirement.parameter_kinds
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
) -> tuple[
    str,
    str,
    str,
    tuple[str, ...],
    tuple[str, ...],
    str,
    tuple[str, str, bool],
]:
    return (
        binding.operation.value,
        binding.source_primitive_name,
        binding.result_kind,
        binding.parameter_kinds,
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
        "vector_splat", PrimitiveOperation.VECTOR_SPLAT, "v", ("s",)
    ),
    RustFacadeCoreOperationRequirement(
        "vector_from_array", PrimitiveOperation.VECTOR_FROM_ARRAY, "v", ("s[]",)
    ),
    RustFacadeCoreOperationRequirement(
        "vector_to_array", PrimitiveOperation.VECTOR_TO_ARRAY, "s[]", ("v",)
    ),
    RustFacadeCoreOperationRequirement(
        "vector_zero", PrimitiveOperation.VECTOR_ZERO, "v", ()
    ),
    RustFacadeCoreOperationRequirement(
        "extract_lane",
        PrimitiveOperation.EXTRACT_LANE,
        "s",
        ("v", "usize"),
    ),
    RustFacadeCoreOperationRequirement(
        "insert_lane",
        PrimitiveOperation.INSERT_LANE,
        "v",
        ("v", "usize", "s"),
    ),
    RustFacadeCoreOperationRequirement(
        "load",
        PrimitiveOperation.LOAD,
        "v",
        ("cptr",),
        axis_names=("aligned",),
    ),
    RustFacadeCoreOperationRequirement(
        "store",
        PrimitiveOperation.STORE,
        "void",
        ("ptr", "v"),
        axis_names=("aligned",),
        overload=("payload_extent", "vector", True),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_false", PrimitiveOperation.MASK_ALL_FALSE, "m", ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_true", PrimitiveOperation.MASK_ALL_TRUE, "m", ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_to_integral", PrimitiveOperation.MASK_TO_INTEGRAL, "im", ("m",)
    ),
    RustFacadeCoreOperationRequirement(
        "mask_from_integral", PrimitiveOperation.MASK_FROM_INTEGRAL, "m", ("im",)
    ),
    RustFacadeCoreOperationRequirement(
        "integral_mask_test",
        PrimitiveOperation.INTEGRAL_MASK_TEST,
        "im",
        ("im", "usize"),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_set_lane",
        PrimitiveOperation.MASK_SET_LANE,
        "m",
        ("m", "usize", "im"),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_population_count",
        PrimitiveOperation.MASK_POPULATION_COUNT,
        "usize",
        ("m",),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_and", PrimitiveOperation.MASK_AND, "m", ("m", "m")
    ),
    RustFacadeCoreOperationRequirement(
        "mask_or", PrimitiveOperation.MASK_OR, "m", ("m", "m")
    ),
    RustFacadeCoreOperationRequirement(
        "mask_xor", PrimitiveOperation.MASK_XOR, "m", ("m", "m")
    ),
    RustFacadeCoreOperationRequirement(
        "mask_not", PrimitiveOperation.MASK_NOT, "m", ("m",)
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
