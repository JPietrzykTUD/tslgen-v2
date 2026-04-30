from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceSpan
from tslgen.domain.values import CatalogMap


@dataclass(frozen=True, slots=True)
class TypeGroup:
    name: str
    members: tuple[str, ...]
    fields: CatalogMap
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("type group name must be non-empty")
        object.__setattr__(self, "members", tuple(self.members))


@dataclass(frozen=True, slots=True)
class LaneSet:
    name: str
    lanes: tuple[int, ...]
    type_names: tuple[str, ...]
    fields: CatalogMap
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("lane set name must be non-empty")
        object.__setattr__(self, "lanes", tuple(self.lanes))
        object.__setattr__(self, "type_names", tuple(self.type_names))

