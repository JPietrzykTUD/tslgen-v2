"""Shared TSIL region descriptor registry.

This module owns lexical facts about TSIL keyword regions. It deliberately does
not import lowering or validation code: scanner, catalog validation, and lowering
registries consume these descriptors from their own layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

RegionBodyShape = Literal["call", "if_block", "loop_block", "switch_block"]


@dataclass(frozen=True, slots=True)
class TsilRegionDescriptor:
    keyword: str
    body_shape: RegionBodyShape = "call"
    shell_validator: str | None = None


DEFAULT_TSIL_REGION_DESCRIPTORS: tuple[TsilRegionDescriptor, ...] = (
    TsilRegionDescriptor("intrin", shell_validator="intrin_selector"),
    TsilRegionDescriptor("op"),
    TsilRegionDescriptor("var"),
    TsilRegionDescriptor("let", shell_validator="let_type"),
    TsilRegionDescriptor("mask"),
    TsilRegionDescriptor("mem"),
    TsilRegionDescriptor("pack"),
    TsilRegionDescriptor("lanes"),
    TsilRegionDescriptor("io"),
    TsilRegionDescriptor("cast"),
    TsilRegionDescriptor("call", shell_validator="call_selector"),
    TsilRegionDescriptor("if", body_shape="if_block"),
    TsilRegionDescriptor("assume_aligned"),
    TsilRegionDescriptor("loop", body_shape="loop_block"),
    TsilRegionDescriptor("switch", body_shape="switch_block"),
    TsilRegionDescriptor("type"),
    TsilRegionDescriptor("value"),
    TsilRegionDescriptor("complete"),
)

TSIL_REGION_BY_KEYWORD = MappingProxyType(
    {descriptor.keyword: descriptor for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS}
)
TSIL_REGION_KEYWORDS: frozenset[str] = frozenset(TSIL_REGION_BY_KEYWORD)


def region_body_shape(keyword: str) -> RegionBodyShape:
    descriptor = TSIL_REGION_BY_KEYWORD.get(keyword)
    return descriptor.body_shape if descriptor is not None else "call"


def region_shell_validator(keyword: str) -> str | None:
    descriptor = TSIL_REGION_BY_KEYWORD.get(keyword)
    return descriptor.shell_validator if descriptor is not None else None


__all__ = [
    "DEFAULT_TSIL_REGION_DESCRIPTORS",
    "RegionBodyShape",
    "TSIL_REGION_BY_KEYWORD",
    "TSIL_REGION_KEYWORDS",
    "TsilRegionDescriptor",
    "region_body_shape",
    "region_shell_validator",
]
