"""Language-neutral primitive facts carried across the lowering boundary."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.arithmetic import ArithmeticContract
from tslc.catalog.conversion import PrimitiveConversionContract
from tslc.catalog.memory import MemoryAlignment, PrimitiveMemoryContract
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import PrimitiveSemanticContract
from tslc.catalog.shift import PrimitiveShiftContract


@dataclass(frozen=True, slots=True)
class LoweredMemoryAlignment:
    """One resolved memory-alignment specialization axis."""

    axis_name: str
    mode: MemoryAlignment

    def __post_init__(self) -> None:
        if not self.axis_name:
            raise ValueError("lowered memory alignment requires an axis name")


@dataclass(frozen=True, slots=True)
class LoweredPrimitiveSemantics:
    """Finalized source facts available to backend-neutral projections.

    The record deliberately carries promoted contracts, not a catalog handle or
    source registries. Backends may apply language policy to these facts, but
    must not reconstruct them from primitive names, signatures, or body text.
    """

    overload: ResolvedPrimitiveOverload | None = None
    arithmetic: ArithmeticContract | None = None
    operation: PrimitiveSemanticContract | None = None
    memory: PrimitiveMemoryContract | None = None
    memory_alignment: LoweredMemoryAlignment | None = None
    conversion: PrimitiveConversionContract | None = None
    shift: PrimitiveShiftContract | None = None


__all__ = ("LoweredMemoryAlignment", "LoweredPrimitiveSemantics")
