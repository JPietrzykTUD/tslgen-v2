from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceSpan
from tslgen.domain.values import CatalogMap, CatalogValue


@dataclass(frozen=True, slots=True)
class PrimitiveAttribute:
    name: str
    value: CatalogValue
    source_span: SourceSpan
    argument: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("primitive attribute name must be non-empty")

    @property
    def key(self) -> str:
        if self.argument is None:
            return self.name
        return f"{self.name}({self.argument})"


@dataclass(frozen=True, slots=True)
class PrimitiveParameter:
    name: str
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("primitive parameter name must be non-empty")


@dataclass(frozen=True, slots=True)
class PrimitiveDeclaration:
    name: str
    signature: str
    parameters: tuple[PrimitiveParameter, ...]
    attributes: tuple[PrimitiveAttribute, ...]
    fields: CatalogMap
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("primitive name must be non-empty")
        if not self.signature:
            raise ValueError("primitive signature must be non-empty")
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "attributes", tuple(self.attributes))

    @property
    def catalog_id(self) -> str:
        parameter_list = ",".join(parameter.name for parameter in self.parameters)
        attribute_list = ",".join(
            f"{attribute.key}={attribute.value!r}" for attribute in self.attributes
        )
        return f"{self.name}<{self.signature}>[{attribute_list}]({parameter_list})"

