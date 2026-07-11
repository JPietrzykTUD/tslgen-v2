"""Static registry of TSIL region lowerers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.lower.implementation_facts import RegionImplementationEffect
from tslc.lower.region_handlers.calls import CallLowerer
from tslc.lower.region_handlers.casts import CastLowerer
from tslc.lower.region_handlers.control import (
    AssumeAlignedLowerer,
    IfLowerer,
    LoopLowerer,
    SelectExprLowerer,
    SwitchLowerer,
)
from tslc.lower.region_handlers.declarations import LetLowerer, VarLowerer
from tslc.lower.region_handlers.helpers import HelperLowerer
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


@dataclass(frozen=True, slots=True)
class RegionLoweringRegistration:
    """A region's handler and its implementation-state meaning in lowering."""

    keyword: str
    factory: RegionLowererFactory
    implementation_effect: RegionImplementationEffect


_EFFECT = RegionImplementationEffect
REGION_LOWERING_REGISTRATIONS: tuple[RegionLoweringRegistration, ...] = (
    RegionLoweringRegistration("intrin", IntrinLowerer, _EFFECT.INTRINSIC),
    RegionLoweringRegistration("helper", HelperLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("op", OpLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("var", VarLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("let", LetLowerer, _EFFECT.NEUTRAL),
    RegionLoweringRegistration("mask", MaskLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("mem", MemLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("lanes", LanesLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("io", IoLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("cast", CastLowerer, _EFFECT.COMPOSITION),
    RegionLoweringRegistration("call", CallLowerer, _EFFECT.CALL),
    RegionLoweringRegistration("if", IfLowerer, _EFFECT.CONTROL),
    RegionLoweringRegistration(
        "select_expr", SelectExprLowerer, _EFFECT.COMPOSITION
    ),
    RegionLoweringRegistration(
        "assume_aligned", AssumeAlignedLowerer, _EFFECT.COMPOSITION
    ),
    RegionLoweringRegistration("loop", LoopLowerer, _EFFECT.LOOP),
    RegionLoweringRegistration("switch", SwitchLowerer, _EFFECT.CONTROL),
    RegionLoweringRegistration(
        "type", lambda: QueryRegionLowerer("type"), _EFFECT.NEUTRAL
    ),
    RegionLoweringRegistration(
        "value", lambda: QueryRegionLowerer("value"), _EFFECT.NEUTRAL
    ),
    RegionLoweringRegistration(
        "complete", CompleteLowerer, _EFFECT.DIRECT_RETURN
    ),
)

_REGISTRATION_BY_KEYWORD = MappingProxyType(
    {
        registration.keyword: registration
        for registration in REGION_LOWERING_REGISTRATIONS
    }
)
IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS = frozenset(_REGISTRATION_BY_KEYWORD)

DEFAULT_REGION_LOWERERS: tuple[RegionLowerer, ...] = tuple(
    registration.factory()
    for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS
    if (registration := _REGISTRATION_BY_KEYWORD.get(descriptor.keyword)) is not None
)


def region_implementation_effect(
    keyword: str,
) -> RegionImplementationEffect | None:
    registration = _REGISTRATION_BY_KEYWORD.get(keyword)
    return None if registration is None else registration.implementation_effect


__all__ = (
    "DEFAULT_REGION_LOWERERS",
    "IMPLEMENTATION_STATE_CLASSIFIED_KEYWORDS",
    "REGION_LOWERING_REGISTRATIONS",
    "RegionLoweringRegistration",
    "region_implementation_effect",
)
