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
from tslc.catalog.semantics import OperandBinding, OperandRole, PrimitiveOperation
from tslc.diagnostics import SourceSpan


class PreconditionKind(StrEnum):
    """Source spellings for catastrophic public-call preconditions."""

    LANE_INDEX_IN_RANGE = "lane_index_in_range"
    ACTIVE_DIVISOR_NONZERO = "active_divisor_nonzero"


class PreconditionHazard(StrEnum):
    """Severity class used by backend API policy."""

    CATASTROPHIC = "catastrophic"


class PreconditionErrorKind(StrEnum):
    """Language-neutral checked-API failure categories."""

    INDEX_OUT_OF_BOUNDS = "index_out_of_bounds"
    ZERO_DIVISOR = "zero_divisor"


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
