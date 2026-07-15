"""Shared helpers for TSIL region lowerers."""

from __future__ import annotations

from tslc.lower.context import (
    LoweringSession,
    SimdTypeParameterValue,
    VectorSpellingPolicy,
    VectorValue,
)
from tslc.lower.queries import QueryEvaluator, QueryValue, TextValue, TypeValue
from tslc.target_text import RenderField, literal_text


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


def _type_value_spelling(
    value: QueryValue, context: LoweringSession
) -> RenderField | None:
    """Render an already-evaluated value in a TSIL-owned type position."""

    if isinstance(value, TextValue):
        return value.text
    if isinstance(value, TypeValue):
        return context.env.backend.types.scalar_spelling(value.type_tag)
    if isinstance(value, VectorValue):
        return _vector_spelling(value, context)
    if isinstance(value, SimdTypeParameterValue):
        return literal_text(value.name)
    return None


def _resolve_type_expression(
    text: str,
    context: LoweringSession,
    evaluator: QueryEvaluator,
    *,
    fallback: RenderField | None = None,
) -> tuple[QueryValue, RenderField] | None:
    """Evaluate one contextually typed TSIL argument and return value plus spelling.

    ``fallback`` preserves explicitly structured target-type expressions such as
    ``array_type<type(base::in), value(vector::length)>``. It is used only when the
    argument is not a query expression; a query that evaluates to a non-type value
    remains invalid.
    """

    value = evaluator.evaluate(text, context)
    if value is None:
        return None if fallback is None else (TextValue(fallback), fallback)
    spelling = _type_value_spelling(value, context)
    return None if spelling is None else (value, spelling)
