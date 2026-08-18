"""Immutable semantic occurrence index and query operations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from tslc.catalog_authoring_index import IndexedDocumentSymbol, IndexedSemanticToken
from tslc.diagnostics import SourceSpan

SymbolKind = Literal[
    "primitive",
    "extension",
    "type-group",
    "region",
    "target-axis",
    "overload-axis",
    "overload-value",
    "arithmetic-operation",
    "arithmetic-role",
    "arithmetic-guarantee",
    "arithmetic-operand",
    "primitive-operation",
    "operand-role",
    "semantic-operand",
    "memory-access",
    "memory-addressing",
    "conversion-kind",
    "lane-count-relation",
    "numeric-conversion-mode",
    "shift-count-rule",
    "shift-lane-rule",
]

ENUM_SYMBOL_KINDS: frozenset[SymbolKind] = frozenset(
    {
        "arithmetic-operation",
        "arithmetic-role",
        "arithmetic-guarantee",
        "primitive-operation",
        "operand-role",
        "memory-access",
        "memory-addressing",
        "conversion-kind",
        "lane-count-relation",
        "numeric-conversion-mode",
        "shift-count-rule",
        "shift-lane-rule",
    }
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
    target_axis_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    target_axis_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    overload_axis_definitions: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    overload_axis_references: Mapping[str, tuple[SourceSpan, ...]] = field(default_factory=dict)
    overload_value_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    overload_value_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    arithmetic_operand_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    arithmetic_operand_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    semantic_operand_definitions: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    semantic_operand_references: Mapping[tuple[str, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    enum_references: Mapping[tuple[SymbolKind, str], tuple[SourceSpan, ...]] = field(default_factory=dict)
    primitive_calls: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    primitive_callers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    occurrences_by_path: Mapping[Path, tuple[IndexedOccurrence, ...]] = field(default_factory=dict)
    document_symbols_by_path: Mapping[Path, tuple[IndexedDocumentSymbol, ...]] = field(default_factory=dict)
    semantic_tokens_by_path: Mapping[Path, tuple[IndexedSemanticToken, ...]] = field(default_factory=dict)
    hover_text: Mapping[tuple[SymbolKind, str], str] = field(default_factory=dict)
    overload_value_hover: Mapping[tuple[str, str], str] = field(default_factory=dict)
    arithmetic_operand_hover: Mapping[tuple[str, str], str] = field(default_factory=dict)
    semantic_operand_hover: Mapping[tuple[str, str], str] = field(default_factory=dict)

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
            "arithmetic_operand_definitions",
            "arithmetic_operand_references",
            "semantic_operand_definitions",
            "semantic_operand_references",
            "enum_references",
            "primitive_calls",
            "primitive_callers",
            "occurrences_by_path",
            "document_symbols_by_path",
            "semantic_tokens_by_path",
            "hover_text",
            "overload_value_hover",
            "arithmetic_operand_hover",
            "semantic_operand_hover",
        ):
            object.__setattr__(
                self,
                name,
                MappingProxyType(dict(getattr(self, name))),
            )

    def occurrence_at(
        self, path: Path, line: int, column: int
    ) -> IndexedOccurrence | None:
        candidates = tuple(
            item
            for item in self.occurrences_by_path.get(path.resolve(), ())
            if _contains(item.span, line, column)
        )
        return min(candidates, key=lambda item: _span_size(item.span), default=None)

    def definitions(self, occurrence: IndexedOccurrence) -> tuple[SourceSpan, ...]:
        scoped = {
            "overload-value": self.overload_value_definitions,
            "target-axis": self.target_axis_definitions,
            "arithmetic-operand": self.arithmetic_operand_definitions,
            "semantic-operand": self.semantic_operand_definitions,
        }.get(occurrence.kind)
        if scoped is not None:
            if occurrence.scope is None:
                return ()
            return scoped.get((occurrence.scope, occurrence.name), ())
        return definitions_for(self, occurrence.kind).get(occurrence.name, ())

    def references(
        self, occurrence: IndexedOccurrence, *, include_declaration: bool = True
    ) -> tuple[SourceSpan, ...]:
        scoped = {
            "target-axis": self.target_axis_references,
            "overload-value": self.overload_value_references,
            "arithmetic-operand": self.arithmetic_operand_references,
            "semantic-operand": self.semantic_operand_references,
        }.get(occurrence.kind)
        if scoped is not None:
            referenced = (
                ()
                if occurrence.scope is None
                else scoped.get((occurrence.scope, occurrence.name), ())
            )
        elif occurrence.kind in ENUM_SYMBOL_KINDS:
            referenced = self.enum_references.get(
                (occurrence.kind, occurrence.name), ()
            )
        else:
            referenced = references_for(self, occurrence.kind).get(
                occurrence.name, ()
            )
        declared = self.definitions(occurrence) if include_declaration else ()
        return sorted_spans((*declared, *referenced))

    def hover(self, occurrence: IndexedOccurrence) -> str | None:
        scoped = {
            "overload-value": self.overload_value_hover,
            "arithmetic-operand": self.arithmetic_operand_hover,
            "semantic-operand": self.semantic_operand_hover,
        }.get(occurrence.kind)
        if scoped is not None and occurrence.scope is not None:
            return scoped.get((occurrence.scope, occurrence.name))
        return self.hover_text.get((occurrence.kind, occurrence.name))


def definitions_for(
    index: CatalogIndex, kind: SymbolKind
) -> Mapping[str, tuple[SourceSpan, ...]]:
    if kind == "primitive":
        return index.primitive_definitions
    if kind == "extension":
        return index.extension_definitions
    if kind == "type-group":
        return index.type_group_definitions
    if kind == "overload-axis":
        return index.overload_axis_definitions
    return {}


def references_for(
    index: CatalogIndex, kind: SymbolKind
) -> Mapping[str, tuple[SourceSpan, ...]]:
    if kind == "primitive":
        return index.primitive_references
    if kind == "extension":
        return index.extension_references
    if kind == "type-group":
        return index.type_group_references
    if kind == "overload-axis":
        return index.overload_axis_references
    return {}


def sorted_spans(spans: Iterable[SourceSpan]) -> tuple[SourceSpan, ...]:
    return tuple(sorted(set(spans), key=_span_key))


def _span_key(span: SourceSpan) -> tuple[str, int, int, int, int]:
    return (
        span.path.as_posix(),
        span.line,
        span.column,
        span.end_line,
        span.end_column,
    )


def _contains(span: SourceSpan, line: int, column: int) -> bool:
    return (line, column) >= (span.line, span.column) and (line, column) < (
        span.end_line,
        span.end_column,
    )


def _span_size(span: SourceSpan) -> tuple[int, int]:
    return (span.end_line - span.line, span.end_column - span.column)


__all__ = (
    "CatalogIndex",
    "ENUM_SYMBOL_KINDS",
    "IndexedOccurrence",
    "SymbolKind",
    "definitions_for",
    "references_for",
    "sorted_spans",
)
