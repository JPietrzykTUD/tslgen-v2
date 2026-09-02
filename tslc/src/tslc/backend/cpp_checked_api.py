"""Finalized C++ checked-wrapper ABI decisions."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.checked_api import (
    CheckedConditionPlan,
    applicable_checked_api_plan,
)
from tslc.catalog.arithmetic import ArithmeticNumericDomain
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
    template_constraint: str | None


def _template_constraint(
    conditions: tuple[CheckedConditionPlan, ...],
) -> str | None:
    domains = frozenset(
        condition.numeric_domain
        for condition in conditions
        if condition.numeric_domain is not None
    )
    if any(condition.numeric_domain is None for condition in conditions):
        return None
    expressions = {
        ArithmeticNumericDomain.INTEGER: (
            "std::is_integral_v<typename Vec::base_type>"
        ),
        ArithmeticNumericDomain.SIGNED_INTEGER: (
            "(std::is_integral_v<typename Vec::base_type> && "
            "std::is_signed_v<typename Vec::base_type>)"
        ),
        ArithmeticNumericDomain.FLOATING: (
            "std::is_floating_point_v<typename Vec::base_type>"
        ),
    }
    condition = " || ".join(
        expressions[domain] for domain in sorted(domains, key=lambda item: item.value)
    )
    return f"std::enable_if_t<({condition}), int> = 0"


def plan_cpp_checked_api(
    specializations: tuple[LoweredSpecialization, ...],
    *,
    result_type: str,
) -> CppCheckedApiPlan | None:
    plan = applicable_checked_api_plan(specializations)
    if plan is None:
        return None
    return CppCheckedApiPlan(
        conditions=plan.conditions,
        error_parameter_name="error",
        error_parameter_declaration="::tsl::precondition_error & error",
        success_error_expression="::tsl::precondition_error::none",
        failure_placeholder_expression=f"{result_type}{{}}",
        inline_specifier="[[nodiscard]] TSL_FORCE_INLINE",
        template_constraint=_template_constraint(plan.conditions),
    )


__all__ = ("CppCheckedApiPlan", "plan_cpp_checked_api")
