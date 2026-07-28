"""Language-neutral primitive operation and operand-role contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


class PrimitiveOperation(StrEnum):
    BIT_AND = "bit_and"
    BIT_AND_NOT = "bit_and_not"
    BIT_NOT = "bit_not"
    BIT_OR = "bit_or"
    BIT_XOR = "bit_xor"
    COMPARE_EQUAL = "compare_equal"
    COMPARE_GREATER = "compare_greater"
    COMPARE_GREATER_EQUAL = "compare_greater_equal"
    COMPARE_LESS = "compare_less"
    COMPARE_LESS_EQUAL = "compare_less_equal"
    COMPARE_NOT_EQUAL = "compare_not_equal"
    CONVERT = "convert"
    EXTRACT_LANE = "extract_lane"
    HORIZONTAL_ADD = "horizontal_add"
    HORIZONTAL_BIT_AND = "horizontal_bit_and"
    HORIZONTAL_BIT_OR = "horizontal_bit_or"
    HORIZONTAL_MAX = "horizontal_max"
    HORIZONTAL_MIN = "horizontal_min"
    INTEGRAL_MASK_TEST = "integral_mask_test"
    INSERT_LANE = "insert_lane"
    LOAD = "load"
    MASK_ALL_FALSE = "mask_all_false"
    MASK_ALL_TRUE = "mask_all_true"
    MASK_AND = "mask_and"
    MASK_FROM_INTEGRAL = "mask_from_integral"
    MASK_NOT = "mask_not"
    MASK_OR = "mask_or"
    MASK_POPULATION_COUNT = "mask_population_count"
    MASK_SET_LANE = "mask_set_lane"
    MASK_TO_INTEGRAL = "mask_to_integral"
    MASK_XOR = "mask_xor"
    REINTERPRET = "reinterpret"
    SELECT = "select"
    SHIFT_LEFT = "shift_left"
    SHIFT_LEFT_WRAPPING = "shift_left_wrapping"
    SHIFT_RIGHT = "shift_right"
    SHIFT_RIGHT_WRAPPING = "shift_right_wrapping"
    STORE = "store"
    VECTOR_FROM_ARRAY = "vector_from_array"
    VECTOR_SPLAT = "vector_splat"
    VECTOR_TO_ARRAY = "vector_to_array"
    VECTOR_ZERO = "vector_zero"


class OperandRole(StrEnum):
    CONTROL_MASK = "control_mask"
    COUNT = "count"
    INDEX = "index"
    MEMORY_DESTINATION = "memory_destination"
    MEMORY_SOURCE = "memory_source"
    PASS_THROUGH = "pass_through"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    VALUE = "value"


@dataclass(frozen=True, slots=True)
class OperandBinding:
    role: OperandRole
    parameter_name: str
    parameter_index: int
    parameter_kind: str
    source: SourceSpan | None = None
    parameter_source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class PrimitiveSemanticContract:
    """Explicit operation identity and declaration-local operand bindings."""

    kind: PrimitiveOperation
    operand_bindings: tuple[OperandBinding, ...]
    source: SourceSpan | None = None
    operation_source: SourceSpan | None = None
    operand_roles_source: SourceSpan | None = None

    def binding(self, role: OperandRole) -> OperandBinding | None:
        return next(
            (binding for binding in self.operand_bindings if binding.role is role),
            None,
        )


PRIMITIVE_OPERATION_DESCRIPTIONS: Mapping[PrimitiveOperation, str] = MappingProxyType(
    {
        PrimitiveOperation.BIT_AND: "Computes lane-wise bitwise AND.",
        PrimitiveOperation.BIT_AND_NOT: "Computes lane-wise bitwise AND with an inverted operand.",
        PrimitiveOperation.BIT_NOT: "Computes lane-wise bitwise inversion.",
        PrimitiveOperation.BIT_OR: "Computes lane-wise bitwise OR.",
        PrimitiveOperation.BIT_XOR: "Computes lane-wise bitwise XOR.",
        PrimitiveOperation.COMPARE_EQUAL: "Compares corresponding lanes for equality.",
        PrimitiveOperation.COMPARE_GREATER: "Compares corresponding lanes using greater-than.",
        PrimitiveOperation.COMPARE_GREATER_EQUAL: (
            "Compares corresponding lanes using greater-than-or-equal."
        ),
        PrimitiveOperation.COMPARE_LESS: "Compares corresponding lanes using less-than.",
        PrimitiveOperation.COMPARE_LESS_EQUAL: (
            "Compares corresponding lanes using less-than-or-equal."
        ),
        PrimitiveOperation.COMPARE_NOT_EQUAL: "Compares corresponding lanes for inequality.",
        PrimitiveOperation.CONVERT: "Converts lane values to a declared result vector type.",
        PrimitiveOperation.EXTRACT_LANE: "Extracts one lane value from a vector.",
        PrimitiveOperation.HORIZONTAL_ADD: (
            "Reduces active vector lanes to their arithmetic sum."
        ),
        PrimitiveOperation.HORIZONTAL_BIT_AND: (
            "Reduces active vector lane bit patterns with bitwise AND."
        ),
        PrimitiveOperation.HORIZONTAL_BIT_OR: (
            "Reduces active vector lane bit patterns with bitwise OR."
        ),
        PrimitiveOperation.HORIZONTAL_MAX: (
            "Reduces active vector lanes to their maximum value."
        ),
        PrimitiveOperation.HORIZONTAL_MIN: (
            "Reduces active vector lanes to their minimum value."
        ),
        PrimitiveOperation.INTEGRAL_MASK_TEST: (
            "Tests one runtime-indexed bit of an integral mask value."
        ),
        PrimitiveOperation.INSERT_LANE: "Returns a vector with one lane value replaced.",
        PrimitiveOperation.LOAD: "Loads a vector payload from memory.",
        PrimitiveOperation.MASK_ALL_FALSE: "Constructs an all-inactive lane mask.",
        PrimitiveOperation.MASK_ALL_TRUE: "Constructs an all-active lane mask.",
        PrimitiveOperation.MASK_AND: "Computes logical AND of corresponding mask lanes.",
        PrimitiveOperation.MASK_FROM_INTEGRAL: (
            "Converts an integral mask representation to a lane mask."
        ),
        PrimitiveOperation.MASK_NOT: "Computes logical inversion of mask lanes.",
        PrimitiveOperation.MASK_OR: "Computes logical OR of corresponding mask lanes.",
        PrimitiveOperation.MASK_POPULATION_COUNT: "Counts active mask lanes.",
        PrimitiveOperation.MASK_SET_LANE: (
            "Returns a mask with one runtime-indexed logical lane replaced."
        ),
        PrimitiveOperation.MASK_TO_INTEGRAL: (
            "Converts a lane mask to its integral mask representation."
        ),
        PrimitiveOperation.MASK_XOR: "Computes logical XOR of corresponding mask lanes.",
        PrimitiveOperation.REINTERPRET: (
            "Reinterprets a vector's bit pattern as another declared vector type."
        ),
        PrimitiveOperation.SELECT: "Selects between value operands under a control mask.",
        PrimitiveOperation.SHIFT_LEFT: "Shifts vector lane bit patterns left.",
        PrimitiveOperation.SHIFT_LEFT_WRAPPING: (
            "Shifts vector lanes left with source-defined wrapping counts."
        ),
        PrimitiveOperation.SHIFT_RIGHT: "Shifts vector lane bit patterns right.",
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING: (
            "Shifts vector lanes right with source-defined wrapping counts."
        ),
        PrimitiveOperation.STORE: "Stores a vector or scalar payload to memory.",
        PrimitiveOperation.VECTOR_FROM_ARRAY: (
            "Constructs a vector from an array of logical lane values."
        ),
        PrimitiveOperation.VECTOR_SPLAT: "Broadcasts one scalar value to every vector lane.",
        PrimitiveOperation.VECTOR_TO_ARRAY: (
            "Materializes vector lanes as an array in logical lane order."
        ),
        PrimitiveOperation.VECTOR_ZERO: "Constructs a vector whose lanes are all zero.",
    }
)

OPERAND_ROLE_DESCRIPTIONS: Mapping[OperandRole, str] = MappingProxyType(
    {
        OperandRole.CONTROL_MASK: "The mask controlling active lanes.",
        OperandRole.COUNT: "The uniform or per-lane count operand.",
        OperandRole.INDEX: "The runtime logical lane index operand.",
        OperandRole.MEMORY_DESTINATION: "The memory destination written by the operation.",
        OperandRole.MEMORY_SOURCE: "The memory source read by the operation.",
        OperandRole.PASS_THROUGH: "The value preserved where a control mask is inactive.",
        OperandRole.PRIMARY: "The primary logical value and natural method receiver.",
        OperandRole.SECONDARY: "The second logical value operand.",
        OperandRole.VALUE: "A scalar or vector value inserted or stored by the operation.",
    }
)


def primitive_operation_values() -> tuple[str, ...]:
    return tuple(sorted(operation.value for operation in PrimitiveOperation))


def operand_role_values() -> tuple[str, ...]:
    return tuple(sorted(role.value for role in OperandRole))


__all__ = (
    "OPERAND_ROLE_DESCRIPTIONS",
    "PRIMITIVE_OPERATION_DESCRIPTIONS",
    "OperandBinding",
    "OperandRole",
    "PrimitiveOperation",
    "PrimitiveSemanticContract",
    "operand_role_values",
    "primitive_operation_values",
)
