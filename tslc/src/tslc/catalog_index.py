"""Typed catalog/source index shared by inspection and language-server features."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TypeVar

from tslc.catalog.arithmetic import (
    ARITHMETIC_GUARANTEE_SPECS,
    ARITHMETIC_OPERAND_ROLE_DESCRIPTIONS,
    ARITHMETIC_OPERATION_DESCRIPTIONS,
)
from tslc.catalog.conversion import (
    CONVERSION_KIND_DESCRIPTIONS,
    LANE_COUNT_RELATION_DESCRIPTIONS,
    NUMERIC_CONVERSION_MODE_DESCRIPTIONS,
)
from tslc.catalog.memory import (
    MEMORY_ACCESS_DESCRIPTIONS,
    MEMORY_ADDRESSING_DESCRIPTIONS,
)
from tslc.catalog.model import Catalog, Primitive, RESULT_DIM_VECTOR
from tslc.catalog.semantics import (
    OPERAND_ROLE_DESCRIPTIONS,
    PRIMITIVE_OPERATION_DESCRIPTIONS,
)
from tslc.catalog.shift import (
    SHIFT_COUNT_RULE_DESCRIPTIONS,
    SHIFT_LANE_RULE_DESCRIPTIONS,
)
from tslc.catalog.selector_paths import classify_selector_path
from tslc.catalog_authoring_index import (
    DocumentSymbolKind,
    IndexedDocumentSymbol,
    IndexedSemanticToken,
    SemanticTokenKind,
    build_document_authoring_index,
    selector_items,
)
from tslc.catalog_hover import (
    arithmetic_operand_hover as _arithmetic_operand_hover,
    hover_text as _hover_text,
    overload_value_hover as _overload_value_hover,
    semantic_operand_hover as _semantic_operand_hover,
)
from tslc.catalog_index_model import (
    ALL_SYMBOL_KINDS as _ALL_SYMBOL_KINDS,
    CatalogIndex,
    ENUM_SYMBOL_KINDS as _ENUM_SYMBOL_KINDS,
    IndexedOccurrence,
    IndexedCallPreconditionDisposition,
    SymbolKind,
    definitions_for as _definitions,
    references_for as _references,
    sorted_spans as _sorted_spans,
)
from tslc.catalog_occurrences import (
    ScopedSymbolKind as _ScopedSymbolKind,
    freeze_scoped_spans as _freeze_scoped_spans,
    freeze_spans as _freeze_spans,
    name_in_source as _name_in_source,
    occurrence_key as _occurrence_key,
    parameter_spans as _parameter_spans,
    record as _record,
    record_scalar_reference as _record_scalar_reference,
    record_scoped as _record_scoped,
    region_selector_name_span as _region_selector_name_span,
    regions as _regions,
    source_span as _source_span,
    subspan as _subspan,
)
from tslc.diagnostics import SourceSpan
from tslc.ir.region_syntax import (
    call_precondition_syntax_occurrences,
    parse_call_selector,
)
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.ir.scan import scan
from tslc.ir.segments import Region
from tslc.syntax.access import child, children
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedImplementationSelectorEntry,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
    ParsedTslListValue,
    ParsedTslScalarValue,
)


_SpanKey = TypeVar("_SpanKey")


@dataclass(frozen=True, slots=True)
class _DocumentIndex:
    definitions: Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]
    references: Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]
    target_axis_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    target_axis_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    overload_value_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    overload_value_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    arithmetic_operand_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    arithmetic_operand_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    semantic_operand_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    semantic_operand_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]]
    occurrences: tuple[IndexedOccurrence, ...]
    primitive_calls: tuple[tuple[str, str], ...]
    primitive_call_preconditions: tuple[IndexedCallPreconditionDisposition, ...]
    symbols: tuple[IndexedDocumentSymbol, ...]
    semantic_tokens: tuple[IndexedSemanticToken, ...]


def _symbol_span_maps() -> dict[SymbolKind, dict[str, list[SourceSpan]]]:
    return {kind: {} for kind in _ALL_SYMBOL_KINDS}


@dataclass(slots=True)
class _IndexAccumulator:
    """Mutable construction state for one document or complete catalog index."""

    definitions: dict[SymbolKind, dict[str, list[SourceSpan]]] = field(
        default_factory=_symbol_span_maps
    )
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = field(
        default_factory=_symbol_span_maps
    )
    target_axis_definitions: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    target_axis_references: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    overload_value_definitions: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    overload_value_references: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    arithmetic_operand_definitions: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    arithmetic_operand_references: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    semantic_operand_definitions: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    semantic_operand_references: dict[tuple[str, str], list[SourceSpan]] = field(
        default_factory=dict
    )
    occurrences: list[IndexedOccurrence] = field(default_factory=list)
    primitive_calls: set[tuple[str, str]] = field(default_factory=set)
    call_preconditions: list[IndexedCallPreconditionDisposition] = field(
        default_factory=list
    )

    def record(
        self,
        kind: SymbolKind,
        name: str,
        span: SourceSpan,
        *,
        definition: bool,
    ) -> None:
        values = self.definitions if definition else self.references
        _record(values, self.occurrences, kind, name, span, definition)

    def record_scalar_reference(
        self,
        value: ParsedTslScalarValue,
        kind: SymbolKind,
    ) -> None:
        _record_scalar_reference(value, self.references, self.occurrences, kind)

    def record_scoped(
        self,
        kind: _ScopedSymbolKind,
        scope: str,
        name: str,
        span: SourceSpan,
        *,
        definition: bool,
    ) -> None:
        _record_scoped(
            self._scoped_spans(kind, definition),
            self.occurrences,
            kind,
            scope,
            name,
            span,
            definition,
        )

    def record_occurrence(self, occurrence: IndexedOccurrence) -> None:
        self.occurrences.append(occurrence)

    def record_primitive_call(self, caller: str, callee: str) -> None:
        self.primitive_calls.add((caller, callee))

    def record_call_precondition(
        self, disposition: IndexedCallPreconditionDisposition
    ) -> None:
        self.call_preconditions.append(disposition)

    def merge(self, fragment: _DocumentIndex) -> None:
        for kind in _ALL_SYMBOL_KINDS:
            self._merge_spans(self.definitions[kind], fragment.definitions[kind])
            self._merge_spans(self.references[kind], fragment.references[kind])
        self._merge_spans(
            self.target_axis_definitions, fragment.target_axis_definitions
        )
        self._merge_spans(
            self.target_axis_references, fragment.target_axis_references
        )
        self._merge_spans(
            self.overload_value_definitions, fragment.overload_value_definitions
        )
        self._merge_spans(
            self.overload_value_references, fragment.overload_value_references
        )
        self._merge_spans(
            self.arithmetic_operand_definitions,
            fragment.arithmetic_operand_definitions,
        )
        self._merge_spans(
            self.arithmetic_operand_references,
            fragment.arithmetic_operand_references,
        )
        self._merge_spans(
            self.semantic_operand_definitions,
            fragment.semantic_operand_definitions,
        )
        self._merge_spans(
            self.semantic_operand_references,
            fragment.semantic_operand_references,
        )
        self.occurrences.extend(fragment.occurrences)
        self.primitive_calls.update(fragment.primitive_calls)
        self.call_preconditions.extend(fragment.primitive_call_preconditions)

    def freeze_document(
        self,
        symbols: tuple[IndexedDocumentSymbol, ...],
        semantic_tokens: tuple[IndexedSemanticToken, ...],
    ) -> _DocumentIndex:
        return _DocumentIndex(
            definitions=self._freeze_symbol_spans(self.definitions),
            references=self._freeze_symbol_spans(self.references),
            target_axis_definitions=self._freeze_scoped(
                self.target_axis_definitions
            ),
            target_axis_references=self._freeze_scoped(self.target_axis_references),
            overload_value_definitions=self._freeze_scoped(
                self.overload_value_definitions
            ),
            overload_value_references=self._freeze_scoped(
                self.overload_value_references
            ),
            arithmetic_operand_definitions=self._freeze_scoped(
                self.arithmetic_operand_definitions
            ),
            arithmetic_operand_references=self._freeze_scoped(
                self.arithmetic_operand_references
            ),
            semantic_operand_definitions=self._freeze_scoped(
                self.semantic_operand_definitions
            ),
            semantic_operand_references=self._freeze_scoped(
                self.semantic_operand_references
            ),
            occurrences=tuple(sorted(self.occurrences, key=_occurrence_key)),
            primitive_calls=tuple(sorted(self.primitive_calls)),
            primitive_call_preconditions=tuple(self.call_preconditions),
            symbols=symbols,
            semantic_tokens=semantic_tokens,
        )

    def freeze_catalog(
        self,
        catalog: Catalog,
        *,
        symbols_by_path: Mapping[Path, tuple[IndexedDocumentSymbol, ...]],
        semantic_tokens_by_path: Mapping[Path, tuple[IndexedSemanticToken, ...]],
    ) -> CatalogIndex:
        calls: dict[str, set[str]] = {}
        callers: dict[str, set[str]] = {}
        for caller, callee in sorted(self.primitive_calls):
            calls.setdefault(caller, set()).add(callee)
            callers.setdefault(callee, set()).add(caller)
        preconditions_by_caller: dict[
            str, set[IndexedCallPreconditionDisposition]
        ] = {}
        for item in self.call_preconditions:
            preconditions_by_caller.setdefault(item.caller, set()).add(item)
        occurrences_by_path: dict[Path, list[IndexedOccurrence]] = {}
        for occurrence in self.occurrences:
            occurrences_by_path.setdefault(
                occurrence.span.path.resolve(), []
            ).append(occurrence)
        return CatalogIndex(
            primitive_definitions=_freeze_spans(self.definitions["primitive"]),
            extension_definitions=_freeze_spans(self.definitions["extension"]),
            type_group_definitions=_freeze_spans(self.definitions["type-group"]),
            primitive_references=_freeze_spans(self.references["primitive"]),
            extension_references=_freeze_spans(self.references["extension"]),
            type_group_references=_freeze_spans(self.references["type-group"]),
            target_axis_definitions=_freeze_scoped_spans(
                self.target_axis_definitions
            ),
            target_axis_references=_freeze_scoped_spans(self.target_axis_references),
            overload_axis_definitions=_freeze_spans(
                self.definitions["overload-axis"]
            ),
            overload_axis_references=_freeze_spans(
                self.references["overload-axis"]
            ),
            overload_value_definitions=_freeze_scoped_spans(
                self.overload_value_definitions
            ),
            overload_value_references=_freeze_scoped_spans(
                self.overload_value_references
            ),
            arithmetic_operand_definitions=_freeze_scoped_spans(
                self.arithmetic_operand_definitions
            ),
            arithmetic_operand_references=_freeze_scoped_spans(
                self.arithmetic_operand_references
            ),
            semantic_operand_definitions=_freeze_scoped_spans(
                self.semantic_operand_definitions
            ),
            semantic_operand_references=_freeze_scoped_spans(
                self.semantic_operand_references
            ),
            enum_references={
                (kind, name): _sorted_spans(spans)
                for kind in sorted(_ENUM_SYMBOL_KINDS)
                for name, spans in sorted(self.references[kind].items())
            },
            primitive_calls={
                name: tuple(sorted(values)) for name, values in sorted(calls.items())
            },
            primitive_callers={
                name: tuple(sorted(values))
                for name, values in sorted(callers.items())
            },
            primitive_call_preconditions={
                name: tuple(
                    sorted(
                        values,
                        key=lambda item: (
                            item.callee,
                            item.condition,
                            item.disposition,
                            item.span.path.as_posix(),
                            item.span.line,
                            item.span.column,
                        ),
                    )
                )
                for name, values in sorted(preconditions_by_caller.items())
            },
            occurrences_by_path={
                path: tuple(sorted(items, key=_occurrence_key))
                for path, items in sorted(
                    occurrences_by_path.items(),
                    key=lambda item: item[0].as_posix(),
                )
            },
            document_symbols_by_path=dict(
                sorted(symbols_by_path.items(), key=lambda item: item[0].as_posix())
            ),
            semantic_tokens_by_path=dict(
                sorted(
                    semantic_tokens_by_path.items(),
                    key=lambda item: item[0].as_posix(),
                )
            ),
            hover_text=_hover_text(catalog, self.definitions),
            overload_value_hover=_overload_value_hover(catalog),
            arithmetic_operand_hover=_arithmetic_operand_hover(catalog),
            semantic_operand_hover=_semantic_operand_hover(catalog),
        )

    def _scoped_spans(
        self, kind: _ScopedSymbolKind, definition: bool
    ) -> dict[tuple[str, str], list[SourceSpan]]:
        if kind == "target-axis":
            return (
                self.target_axis_definitions
                if definition
                else self.target_axis_references
            )
        if kind == "overload-value":
            return (
                self.overload_value_definitions
                if definition
                else self.overload_value_references
            )
        if kind == "arithmetic-operand":
            return (
                self.arithmetic_operand_definitions
                if definition
                else self.arithmetic_operand_references
            )
        if kind == "semantic-operand":
            return (
                self.semantic_operand_definitions
                if definition
                else self.semantic_operand_references
            )
        raise ValueError(f"unsupported scoped catalog symbol kind {kind!r}")

    @staticmethod
    def _merge_spans(
        destination: dict[_SpanKey, list[SourceSpan]],
        source: Mapping[_SpanKey, tuple[SourceSpan, ...]],
    ) -> None:
        for key, spans in source.items():
            destination.setdefault(key, []).extend(spans)

    @staticmethod
    def _freeze_symbol_spans(
        values: Mapping[SymbolKind, dict[str, list[SourceSpan]]],
    ) -> Mapping[SymbolKind, Mapping[str, tuple[SourceSpan, ...]]]:
        return MappingProxyType(
            {
                kind: MappingProxyType(_freeze_spans(values[kind]))
                for kind in _ALL_SYMBOL_KINDS
            }
        )

    @staticmethod
    def _freeze_scoped(
        values: dict[tuple[str, str], list[SourceSpan]],
    ) -> Mapping[tuple[str, str], tuple[SourceSpan, ...]]:
        return MappingProxyType(_freeze_scoped_spans(values))


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
    accumulator = _IndexAccumulator()
    symbols_by_path: dict[Path, tuple[IndexedDocumentSymbol, ...]] = {}
    semantic_tokens_by_path: dict[Path, tuple[IndexedSemanticToken, ...]] = {}

    documents = tuple(sorted(parsed.documents, key=lambda item: item.path.as_posix()))
    fragments = (
        cache.fragments(documents)
        if cache is not None
        else tuple(_build_document_index(document) for document in documents)
    )
    for fragment in fragments:
        accumulator.merge(fragment)
        if fragment.symbols:
            path = fragment.symbols[0].span.path.resolve()
            symbols_by_path[path] = fragment.symbols
        if fragment.semantic_tokens:
            path = fragment.semantic_tokens[0].span.path.resolve()
            semantic_tokens_by_path[path] = fragment.semantic_tokens

    return accumulator.freeze_catalog(
        catalog,
        symbols_by_path=symbols_by_path,
        semantic_tokens_by_path=semantic_tokens_by_path,
    )


def _build_document_index(document: ParsedOuterTslDocument) -> _DocumentIndex:
    accumulator = _IndexAccumulator()
    _index_document(document, accumulator)
    authoring = build_document_authoring_index(document)
    return accumulator.freeze_document(
        authoring.symbols,
        authoring.semantic_tokens,
    )


def _index_document(
    document: ParsedOuterTslDocument,
    accumulator: _IndexAccumulator,
) -> None:
    for primitive in document.primitives:
        scope = _primitive_scope(primitive)
        result_target = _result_target(primitive)
        span = _name_in_source(primitive.header_source, primitive.name)
        accumulator.record("primitive", primitive.name, span, definition=True)
        _index_primitive_overload(primitive, accumulator)
        _index_primitive_arithmetic(primitive, accumulator, scope)
        _index_primitive_semantics(primitive, accumulator, scope)
        if result_target is not None:
            _, target_name, target_span = result_target
            accumulator.record_scoped(
                "target-axis",
                scope,
                target_name,
                target_span,
                definition=True,
            )
        _index_implementation_selectors(
            primitive,
            accumulator,
            result_target=(
                result_target
                if result_target is None or result_target[0] != RESULT_DIM_VECTOR
                else None
            ),
            scope=scope,
        )
        for envelope in primitive.body_envelopes:
            source = _source_span(envelope.payload_source)
            for region in _regions(scan(envelope.payload_text, source=source)):
                _index_region(primitive, region, accumulator)

    for block in document.blocks:
        if block.kind == "extension" and block.name:
            span = _name_in_source(block.source, block.name)
            accumulator.record("extension", block.name, span, definition=True)
            for block_field in block.fields:
                if block_field.key.text == "inherits" and isinstance(
                    block_field.value, ParsedTslScalarValue
                ):
                    accumulator.record_scalar_reference(
                        block_field.value, "extension"
                    )
                elif block_field.key.text == "supersedes" and isinstance(
                    block_field.value, ParsedTslListValue
                ):
                    for item in block_field.value.items:
                        if isinstance(item, ParsedTslScalarValue):
                            accumulator.record_scalar_reference(item, "extension")
        elif block.kind == "types":
            for block_field in block.fields:
                span = _source_span(block_field.key.source)
                accumulator.record(
                    "type-group",
                    block_field.key.text,
                    span,
                    definition=True,
                )

    for declaration in document.fields:
        if declaration.field.key.text != "overload_axes":
            continue
        for axis in children(declaration.field):
            accumulator.record(
                "overload-axis",
                axis.key.text,
                _source_span(axis.key.source),
                definition=True,
            )
            for value in children(child(axis, "values")):
                accumulator.record_scoped(
                    "overload-value",
                    axis.key.text,
                    value.key.text,
                    _source_span(value.key.source),
                    definition=True,
                )


def _index_primitive_overload(
    primitive: ParsedPrimitiveDeclaration,
    accumulator: _IndexAccumulator,
) -> None:
    for primitive_field in primitive.fields_by_name("overload"):
        axis_field = child(primitive_field.field, "axis")
        value_field = child(primitive_field.field, "value")
        if axis_field is None or not isinstance(axis_field.value, ParsedTslScalarValue):
            continue
        axis_value = axis_field.value
        accumulator.record_scalar_reference(axis_value, "overload-axis")
        if value_field is None or not isinstance(value_field.value, ParsedTslScalarValue):
            continue
        value = value_field.value
        accumulator.record_scoped(
            "overload-value",
            axis_value.text,
            value.text,
            _source_span(value.payload_source or value.source),
            definition=False,
        )


def _index_primitive_arithmetic(
    primitive: ParsedPrimitiveDeclaration,
    accumulator: _IndexAccumulator,
    scope: str,
) -> None:
    arithmetic_fields = primitive.fields_by_name("arithmetic")
    if not arithmetic_fields:
        return
    bound_names: set[str] = set()
    for parsed in arithmetic_fields:
        arithmetic = parsed.field
        arithmetic_lists: tuple[tuple[str, SymbolKind], ...] = (
            ("operations", "arithmetic-operation"),
            ("guarantees", "arithmetic-guarantee"),
        )
        for field_name, kind in arithmetic_lists:
            value = child(arithmetic, field_name)
            if value is None or not isinstance(value.value, ParsedTslListValue):
                continue
            for item in value.value.items:
                if isinstance(item, ParsedTslScalarValue):
                    accumulator.record_scalar_reference(item, kind)
        for role in children(child(arithmetic, "operand_roles")):
            accumulator.record(
                "arithmetic-role",
                role.key.text,
                _source_span(role.key.source),
                definition=False,
            )
            if not isinstance(role.value, ParsedTslScalarValue):
                continue
            source = role.value.payload_source or role.value.source
            bound_names.add(role.value.text)
            accumulator.record_scoped(
                "arithmetic-operand",
                scope,
                role.value.text,
                _source_span(source),
                definition=False,
            )
    for name, span in _parameter_spans(primitive):
        if name not in bound_names:
            continue
        accumulator.record_scoped(
            "arithmetic-operand",
            scope,
            name,
            span,
            definition=True,
        )


def _index_primitive_semantics(
    primitive: ParsedPrimitiveDeclaration,
    accumulator: _IndexAccumulator,
    scope: str,
) -> None:
    bound_names: set[str] = set()
    for parsed in primitive.fields_by_name("operation"):
        if isinstance(parsed.field.value, ParsedTslScalarValue):
            accumulator.record_scalar_reference(
                parsed.field.value, "primitive-operation"
            )
    for parsed in primitive.fields_by_name("operand_roles"):
        for role in children(parsed.field):
            accumulator.record(
                "operand-role",
                role.key.text,
                _source_span(role.key.source),
                definition=False,
            )
            if not isinstance(role.value, ParsedTslScalarValue):
                continue
            source = role.value.payload_source or role.value.source
            bound_names.add(role.value.text)
            accumulator.record_scoped(
                "semantic-operand",
                scope,
                role.value.text,
                _source_span(source),
                definition=False,
            )
    for parsed in primitive.fields_by_name("preconditions"):
        value = parsed.field.value
        if not isinstance(value, ParsedTslListValue):
            continue
        for item in value.items:
            if isinstance(item, ParsedTslScalarValue):
                accumulator.record_scalar_reference(item, "precondition")
    semantic_members: tuple[
        tuple[str, tuple[tuple[str, SymbolKind], ...]], ...
    ] = (
        (
            "memory",
            (
                ("access", "memory-access"),
                ("addressing", "memory-addressing"),
                ("indexed_lanes", "memory-indexed-lane-extent"),
            ),
        ),
        (
            "conversion",
            (
                ("kind", "conversion-kind"),
                ("lane_count", "lane-count-relation"),
                ("numeric_mode", "numeric-conversion-mode"),
            ),
        ),
        (
            "shift",
            (
                ("count_rule", "shift-count-rule"),
                ("lane_rule", "shift-lane-rule"),
            ),
        ),
    )
    for field_name, members in semantic_members:
        for parsed in primitive.fields_by_name(field_name):
            for member_name, kind in members:
                member = child(parsed.field, member_name)
                if member is not None and isinstance(member.value, ParsedTslScalarValue):
                    accumulator.record_scalar_reference(member.value, kind)
    for name, span in _parameter_spans(primitive):
        if name in bound_names:
            accumulator.record_scoped(
                "semantic-operand",
                scope,
                name,
                span,
                definition=True,
            )


def _index_implementation_selectors(
    primitive: ParsedPrimitiveDeclaration,
    accumulator: _IndexAccumulator,
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
                accumulator.record("extension", name, span, definition=False)
        elif level.kind == "source-type-group":
            for name, span in items:
                accumulator.record("type-group", name, span, definition=False)
        elif level.kind == "target-axis":
            for name, span in items:
                accumulator.record_scoped(
                    "target-axis",
                    scope,
                    name,
                    span,
                    definition=False,
                )
        elif level.kind == "target-reference":
            for name, span in items:
                accumulator.record("type-group", name, span, definition=False)
        # A `where` constraint level references no catalog symbol; it is never
        # indexed as a type group.
        for child in entry.children:
            visit(child, path)

    for entry in primitive.impl_entries:
        visit(entry, ())


def _index_region(
    primitive: ParsedPrimitiveDeclaration,
    region: Region,
    accumulator: _IndexAccumulator,
) -> None:
    if region.source is None:
        return
    keyword_span = _subspan(
        region.source,
        region.full_text,
        0,
        len(region.keyword),
    )
    accumulator.record_occurrence(
        IndexedOccurrence("region", region.keyword, keyword_span, False)
    )
    if region.keyword != "call":
        return
    call = parse_call_selector(region.selector_text)
    if call is None:
        return
    name = primitive.name if call.primitive_ref == "@self" else call.primitive_ref
    accumulator.record_primitive_call(primitive.name, name)
    reference_span = _region_selector_name_span(region, call.primitive_ref)
    if reference_span is not None:
        accumulator.record("primitive", name, reference_span, definition=False)
    selector_offset = region.full_text.find(region.selector_text)
    if selector_offset < 0:
        return
    for item in call_precondition_syntax_occurrences(region.selector_text, call):
        span = _subspan(
            region.source,
            region.full_text,
            selector_offset + item.start,
            selector_offset + item.end,
        )
        accumulator.record(
            "precondition",
            item.condition,
            span,
            definition=False,
        )
        accumulator.record_call_precondition(
            IndexedCallPreconditionDisposition(
                caller=primitive.name,
                callee=name,
                condition=item.condition,
                disposition=item.disposition,
                span=span,
            )
        )


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
