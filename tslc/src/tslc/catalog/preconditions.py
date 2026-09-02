"""Language-neutral primitive preconditions and their closed descriptors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.catalog.semantics import OperandBinding, OperandRole, PrimitiveOperation
from tslc.diagnostics import SourceSpan


class PreconditionKind(StrEnum):
    """Source spellings for catastrophic public-call preconditions."""

    LANE_INDEX_IN_RANGE = "lane_index_in_range"


class PreconditionHazard(StrEnum):
    """Severity class used by backend API policy."""

    CATASTROPHIC = "catastrophic"


class PreconditionErrorKind(StrEnum):
    """Language-neutral checked-API failure categories."""

    INDEX_OUT_OF_BOUNDS = "index_out_of_bounds"


@dataclass(frozen=True, slots=True)
class PreconditionDescriptor:
    """Compiler-owned meaning of one closed precondition spelling."""

    kind: PreconditionKind
    description: str
    required_roles: frozenset[OperandRole]
    compatible_operations: frozenset[PrimitiveOperation]
    logical_lane_owner_role: OperandRole | None
    hazard: PreconditionHazard
    error: PreconditionErrorKind
    unchecked_consequence: str


@dataclass(frozen=True, slots=True)
class PrimitivePrecondition:
    """One declaration-local precondition with resolved operand bindings."""

    kind: PreconditionKind
    operand_bindings: tuple[OperandBinding, ...]
    source: SourceSpan | None = None

    def binding(self, role: OperandRole) -> OperandBinding | None:
        return next(
            (binding for binding in self.operand_bindings if binding.role is role),
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
        )
    }
)


def precondition_values() -> tuple[str, ...]:
    return tuple(sorted(item.value for item in PreconditionKind))


__all__ = (
    "PRECONDITION_DESCRIPTORS",
    "PreconditionDescriptor",
    "PreconditionErrorKind",
    "PreconditionHazard",
    "PreconditionKind",
    "PrimitivePrecondition",
    "precondition_values",
)
