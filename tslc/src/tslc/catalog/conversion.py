"""Typed conversion semantics for source primitive declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.catalog.register_shapes import RegisterMultiplicity
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.diagnostics import SourceSpan


class ConversionKind(StrEnum):
    BIT_PATTERN = "bit_pattern"
    NUMERIC = "numeric"


class LaneCountRelation(StrEnum):
    PRESERVE_LANE_COUNT = "preserve_lane_count"
    PRESERVE_REGISTER_WIDTH = "preserve_register_width"


class NumericConversionMode(StrEnum):
    SCALAR_AS = "scalar_as"


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
NUMERIC_CONVERSION_MODE_DESCRIPTIONS: Mapping[NumericConversionMode, str] = (
    MappingProxyType(
        {
            NumericConversionMode.SCALAR_AS: (
                "Uses wrapping integer casts, ordinary integer/float rounding, and "
                "truncating saturating float-to-integer conversion with NaN mapped to zero."
            )
        }
    )
)


@dataclass(frozen=True, slots=True)
class PrimitiveConversionContract:
    kind: ConversionKind
    lane_count: LaneCountRelation
    numeric_mode: NumericConversionMode | None = None
    source: SourceSpan | None = None
    kind_source: SourceSpan | None = None
    lane_count_source: SourceSpan | None = None
    numeric_mode_source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class ConversionRegisterShape:
    """Register multiplicity required by one concrete conversion result."""

    source_type: str
    target_type: str
    target_multiplicity: RegisterMultiplicity


def conversion_register_shape(
    contract: PrimitiveConversionContract,
    source_type: str,
    target_type: str,
) -> ConversionRegisterShape | None:
    """Finalize the physical result shape for known scalar types.

    Width-preserving conversions stay at one register.  A lane-preserving
    conversion scales result capacity by ``target_bits / source_bits`` so the
    logical lane count remains unchanged.
    """

    source_bits = scalar_bit_width(source_type)
    target_bits = scalar_bit_width(target_type)
    if source_bits is None or target_bits is None:
        return None
    multiplicity = (
        RegisterMultiplicity()
        if contract.lane_count is LaneCountRelation.PRESERVE_REGISTER_WIDTH
        else RegisterMultiplicity(target_bits, source_bits)
    )
    return ConversionRegisterShape(
        source_type=source_type,
        target_type=target_type,
        target_multiplicity=multiplicity,
    )


def conversion_kind_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in ConversionKind))


def lane_count_relation_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in LaneCountRelation))


def numeric_conversion_mode_values() -> tuple[str, ...]:
    return tuple(sorted(value.value for value in NumericConversionMode))


__all__ = (
    "CONVERSION_KIND_DESCRIPTIONS",
    "LANE_COUNT_RELATION_DESCRIPTIONS",
    "NUMERIC_CONVERSION_MODE_DESCRIPTIONS",
    "ConversionKind",
    "ConversionRegisterShape",
    "LaneCountRelation",
    "NumericConversionMode",
    "PrimitiveConversionContract",
    "conversion_register_shape",
    "conversion_kind_values",
    "lane_count_relation_values",
    "numeric_conversion_mode_values",
)
