from __future__ import annotations

from tslgen.core.frozen_map import FrozenMap


type CatalogValue = (
    str
    | int
    | float
    | bool
    | None
    | tuple[CatalogValue, ...]
    | FrozenMap[str, CatalogValue]
)
type CatalogMap = FrozenMap[str, CatalogValue]

