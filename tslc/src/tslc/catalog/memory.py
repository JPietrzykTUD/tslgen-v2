"""Typed memory semantics for source primitive declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.catalog.semantics import PrimitiveOperation
from tslc.diagnostics import SourceSpan


class MemoryAccess(StrEnum):
    READ = "read"
    WRITE = "write"


class MemoryAddressing(StrEnum):
    CONTIGUOUS = "contiguous"
    INDEXED = "indexed"
    COMPACTED = "compacted"


class MemoryAlignment(StrEnum):
    ALIGNED = "aligned"
    UNALIGNED = "unaligned"


class MemoryPayloadExtent(StrEnum):
    """How a memory operation determines its element payload."""

    SCALAR = "scalar"
    VECTOR = "vector"
    TARGET_VECTOR = "target_vector"
    ACTIVE_LANES = "active_lanes"


class MemoryIndexedLaneExtent(StrEnum):
    """Which logical lanes an indexed memory operation may access."""

    VECTOR = "vector"
    INDEX_VECTOR = "index_vector"


_MEMORY_ALIGNMENT_AXIS = "aligned"


def resolve_memory_alignment(
    attributes: Mapping[str, str],
) -> tuple[str, MemoryAlignment] | None:
    """Resolve one concrete specialization of the catalog alignment axis."""

    mode = {
        "false": MemoryAlignment.UNALIGNED,
        "true": MemoryAlignment.ALIGNED,
    }.get(attributes.get(_MEMORY_ALIGNMENT_AXIS, ""))
    return None if mode is None else (_MEMORY_ALIGNMENT_AXIS, mode)


def memory_operations(access: MemoryAccess) -> frozenset[PrimitiveOperation]:
    """Return the semantic operations admitted by one memory access."""

    return {
        MemoryAccess.READ: frozenset(
            {PrimitiveOperation.LOAD, PrimitiveOperation.LOAD_SCALAR}
        ),
        MemoryAccess.WRITE: frozenset(
            {PrimitiveOperation.RANDOM_STEP, PrimitiveOperation.STORE}
        ),
    }[access]


MEMORY_ACCESS_DESCRIPTIONS: Mapping[MemoryAccess, str] = MappingProxyType(
    {
        MemoryAccess.READ: "Reads a payload from memory.",
        MemoryAccess.WRITE: "Writes a payload to memory.",
    }
)
MEMORY_ADDRESSING_DESCRIPTIONS: Mapping[MemoryAddressing, str] = MappingProxyType(
    {
        MemoryAddressing.CONTIGUOUS: "Accesses consecutive elements in memory.",
        MemoryAddressing.INDEXED: (
            "Accesses per-lane byte offsets computed from indices and a scale."
        ),
        MemoryAddressing.COMPACTED: (
            "Accesses consecutive elements selected by active mask lanes."
        ),
    }
)
MEMORY_INDEXED_LANE_EXTENT_DESCRIPTIONS: Mapping[
    MemoryIndexedLaneExtent, str
] = MappingProxyType(
    {
        MemoryIndexedLaneExtent.VECTOR: (
            "Accesses one index for every logical operation lane; the index "
            "source must cover those lanes."
        ),
        MemoryIndexedLaneExtent.INDEX_VECTOR: (
            "Accesses one element for every supplied index lane; those lanes "
            "must fit in the operation result."
        ),
    }
)


@dataclass(frozen=True, slots=True)
class PrimitiveMemoryContract:
    access: MemoryAccess
    addressing: MemoryAddressing
    payload_extent: MemoryPayloadExtent
    indexed_lane_extent: MemoryIndexedLaneExtent | None = None
    source: SourceSpan | None = None
    access_source: SourceSpan | None = None
    addressing_source: SourceSpan | None = None
    indexed_lane_extent_source: SourceSpan | None = None

    def __post_init__(self) -> None:
        if (self.addressing is MemoryAddressing.INDEXED) != (
            self.indexed_lane_extent is not None
        ):
            raise ValueError(
                "indexed memory contracts require exactly one indexed-lane extent"
            )


def memory_access_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in MemoryAccess))


def memory_addressing_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in MemoryAddressing))


def memory_indexed_lane_extent_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in MemoryIndexedLaneExtent))


__all__ = (
    "MEMORY_ACCESS_DESCRIPTIONS",
    "MEMORY_ADDRESSING_DESCRIPTIONS",
    "MEMORY_INDEXED_LANE_EXTENT_DESCRIPTIONS",
    "MemoryAccess",
    "MemoryAddressing",
    "MemoryAlignment",
    "MemoryIndexedLaneExtent",
    "MemoryPayloadExtent",
    "PrimitiveMemoryContract",
    "memory_access_values",
    "memory_addressing_values",
    "memory_indexed_lane_extent_values",
    "memory_operations",
    "resolve_memory_alignment",
)
