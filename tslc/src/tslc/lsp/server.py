"""pygls transport wiring for the compiler-owned authoring workspace."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from tslc.lsp.features import (
    SEMANTIC_TOKEN_TYPES,
    completions,
    definition_locations,
    diagnostics_by_path,
    document_symbols,
    hover,
    lsp_diagnostic,
    reference_locations,
    semantic_tokens,
)
from tslc.lsp.positions import path_to_uri, uri_to_path
from tslc.lsp.workspace import AuthoringWorkspace, WorkspaceSnapshot

SERVER_NAME = "tslc"
SERVER_VERSION = "0.1.0"
_DEBOUNCE_SECONDS = 0.15
_INDEX_WAIT_SECONDS = 5.0


@dataclass(slots=True)
class _ServerState:
    root_override: Path | None = None
    config_override: Path | None = None
    workspace: AuthoringWorkspace | None = None
    root: Path | None = None
    setup_error: str | None = None
    published_paths: set[Path] = field(default_factory=set)
    shown_setup_error: bool = False
    source_roots: tuple[Path, ...] | None = None
    machine_profiles_path: Path | None = None
    backends: tuple[str, ...] | None = None
    index_ready: asyncio.Event = field(default_factory=asyncio.Event)


def create_server(
    *, root: Path | None = None, config: Path | None = None
) -> LanguageServer:
    server = LanguageServer(
        SERVER_NAME,
        SERVER_VERSION,
        text_document_sync_kind=types.TextDocumentSyncKind.Full,
        max_workers=2,
    )
    state = _ServerState(root_override=root, config_override=config)

    @server.feature(types.INITIALIZE)
    def initialize(params: types.InitializeParams) -> None:
        selected_root = state.root_override or _initialization_root(params)
        options = _options(params.initialization_options)
        config_path = state.config_override or _path_option(options, "config")
        sources = _path_tuple_option(options, "sources")
        profiles = _path_option(options, "machineProfiles")
        backends = _string_tuple_option(options, "backends")
        state.config_override = config_path
        state.source_roots = sources
        state.machine_profiles_path = profiles
        state.backends = backends
        state.index_ready.clear()
        try:
            state.workspace = AuthoringWorkspace.from_root(
                selected_root,
                config_path=config_path,
                source_roots=sources,
                machine_profiles_path=profiles,
                backends=backends,
            )
            state.root = selected_root
            state.setup_error = None
        except ValueError as exc:
            state.root = selected_root
            state.setup_error = str(exc)

    @server.feature(types.WORKSPACE_DID_CHANGE_CONFIGURATION)
    async def did_change_configuration(
        params: types.DidChangeConfigurationParams,
    ) -> None:
        del params
        old = state.workspace
        if state.root is None:
            return
        documents = old.open_documents if old is not None else ()
        try:
            replacement = AuthoringWorkspace.from_root(
                state.root,
                config_path=state.config_override,
                source_roots=state.source_roots,
                machine_profiles_path=state.machine_profiles_path,
                backends=state.backends,
            )
        except ValueError as exc:
            state.setup_error = str(exc)
            state.shown_setup_error = False
            _show_setup_error(server, state)
            return
        for document in documents:
            replacement.open(document.path, document.text, document.version)
        state.index_ready.clear()
        state.workspace = replacement
        state.setup_error = None
        state.shown_setup_error = False
        if old is not None:
            old.close()
        await _check_and_publish(
            server,
            state,
            replacement.generation,
            debounce=False,
        )

    @server.feature(types.INITIALIZED)
    def initialized(params: types.InitializedParams) -> None:
        del params
        _show_setup_error(server, state)

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    async def did_open(params: types.DidOpenTextDocumentParams) -> None:
        workspace = state.workspace
        if workspace is None:
            _show_setup_error(server, state)
            return
        path = uri_to_path(params.text_document.uri)
        generation = workspace.open(
            path,
            params.text_document.text,
            params.text_document.version,
        )
        await _check_and_publish(server, state, generation)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    async def did_change(params: types.DidChangeTextDocumentParams) -> None:
        workspace = state.workspace
        if workspace is None:
            return
        path = uri_to_path(params.text_document.uri)
        document = server.workspace.get_text_document(params.text_document.uri)
        generation = workspace.change(path, document.source, params.text_document.version)
        await _check_and_publish(server, state, generation)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    async def did_save(params: types.DidSaveTextDocumentParams) -> None:
        workspace = state.workspace
        if workspace is None:
            return
        await _check_and_publish(server, state, workspace.generation, debounce=False)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    async def did_close(params: types.DidCloseTextDocumentParams) -> None:
        workspace = state.workspace
        if workspace is None:
            return
        generation = workspace.close_document(uri_to_path(params.text_document.uri))
        await _check_and_publish(server, state, generation)

    @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    async def symbols(
        params: types.DocumentSymbolParams,
    ) -> list[types.DocumentSymbol]:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return []
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return list(document_symbols(workspace.latest.index, path, text))

    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    async def definition(
        params: types.DefinitionParams,
    ) -> list[types.Location]:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return []
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return list(
            definition_locations(
                workspace.latest.index, path, text, params.position, workspace
            )
        )

    @server.feature(types.TEXT_DOCUMENT_REFERENCES)
    async def references(
        params: types.ReferenceParams,
    ) -> list[types.Location]:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return []
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return list(
            reference_locations(
                workspace.latest.index,
                path,
                text,
                params.position,
                workspace,
                include_declaration=params.context.include_declaration,
            )
        )

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    async def hover_request(params: types.HoverParams) -> types.Hover | None:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return None
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return hover(workspace.latest.index, path, text, params.position)

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(trigger_characters=["<", "=", ","]),
    )
    async def completion_request(
        params: types.CompletionParams,
    ) -> types.CompletionList:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return types.CompletionList(is_incomplete=False, items=[])
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return completions(workspace.latest, text, params.position)

    @server.feature(
        types.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
        types.SemanticTokensLegend(
            token_types=list(SEMANTIC_TOKEN_TYPES), token_modifiers=[]
        ),
    )
    async def semantic_tokens_request(
        params: types.SemanticTokensParams,
    ) -> types.SemanticTokens:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return types.SemanticTokens(data=[])
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return semantic_tokens(workspace.latest.index, path, text)

    @server.feature(types.SHUTDOWN)
    def shutdown(*args: object) -> None:
        del args
        state.index_ready.set()
        if state.workspace is not None:
            state.workspace.close()

    return server


async def _workspace_with_index(state: _ServerState) -> AuthoringWorkspace | None:
    workspace = state.workspace
    if workspace is None or workspace.latest.index is not None:
        return workspace
    try:
        await asyncio.wait_for(state.index_ready.wait(), timeout=_INDEX_WAIT_SECONDS)
    except TimeoutError:
        pass
    return state.workspace


async def _check_and_publish(
    server: LanguageServer,
    state: _ServerState,
    generation: int,
    *,
    debounce: bool = True,
) -> None:
    workspace = state.workspace
    if workspace is None:
        return
    if debounce:
        await asyncio.sleep(_DEBOUNCE_SECONDS)
    if generation != workspace.generation:
        return
    snapshot = await asyncio.to_thread(workspace.check, generation)
    if snapshot is None:
        return
    _publish(server, state, snapshot)


def _publish(
    server: LanguageServer, state: _ServerState, snapshot: WorkspaceSnapshot
) -> None:
    workspace = state.workspace
    if workspace is None:
        return
    if snapshot.index is not None:
        state.index_ready.set()
    grouped = diagnostics_by_path(snapshot)
    current_paths = set(grouped) | set(snapshot.versions)
    paths = current_paths | state.published_paths
    for path in sorted(paths, key=lambda item: item.as_posix()):
        diagnostics = [lsp_diagnostic(item, workspace) for item in grouped.get(path, ())]
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(
                uri=path_to_uri(path),
                diagnostics=diagnostics,
                version=snapshot.versions.get(path),
            )
        )
    state.published_paths = current_paths
    for diagnostic in snapshot.diagnostics:
        if diagnostic.span is None:
            server.window_log_message(
                types.LogMessageParams(
                    type=types.MessageType.Error
                    if diagnostic.severity == "error"
                    else types.MessageType.Warning,
                    message=f"{diagnostic.code}: {diagnostic.message}",
                )
            )


def _initialization_root(params: types.InitializeParams) -> Path:
    if params.workspace_folders:
        return uri_to_path(params.workspace_folders[0].uri)
    if params.root_uri:
        return uri_to_path(params.root_uri)
    if params.root_path:
        return Path(params.root_path).resolve()
    return Path.cwd().resolve()


def _options(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _path_option(options: dict[str, Any], name: str) -> Path | None:
    value = options.get(name)
    return Path(value).resolve() if isinstance(value, str) and value else None


def _path_tuple_option(options: dict[str, Any], name: str) -> tuple[Path, ...] | None:
    value = options.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return tuple(Path(item).resolve() for item in value)


def _string_tuple_option(options: dict[str, Any], name: str) -> tuple[str, ...] | None:
    value = options.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return tuple(value)


def _show_setup_error(server: LanguageServer, state: _ServerState) -> None:
    if state.setup_error is None or state.shown_setup_error:
        return
    state.shown_setup_error = True
    server.window_show_message(
        types.ShowMessageParams(
            type=types.MessageType.Error,
            message=(
                f"TSL language server setup failed: {state.setup_error}. "
                "Install tslc[editor] in the workspace environment or configure "
                "an explicit server command."
            ),
        )
    )


__all__ = ("SERVER_NAME", "SERVER_VERSION", "create_server")
