from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceSpan
from tslgen.domain.values import CatalogMap


@dataclass(frozen=True, slots=True)
class Extension:
    name: str
    fields: CatalogMap
    source_span: SourceSpan
    vendor: str | None = None
    family: str | None = None
    extension_name: str | None = None
    vector_bits: int | str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("extension name must be non-empty")
