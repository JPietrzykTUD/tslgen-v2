"""Pure index-backed language-server feature projections."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from lsprotocol import types

from tslc.authoring_vocabulary import completion_context, completion_values
from tslc.catalog_index import CatalogIndex, IndexedOccurrence, SymbolKind
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.lsp.positions import (
    path_to_uri,
    position_offset,
    source_position,
    span_to_range,
)
from tslc.lsp.workspace import AuthoringWorkspace, WorkspaceSnapshot

SEMANTIC_TOKEN_TYPES = ("function", "class", "type", "keyword")
_TOKEN_INDEX = {name: index for index, name in enumerate(SEMANTIC_TOKEN_TYPES)}


def diagnostics_by_path(
    snapshot: WorkspaceSnapshot,
) -> dict[Path, tuple[Diagnostic, ...]]:
    grouped: dict[Path, list[Diagnostic]] = {}
    for diagnostic in snapshot.diagnostics:
        if diagnostic.span is None:
            continue
        grouped.setdefault(diagnostic.span.path.resolve(), []).append(diagnostic)
    return {
        path: tuple(items)
        for path, items in sorted(grouped.items(), key=lambda item: item[0].as_posix())
    }


def lsp_diagnostic(diagnostic: Diagnostic, workspace: AuthoringWorkspace) -> types.Diagnostic:
    span = diagnostic.span
    if span is None:
        raise ValueError("document diagnostics require a source span")
    text = workspace.document_text(span.path) or ""
    related: list[types.DiagnosticRelatedInformation] = []
    for item in diagnostic.related:
        related_text = workspace.document_text(item.span.path) or ""
        related.append(
            types.DiagnosticRelatedInformation(
                location=types.Location(
                    uri=path_to_uri(item.span.path),
                    range=span_to_range(item.span, related_text),
                ),
                message=item.message,
            )
        )
    message = diagnostic.message
    if diagnostic.help:
        message = f"{message}\nHelp: {diagnostic.help}"
    return types.Diagnostic(
        range=span_to_range(span, text),
        message=message,
        severity=_severity(diagnostic.severity),
        code=diagnostic.code,
        source="tslc",
        related_information=related or None,
    )


def document_symbols(
    index: CatalogIndex | None, path: Path, text: str
) -> tuple[types.DocumentSymbol, ...]:
    if index is None:
        return ()
    symbols: list[types.DocumentSymbol] = []
    for occurrence in index.occurrences_by_path.get(path.resolve(), ()):
        if not occurrence.definition:
            continue
        range_ = span_to_range(occurrence.span, text)
        symbols.append(
            types.DocumentSymbol(
                name=occurrence.name,
                kind=_symbol_kind(occurrence.kind),
                range=range_,
                selection_range=range_,
                detail=occurrence.kind,
            )
        )
    return tuple(symbols)


def definition_locations(
    index: CatalogIndex | None,
    path: Path,
    text: str,
    position: types.Position,
    workspace: AuthoringWorkspace,
) -> tuple[types.Location, ...]:
    occurrence = _occurrence(index, path, text, position)
    if occurrence is None or index is None:
        return ()
    return _locations(index.definitions(occurrence), workspace)


def reference_locations(
    index: CatalogIndex | None,
    path: Path,
    text: str,
    position: types.Position,
    workspace: AuthoringWorkspace,
    *,
    include_declaration: bool,
) -> tuple[types.Location, ...]:
    occurrence = _occurrence(index, path, text, position)
    if occurrence is None or index is None:
        return ()
    return _locations(
        index.references(occurrence, include_declaration=include_declaration),
        workspace,
    )


def hover(
    index: CatalogIndex | None,
    path: Path,
    text: str,
    position: types.Position,
) -> types.Hover | None:
    occurrence = _occurrence(index, path, text, position)
    if occurrence is None or index is None:
        return None
    value = index.hover(occurrence)
    if value is None:
        return None
    return types.Hover(
        contents=types.MarkupContent(kind=types.MarkupKind.Markdown, value=value),
        range=span_to_range(occurrence.span, text),
    )


def completions(
    snapshot: WorkspaceSnapshot,
    text: str,
    position: types.Position,
) -> types.CompletionList:
    if snapshot.catalog is None:
        return types.CompletionList(is_incomplete=False, items=[])
    context = completion_context(text, position_offset(text, position))
    values = completion_values(
        context,
        snapshot.catalog,
        target_features=snapshot.target_features,
    )
    items = [
        types.CompletionItem(
            label=value,
            kind=_completion_kind(context.kind),
            sort_text=value,
        )
        for value in values
    ]
    return types.CompletionList(is_incomplete=False, items=items)


def semantic_tokens(
    index: CatalogIndex | None, path: Path, text: str
) -> types.SemanticTokens:
    if index is None:
        return types.SemanticTokens(data=[])
    absolute: list[tuple[int, int, int, int]] = []
    for occurrence in index.occurrences_by_path.get(path.resolve(), ()):
        range_ = span_to_range(occurrence.span, text)
        if range_.start.line != range_.end.line:
            continue
        length = range_.end.character - range_.start.character
        if length <= 0:
            continue
        absolute.append(
            (
                range_.start.line,
                range_.start.character,
                length,
                _TOKEN_INDEX[_token_type(occurrence.kind)],
            )
        )
    absolute.sort()
    data: list[int] = []
    previous_line = 0
    previous_character = 0
    for line, character, length, token_type in absolute:
        delta_line = line - previous_line
        delta_character = character - previous_character if delta_line == 0 else character
        data.extend((delta_line, delta_character, length, token_type, 0))
        previous_line = line
        previous_character = character
    return types.SemanticTokens(data=data)


def _occurrence(
    index: CatalogIndex | None,
    path: Path,
    text: str,
    position: types.Position,
) -> IndexedOccurrence | None:
    if index is None:
        return None
    line, column = source_position(text, position)
    return index.occurrence_at(path.resolve(), line, column)


def _locations(
    spans: Iterable[SourceSpan], workspace: AuthoringWorkspace
) -> tuple[types.Location, ...]:
    locations: list[types.Location] = []
    for span in spans:
        text = workspace.document_text(span.path)
        if text is None:
            continue
        locations.append(
            types.Location(
                uri=path_to_uri(span.path),
                range=span_to_range(span, text),
            )
        )
    return tuple(locations)


def _severity(value: str) -> types.DiagnosticSeverity:
    return {
        "error": types.DiagnosticSeverity.Error,
        "warning": types.DiagnosticSeverity.Warning,
        "info": types.DiagnosticSeverity.Information,
    }[value]


def _symbol_kind(kind: SymbolKind) -> types.SymbolKind:
    return {
        "primitive": types.SymbolKind.Function,
        "extension": types.SymbolKind.Class,
        "type-group": types.SymbolKind.Struct,
        "region": types.SymbolKind.Namespace,
    }[kind]


def _completion_kind(kind: str) -> types.CompletionItemKind:
    if kind in {"primitive-field", "extension-field", "implementation-field"}:
        return types.CompletionItemKind.Field
    if kind == "primitive-call":
        return types.CompletionItemKind.Function
    if kind == "implementation-extension":
        return types.CompletionItemKind.Class
    if kind == "implementation-type-group":
        return types.CompletionItemKind.TypeParameter
    return types.CompletionItemKind.Keyword


def _token_type(kind: SymbolKind) -> str:
    return {
        "primitive": "function",
        "extension": "class",
        "type-group": "type",
        "region": "keyword",
    }[kind]


__all__ = (
    "SEMANTIC_TOKEN_TYPES",
    "completions",
    "definition_locations",
    "diagnostics_by_path",
    "document_symbols",
    "hover",
    "lsp_diagnostic",
    "reference_locations",
    "semantic_tokens",
)
