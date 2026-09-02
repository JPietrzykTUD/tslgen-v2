"""Render-independent checked-API planning from lowered preconditions."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.arithmetic import (
    ArithmeticNumericDomain,
    ArithmeticOperandBinding,
    ArithmeticOperandRole,
)
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
    PreconditionHazard,
    PreconditionKind,
    PreconditionCheckPrimitive,
    precondition_applies_to_type,
)
from tslc.catalog.semantics import OperandBinding, OperandRole
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class CheckedConditionPlan:
    kind: PreconditionKind
    error: PreconditionErrorKind
    parameter_name: str
    parameter_index: int
    numeric_domain: ArithmeticNumericDomain | None = None
    check_primitives: tuple[PreconditionCheckPrimitive, ...] = ()
    mask_parameter_name: str | None = None
    mask_parameter_index: int | None = None


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
                (
                    "arithmetic"
                    if isinstance(binding, ArithmeticOperandBinding)
                    else "operation",
                    binding.role.value,
                    binding.parameter_index,
                    binding.parameter_name,
                )
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
                    (
                        "arithmetic"
                        if isinstance(binding, ArithmeticOperandBinding)
                        else "operation",
                        binding.role.value,
                        binding.parameter_index,
                        binding.parameter_name,
                    )
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
        mask_name: str | None = None
        mask_index: int | None = None
        check_primitives = descriptor.check_primitives
        if first.mask_policy is not None and descriptor.masked_check_primitives:
            mask_indexes = tuple(
                index for index, kind in enumerate(first.param_kinds) if kind == "m"
            )
            if len(mask_indexes) != 1:
                raise ValueError("masked checked API requires one mask parameter")
            mask_index = mask_indexes[0]
            mask_name = first.param_names[mask_index]
            check_primitives += descriptor.masked_check_primitives
        binding: OperandBinding | ArithmeticOperandBinding | None
        if precondition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
            binding = precondition.binding(OperandRole.INDEX)
            if binding is None:
                raise ValueError("lane-index precondition has no resolved index binding")
        elif precondition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO:
            binding = precondition.arithmetic_binding(ArithmeticOperandRole.DIVISOR)
            if binding is None:
                raise ValueError("divisor precondition has no resolved divisor binding")
        else:
            return None
        conditions.append(
            CheckedConditionPlan(
                kind=precondition.kind,
                error=descriptor.error,
                parameter_name=binding.parameter_name,
                parameter_index=binding.parameter_index,
                numeric_domain=descriptor.numeric_domain,
                check_primitives=check_primitives,
                mask_parameter_name=mask_name,
                mask_parameter_index=mask_index,
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
        PRECONDITION_DESCRIPTORS[precondition.kind].hazard
        is PreconditionHazard.CATASTROPHIC
        and precondition_applies_to_type(precondition, spec.type_tag)
        for spec in specializations
        for precondition in spec.primitive_semantics.preconditions
    )


def applicable_checked_api_plan(
    specializations: tuple[LoweredSpecialization, ...],
) -> CheckedApiPlan | None:
    """Plan conditions that apply to at least one represented concrete type."""

    plan = checked_api_plan(specializations)
    if plan is None:
        return None
    applicable_kinds = {
        precondition.kind
        for spec in specializations
        for precondition in spec.primitive_semantics.preconditions
        if precondition_applies_to_type(precondition, spec.type_tag)
    }
    conditions = tuple(
        condition for condition in plan.conditions if condition.kind in applicable_kinds
    )
    return CheckedApiPlan(conditions, plan.result_kind) if conditions else None


__all__ = (
    "CheckedApiPlan",
    "CheckedConditionPlan",
    "applicable_checked_api_plan",
    "checked_api_plan",
    "public_call_requires_unsafe",
)
