"""Static registry of TSIL region lowerers."""

from __future__ import annotations

from collections.abc import Callable

from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.lower.region_handlers.calls import CallLowerer
from tslc.lower.region_handlers.casts import CastLowerer
from tslc.lower.region_handlers.control import (
    AssumeAlignedLowerer,
    IfLowerer,
    LoopLowerer,
    SwitchLowerer,
)
from tslc.lower.region_handlers.declarations import LetLowerer, VarLowerer
from tslc.lower.region_handlers.intrinsics import IntrinLowerer
from tslc.lower.region_handlers.io import IoLowerer
from tslc.lower.region_handlers.lanes import LanesLowerer
from tslc.lower.region_handlers.masks import MaskLowerer
from tslc.lower.region_handlers.memory import MemLowerer
from tslc.lower.region_handlers.operators import OpLowerer
from tslc.lower.region_handlers.protocol import RegionLowerer
from tslc.lower.region_handlers.queries import QueryRegionLowerer
from tslc.lower.region_handlers.returns import CompleteLowerer

RegionLowererFactory = Callable[[], RegionLowerer]

_REGION_LOWERER_FACTORIES: dict[str, RegionLowererFactory] = {
    "intrin": IntrinLowerer,
    "op": OpLowerer,
    "var": VarLowerer,
    "let": LetLowerer,
    "mask": MaskLowerer,
    "mem": MemLowerer,
    "lanes": LanesLowerer,
    "io": IoLowerer,
    "cast": CastLowerer,
    "call": CallLowerer,
    "if": IfLowerer,
    "assume_aligned": AssumeAlignedLowerer,
    "loop": LoopLowerer,
    "switch": SwitchLowerer,
    "type": lambda: QueryRegionLowerer("type"),
    "value": lambda: QueryRegionLowerer("value"),
    "complete": CompleteLowerer,
}

DEFAULT_REGION_LOWERERS: tuple[RegionLowerer, ...] = tuple(
    factory()
    for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS
    if (factory := _REGION_LOWERER_FACTORIES.get(descriptor.keyword)) is not None
)
