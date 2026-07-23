"""Typed conversion semantics for source primitive declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


class ConversionKind(StrEnum):
    BIT_PATTERN = "bit_pattern"
    NUMERIC = "numeric"


class LaneCountRelation(StrEnum):
    PRESERVE_LANE_COUNT = "preserve_lane_count"
    PRESERVE_REGISTER_WIDTH = "preserve_register_width"


CONVERSION_KIND_DESCRIPTIONS: Mapping[ConversionKind, str] = MappingProxyType(
    {
        ConversionKind.BIT_PATTERN: "Preserves bits while changing their interpreted type.",
        ConversionKind.NUMERIC: "Converts each lane's numeric value to the result type.",
    }
)
LANE_COUNT_RELATION_DESCRIPTIONS: Mapping[LaneCountRelation, str] = MappingProxyType(
    {
        LaneCountRelation.PRESERVE_LANE_COUNT: "Keeps the source and result lane counts equal.",
        LaneCountRelation.PRESERVE_REGISTER_WIDTH: (
            "Keeps the source and result register widths equal."
        ),
    }
)


@dataclass(frozen=True, slots=True)
class PrimitiveConversionContract:
    kind: ConversionKind
    lane_count: LaneCountRelation
    source: SourceSpan | None = None
    kind_source: SourceSpan | None = None
    lane_count_source: SourceSpan | None = None


def conversion_kind_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in ConversionKind))


def lane_count_relation_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in LaneCountRelation))


__all__ = (
    "CONVERSION_KIND_DESCRIPTIONS",
    "LANE_COUNT_RELATION_DESCRIPTIONS",
    "ConversionKind",
    "LaneCountRelation",
    "PrimitiveConversionContract",
    "conversion_kind_values",
    "lane_count_relation_values",
)
