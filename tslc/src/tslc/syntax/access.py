"""Parse-tree shape accessors shared by catalog promotion and validation.

A field's children can be spelled as an indented block (``field.children``) or
as an inline ``{}`` map (``field.value`` entries). These helpers own that
equivalence — plus scalar/list text extraction and span conversion — so every
parsed-TSL consumer reads the tree through one implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

from tslc.diagnostics import SourceSpan
from tslc.syntax.ast import (
    ParsedTslAttribute,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
)


def children(field: ParsedTslField | None) -> tuple[ParsedTslField, ...]:
    """Child fields, whether the source used an indented block or an inline ``{}`` map."""

    if field is None:
        return ()
    if field.children:
        return field.children
    if isinstance(field.value, ParsedTslMapValue):
        return field.value.entries
    return ()


def child(field: ParsedTslField | None, key: str) -> ParsedTslField | None:
    for candidate in children(field):
        if candidate.key.text == key:
            return candidate
    return None


def child_from_sequence(
    fields: Sequence[ParsedTslField],
    key: str,
) -> ParsedTslField | None:
    for field in fields:
        if field.key.text == key:
            return field
    return None


def field_text(field: ParsedTslField | None) -> str | None:
    if field is not None and isinstance(field.value, ParsedTslScalarValue):
        return field.value.text
    return None


def list_text(field: ParsedTslField | None) -> tuple[str, ...]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return ()
    return tuple(
        item.text for item in field.value.items if isinstance(item, ParsedTslScalarValue)
    )


def attribute_scalar_text(attribute: ParsedTslAttribute) -> str | None:
    return attribute.value.text if isinstance(attribute.value, ParsedTslScalarValue) else None


def source_span(source: ParsedTslSourceSpan | None) -> SourceSpan | None:
    if source is None:
        return None
    return SourceSpan(
        path=source.path,
        line=source.line,
        column=source.column,
        end_line=source.end_line,
        end_column=source.end_column,
    )
