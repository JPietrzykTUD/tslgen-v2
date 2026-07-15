"""Pure index-backed language-server feature projections."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from lsprotocol import types

from tslc.authoring_completion import (
    AuthoringCompletionKind,
    authoring_completions,
)
from tslc.catalog_index import (
    CatalogIndex,
    DocumentSymbolKind,
    IndexedDocumentSymbol,
    IndexedOccurrence,
)
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.lsp.positions import (
    SourceTextMap,
    offset_position,
    path_to_uri,
    position_offset,
    source_position,
    span_to_range,
)
from tslc.syntax.authoring import authoring_cursor_context
from tslc.lsp.workspace import AuthoringWorkspace, WorkspaceSnapshot

SEMANTIC_TOKEN_TYPES = (
    "function",
    "class",
    "type",
    "keyword",
    "property",
    "parameter",
    "typeParameter",
    "enumMember",
    "namespace",
)
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
    source_map = SourceTextMap.from_text(text)
    return tuple(
        _document_symbol(symbol, source_map)
        for symbol in index.document_symbols_by_path.get(path.resolve(), ())
    )


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
    path: Path,
    text: str,
    position: types.Position,
) -> types.CompletionList:
    if snapshot.catalog is None:
        return types.CompletionList(is_incomplete=False, items=[])
    context = authoring_cursor_context(
        snapshot.parsed,
        path,
        text,
        position_offset(text, position),
    )
    records = authoring_completions(
        context,
        snapshot.catalog,
        target_features=snapshot.target_features,
    )
    items = [
        types.CompletionItem(
            label=record.label,
            kind=_completion_kind(record.kind),
            detail=record.detail,
            documentation=record.documentation,
            sort_text=f"{record.sort_group:03d}:{record.label}",
            text_edit=types.TextEdit(
                range=types.Range(
                    start=offset_position(text, record.replacement_range.start),
                    end=offset_position(text, record.replacement_range.end),
                ),
                new_text=record.insert_text,
            ),
            insert_text_format=(
                types.InsertTextFormat.Snippet
                if record.snippet
                else types.InsertTextFormat.PlainText
            ),
            commit_characters=list(record.commit_characters) or None,
        )
        for record in records
    ]
    return types.CompletionList(is_incomplete=False, items=items)


def semantic_tokens(
    index: CatalogIndex | None, path: Path, text: str
) -> types.SemanticTokens:
    if index is None:
        return types.SemanticTokens(data=[])
    source_map = SourceTextMap.from_text(text)
    absolute: list[tuple[int, int, int, int]] = []
    for token in index.semantic_tokens_by_path.get(path.resolve(), ()):
        range_ = source_map.range(token.span)
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
                _TOKEN_INDEX[token.kind],
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


def _document_symbol(
    symbol: IndexedDocumentSymbol,
    source_map: SourceTextMap,
) -> types.DocumentSymbol:
    return types.DocumentSymbol(
        name=symbol.name,
        kind=_symbol_kind(symbol.kind),
        range=source_map.range(symbol.span),
        selection_range=source_map.range(symbol.selection_span),
        detail=symbol.detail,
        children=[_document_symbol(child, source_map) for child in symbol.children]
        or None,
    )


def _symbol_kind(kind: DocumentSymbolKind) -> types.SymbolKind:
    return {
        "primitive": types.SymbolKind.Function,
        "extension": types.SymbolKind.Class,
        "type-group": types.SymbolKind.Struct,
        "block": types.SymbolKind.Namespace,
        "field": types.SymbolKind.Field,
        "implementation": types.SymbolKind.Object,
        "variant": types.SymbolKind.Method,
        "parameter": types.SymbolKind.Variable,
        "generic-parameter": types.SymbolKind.TypeParameter,
        "target-axis": types.SymbolKind.TypeParameter,
        "test-case": types.SymbolKind.Event,
    }[kind]


def _completion_kind(kind: AuthoringCompletionKind) -> types.CompletionItemKind:
    return {
        "field": types.CompletionItemKind.Field,
        "keyword": types.CompletionItemKind.Keyword,
        "value": types.CompletionItemKind.Value,
        "function": types.CompletionItemKind.Function,
        "class": types.CompletionItemKind.Class,
        "type": types.CompletionItemKind.TypeParameter,
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
