"""Shared helpers for TSIL region lowerers."""

from __future__ import annotations

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
        return context.env.backend.types.sized_vector_spelling(
            base, value.extension_isa, lanes
        )
    return context.env.backend.types.vector_type_spelling(base, value.extension_isa)
