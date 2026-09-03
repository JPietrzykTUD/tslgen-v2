"""Language-neutral primitive preconditions and their closed descriptors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.catalog.arithmetic import (
    ArithmeticNumericDomain,
    ArithmeticOperandBinding,
    ArithmeticOperandRole,
    ArithmeticOperation,
    matches_numeric_domain,
)
from tslc.catalog.scalar_types import scalar_type_info
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
)
from tslc.catalog.semantics import OperandBinding, OperandRole, PrimitiveOperation
from tslc.diagnostics import SourceSpan


class PreconditionKind(StrEnum):
    """Source spellings for catastrophic public-call preconditions."""

    LANE_INDEX_IN_RANGE = "lane_index_in_range"
    ACTIVE_DIVISOR_NONZERO = "active_divisor_nonzero"
    CONTIGUOUS_MEMORY_EXTENT = "contiguous_memory_extent"
    SELECTED_MEMORY_ALIGNMENT = "selected_memory_alignment"


class PreconditionHazard(StrEnum):
    """Severity class used by backend API policy."""

    CATASTROPHIC = "catastrophic"


class PreconditionErrorKind(StrEnum):
    """Language-neutral checked-API failure categories."""

    INDEX_OUT_OF_BOUNDS = "index_out_of_bounds"
    ZERO_DIVISOR = "zero_divisor"
    INSUFFICIENT_EXTENT = "insufficient_extent"
    INSUFFICIENT_INPUT = "insufficient_input"
    INSUFFICIENT_OUTPUT = "insufficient_output"
    MISALIGNED = "misaligned"
    OVERLAPPING_RANGES = "overlapping_ranges"
    ADDRESS_OVERFLOW = "address_overflow"


class PreconditionCheckPrimitive(StrEnum):
    """Canonical primitive dependencies used by generated checks."""

    EQUAL = "equal"
    MASK_AND = "mask_binary_and"
    MASK_POPULATION_COUNT = "mask_population_count"
    ZERO_VECTOR = "set_zero"


@dataclass(frozen=True, slots=True)
class PreconditionDescriptor:
    """Compiler-owned meaning of one closed precondition spelling."""

    kind: PreconditionKind
    description: str
    hazard: PreconditionHazard
    error: PreconditionErrorKind
    unchecked_consequence: str
    required_roles: frozenset[OperandRole] = frozenset()
    compatible_operations: frozenset[PrimitiveOperation] = frozenset()
    logical_lane_owner_role: OperandRole | None = None
    required_arithmetic_roles: frozenset[ArithmeticOperandRole] = frozenset()
    compatible_arithmetic_operations: frozenset[ArithmeticOperation] = frozenset()
    numeric_domain: ArithmeticNumericDomain | None = None
    checkable_arithmetic_binding_kinds: frozenset[str] = frozenset()
    check_primitives: tuple[PreconditionCheckPrimitive, ...] = ()
    masked_check_primitives: tuple[PreconditionCheckPrimitive, ...] = ()
    compatible_memory_accesses: frozenset[MemoryAccess] = frozenset()
    compatible_memory_addressings: frozenset[MemoryAddressing] = frozenset()
    binds_memory_operand: bool = False


@dataclass(frozen=True, slots=True)
class PrimitivePrecondition:
    """One declaration-local precondition with resolved operand bindings."""

    kind: PreconditionKind
    operand_bindings: tuple[OperandBinding | ArithmeticOperandBinding, ...]
    source: SourceSpan | None = None

    def binding(self, role: OperandRole) -> OperandBinding | None:
        return next(
            (
                binding
                for binding in self.operand_bindings
                if isinstance(binding, OperandBinding) and binding.role is role
            ),
            None,
        )

    def arithmetic_binding(
        self, role: ArithmeticOperandRole
    ) -> ArithmeticOperandBinding | None:
        return next(
            (
                binding
                for binding in self.operand_bindings
                if isinstance(binding, ArithmeticOperandBinding)
                and binding.role is role
            ),
            None,
        )


PRECONDITION_DESCRIPTORS: Mapping[
    PreconditionKind, PreconditionDescriptor
] = MappingProxyType(
    {
        PreconditionKind.LANE_INDEX_IN_RANGE: PreconditionDescriptor(
            kind=PreconditionKind.LANE_INDEX_IN_RANGE,
            description="The runtime lane index is smaller than the logical lane count.",
            required_roles=frozenset({OperandRole.PRIMARY, OperandRole.INDEX}),
            compatible_operations=frozenset(
                {
                    PrimitiveOperation.EXTRACT_LANE,
                    PrimitiveOperation.INSERT_LANE,
                    PrimitiveOperation.MASK_SET_LANE,
                }
            ),
            logical_lane_owner_role=OperandRole.PRIMARY,
            hazard=PreconditionHazard.CATASTROPHIC,
            error=PreconditionErrorKind.INDEX_OUT_OF_BOUNDS,
            unchecked_consequence=(
                "Violating this precondition may cause undefined behavior or a "
                "process-terminating memory access."
            ),
        ),
        PreconditionKind.ACTIVE_DIVISOR_NONZERO: PreconditionDescriptor(
            kind=PreconditionKind.ACTIVE_DIVISOR_NONZERO,
            description=(
                "Every participating integer divisor lane is nonzero; inactive "
                "masked lanes and floating-point lanes are excluded."
            ),
            required_arithmetic_roles=frozenset(
                {ArithmeticOperandRole.DIVISOR}
            ),
            compatible_arithmetic_operations=frozenset(
                {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
            ),
            numeric_domain=ArithmeticNumericDomain.INTEGER,
            checkable_arithmetic_binding_kinds=frozenset({"v"}),
            check_primitives=(
                PreconditionCheckPrimitive.ZERO_VECTOR,
                PreconditionCheckPrimitive.EQUAL,
                PreconditionCheckPrimitive.MASK_POPULATION_COUNT,
            ),
            masked_check_primitives=(PreconditionCheckPrimitive.MASK_AND,),
            hazard=PreconditionHazard.CATASTROPHIC,
            error=PreconditionErrorKind.ZERO_DIVISOR,
            unchecked_consequence=(
                "Violating this precondition may cause undefined behavior, a "
                "hardware trap, or process termination."
            ),
        ),
        PreconditionKind.CONTIGUOUS_MEMORY_EXTENT: PreconditionDescriptor(
            kind=PreconditionKind.CONTIGUOUS_MEMORY_EXTENT,
            description=(
                "The contiguous memory operand represents at least the operation's "
                "complete scalar or vector payload extent."
            ),
            compatible_operations=frozenset(
                {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
            ),
            compatible_memory_accesses=frozenset(
                {MemoryAccess.READ, MemoryAccess.WRITE}
            ),
            compatible_memory_addressings=frozenset(
                {MemoryAddressing.CONTIGUOUS}
            ),
            binds_memory_operand=True,
            hazard=PreconditionHazard.CATASTROPHIC,
            error=PreconditionErrorKind.INSUFFICIENT_EXTENT,
            unchecked_consequence=(
                "Violating this precondition may read or write outside the live "
                "memory object, causing undefined behavior or a process-level fault."
            ),
        ),
        PreconditionKind.SELECTED_MEMORY_ALIGNMENT: PreconditionDescriptor(
            kind=PreconditionKind.SELECTED_MEMORY_ALIGNMENT,
            description=(
                "When aligned access is selected, the contiguous memory operand "
                "satisfies the payload's required alignment."
            ),
            compatible_operations=frozenset(
                {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
            ),
            compatible_memory_accesses=frozenset(
                {MemoryAccess.READ, MemoryAccess.WRITE}
            ),
            compatible_memory_addressings=frozenset(
                {MemoryAddressing.CONTIGUOUS}
            ),
            binds_memory_operand=True,
            hazard=PreconditionHazard.CATASTROPHIC,
            error=PreconditionErrorKind.MISALIGNED,
            unchecked_consequence=(
                "Violating this precondition may cause undefined behavior, a "
                "hardware fault, or a process-level trap."
            ),
        ),
    }
)


def precondition_values() -> tuple[str, ...]:
    return tuple(sorted(item.value for item in PreconditionKind))


def precondition_applies_to_type(
    precondition: PrimitivePrecondition,
    type_tag: str,
) -> bool:
    """Resolve a conditional precondition against one concrete lane type."""

    domain = PRECONDITION_DESCRIPTORS[precondition.kind].numeric_domain
    if domain is None:
        return True
    info = scalar_type_info(type_tag)
    return info is not None and matches_numeric_domain(info, domain)


__all__ = (
    "PRECONDITION_DESCRIPTORS",
    "PreconditionDescriptor",
    "PreconditionCheckPrimitive",
    "PreconditionErrorKind",
    "PreconditionHazard",
    "PreconditionKind",
    "PrimitivePrecondition",
    "precondition_applies_to_type",
    "precondition_values",
)
