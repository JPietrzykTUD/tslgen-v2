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


class MemoryAlignment(StrEnum):
    ALIGNED = "aligned"
    UNALIGNED = "unaligned"


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


def memory_operation(access: MemoryAccess) -> PrimitiveOperation:
    """Return the semantic operation required by one memory access."""

    return {
        MemoryAccess.READ: PrimitiveOperation.LOAD,
        MemoryAccess.WRITE: PrimitiveOperation.STORE,
    }[access]


MEMORY_ACCESS_DESCRIPTIONS: Mapping[MemoryAccess, str] = MappingProxyType(
    {
        MemoryAccess.READ: "Reads a payload from memory.",
        MemoryAccess.WRITE: "Writes a payload to memory.",
    }
)
MEMORY_ADDRESSING_DESCRIPTIONS: Mapping[MemoryAddressing, str] = MappingProxyType(
    {MemoryAddressing.CONTIGUOUS: "Accesses consecutive elements in memory."}
)


@dataclass(frozen=True, slots=True)
class PrimitiveMemoryContract:
    access: MemoryAccess
    addressing: MemoryAddressing
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
    "PrimitiveMemoryContract",
    "memory_access_values",
    "memory_addressing_values",
    "memory_operation",
    "resolve_memory_alignment",
)
