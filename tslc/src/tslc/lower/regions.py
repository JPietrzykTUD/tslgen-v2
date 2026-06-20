"""Compatibility facade for TSIL region lowerers.

The handler implementations live in :mod:`tslc.lower.region_handlers`. This module keeps the
older import path stable for callers that import ``DEFAULT_REGION_LOWERERS`` or individual handler
classes from ``tslc.lower.regions``.
"""

from __future__ import annotations

from tslc.lower.region_handlers.bitwise import BitNegateLowerer
from tslc.lower.region_handlers.calls import CallLowerer
from tslc.lower.region_handlers.casts import CastLowerer
from tslc.lower.region_handlers.common import _segment_text, _split_arg_groups, _vector_spelling
from tslc.lower.region_handlers.control import (
    AssumeAlignedLowerer,
    IfLowerer,
    LoopLowerer,
    SwitchLowerer,
)
from tslc.lower.region_handlers.declarations import LetLowerer, VarLowerer
from tslc.lower.region_handlers.intrinsics import (
    ComposeModifiers,
    IntrinComposeLowerer,
    IntrinLowerer,
)
from tslc.lower.region_handlers.masks import MaskLowerer
from tslc.lower.region_handlers.memory import MemLowerer
from tslc.lower.region_handlers.protocol import RegionLowerer, RenderBody
from tslc.lower.region_handlers.queries import QueryRegionLowerer
from tslc.lower.region_handlers.registry import DEFAULT_REGION_LOWERERS
from tslc.lower.region_handlers.returns import EmitReturnLowerer

__all__ = [
    "AssumeAlignedLowerer",
    "BitNegateLowerer",
    "CallLowerer",
    "CastLowerer",
    "ComposeModifiers",
    "DEFAULT_REGION_LOWERERS",
    "EmitReturnLowerer",
    "IfLowerer",
    "IntrinComposeLowerer",
    "IntrinLowerer",
    "LetLowerer",
    "LoopLowerer",
    "MaskLowerer",
    "MemLowerer",
    "QueryRegionLowerer",
    "RegionLowerer",
    "RenderBody",
    "SwitchLowerer",
    "VarLowerer",
    "_segment_text",
    "_split_arg_groups",
    "_vector_spelling",
]
