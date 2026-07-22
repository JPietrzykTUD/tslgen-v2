"""Typed object-representation facts used by value reinterpretation lowering."""

from __future__ import annotations

from tslc.catalog.model import Extension
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.lane_count import LaneCount
from tslc.lower._query_model import ObjectSize


def register_object_size(
    base_tag: str,
    extension: Extension,
    *,
    uses_sized_vector: bool,
    lane_count: LaneCount | None,
) -> ObjectSize | None:
    """Return a comparable size fact for one selected vector register."""

    element_bits = scalar_bit_width(base_tag)
    if element_bits is None:
        return None
    if uses_sized_vector:
        if lane_count is None:
            return None
        if lane_count.value is not None:
            return ObjectSize.fixed(element_bits * lane_count.value)
        if lane_count.is_scaled or lane_count.symbol is None:
            return None
        return ObjectSize.sized(element_bits, lane_count.symbol)
    if extension.vector_bits_kind == "fixed" and extension.vector_bits > 0:
        return ObjectSize.fixed(extension.vector_bits)
    if extension.vector_bits == 0:
        return ObjectSize.fixed(element_bits)
    return None


__all__ = ["register_object_size"]
