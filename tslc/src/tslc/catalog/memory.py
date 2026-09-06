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
            "Accesses per-lane byte offsets computed from an index vector and scale."
        ),
        MemoryAddressing.COMPACTED: (
            "Accesses consecutive elements selected by active mask lanes."
        ),
    }
)


@dataclass(frozen=True, slots=True)
class PrimitiveMemoryContract:
    access: MemoryAccess
    addressing: MemoryAddressing
    payload_extent: MemoryPayloadExtent
    source: SourceSpan | None = None
    access_source: SourceSpan | None = None
    addressing_source: SourceSpan | None = None


def memory_access_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in MemoryAccess))


def memory_addressing_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in MemoryAddressing))


__all__ = (
    "MEMORY_ACCESS_DESCRIPTIONS",
    "MEMORY_ADDRESSING_DESCRIPTIONS",
    "MemoryAccess",
    "MemoryAddressing",
    "MemoryAlignment",
    "MemoryPayloadExtent",
    "PrimitiveMemoryContract",
    "memory_access_values",
    "memory_addressing_values",
    "memory_operations",
    "resolve_memory_alignment",
)
