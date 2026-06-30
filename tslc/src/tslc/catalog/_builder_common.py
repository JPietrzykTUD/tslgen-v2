"""Shared parse-tree accessors for catalog promotion."""

from __future__ import annotations

from tslc.diagnostics import SourceSpan
from tslc.syntax.ast import (
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
)


def _source_span(source: ParsedTslSourceSpan | None) -> SourceSpan | None:
    if source is None:
        return None
    return SourceSpan(
        path=source.path,
        line=source.line,
        column=source.column,
        end_line=source.end_line,
        end_column=source.end_column,
    )



def _opt_int(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None



def _children(field: ParsedTslField | None) -> tuple[ParsedTslField, ...]:
    """Child fields, whether the source used an indented block or an inline ``{}`` map."""

    if field is None:
        return ()
    if field.children:
        return field.children
    if isinstance(field.value, ParsedTslMapValue):
        return field.value.entries
    return ()



def _child(field: ParsedTslField | None, key: str) -> ParsedTslField | None:
    for child in _children(field):
        if child.key.text == key:
            return child
    return None



def _entry(field: ParsedTslField, key: str) -> ParsedTslField | None:
    return _child(field, key)



def _scalar_text(field: ParsedTslField | None) -> str | None:
    if field is None:
        return None
    if isinstance(field.value, ParsedTslScalarValue):
        return field.value.text
    return None



def _field_text(field: ParsedTslField | None) -> str | None:
    return _scalar_text(field)


def _bool_field(field: ParsedTslField | None) -> bool:
    return (_field_text(field) or "").lower() == "true"



def _list_text(field: ParsedTslField | None) -> tuple[str, ...]:
    if field is None or not isinstance(field.value, ParsedTslListValue):
        return ()
    return tuple(
        item.text for item in field.value.items if isinstance(item, ParsedTslScalarValue)
    )



def _list_text_set(field: ParsedTslField | None) -> frozenset[str]:
    return frozenset(_list_text(field))
