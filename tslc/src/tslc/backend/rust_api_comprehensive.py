"""Plan comprehensive Rust facade admission and public method facts."""

from __future__ import annotations

import re
from collections import defaultdict

from tslc.backend.primitive_facade import (
    DataparallelPrimitiveFacadeKind,
    plan_dataparallel_primitive_facade,
)
from tslc.backend.rust_api_candidates import (
    _Candidate,
    _conversion_pairs,
    _delegate_diagnostic,
    _delegates,
    _diagnostic,
    _primary_indices,
    _result_type_tag,
    _role_signature_diagnostic,
    _roles_by_index,
)
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustFacadeConstParameter,
    RustFacadeConstParameterSource,
    RustFacadeCoverageEntry,
    RustFacadeCoverageStatus,
    RustFacadeParameter,
    RustFacadeParameterPlacement,
    RustFacadeReceiverKind,
    RustFacadeTypeParameter,
    RustFacadeTypeParameterRole,
)
from tslc.backend.rust_api_types import RUST_FACADE_SIGNATURE_TYPES
from tslc.catalog.arithmetic import ArithmeticGuarantee, ArithmeticOperandRole
from tslc.catalog.conversion import LaneCountRelation
from tslc.catalog.memory import MemoryAccess
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.diagnostics import Diagnostic


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
    if key.result_vector_param is not None and any(
        _result_type_tag(specialization, key.result_vector_param) is None
        for _profile_name, specialization in candidate.specs
    ):
        return None, None, (
            _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-TARGET-BINDING-MISMATCH",
                "has an unresolved result-vector type binding",
            ),
        )
    conversion_pairs = _conversion_pairs(candidate)
    if key.result_vector_param is not None and (
        key.conversion is None
        or key.conversion[1] is not LaneCountRelation.PRESERVE_LANE_COUNT
        or not conversion_pairs
    ):
        return None, "result vector is not a closed lane-preserving shape", ()
    if any(item is not None for item in key.param_type_overrides):
        return None, "backend-specific parameter spelling is lower-level only", ()
    if not RUST_FACADE_SIGNATURE_TYPES.supports_runtime_kind(
        key.result_kind
    ) or any(
        kind != "sImm"
        and not RUST_FACADE_SIGNATURE_TYPES.supports_runtime_kind(kind)
        for kind in key.param_kinds
    ):
        return None, "signature kind is not facade-representable", ()
    role_diagnostic = _role_signature_diagnostic(candidate)
    if role_diagnostic is not None:
        return None, None, (role_diagnostic,)
    memory_decision = plan_dataparallel_primitive_facade(
        key.source_name,
        tuple(spec for _profile_name, spec in candidate.specs),
    )
    if memory_decision.diagnostic_reason is not None:
        return None, None, (
            _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-MEMORY-CONTRACT",
                memory_decision.diagnostic_reason,
            ),
        )
    if (
        memory_decision.facade is not None
        and memory_decision.facade.kind
        is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
    ):
        memory_noun = (
            "load"
            if memory_decision.facade.memory_access is MemoryAccess.READ
            else "store"
        )
        return (
            None,
            f"unmasked vector {memory_noun} is exposed by the curated memory boundary",
            (),
        )

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
                tuple(
                    sorted(
                        {
                            pair.target_type_tag
                            for pair in conversion_pairs
                        }
                    )
                ),
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
            suppress_should_implement_trait_lint=(
                public_name in _STANDARD_TRAIT_METHOD_NAMES
            ),
            documentation=representative.documentation,
            conversion_pairs=conversion_pairs,
            delegates=() if conversion_pairs else _delegates(candidate),
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
    if key.mask_policy == PrimitiveMaskMode.PASS_THROUGH:
        name = _append_component(name, "_masked")
    elif key.mask_policy == PrimitiveMaskMode.ZERO:
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


def _excluded(candidate: _Candidate, reason: str) -> RustFacadeCoverageEntry:
    return RustFacadeCoverageEntry(
        candidate.key.source_name,
        candidate.key.signature,
        candidate.key.mask_policy,
        RustFacadeCoverageStatus.EXCLUDED,
        reason=reason,
    )


def _append_component(name: str, component: str) -> str:
    return name if name.endswith(component) else f"{name}{component}"


def _rust_const_name(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


def _method_sort_key(method: RustComprehensiveMethod) -> tuple[str, str, str]:
    return (method.receiver_kind.value, method.public_name, method.source_primitive_name)


def _coverage_sort_key(
    entry: RustFacadeCoverageEntry,
) -> tuple[str, str, str, str]:
    return (
        entry.source_primitive_name,
        entry.signature,
        entry.mask_policy or "",
        entry.public_name or "",
    )


_STANDARD_TRAIT_METHOD_NAMES = frozenset(
    {
        "add",
        "bitand",
        "bitor",
        "bitxor",
        "div",
        "mul",
        "neg",
        "not",
        "rem",
        "shl",
        "shr",
        "sub",
    }
)
