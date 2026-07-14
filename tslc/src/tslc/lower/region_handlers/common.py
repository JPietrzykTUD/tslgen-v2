"""Shared helpers for TSIL region lowerers."""

from __future__ import annotations

from tslc.lower.context import (
    LoweringSession,
    VectorSpellingPolicy,
    VectorValue,
)


def _vector_spelling(value: VectorValue, context: LoweringSession) -> str | None:
    """The backend type spelling of a :class:`VectorValue` (`simd<base, ext>`)."""

    base = context.env.backend.types.scalar_spelling(value.base_tag)
    if base is None:
        return None
    if value.spelling_policy is VectorSpellingPolicy.FIXED_FACADE:
        if value.lanes is None:
            return None
        return context.env.backend.types.fixed_vector_spelling(base, value.lanes)
    if value.uses_sized_vector:
        # A concrete lane count when known; otherwise the sized vector's lane parameter
        # (e.g. a representation-change's `OutVec`).
        lanes = (
            value.lanes
            if value.lanes is not None
            else (
                context.env.backend.types.render_lane_count(value.lane_parameter)
                if value.lane_parameter is not None
                else None
            )
        )
        if lanes is None:
            return None
        return context.env.backend.types.sized_vector_spelling(
            base, value.extension_isa, lanes
        )
    return context.env.backend.types.vector_type_spelling(base, value.extension_isa)
