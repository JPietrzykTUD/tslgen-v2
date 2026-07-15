"""Typed catalog/source index shared by inspection and language-server features."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from tslc.catalog.model import Catalog
from tslc.diagnostics import SourceSpan
from tslc.ir.region_syntax import parse_call_selector
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedImplementationSelectorEntry,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
    ParsedTslListValue,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
)

SymbolKind = Literal["primitive", "extension", "type-group", "region"]


@dataclass(frozen=True, slots=True)
class IndexedOccurrence:
    kind: SymbolKind
    name: str
    span: SourceSpan
    definition: bool = False


@dataclass(frozen=True, slots=True)
class CatalogIndex:
    primitive_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    extension_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    type_group_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    primitive_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    extension_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    type_group_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    primitive_calls: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    primitive_callers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    occurrences_by_path: Mapping[Path, tuple[IndexedOccurrence, ...]] = field(default_factory=dict)
    hover_text: Mapping[tuple[SymbolKind, str], str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "primitive_definitions",
            "extension_definitions",
            "type_group_definitions",
            "primitive_references",
            "extension_references",
            "type_group_references",
            "primitive_calls",
            "primitive_callers",
            "occurrences_by_path",
            "hover_text",
        ):
            values = getattr(self, name)
            object.__setattr__(self, name, MappingProxyType(dict(values)))

    def occurrence_at(self, path: Path, line: int, column: int) -> IndexedOccurrence | None:
        candidates = tuple(
            item
            for item in self.occurrences_by_path.get(path.resolve(), ())
            if _contains(item.span, line, column)
        )
        return min(candidates, key=lambda item: _span_size(item.span), default=None)

    def definitions(self, occurrence: IndexedOccurrence) -> tuple[SourceSpan, ...]:
        return _definitions(self, occurrence.kind).get(occurrence.name, ())

    def references(
        self, occurrence: IndexedOccurrence, *, include_declaration: bool = True
    ) -> tuple[SourceSpan, ...]:
        referenced = _references(self, occurrence.kind).get(occurrence.name, ())
        declared = self.definitions(occurrence) if include_declaration else ()
        return _sorted_spans((*declared, *referenced))

    def hover(self, occurrence: IndexedOccurrence) -> str | None:
        return self.hover_text.get((occurrence.kind, occurrence.name))


@dataclass(frozen=True, slots=True)
class _DocumentIndex:
    definitions: Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]
    references: Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]
    occurrences: tuple[IndexedOccurrence, ...]
    primitive_calls: tuple[tuple[str, str], ...]


class CatalogIndexCache:
    """Reuse source-index fragments for unchanged parsed document objects."""

    def __init__(self) -> None:
        self._documents: dict[Path, tuple[ParsedOuterTslDocument, _DocumentIndex]] = {}
        self._last_reindexed: tuple[Path, ...] = ()

    @property
    def last_reindexed(self) -> tuple[Path, ...]:
        return self._last_reindexed

    def fragments(
        self, documents: tuple[ParsedOuterTslDocument, ...]
    ) -> tuple[_DocumentIndex, ...]:
        current = {document.path.resolve() for document in documents}
        for path in tuple(self._documents):
            if path not in current:
                del self._documents[path]
        reindexed: list[Path] = []
        values: list[_DocumentIndex] = []
        for document in sorted(documents, key=lambda item: item.path.as_posix()):
            path = document.path.resolve()
            cached = self._documents.get(path)
            if cached is None or cached[0] is not document:
                fragment = _build_document_index(document)
                self._documents[path] = (document, fragment)
                reindexed.append(path)
            else:
                fragment = cached[1]
            values.append(fragment)
        self._last_reindexed = tuple(reindexed)
        return tuple(values)


def build_catalog_index(
    catalog: Catalog,
    parsed: OuterTslParseResult,
    *,
    cache: CatalogIndexCache | None = None,
) -> CatalogIndex:
    definitions: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
    }
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
    }
    occurrences: list[IndexedOccurrence] = []
    primitive_calls: set[tuple[str, str]] = set()

    fragments = (
        cache.fragments(parsed.documents)
        if cache is not None
        else tuple(_build_document_index(document) for document in parsed.documents)
    )
    for fragment in fragments:
        for kind, names in fragment.definitions.items():
            for name, spans in names.items():
                definitions[kind].setdefault(name, []).extend(spans)
        for kind, names in fragment.references.items():
            for name, spans in names.items():
                references[kind].setdefault(name, []).extend(spans)
        occurrences.extend(fragment.occurrences)
        primitive_calls.update(fragment.primitive_calls)

    calls: dict[str, set[str]] = {}
    callers: dict[str, set[str]] = {}
    for caller, callee in sorted(primitive_calls):
        calls.setdefault(caller, set()).add(callee)
        callers.setdefault(callee, set()).add(caller)

    by_path: dict[Path, list[IndexedOccurrence]] = {}
    for occurrence in occurrences:
        by_path.setdefault(occurrence.span.path.resolve(), []).append(occurrence)
    return CatalogIndex(
        primitive_definitions=_freeze_spans(definitions["primitive"]),
        extension_definitions=_freeze_spans(definitions["extension"]),
        type_group_definitions=_freeze_spans(definitions["type-group"]),
        primitive_references=_freeze_spans(references["primitive"]),
        extension_references=_freeze_spans(references["extension"]),
        type_group_references=_freeze_spans(references["type-group"]),
        primitive_calls={
            name: tuple(sorted(values)) for name, values in sorted(calls.items())
        },
        primitive_callers={
            name: tuple(sorted(values)) for name, values in sorted(callers.items())
        },
        occurrences_by_path={
            path: tuple(sorted(items, key=_occurrence_key))
            for path, items in sorted(by_path.items(), key=lambda item: item[0].as_posix())
        },
        hover_text=_hover_text(catalog),
    )


def _build_document_index(document: ParsedOuterTslDocument) -> _DocumentIndex:
    definitions: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
    }
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
    }
    occurrences: list[IndexedOccurrence] = []
    primitive_calls: set[tuple[str, str]] = set()
    _index_document(
        document, definitions, references, occurrences, primitive_calls
    )
    return _DocumentIndex(
        definitions={
            kind: _freeze_spans(names) for kind, names in definitions.items()
        },
        references={
            kind: _freeze_spans(names) for kind, names in references.items()
        },
        occurrences=tuple(sorted(occurrences, key=_occurrence_key)),
        primitive_calls=tuple(sorted(primitive_calls)),
    )


def _index_document(
    document: ParsedOuterTslDocument,
    definitions: dict[SymbolKind, dict[str, list[SourceSpan]]],
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
    primitive_calls: set[tuple[str, str]],
) -> None:
    for primitive in document.primitives:
        span = _name_in_source(primitive.header_source, primitive.name)
        _record(definitions, occurrences, "primitive", primitive.name, span, True)
        _index_implementation_selectors(primitive, references, occurrences)
        for envelope in primitive.body_envelopes:
            source = _source_span(envelope.payload_source)
            for region in _regions(scan(envelope.payload_text, source=source)):
                if region.source is not None:
                    keyword_span = _subspan(
                        region.source,
                        region.full_text,
                        0,
                        len(region.keyword),
                    )
                    occurrences.append(
                        IndexedOccurrence("region", region.keyword, keyword_span, False)
                    )
                if region.keyword != "call":
                    continue
                call = parse_call_selector(region.selector_text)
                if call is None:
                    continue
                name = primitive.name if call.primitive_ref == "@self" else call.primitive_ref
                primitive_calls.add((primitive.name, name))
                reference_span = _region_selector_name_span(region, call.primitive_ref)
                if reference_span is not None:
                    _record(references, occurrences, "primitive", name, reference_span, False)

    for block in document.blocks:
        if block.kind == "extension" and block.name:
            span = _name_in_source(block.source, block.name)
            _record(definitions, occurrences, "extension", block.name, span, True)
            for field in block.fields:
                if field.key.text == "inherits" and isinstance(field.value, ParsedTslScalarValue):
                    _record_scalar_reference(
                        field.value, references, occurrences, "extension"
                    )
                elif field.key.text == "supersedes" and isinstance(field.value, ParsedTslListValue):
                    for item in field.value.items:
                        if isinstance(item, ParsedTslScalarValue):
                            _record_scalar_reference(
                                item, references, occurrences, "extension"
                            )
        elif block.kind == "types":
            for field in block.fields:
                span = _source_span(field.key.source)
                _record(
                    definitions,
                    occurrences,
                    "type-group",
                    field.key.text,
                    span,
                    True,
                )


def _index_implementation_selectors(
    primitive: ParsedPrimitiveDeclaration,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
) -> None:
    def visit(entry: ParsedImplementationSelectorEntry, depth: int) -> None:
        name = entry.selector.text
        if depth == 0:
            _record(
                references,
                occurrences,
                "extension",
                name,
                _source_span(entry.selector.source),
                False,
            )
        elif depth == 1:
            _record(
                references,
                occurrences,
                "type-group",
                name,
                _source_span(entry.selector.source),
                False,
            )
        for child in entry.children:
            visit(child, depth + 1)

    for entry in primitive.impl_entries:
        visit(entry, 0)


def _record_scalar_reference(
    value: ParsedTslScalarValue,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
    kind: SymbolKind,
) -> None:
    source = value.payload_source or value.source
    _record(references, occurrences, kind, value.text, _source_span(source), False)


def _record(
    values: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
    kind: SymbolKind,
    name: str,
    span: SourceSpan,
    definition: bool,
) -> None:
    values[kind].setdefault(name, []).append(span)
    occurrences.append(IndexedOccurrence(kind, name, span, definition))


def _regions(segments: Iterable[Segment]) -> Iterable[Region]:
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        yield segment
        yield from _regions(segment.body)
        if segment.block is not None:
            yield from _regions(segment.block)
        if segment.else_block is not None:
            yield from _regions(segment.else_block)
        if segment.arms is not None:
            for _, body in segment.arms:
                yield from _regions(body)


def _region_selector_name_span(region: Region, name: str) -> SourceSpan | None:
    if region.source is None:
        return None
    selector_offset = region.full_text.find(region.selector_text)
    name_offset = region.selector_text.find(name)
    if selector_offset < 0 or name_offset < 0:
        return region.source
    start = selector_offset + name_offset
    return _subspan(region.source, region.full_text, start, start + len(name))


def _name_in_source(source: ParsedTslSourceSpan, name: str) -> SourceSpan:
    offset = source.text.find(name)
    if offset < 0:
        return _source_span(source)
    return _subspan(_source_span(source), source.text, offset, offset + len(name))


def _subspan(source: SourceSpan, text: str, start: int, end: int) -> SourceSpan:
    start_line, start_column = _offset_position(source, text, start)
    end_line, end_column = _offset_position(source, text, end)
    return SourceSpan(source.path, start_line, start_column, end_line, end_column)


def _offset_position(source: SourceSpan, text: str, offset: int) -> tuple[int, int]:
    before = text[:offset]
    line_offset = before.count("\n")
    if line_offset == 0:
        return source.line, source.column + offset
    return source.line + line_offset, len(before.rsplit("\n", 1)[-1]) + 1


def _source_span(source: ParsedTslSourceSpan) -> SourceSpan:
    return SourceSpan(
        source.path.resolve(),
        source.line,
        source.column,
        source.end_line,
        source.end_column,
    )


def _hover_text(catalog: Catalog) -> dict[tuple[SymbolKind, str], str]:
    hover: dict[tuple[SymbolKind, str], str] = {}
    for name in sorted({primitive.name for primitive in catalog.primitives}):
        variants = catalog.primitives_named(name, unmasked=False)
        signatures = sorted({primitive.signature for primitive in variants})
        brief = next((primitive.brief_description for primitive in variants if primitive.brief_description), None)
        text = f"primitive {name}: {', '.join(signatures)}"
        hover[("primitive", name)] = f"{text}\n\n{brief}" if brief else text
    for name, extension in sorted(catalog.extensions.items()):
        parts = [f"extension {name}", f"family: {extension.family}"]
        if extension.inherits:
            parts.append(f"inherits: {extension.inherits}")
        if extension.vector_bits:
            parts.append(f"width: {extension.vector_bits} bits")
        hover[("extension", name)] = "\n\n".join(parts)
    for name, members in sorted(catalog.type_groups.items()):
        hover[("type-group", name)] = f"type group {name}: {', '.join(members)}"
    for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS:
        details = [f"TSIL region {descriptor.keyword}", f"shape: {descriptor.body_shape}"]
        if descriptor.shell_validator:
            details.append(f"selector: {descriptor.shell_validator}")
        hover[("region", descriptor.keyword)] = "\n\n".join(details)
    return hover


def _definitions(index: CatalogIndex, kind: SymbolKind) -> Mapping[str, tuple[SourceSpan, ...]]:
    if kind == "primitive":
        return index.primitive_definitions
    if kind == "extension":
        return index.extension_definitions
    if kind == "type-group":
        return index.type_group_definitions
    return {}


def _references(index: CatalogIndex, kind: SymbolKind) -> Mapping[str, tuple[SourceSpan, ...]]:
    if kind == "primitive":
        return index.primitive_references
    if kind == "extension":
        return index.extension_references
    if kind == "type-group":
        return index.type_group_references
    return {}


def _freeze_spans(values: dict[str, list[SourceSpan]]) -> dict[str, tuple[SourceSpan, ...]]:
    return {name: _sorted_spans(spans) for name, spans in sorted(values.items())}


def _sorted_spans(spans: Iterable[SourceSpan]) -> tuple[SourceSpan, ...]:
    return tuple(sorted(set(spans), key=_span_key))


def _span_key(span: SourceSpan) -> tuple[str, int, int, int, int]:
    return (span.path.as_posix(), span.line, span.column, span.end_line, span.end_column)


def _occurrence_key(item: IndexedOccurrence) -> tuple[int, int, int, int, str, str]:
    span = item.span
    return (span.line, span.column, span.end_line, span.end_column, item.kind, item.name)


def _contains(span: SourceSpan, line: int, column: int) -> bool:
    return (line, column) >= (span.line, span.column) and (line, column) < (
        span.end_line,
        span.end_column,
    )


def _span_size(span: SourceSpan) -> tuple[int, int]:
    return (span.end_line - span.line, span.end_column - span.column)


__all__ = (
    "CatalogIndex",
    "CatalogIndexCache",
    "IndexedOccurrence",
    "SymbolKind",
    "build_catalog_index",
)
