"""Static registry of TSIL region lowerers."""

from __future__ import annotations

from tslc.lower.region_handlers.bitwise import BitNegateLowerer
from tslc.lower.region_handlers.calls import CallLowerer
from tslc.lower.region_handlers.casts import CastLowerer
from tslc.lower.region_handlers.control import (
    AssumeAlignedLowerer,
    IfLowerer,
    LoopLowerer,
    SwitchLowerer,
)
from tslc.lower.region_handlers.declarations import LetLowerer, VarLowerer
from tslc.lower.region_handlers.intrinsics import IntrinComposeLowerer, IntrinLowerer
from tslc.lower.region_handlers.masks import MaskLowerer
from tslc.lower.region_handlers.memory import MemLowerer
from tslc.lower.region_handlers.pack import PackLowerer
from tslc.lower.region_handlers.protocol import RegionLowerer
from tslc.lower.region_handlers.queries import QueryRegionLowerer
from tslc.lower.region_handlers.returns import EmitReturnLowerer

DEFAULT_REGION_LOWERERS: tuple[RegionLowerer, ...] = (
    IntrinComposeLowerer(),
    IntrinLowerer(),
    BitNegateLowerer(),
    VarLowerer(),
    LetLowerer(),
    MaskLowerer(),
    MemLowerer(),
    PackLowerer(),
    CastLowerer(),
    CallLowerer(),
    IfLowerer(),
    AssumeAlignedLowerer(),
    LoopLowerer(),
    SwitchLowerer(),
    QueryRegionLowerer("type"),
    QueryRegionLowerer("value"),
    EmitReturnLowerer(),
)
