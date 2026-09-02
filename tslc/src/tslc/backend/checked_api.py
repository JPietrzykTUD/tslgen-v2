"""Render-independent checked-API planning from lowered preconditions."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
    PreconditionHazard,
    PreconditionKind,
)
from tslc.catalog.semantics import OperandRole
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class CheckedConditionPlan:
    kind: PreconditionKind
    error: PreconditionErrorKind
    parameter_name: str
    parameter_index: int


@dataclass(frozen=True, slots=True)
class CheckedApiPlan:
    conditions: tuple[CheckedConditionPlan, ...]
    result_kind: str


def checked_api_plan(
    specializations: tuple[LoweredSpecialization, ...],
) -> CheckedApiPlan | None:
    """Plan a checked twin only when every catastrophic condition is checkable."""

    if not specializations:
        return None
    first = specializations[0]
    declared = first.primitive_semantics.preconditions
    if not declared:
        return None
    semantic_keys = tuple(
        (
            item.kind,
            tuple(
                (binding.role, binding.parameter_index, binding.parameter_name)
                for binding in item.operand_bindings
            ),
        )
        for item in declared
    )
    for spec in specializations[1:]:
        candidate = tuple(
            (
                item.kind,
                tuple(
                    (binding.role, binding.parameter_index, binding.parameter_name)
                    for binding in item.operand_bindings
                ),
            )
            for item in spec.primitive_semantics.preconditions
        )
        if candidate != semantic_keys:
            raise ValueError("checked API requires consistent lowered preconditions")
    if any(spec.safety.caller_unsafe for spec in specializations):
        return None

    conditions: list[CheckedConditionPlan] = []
    for precondition in declared:
        descriptor = PRECONDITION_DESCRIPTORS[precondition.kind]
        if descriptor.hazard is not PreconditionHazard.CATASTROPHIC:
            continue
        if precondition.kind is not PreconditionKind.LANE_INDEX_IN_RANGE:
            return None
        binding = precondition.binding(OperandRole.INDEX)
        if binding is None:
            raise ValueError("lane-index precondition has no resolved index binding")
        conditions.append(
            CheckedConditionPlan(
                kind=precondition.kind,
                error=descriptor.error,
                parameter_name=binding.parameter_name,
                parameter_index=binding.parameter_index,
            )
        )
    if not conditions:
        return None
    if first.result_kind == "void":
        return None
    return CheckedApiPlan(tuple(conditions), first.result_kind)


def public_call_requires_unsafe(
    specializations: tuple[LoweredSpecialization, ...],
) -> bool:
    if not specializations:
        return False
    return any(spec.safety.caller_unsafe for spec in specializations) or any(
        PRECONDITION_DESCRIPTORS[item.kind].hazard
        is PreconditionHazard.CATASTROPHIC
        for item in specializations[0].primitive_semantics.preconditions
    )


__all__ = (
    "CheckedApiPlan",
    "CheckedConditionPlan",
    "checked_api_plan",
    "public_call_requires_unsafe",
)
