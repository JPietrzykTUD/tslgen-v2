"""Finalized C++ checked-wrapper ABI decisions."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.checked_api import CheckedConditionPlan, checked_api_plan
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class CppCheckedApiPlan:
    """C++-specific checked signature and failure-result policy."""

    conditions: tuple[CheckedConditionPlan, ...]
    error_parameter_name: str
    error_parameter_declaration: str
    success_error_expression: str
    failure_placeholder_expression: str
    inline_specifier: str


def plan_cpp_checked_api(
    specializations: tuple[LoweredSpecialization, ...],
    *,
    result_type: str,
) -> CppCheckedApiPlan | None:
    plan = checked_api_plan(specializations)
    if plan is None:
        return None
    return CppCheckedApiPlan(
        conditions=plan.conditions,
        error_parameter_name="error",
        error_parameter_declaration="::tsl::precondition_error & error",
        success_error_expression="::tsl::precondition_error::none",
        failure_placeholder_expression=f"{result_type}{{}}",
        inline_specifier="[[nodiscard]] TSL_FORCE_INLINE",
    )


__all__ = ("CppCheckedApiPlan", "plan_cpp_checked_api")
