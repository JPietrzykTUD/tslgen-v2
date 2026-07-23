"""Typed shift semantics for source primitive declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


class ShiftCountRule(StrEnum):
    UNSIGNED_BIT_PATTERN_MODULO_LANE_WIDTH = (
        "unsigned_bit_pattern_modulo_lane_width"
    )


class ShiftLaneRule(StrEnum):
    UNSIGNED_BIT_PATTERN_LEFT = "unsigned_bit_pattern_left"
    SIGNED_ARITHMETIC_UNSIGNED_LOGICAL_RIGHT = (
        "signed_arithmetic_unsigned_logical_right"
    )


SHIFT_COUNT_RULE_DESCRIPTIONS: Mapping[ShiftCountRule, str] = MappingProxyType(
    {
        ShiftCountRule.UNSIGNED_BIT_PATTERN_MODULO_LANE_WIDTH: (
            "Interprets each count as an unsigned bit pattern and reduces it "
            "modulo the shifted lane width."
        ),
    }
)
SHIFT_LANE_RULE_DESCRIPTIONS: Mapping[ShiftLaneRule, str] = MappingProxyType(
    {
        ShiftLaneRule.UNSIGNED_BIT_PATTERN_LEFT: (
            "Shifts the lane bit pattern left and discards bits beyond the lane width."
        ),
        ShiftLaneRule.SIGNED_ARITHMETIC_UNSIGNED_LOGICAL_RIGHT: (
            "Shifts signed lanes arithmetically and unsigned lanes logically "
            "to the right."
        ),
    }
)


@dataclass(frozen=True, slots=True)
class PrimitiveShiftContract:
    count_rule: ShiftCountRule
    lane_rule: ShiftLaneRule
    scalar_count_types: tuple[str, ...]
    source: SourceSpan | None = None
    count_rule_source: SourceSpan | None = None
    lane_rule_source: SourceSpan | None = None
    scalar_count_types_source: SourceSpan | None = None


def shift_count_rule_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in ShiftCountRule))


def shift_lane_rule_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in ShiftLaneRule))


__all__ = (
    "SHIFT_COUNT_RULE_DESCRIPTIONS",
    "SHIFT_LANE_RULE_DESCRIPTIONS",
    "PrimitiveShiftContract",
    "ShiftCountRule",
    "ShiftLaneRule",
    "shift_count_rule_values",
    "shift_lane_rule_values",
)
