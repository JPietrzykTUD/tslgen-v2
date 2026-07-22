"""Promotion helpers for source-owned semantic-overload declarations."""

from __future__ import annotations

from tslc.catalog.overloads import (
    OverloadAxisSpec,
    OverloadRegistry,
    OverloadValueSpec,
)
from tslc.syntax.access import child, children, list_text, source_span
from tslc.syntax.ast import ParsedTslField


def _build_overload_registry(fields: list[ParsedTslField]) -> OverloadRegistry:
    axes: dict[str, OverloadAxisSpec] = {}
    for field in fields:
        for axis_field in children(field):
            values: dict[str, OverloadValueSpec] = {}
            for value_field in children(child(axis_field, "values")):
                values.setdefault(
                    value_field.key.text,
                    OverloadValueSpec(
                        name=value_field.key.text,
                        operand_kinds=tuple(
                            sorted(set(list_text(child(value_field, "operand_kinds"))))
                        ),
                        source=source_span(value_field.source),
                    ),
                )
            axes.setdefault(
                axis_field.key.text,
                OverloadAxisSpec(
                    name=axis_field.key.text,
                    values=values,
                    source=source_span(axis_field.source),
                ),
            )
    return OverloadRegistry(axes)


__all__ = ("_build_overload_registry",)
