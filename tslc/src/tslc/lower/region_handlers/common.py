"""Shared helpers for TSIL region lowerers."""

from __future__ import annotations

from tslc.ir.segments import RawText, Region, Segment
from tslc.lower.context import LoweringSession, VectorValue


def _vector_spelling(value: VectorValue, context: LoweringSession) -> str | None:
    """The backend type spelling of a :class:`VectorValue` (`simd<base, ext>`)."""

    base = context.env.backend.types.scalar_spelling(value.base_tag)
    if base is None:
        return None
    if value.uses_sized_vector:
        # A concrete lane count when known; otherwise the sized vector's lane parameter
        # (e.g. a representation-change's `OutVec`).
        lanes = (
            value.lanes
            if value.lanes is not None
            else value.lane_parameter
        )
        return context.env.backend.types.sized_vector_spelling(base, lanes)
    return context.env.backend.types.vector_type_spelling(base, value.extension_isa)


def _split_arg_groups(segments: tuple[Segment, ...]) -> list[tuple[Segment, ...]]:
    """Split a body segment sequence into top-level comma-separated argument groups.

    Regions are atomic (their internal commas/brackets stay inside them); only
    depth-0 commas in raw text separate arguments.
    """

    groups: list[list[Segment]] = [[]]
    depth = 0
    for segment in segments:
        if isinstance(segment, Region):
            groups[-1].append(segment)
            continue
        text = segment.text
        start = 0
        for index, char in enumerate(text):
            if char in "(<[":
                depth += 1
            elif char in ")>]":
                depth -= 1
            elif char == "," and depth == 0:
                piece = text[start:index]
                if piece.strip():
                    groups[-1].append(RawText(piece))
                groups.append([])
                start = index + 1
        tail = text[start:]
        if tail.strip():
            groups[-1].append(RawText(tail))
    return [tuple(group) for group in groups]


def _segment_text(segments: tuple[Segment, ...]) -> str:
    """Reconstruct the source text of a segment group (for query delegation)."""

    return "".join(
        seg.full_text if isinstance(seg, Region) else seg.text for seg in segments
    ).strip()
