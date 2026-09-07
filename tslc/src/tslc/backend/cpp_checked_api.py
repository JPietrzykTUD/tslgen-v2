"""Finalized C++ checked-wrapper ABI decisions."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.checked_api import (
    CheckedConditionPlan,
    applicable_checked_api_plan,
    checked_memory_condition,
)
from tslc.catalog.arithmetic import ArithmeticNumericDomain
from tslc.catalog.memory import MemoryAccess, MemoryAddressing, MemoryPayloadExtent
from tslc.catalog.semantics import OperandRole
from tslc.lower.lowerer import LoweredSpecialization, varying_positions


@dataclass(frozen=True, slots=True)
class CppCheckedApiPlan:
    """C++-specific checked signature and failure-result policy."""

    conditions: tuple[CheckedConditionPlan, ...]
    error_parameter_name: str
    error_parameter_declaration: str | None
    success_error_expression: str
    failure_placeholder_expression: str | None
    inline_specifier: str
    template_constraint: str | None
    public_result_type: str
    has_value_result: bool
    memory_parameter_name: str | None
    memory_parameter_index: int | None
    memory_access: MemoryAccess | None
    memory_addressing: MemoryAddressing | None
    required_extent_expression: str | None
    required_alignment_expression: str | None
    alignment_parameter_name: str | None
    index_type_parameter_name: str | None


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
    result_kind: str,
    result_type: str,
) -> CppCheckedApiPlan | None:
    plan = applicable_checked_api_plan(specializations)
    if plan is None:
        return None
    has_value_result = result_kind != "void"
    memory_condition = checked_memory_condition(plan.conditions)
    memory_parameter_name: str | None = None
    memory_parameter_index: int | None = None
    memory_access: MemoryAccess | None = None
    memory_addressing: MemoryAddressing | None = None
    required_extent_expression: str | None = None
    required_alignment_expression: str | None = None
    alignment_parameter_name: str | None = None
    index_type_parameter_name: str | None = None
    if memory_condition is not None:
        (
            memory_parameter_name,
            memory_parameter_index,
            memory_access,
            memory_addressing,
            payload_extents,
            alignment_axis_name,
        ) = (
            memory_condition.parameter_name,
            memory_condition.parameter_index,
            memory_condition.memory_access,
            memory_condition.memory_addressing,
            memory_condition.memory_payload_extents,
            memory_condition.memory_alignment_axis_name,
        )
        alignment_parameter_name = (
            alignment_axis_name[:1].upper() + alignment_axis_name[1:]
            if alignment_axis_name is not None
            else None
        )
        if memory_addressing is MemoryAddressing.INDEXED:
            required_extent_expression = None
            required_alignment_expression = None
        elif memory_addressing is MemoryAddressing.COMPACTED:
            if payload_extents != (MemoryPayloadExtent.ACTIVE_LANES,):
                raise ValueError(
                    "compacted C++ checked memory requires active-lane extent"
                )
            required_extent_expression = None
            required_alignment_expression = "Vec::vector_alignment"
        elif payload_extents == (MemoryPayloadExtent.SCALAR,):
            required_extent_expression = "std::size_t{1}"
            required_alignment_expression = "alignof(typename Vec::base_type)"
        elif payload_extents == (MemoryPayloadExtent.VECTOR,):
            required_extent_expression = "Vec::lane_count()"
            required_alignment_expression = "Vec::vector_alignment"
        elif payload_extents == (MemoryPayloadExtent.TARGET_VECTOR,):
            required_extent_expression = "ToVec::lane_count()"
            required_alignment_expression = "alignof(typename Vec::base_type)"
        elif set(payload_extents) == {
            MemoryPayloadExtent.SCALAR,
            MemoryPayloadExtent.VECTOR,
        }:
            varying = varying_positions(specializations)
            if len(varying) != 1:
                raise ValueError(
                    "mixed scalar/vector checked memory requires one overload parameter"
                )
            value_bindings: set[int] = set()
            for spec in specializations:
                operation = spec.primitive_semantics.operation
                binding = (
                    None if operation is None else operation.binding(OperandRole.VALUE)
                )
                if binding is not None:
                    value_bindings.add(binding.parameter_index)
            if value_bindings != {varying[0]}:
                raise ValueError(
                    "checked memory payload extent disagrees with overload dispatch"
                )
            scalar_test = (
                f"std::is_same_v<std::decay_t<Arg{varying[0]}>, "
                "typename Vec::base_type>"
            )
            required_extent_expression = (
                f"({scalar_test} ? std::size_t{{1}} : Vec::lane_count())"
            )
            required_alignment_expression = (
                f"({scalar_test} ? alignof(typename Vec::base_type) : "
                "Vec::vector_alignment)"
            )
        else:
            raise ValueError("unsupported C++ checked memory payload extent")
        if memory_addressing is MemoryAddressing.INDEXED:
            index_type_names = {
                spec.type_params[0].name
                for spec in specializations
                if spec.type_params
            }
            if len(index_type_names) != 1 or any(
                len(spec.type_params) != 1 for spec in specializations
            ):
                raise ValueError(
                    "checked indexed memory requires one consistent index type parameter"
                )
            index_type_parameter_name = next(iter(index_type_names))
    return CppCheckedApiPlan(
        conditions=plan.conditions,
        error_parameter_name="error",
        error_parameter_declaration=(
            "::tsl::precondition_error & error" if has_value_result else None
        ),
        success_error_expression="::tsl::precondition_error::none",
        failure_placeholder_expression=(
            f"{result_type}{{}}" if has_value_result else None
        ),
        inline_specifier="[[nodiscard]] TSL_FORCE_INLINE",
        template_constraint=_template_constraint(plan.conditions),
        public_result_type=(
            result_type if has_value_result else "::tsl::precondition_error"
        ),
        has_value_result=has_value_result,
        memory_parameter_name=memory_parameter_name,
        memory_parameter_index=memory_parameter_index,
        memory_access=memory_access,
        memory_addressing=memory_addressing,
        required_extent_expression=required_extent_expression,
        required_alignment_expression=required_alignment_expression,
        alignment_parameter_name=alignment_parameter_name,
        index_type_parameter_name=index_type_parameter_name,
    )


__all__ = ("CppCheckedApiPlan", "plan_cpp_checked_api")
