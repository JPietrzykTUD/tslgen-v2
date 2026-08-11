"""Semantic occurrence recording and precise source-span construction."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from tslc.catalog_index_model import IndexedOccurrence, SymbolKind, sorted_spans
from tslc.diagnostics import SourceSpan
from tslc.ir.segments import Region, Segment
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
)

ScopedSymbolKind = Literal[
    "target-axis",
    "overload-value",
    "arithmetic-operand",
    "semantic-operand",
]


def record_scoped(
    values: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
    kind: ScopedSymbolKind,
    scope: str,
    name: str,
    span: SourceSpan,
    definition: bool,
) -> None:
    values.setdefault((scope, name), []).append(span)
    occurrences.append(IndexedOccurrence(kind, name, span, definition, scope))


def record_scalar_reference(
    value: ParsedTslScalarValue,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
    kind: SymbolKind,
) -> None:
    source = value.payload_source or value.source
    record(references, occurrences, kind, value.text, source_span(source), False)


def record(
    values: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
    kind: SymbolKind,
    name: str,
    span: SourceSpan,
    definition: bool,
) -> None:
    values[kind].setdefault(name, []).append(span)
    occurrences.append(IndexedOccurrence(kind, name, span, definition))


def regions(segments: Iterable[Segment]) -> Iterable[Region]:
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        yield segment
        yield from regions(segment.body)
        if segment.block is not None:
            yield from regions(segment.block)
        if segment.else_block is not None:
            yield from regions(segment.else_block)
        if segment.arms is not None:
            for _, body in segment.arms:
                yield from regions(body)


def region_selector_name_span(region: Region, name: str) -> SourceSpan | None:
    if region.source is None:
        return None
    selector_offset = region.full_text.find(region.selector_text)
    name_offset = region.selector_text.find(name)
    if selector_offset < 0 or name_offset < 0:
        return region.source
    start = selector_offset + name_offset
    return subspan(region.source, region.full_text, start, start + len(name))


def name_in_source(source: ParsedTslSourceSpan, name: str) -> SourceSpan:
    offset = source.text.find(name)
    if offset < 0:
        return source_span(source)
    return subspan(source_span(source), source.text, offset, offset + len(name))


def parameter_spans(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[tuple[str, SourceSpan], ...]:
    text = primitive.header_source.text
    name_offset = text.find(primitive.name)
    open_paren = text.find("(", max(name_offset, 0) + len(primitive.name))
    close_paren = text.find(")", open_paren + 1)
    if open_paren < 0 or close_paren < 0:
        return ()
    cursor = open_paren + 1
    source = source_span(primitive.header_source)
    spans: list[tuple[str, SourceSpan]] = []
    for parameter in primitive.parameters:
        offset = text.find(parameter, cursor, close_paren)
        if offset < 0:
            continue
        spans.append(
            (parameter, subspan(source, text, offset, offset + len(parameter)))
        )
        cursor = offset + len(parameter)
    return tuple(spans)


def subspan(source: SourceSpan, text: str, start: int, end: int) -> SourceSpan:
    start_line, start_column = _offset_position(source, text, start)
    end_line, end_column = _offset_position(source, text, end)
    return SourceSpan(source.path, start_line, start_column, end_line, end_column)


def _offset_position(
    source: SourceSpan, text: str, offset: int
) -> tuple[int, int]:
    before = text[:offset]
    line_offset = before.count("\n")
    if line_offset == 0:
        return source.line, source.column + offset
    return source.line + line_offset, len(before.rsplit("\n", 1)[-1]) + 1


def source_span(source: ParsedTslSourceSpan) -> SourceSpan:
    return SourceSpan(
        source.path.resolve(),
        source.line,
        source.column,
        source.end_line,
        source.end_column,
    )


def freeze_spans(
    values: dict[str, list[SourceSpan]],
) -> dict[str, tuple[SourceSpan, ...]]:
    return {name: sorted_spans(spans) for name, spans in sorted(values.items())}


def freeze_scoped_spans(
    values: dict[tuple[str, str], list[SourceSpan]],
) -> dict[tuple[str, str], tuple[SourceSpan, ...]]:
    return {key: sorted_spans(spans) for key, spans in sorted(values.items())}


def occurrence_key(
    item: IndexedOccurrence,
) -> tuple[int, int, int, int, str, str]:
    span = item.span
    return (
        span.line,
        span.column,
        span.end_line,
        span.end_column,
        item.kind,
        item.name,
    )


__all__ = (
    "freeze_scoped_spans",
    "freeze_spans",
    "name_in_source",
    "occurrence_key",
    "parameter_spans",
    "record",
    "record_scalar_reference",
    "record_scoped",
    "region_selector_name_span",
    "regions",
    "source_span",
    "subspan",
)
