"""Typed catalog/source index shared by inspection and language-server features."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

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
    CatalogIndex,
    ENUM_SYMBOL_KINDS as _ENUM_SYMBOL_KINDS,
    IndexedOccurrence,
    SymbolKind,
    definitions_for as _definitions,
    references_for as _references,
    sorted_spans as _sorted_spans,
)
from tslc.catalog_occurrences import (
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
from tslc.ir.region_syntax import parse_call_selector
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
        "arithmetic-operation": {},
        "arithmetic-role": {},
        "arithmetic-guarantee": {},
        "arithmetic-operand": {},
        "primitive-operation": {},
        "operand-role": {},
        "semantic-operand": {},
        "memory-access": {},
        "memory-addressing": {},
        "conversion-kind": {},
        "lane-count-relation": {},
        "numeric-conversion-mode": {},
        "shift-count-rule": {},
        "shift-lane-rule": {},
    }
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
        "target-axis": {},
        "overload-axis": {},
        "overload-value": {},
        "arithmetic-operation": {},
        "arithmetic-role": {},
        "arithmetic-guarantee": {},
        "arithmetic-operand": {},
        "primitive-operation": {},
        "operand-role": {},
        "semantic-operand": {},
        "memory-access": {},
        "memory-addressing": {},
        "conversion-kind": {},
        "lane-count-relation": {},
        "numeric-conversion-mode": {},
        "shift-count-rule": {},
        "shift-lane-rule": {},
    }
    target_axis_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    target_axis_references: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_references: dict[tuple[str, str], list[SourceSpan]] = {}
    arithmetic_operand_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    arithmetic_operand_references: dict[tuple[str, str], list[SourceSpan]] = {}
    semantic_operand_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    semantic_operand_references: dict[tuple[str, str], list[SourceSpan]] = {}
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
        for key, spans in fragment.arithmetic_operand_definitions.items():
            arithmetic_operand_definitions.setdefault(key, []).extend(spans)
        for key, spans in fragment.arithmetic_operand_references.items():
            arithmetic_operand_references.setdefault(key, []).extend(spans)
        for key, spans in fragment.semantic_operand_definitions.items():
            semantic_operand_definitions.setdefault(key, []).extend(spans)
        for key, spans in fragment.semantic_operand_references.items():
            semantic_operand_references.setdefault(key, []).extend(spans)
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
        arithmetic_operand_definitions=_freeze_scoped_spans(
            arithmetic_operand_definitions
        ),
        arithmetic_operand_references=_freeze_scoped_spans(
            arithmetic_operand_references
        ),
        semantic_operand_definitions=_freeze_scoped_spans(
            semantic_operand_definitions
        ),
        semantic_operand_references=_freeze_scoped_spans(
            semantic_operand_references
        ),
        enum_references={
            (kind, name): _sorted_spans(spans)
            for kind in sorted(_ENUM_SYMBOL_KINDS)
            for name, spans in sorted(references[kind].items())
        },
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
        arithmetic_operand_hover=_arithmetic_operand_hover(catalog),
        semantic_operand_hover=_semantic_operand_hover(catalog),
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
        "arithmetic-operation": {},
        "arithmetic-role": {},
        "arithmetic-guarantee": {},
        "arithmetic-operand": {},
        "primitive-operation": {},
        "operand-role": {},
        "semantic-operand": {},
        "memory-access": {},
        "memory-addressing": {},
        "conversion-kind": {},
        "lane-count-relation": {},
        "numeric-conversion-mode": {},
        "shift-count-rule": {},
        "shift-lane-rule": {},
    }
    references: dict[SymbolKind, dict[str, list[SourceSpan]]] = {
        "primitive": {},
        "extension": {},
        "type-group": {},
        "region": {},
        "target-axis": {},
        "overload-axis": {},
        "overload-value": {},
        "arithmetic-operation": {},
        "arithmetic-role": {},
        "arithmetic-guarantee": {},
        "arithmetic-operand": {},
        "primitive-operation": {},
        "operand-role": {},
        "semantic-operand": {},
        "memory-access": {},
        "memory-addressing": {},
        "conversion-kind": {},
        "lane-count-relation": {},
        "numeric-conversion-mode": {},
        "shift-count-rule": {},
        "shift-lane-rule": {},
    }
    target_axis_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    target_axis_references: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    overload_value_references: dict[tuple[str, str], list[SourceSpan]] = {}
    arithmetic_operand_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    arithmetic_operand_references: dict[tuple[str, str], list[SourceSpan]] = {}
    semantic_operand_definitions: dict[tuple[str, str], list[SourceSpan]] = {}
    semantic_operand_references: dict[tuple[str, str], list[SourceSpan]] = {}
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
        arithmetic_operand_definitions,
        arithmetic_operand_references,
        semantic_operand_definitions,
        semantic_operand_references,
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
        arithmetic_operand_definitions=_freeze_scoped_spans(
            arithmetic_operand_definitions
        ),
        arithmetic_operand_references=_freeze_scoped_spans(
            arithmetic_operand_references
        ),
        semantic_operand_definitions=_freeze_scoped_spans(
            semantic_operand_definitions
        ),
        semantic_operand_references=_freeze_scoped_spans(
            semantic_operand_references
        ),
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
    arithmetic_operand_definitions: dict[tuple[str, str], list[SourceSpan]],
    arithmetic_operand_references: dict[tuple[str, str], list[SourceSpan]],
    semantic_operand_definitions: dict[tuple[str, str], list[SourceSpan]],
    semantic_operand_references: dict[tuple[str, str], list[SourceSpan]],
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
        _index_primitive_arithmetic(
            primitive,
            references,
            arithmetic_operand_definitions,
            arithmetic_operand_references,
            occurrences,
            scope,
        )
        _index_primitive_semantics(
            primitive,
            references,
            semantic_operand_definitions,
            semantic_operand_references,
            occurrences,
            scope,
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


def _index_primitive_arithmetic(
    primitive: ParsedPrimitiveDeclaration,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    operand_definitions: dict[tuple[str, str], list[SourceSpan]],
    operand_references: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
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
                    _record_scalar_reference(item, references, occurrences, kind)
        for role in children(child(arithmetic, "operand_roles")):
            _record(
                references,
                occurrences,
                "arithmetic-role",
                role.key.text,
                _source_span(role.key.source),
                False,
            )
            if not isinstance(role.value, ParsedTslScalarValue):
                continue
            source = role.value.payload_source or role.value.source
            bound_names.add(role.value.text)
            _record_scoped(
                operand_references,
                occurrences,
                "arithmetic-operand",
                scope,
                role.value.text,
                _source_span(source),
                False,
            )
    for name, span in _parameter_spans(primitive):
        if name not in bound_names:
            continue
        _record_scoped(
            operand_definitions,
            occurrences,
            "arithmetic-operand",
            scope,
            name,
            span,
            True,
        )


def _index_primitive_semantics(
    primitive: ParsedPrimitiveDeclaration,
    references: dict[SymbolKind, dict[str, list[SourceSpan]]],
    operand_definitions: dict[tuple[str, str], list[SourceSpan]],
    operand_references: dict[tuple[str, str], list[SourceSpan]],
    occurrences: list[IndexedOccurrence],
    scope: str,
) -> None:
    bound_names: set[str] = set()
    for parsed in primitive.fields_by_name("operation"):
        if isinstance(parsed.field.value, ParsedTslScalarValue):
            _record_scalar_reference(
                parsed.field.value,
                references,
                occurrences,
                "primitive-operation",
            )
    for parsed in primitive.fields_by_name("operand_roles"):
        for role in children(parsed.field):
            _record(
                references,
                occurrences,
                "operand-role",
                role.key.text,
                _source_span(role.key.source),
                False,
            )
            if not isinstance(role.value, ParsedTslScalarValue):
                continue
            source = role.value.payload_source or role.value.source
            bound_names.add(role.value.text)
            _record_scoped(
                operand_references,
                occurrences,
                "semantic-operand",
                scope,
                role.value.text,
                _source_span(source),
                False,
            )
    semantic_members: tuple[
        tuple[str, tuple[tuple[str, SymbolKind], ...]], ...
    ] = (
        (
            "memory",
            (
                ("access", "memory-access"),
                ("addressing", "memory-addressing"),
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
                    _record_scalar_reference(
                        member.value,
                        references,
                        occurrences,
                        kind,
                    )
    for name, span in _parameter_spans(primitive):
        if name in bound_names:
            _record_scoped(
                operand_definitions,
                occurrences,
                "semantic-operand",
                scope,
                name,
                span,
                True,
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
