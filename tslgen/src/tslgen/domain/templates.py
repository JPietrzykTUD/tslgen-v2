from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceSpan
from tslgen.domain.values import CatalogMap


@dataclass(frozen=True, slots=True)
class OperationTemplate:
    name: str
    fields: CatalogMap
    source_span: SourceSpan
    description: str | None = None
    shape: str | None = None
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("template name must be non-empty")
        object.__setattr__(self, "required_fields", tuple(self.required_fields))
        object.__setattr__(self, "optional_fields", tuple(self.optional_fields))

