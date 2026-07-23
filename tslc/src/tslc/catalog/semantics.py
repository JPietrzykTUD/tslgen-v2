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
    INSERT_LANE = "insert_lane"
    LOAD = "load"
    MASK_AND = "mask_and"
    MASK_NOT = "mask_not"
    MASK_OR = "mask_or"
    MASK_POPULATION_COUNT = "mask_population_count"
    MASK_XOR = "mask_xor"
    REINTERPRET = "reinterpret"
    SELECT = "select"
    SHIFT_LEFT = "shift_left"
    SHIFT_RIGHT = "shift_right"
    STORE = "store"


class OperandRole(StrEnum):
    CONTROL_MASK = "control_mask"
    COUNT = "count"
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
        PrimitiveOperation.INSERT_LANE: "Returns a vector with one lane value replaced.",
        PrimitiveOperation.LOAD: "Loads a vector payload from memory.",
        PrimitiveOperation.MASK_AND: "Computes logical AND of corresponding mask lanes.",
        PrimitiveOperation.MASK_NOT: "Computes logical inversion of mask lanes.",
        PrimitiveOperation.MASK_OR: "Computes logical OR of corresponding mask lanes.",
        PrimitiveOperation.MASK_POPULATION_COUNT: "Counts active mask lanes.",
        PrimitiveOperation.MASK_XOR: "Computes logical XOR of corresponding mask lanes.",
        PrimitiveOperation.REINTERPRET: (
            "Reinterprets a vector's bit pattern as another declared vector type."
        ),
        PrimitiveOperation.SELECT: "Selects between value operands under a control mask.",
        PrimitiveOperation.SHIFT_LEFT: "Shifts vector lane bit patterns left.",
        PrimitiveOperation.SHIFT_RIGHT: "Shifts vector lane bit patterns right.",
        PrimitiveOperation.STORE: "Stores a vector or scalar payload to memory.",
    }
)

OPERAND_ROLE_DESCRIPTIONS: Mapping[OperandRole, str] = MappingProxyType(
    {
        OperandRole.CONTROL_MASK: "The mask controlling active lanes.",
        OperandRole.COUNT: "The uniform or per-lane count operand.",
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
