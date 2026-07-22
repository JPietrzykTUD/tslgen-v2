"""Typed catalog/source index shared by inspection and language-server features."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from tslc.catalog.model import Catalog
from tslc.catalog.selector_paths import classify_selector_path
from tslc.catalog_authoring_index import (
    DocumentSymbolKind,
    IndexedDocumentSymbol,
    IndexedSemanticToken,
    SemanticTokenKind,
    build_document_authoring_index,
    selector_items,
)
from tslc.diagnostics import SourceSpan
from tslc.ir.region_syntax import parse_call_selector
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment
from tslc.syntax.access import child, children
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

SymbolKind = Literal[
    "primitive",
    "extension",
    "type-group",
    "region",
    "target-axis",
    "overload-axis",
    "overload-value",
]
_TSIL_REGION_GUIDE = (
    "https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/tsil-keywords.md"
)


@dataclass(frozen=True, slots=True)
class IndexedOccurrence:
    kind: SymbolKind
    name: str
    span: SourceSpan
    definition: bool = False
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogIndex:
    primitive_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    extension_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    type_group_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    primitive_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    extension_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    type_group_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    target_axis_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(
        default_factory=dict
    )
    target_axis_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(
        default_factory=dict
    )
    overload_axis_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(
        default_factory=dict
    )
    overload_axis_references: Mapping[str, tuple[SourceSpan, ...]] = field(
        default_factory=dict
    )
    overload_value_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(
        default_factory=dict
    )
    overload_value_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(
        default_factory=dict
    )
    primitive_calls: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    primitive_callers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    occurrences_by_path: Mapping[Path, tuple[IndexedOccurrence, ...]] = field(default_factory=dict)
    document_symbols_by_path: Mapping[Path, tuple[IndexedDocumentSymbol, ...]] = field(
        default_factory=dict
    )
    semantic_tokens_by_path: Mapping[Path, tuple[IndexedSemanticToken, ...]] = field(
        default_factory=dict
    )
    hover_text: Mapping[tuple[SymbolKind, str], str] = field(default_factory=dict)
    overload_value_hover: Mapping[tuple[str, str], str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "primitive_definitions",
            "extension_definitions",
            "type_group_definitions",
            "primitive_references",
            "extension_references",
            "type_group_references",
            "target_axis_definitions",
            "target_axis_references",
            "overload_axis_definitions",
            "overload_axis_references",
            "overload_value_definitions",
            "overload_value_references",
            "primitive_calls",
            "primitive_callers",
            "occurrences_by_path",
            "document_symbols_by_path",
            "semantic_tokens_by_path",
            "hover_text",
            "overload_value_hover",
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
        if occurrence.kind == "overload-value":
            if occurrence.scope is None:
                return ()
            return self.overload_value_definitions.get(
                (occurrence.scope, occurrence.name), ()
            )
        if occurrence.kind == "target-axis":
            if occurrence.scope is None:
                return ()
            return self.target_axis_definitions.get(
                (occurrence.scope, occurrence.name), ()
            )
        return _definitions(self, occurrence.kind).get(occurrence.name, ())

    def references(
        self, occurrence: IndexedOccurrence, *, include_declaration: bool = True
    ) -> tuple[SourceSpan, ...]:
        if occurrence.kind == "target-axis":
            referenced = (
                ()
                if occurrence.scope is None
                else self.target_axis_references.get(
                    (occurrence.scope, occurrence.name), ()
                )
            )
        elif occurrence.kind == "overload-value":
            referenced = (
                ()
                if occurrence.scope is None
                else self.overload_value_references.get(
                    (occurrence.scope, occurrence.name), ()
                )
            )
        else:
            referenced = _references(self, occurrence.kind).get(occurrence.name, ())
        declared = self.definitions(occurrence) if include_declaration else ()
        return _sorted_spans((*declared, *referenced))

    def hover(self, occurrence: IndexedOccurrence) -> str | None:
        if occurrence.kind == "overload-value" and occurrence.scope is not None:
            return self.overload_value_hover.get((occurrence.scope, occurrence.name))
        return self.hover_text.get((occurrence.kind, occurrence.name))


@dataclass(frozen=True, slots=True)
class _DocumentIndex:
    definitions: Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]
    references: Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]
    target_axis_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    target_axis_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    overload_value_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    overload_value_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    occurrences: tuple[IndexedOccurrence, ...]
    primitive_calls: tuple[tuple[str, str], ...]
    symbols: tuple[IndexedDocumentSymbol, ...]
    semantic_tokens: tuple[IndexedSemanticToken, ...]


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
        "target-axis": {},
        "overload-axis": {},
        "overload-value": {},
    }
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
        "target-axis": {},
        "overload-axis": {},
        "overload-value": {},
    }
    target_axis_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    target_axis_references: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_references: dict[tuple[str, str], list[SourceSpan]] = {}
    occurrences: list[IndexedOccurrence] = []
    primitive_calls: set[tuple[str, str]] = set()
    symbols_by_path: dict[Path, tuple[IndexedDocumentSymbol, ...]] = {}
    semantic_tokens_by_path: dict[Path, tuple[IndexedSemanticToken, ...]] = {}

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
        for key, spans in fragment.target_axis_definitions.items():
            target_axis_definitions.setdefault(key, []).extend(spans)
        for key, spans in fragment.target_axis_references.items():
            target_axis_references.setdefault(key, []).extend(spans)
        for key, spans in fragment.overload_value_definitions.items():
            overload_value_definitions.setdefault(key, []).extend(spans)
        for key, spans in fragment.overload_value_references.items():
            overload_value_references.setdefault(key, []).extend(spans)
        occurrences.extend(fragment.occurrences)
        primitive_calls.update(fragment.primitive_calls)
        if fragment.symbols:
            path = fragment.symbols[0].span.path.resolve()
            symbols_by_path[path] = fragment.symbols
        if fragment.semantic_tokens:
            path = fragment.semantic_tokens[0].span.path.resolve()
            semantic_tokens_by_path[path] = fragment.semantic_tokens

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
        target_axis_definitions=_freeze_scoped_spans(target_axis_definitions),
        target_axis_references=_freeze_scoped_spans(target_axis_references),
        overload_axis_definitions=_freeze_spans(definitions["overload-axis"]),
        overload_axis_references=_freeze_spans(references["overload-axis"]),
        overload_value_definitions=_freeze_scoped_spans(overload_value_definitions),
        overload_value_references=_freeze_scoped_spans(overload_value_references),
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
        document_symbols_by_path=symbols_by_path,
        semantic_tokens_by_path=semantic_tokens_by_path,
        hover_text=_hover_text(catalog, definitions),
        overload_value_hover=_overload_value_hover(catalog),
    )


def _build_document_index(document: ParsedOuterTslDocument) -> _DocumentIndex:
    definitions: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
        "target-axis": {},
        "overload-axis": {},
        "overload-value": {},
    }
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
        "target-axis": {},
        "overload-axis": {},
        "overload-value": {},
    }
    target_axis_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    target_axis_references: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_references: dict[tuple[str, str], list[SourceSpan]] = {}
    occurrences: list[IndexedOccurrence] = []
    primitive_calls: set[tuple[str, str]] = set()
    _index_document(
        document,
        definitions,
        references,
        target_axis_definitions,
        target_axis_references,
        overload_value_definitions,
        overload_value_references,
        occurrences,
        primitive_calls,
    )
    authoring = build_document_authoring_index(document)
    return _DocumentIndex(
        definitions={
            kind: _freeze_spans(names) for kind, names in definitions.items()
        },
        references={
            kind: _freeze_spans(names) for kind, names in references.items()
        },
        target_axis_definitions=_freeze_scoped_spans(target_axis_definitions),
        target_axis_references=_freeze_scoped_spans(target_axis_references),
        overload_value_definitions=_freeze_scoped_spans(overload_value_definitions),
        overload_value_references=_freeze_scoped_spans(overload_value_references),
        occurrences=tuple(sorted(occurrences, key=_occurrence_key)),
        primitive_calls=tuple(sorted(primitive_calls)),
        symbols=authoring.symbols,
        semantic_tokens=authoring.semantic_tokens,
    )


def _index_document(
    document: ParsedOuterTslDocument,
    definitions: dict[SymbolKind, dict[str, list[SourceSpan]]],
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    target_axis_definitions: dict[tuple[str, str], list[SourceSpan]],
    target_axis_references: dict[tuple[str, str], list[SourceSpan]],
    overload_value_definitions: dict[tuple[str, str], list[SourceSpan]],
    overload_value_references: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
    primitive_calls: set[tuple[str, str]],
) -> None:
    for primitive in document.primitives:
        scope = _primitive_scope(primitive)
        result_target = _result_target(primitive)
        span = _name_in_source(primitive.header_source, primitive.name)
        _record(definitions, occurrences, "primitive", primitive.name, span, True)
        _index_primitive_overload(
            primitive,
            references,
            overload_value_references,
            occurrences,
        )
        if result_target is not None:
            _, target_name, target_span = result_target
            _record_scoped(
                target_axis_definitions,
                occurrences,
                "target-axis",
                scope,
                target_name,
                target_span,
                True,
            )
        _index_implementation_selectors(
            primitive,
            references,
            target_axis_references,
            occurrences,
            result_target=result_target,
            scope=scope,
        )
        for envelope in primitive.body_envelopes:
            source = _source_span(envelope.payload_source)
            for region in _regions(scan(envelope.payload_text, source=source)):
                _index_region(
                    primitive,
                    region,
                    references,
                    occurrences,
                    primitive_calls,
                )

    for block in document.blocks:
        if block.kind == "extension" and block.name:
            span = _name_in_source(block.source, block.name)
            _record(definitions, occurrences, "extension", block.name, span, True)
            for block_field in block.fields:
                if block_field.key.text == "inherits" and isinstance(
                    block_field.value, ParsedTslScalarValue
                ):
                    _record_scalar_reference(
                        block_field.value, references, occurrences, "extension"
                    )
                elif block_field.key.text == "supersedes" and isinstance(
                    block_field.value, ParsedTslListValue
                ):
                    for item in block_field.value.items:
                        if isinstance(item, ParsedTslScalarValue):
                            _record_scalar_reference(
                                item, references, occurrences, "extension"
                            )
        elif block.kind == "types":
            for block_field in block.fields:
                span = _source_span(block_field.key.source)
                _record(
                    definitions,
                    occurrences,
                    "type-group",
                    block_field.key.text,
                    span,
                    True,
                )

    for declaration in document.fields:
        if declaration.field.key.text != "overload_axes":
            continue
        for axis in children(declaration.field):
            _record(
                definitions,
                occurrences,
                "overload-axis",
                axis.key.text,
                _source_span(axis.key.source),
                True,
            )
            for value in children(child(axis, "values")):
                _record_scoped(
                    overload_value_definitions,
                    occurrences,
                    "overload-value",
                    axis.key.text,
                    value.key.text,
                    _source_span(value.key.source),
                    True,
                )


def _index_primitive_overload(
    primitive: ParsedPrimitiveDeclaration,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    overload_value_references: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
) -> None:
    for primitive_field in primitive.fields_by_name("overload"):
        axis_field = child(primitive_field.field, "axis")
        value_field = child(primitive_field.field, "value")
        if axis_field is None or not isinstance(axis_field.value, ParsedTslScalarValue):
            continue
        axis_value = axis_field.value
        _record_scalar_reference(
            axis_value,
            references,
            occurrences,
            "overload-axis",
        )
        if value_field is None or not isinstance(value_field.value, ParsedTslScalarValue):
            continue
        value = value_field.value
        _record_scoped(
            overload_value_references,
            occurrences,
            "overload-value",
            axis_value.text,
            value.text,
            _source_span(value.payload_source or value.source),
            False,
        )


def _index_implementation_selectors(
    primitive: ParsedPrimitiveDeclaration,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    target_axis_references: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
    *,
    result_target: tuple[str, str, SourceSpan] | None,
    scope: str,
) -> None:
    target_name = result_target[1] if result_target is not None else None

    def visit(
        entry: ParsedImplementationSelectorEntry, prefix: tuple[str, ...]
    ) -> None:
        path = (*prefix, entry.selector.text)
        level = classify_selector_path(path, target_name)[-1]
        items = selector_items(entry.selector)
        if level.kind == "extensions":
            for name, span in items:
                _record(references, occurrences, "extension", name, span, False)
        elif level.kind == "source-type-group":
            for name, span in items:
                _record(references, occurrences, "type-group", name, span, False)
        elif level.kind == "target-axis":
            for name, span in items:
                _record_scoped(
                    target_axis_references,
                    occurrences,
                    "target-axis",
                    scope,
                    name,
                    span,
                    False,
                )
        elif level.kind == "target-reference":
            for name, span in items:
                _record(references, occurrences, "type-group", name, span, False)
        # A `where` constraint level references no catalog symbol; it is never
        # indexed as a type group.
        for child in entry.children:
            visit(child, path)

    for entry in primitive.impl_entries:
        visit(entry, ())


def _index_region(
    primitive: ParsedPrimitiveDeclaration,
    region: Region,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    occurrences: list[IndexedOccurrence],
    primitive_calls: set[tuple[str, str]],
) -> None:
    if region.source is None:
        return
    keyword_span = _subspan(
        region.source,
        region.full_text,
        0,
        len(region.keyword),
    )
    occurrences.append(IndexedOccurrence("region", region.keyword, keyword_span, False))
    if region.keyword != "call":
        return
    call = parse_call_selector(region.selector_text)
    if call is None:
        return
    name = primitive.name if call.primitive_ref == "@self" else call.primitive_ref
    primitive_calls.add((primitive.name, name))
    reference_span = _region_selector_name_span(region, call.primitive_ref)
    if reference_span is not None:
        _record(references, occurrences, "primitive", name, reference_span, False)


def _result_target(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[str, str, SourceSpan] | None:
    for primitive_field in primitive.fields_by_name("return_type"):
        for field in primitive_field.field.children:
            if not isinstance(field.value, ParsedTslScalarValue):
                continue
            source = field.value.payload_source or field.value.source
            return field.key.text, field.value.text, _source_span(source)
    return None


def _primitive_scope(primitive: ParsedPrimitiveDeclaration) -> str:
    source = primitive.header_source
    return f"{source.path.resolve().as_posix()}:{source.line}:{source.column}:{primitive.name}"


def _record_scoped(
    values: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
    kind: Literal["target-axis", "overload-value"],
    scope: str,
    name: str,
    span: SourceSpan,
    definition: bool,
) -> None:
    values.setdefault((scope, name), []).append(span)
    occurrences.append(IndexedOccurrence(kind, name, span, definition, scope))


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


def _hover_text(
    catalog: Catalog,
    definitions: Mapping[SymbolKind, Mapping[str, Iterable[SourceSpan]]],
) -> dict[tuple[SymbolKind, str], str]:
    hover: dict[tuple[SymbolKind, str], str] = {}
    for name in sorted({primitive.name for primitive in catalog.primitives}):
        variants = catalog.primitives_named(name, unmasked=False)
        declarations = {
            (
                primitive.signature,
                primitive.parameters,
                primitive.brief_description,
                primitive.header_source,
            )
            for primitive in variants
        }
        lines = [f"**Primitive** `{name}`", "", "**Declarations**", ""]
        for signature, parameters, brief, source in sorted(
            declarations,
            key=lambda item: (*_optional_span_key(item[3]), item[0], item[1]),
        ):
            declaration = f"prim<{signature}> {name}({', '.join(parameters)})"
            line = f"- `{declaration}`"
            if brief:
                line += f" — {brief}"
            if source is not None:
                line += f" ([{source.path.name}:{source.line}]({_source_uri(source)}))"
            lines.append(line)
        hover[("primitive", name)] = "\n".join(lines)
    for name, extension in sorted(catalog.extensions.items()):
        parts = [f"**Extension** `{name}`"]
        if extension.family:
            parts.append(f"**Family:** `{extension.family}`")
        if extension.inherits:
            parts.append(f"**Inherits:** `{extension.inherits}`")
        if extension.vector_bits:
            width = f"{extension.vector_bits} bits"
            if extension.vector_bits_kind:
                width += f" (`{extension.vector_bits_kind}`)"
            parts.append(f"**Width:** {width}")
        elif extension.vector_bits_kind in {"scalable", "sized"}:
            parts.append(f"**Width:** {extension.vector_bits_kind}")
        backends = tuple(
            sorted(
                backend
                for backend, supported in extension.backend_supported.items()
                if supported
            )
        )
        if backends:
            parts.append(f"**Supported backends:** {_inline_code(backends)}")
        target_features = tuple(sorted(extension.active_when.target_features))
        if target_features:
            parts.append(
                f"**Required target features:** {_inline_code(target_features)}"
            )
        compile_modes = tuple(sorted(extension.active_when.compile_modes))
        if compile_modes:
            parts.append(f"**Required compile modes:** {_inline_code(compile_modes)}")
        if extension.source is not None:
            parts.append(
                f"[Declaration: {extension.source.path.name}:{extension.source.line}]"
                f"({_source_uri(extension.source)})"
            )
        hover[("extension", name)] = "\n\n".join(parts)
    for name, members in sorted(catalog.type_groups.items()):
        parts = [f"**Type group** `{name}`", _inline_code(members)]
        declaration_links = _declaration_links(
            definitions["type-group"].get(name, ())
        )
        if declaration_links:
            parts.append(f"**Declared at:** {', '.join(declaration_links)}")
        hover[("type-group", name)] = "\n\n".join(parts)
    for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS:
        forms = "\n".join(f"- `{form}`" for form in descriptor.accepted_forms)
        guide = f"{_TSIL_REGION_GUIDE}#{descriptor.keyword}"
        hover[("region", descriptor.keyword)] = "\n\n".join(
            (
                f"**TSIL region** `{descriptor.keyword}`",
                descriptor.purpose,
                f"**Accepted forms**\n\n{forms}",
                f"[TSIL region guide]({guide})",
            )
        )
    for name, axis in catalog.overload_registry.axes.items():
        hover[("overload-axis", name)] = "\n\n".join(
            (
                f"**Overload axis** `{name}`",
                f"**Values:** {_inline_code(axis.values)}",
            )
        )
    return hover


def _overload_value_hover(catalog: Catalog) -> dict[tuple[str, str], str]:
    return {
        (axis_name, value_name): "\n\n".join(
            (
                f"**Overload value** `{axis_name}={value_name}`",
                f"**Accepted operand kinds:** {_inline_code(value.operand_kinds)}",
            )
        )
        for axis_name, axis in catalog.overload_registry.axes.items()
        for value_name, value in axis.values.items()
    }


def _optional_span_key(span: SourceSpan | None) -> tuple[str, int, int]:
    if span is None:
        return ("", 0, 0)
    return (span.path.as_posix(), span.line, span.column)


def _source_uri(span: SourceSpan) -> str:
    return f"{span.path.resolve().as_uri()}#L{span.line},{span.column}"


def _declaration_links(spans: Iterable[SourceSpan]) -> tuple[str, ...]:
    return tuple(
        f"[{span.path.name}:{span.line}]({_source_uri(span)})"
        for span in _sorted_spans(spans)
    )


def _inline_code(values: Iterable[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def _definitions(index: CatalogIndex, kind: SymbolKind) -> Mapping[str, tuple[SourceSpan, ...]]:
    if kind == "primitive":
        return index.primitive_definitions
    if kind == "extension":
        return index.extension_definitions
    if kind == "type-group":
        return index.type_group_definitions
    if kind == "overload-axis":
        return index.overload_axis_definitions
    return {}


def _references(index: CatalogIndex, kind: SymbolKind) -> Mapping[str, tuple[SourceSpan, ...]]:
    if kind == "primitive":
        return index.primitive_references
    if kind == "extension":
        return index.extension_references
    if kind == "type-group":
        return index.type_group_references
    if kind == "overload-axis":
        return index.overload_axis_references
    return {}


def _freeze_spans(values: dict[str, list[SourceSpan]]) -> dict[str, tuple[SourceSpan, ...]]:
    return {name: _sorted_spans(spans) for name, spans in sorted(values.items())}


def _freeze_scoped_spans(
    values: dict[tuple[str, str], list[SourceSpan]],
) -> dict[tuple[str, str], tuple[SourceSpan, ...]]:
    return {key: _sorted_spans(spans) for key, spans in sorted(values.items())}


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
    "DocumentSymbolKind",
    "IndexedDocumentSymbol",
    "IndexedOccurrence",
    "IndexedSemanticToken",
    "SemanticTokenKind",
    "SymbolKind",
    "build_catalog_index",
)
