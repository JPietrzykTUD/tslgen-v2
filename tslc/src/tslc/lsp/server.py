"""pygls transport wiring for the compiler-owned authoring workspace."""

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from tslc.diagnostics import SourceSpan
from tslc.lsp.features import (
    SEMANTIC_TOKEN_TYPES,
    code_actions,
    completions,
    definition_locations,
    diagnostics_by_path,
    document_symbols,
    hover,
    lsp_diagnostic,
    reference_locations,
    semantic_tokens,
)
from tslc.lsp.positions import path_to_uri, source_position, span_to_range, uri_to_path
from tslc.lsp.primitive_explorer import (
    PrimitiveExplorer,
    PrimitiveExplorerCache,
    primitive_explorer,
)
from tslc.lsp.primitive_scaffold import (
    primitive_scaffold,
    primitive_shape_choices,
)
from tslc.lsp.specialization_context import specialization_context
from tslc.lsp.workspace import AuthoringWorkspace, WorkspaceSnapshot
from tslc.version import package_version

SERVER_NAME = "tslc"
SERVER_VERSION = package_version()
_DEBOUNCE_SECONDS = 0.15
SPECIALIZATION_CONTEXT_METHOD = "tsl/specializationContext"
PRIMITIVE_SCAFFOLD_CHOICES_METHOD = "tsl/primitiveScaffoldChoices"
PRIMITIVE_SCAFFOLD_METHOD = "tsl/primitiveScaffold"
PRIMITIVE_EXPLORER_METHOD = "tsl/primitiveExplorer"


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
    initial_check_complete: asyncio.Event = field(default_factory=asyncio.Event)
    explorer_cache: PrimitiveExplorerCache = field(
        default_factory=PrimitiveExplorerCache
    )


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
        state.initial_check_complete.clear()
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
        state.initial_check_complete.clear()
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
    async def initialized(params: types.InitializedParams) -> None:
        del params
        _show_setup_error(server, state)
        workspace = state.workspace
        if workspace is not None:
            await _check_and_publish(
                server,
                state,
                workspace.generation,
                debounce=False,
            )

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
        types.CompletionOptions(trigger_characters=["<", "=", ",", "["]),
    )
    async def completion_request(
        params: types.CompletionParams,
    ) -> types.CompletionList:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return types.CompletionList(is_incomplete=False, items=[])
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return completions(workspace.latest, path, text, params.position)

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

    @server.feature(
        types.TEXT_DOCUMENT_CODE_ACTION,
        types.CodeActionOptions(
            code_action_kinds=[types.CodeActionKind.QuickFix],
            resolve_provider=False,
        ),
    )
    async def code_action_request(
        params: types.CodeActionParams,
    ) -> list[types.CodeAction]:
        workspace = await _workspace_with_index(state)
        if workspace is None:
            return []
        path = uri_to_path(params.text_document.uri)
        text = workspace.document_text(path) or ""
        return list(
            code_actions(
                workspace.latest,
                path,
                text,
                params.range,
                tuple(params.context.diagnostics),
                workspace,
            )
        )

    @server.feature(SPECIALIZATION_CONTEXT_METHOD)
    async def specialization_context_request(params: Any) -> dict[str, object]:
        workspace = await _workspace_with_index(state)
        if workspace is None or workspace.latest.catalog is None:
            return {
                "primitive": None,
                "extension": None,
                "type": None,
                "contextualExtensions": [],
                "contextualTypes": [],
                "profiles": [],
                "slots": [],
            }
        uri = _document_uri(params)
        position = _position(params)
        path = uri_to_path(uri) if uri is not None else None
        text = workspace.document_text(path) if path is not None else None
        line, column = (
            source_position(text, position)
            if text is not None and position is not None
            else (None, None)
        )
        backend = _field(params, "backend")
        selected_backend = backend if isinstance(backend, str) else "cpp"
        context = await asyncio.to_thread(
            specialization_context,
            workspace.latest.catalog,
            workspace.latest.parsed,
            workspace.config.profiles,
            backend=selected_backend,
            path=path,
            line=line,
            column=column,
        )
        return context.payload()

    @server.feature(PRIMITIVE_SCAFFOLD_CHOICES_METHOD)
    async def primitive_scaffold_choices_request(
        params: Any,
    ) -> dict[str, object]:
        del params
        workspace = await _workspace_with_index(state)
        if workspace is None or workspace.latest.catalog is None:
            return {"shapes": []}
        return {
            "shapes": [
                choice.payload()
                for choice in primitive_shape_choices(workspace.latest.catalog)
            ]
        }

    @server.feature(PRIMITIVE_SCAFFOLD_METHOD)
    async def primitive_scaffold_request(params: Any) -> dict[str, object]:
        workspace = await _workspace_with_index(state)
        if workspace is None or workspace.latest.catalog is None:
            return _primitive_scaffold_error("the TSL catalog is not available")
        uri = _document_uri(params)
        path = uri_to_path(uri) if uri is not None else None
        text = workspace.document_text(path) if path is not None else None
        signature = _field(params, "signature")
        name = _field(params, "name")
        if path is None or text is None:
            return _primitive_scaffold_error("the target TSL document is not available")
        if not isinstance(signature, str) or not isinstance(name, str):
            return _primitive_scaffold_error(
                "primitive scaffold requires string signature and name values",
                document_version=workspace.document_version(path),
            )
        try:
            scaffold = primitive_scaffold(
                workspace.latest.catalog,
                text,
                signature=signature,
                name=name,
            )
        except ValueError as exc:
            return _primitive_scaffold_error(
                str(exc), document_version=workspace.document_version(path)
            )
        return scaffold.payload(document_version=workspace.document_version(path))

    @server.feature(PRIMITIVE_EXPLORER_METHOD)
    async def primitive_explorer_request(params: Any) -> dict[str, object]:
        workspace = await _workspace_with_index(state)
        snapshot = workspace.latest if workspace is not None else None
        if (
            workspace is None
            or snapshot is None
            or snapshot.catalog is None
            or snapshot.index is None
        ):
            return _empty_primitive_explorer()
        scope_uri = _field(params, "scopeUri")
        scope_path = (
            uri_to_path(scope_uri) if isinstance(scope_uri, str) and scope_uri else None
        )
        requested_profile = _field(params, "profile")
        requested_mode = _field(params, "mode")
        requested_backend = _field(params, "backend")
        selected_primitive = _field(params, "primitive")
        explorer = await asyncio.to_thread(
            primitive_explorer,
            snapshot.catalog,
            snapshot.index,
            workspace.config.profiles,
            workspace.config.backends,
            mode=(
                requested_mode
                if requested_mode in ("authored", "resolved")
                else None
            ),
            profile=requested_profile if isinstance(requested_profile, str) else None,
            backend=requested_backend if isinstance(requested_backend, str) else None,
            path=scope_path,
            selected_primitive=(
                selected_primitive if isinstance(selected_primitive, str) else None
            ),
            preferred_profiles=workspace.config.preferred_profiles,
            stale=any(item.severity == "error" for item in snapshot.diagnostics),
            cache=state.explorer_cache,
        )
        return _primitive_explorer_payload(explorer, workspace)

    @server.feature(types.SHUTDOWN)
    def shutdown(*args: object) -> None:
        del args
        state.initial_check_complete.set()
        if state.workspace is not None:
            state.workspace.close()

    return server


async def _workspace_with_index(state: _ServerState) -> AuthoringWorkspace | None:
    workspace = state.workspace
    if workspace is None or workspace.latest.index is not None:
        return workspace
    await state.initial_check_complete.wait()
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
    try:
        snapshot = await asyncio.to_thread(workspace.check, generation)
    except Exception as error:  # noqa: BLE001 — a wedged server is worse than a broad catch
        _report_check_failure(server, state, generation, error)
        return
    if snapshot is None:
        return
    _publish(server, state, snapshot)


def _report_check_failure(
    server: LanguageServer,
    state: _ServerState,
    generation: int,
    error: Exception,
) -> None:
    """Release waiting requests and surface one actionable failure message.

    The last successful snapshot is deliberately retained: index-backed requests
    degrade to the previous (or empty) projection instead of hanging forever on
    the unset initial-check event.
    """

    workspace = state.workspace
    if workspace is not None and generation == workspace.generation:
        state.initial_check_complete.set()
    server.window_log_message(
        types.LogMessageParams(
            type=types.MessageType.Error,
            message=(
                "TSL corpus check failed unexpectedly: "
                f"{error!r}\n{traceback.format_exc()}"
            ),
        )
    )
    server.window_show_message(
        types.ShowMessageParams(
            type=types.MessageType.Error,
            message=(
                "TSL corpus check failed unexpectedly; language features may use"
                " stale results. See the TSL language server log for details."
            ),
        )
    )


def _publish(
    server: LanguageServer, state: _ServerState, snapshot: WorkspaceSnapshot
) -> None:
    workspace = state.workspace
    if workspace is None:
        return
    state.initial_check_complete.set()
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


def _document_uri(params: Any) -> str | None:
    document = _field(params, "textDocument", "text_document")
    if document is None:
        return None
    uri = _field(document, "uri")
    return uri if isinstance(uri, str) else None


def _position(params: Any) -> types.Position | None:
    value = _field(params, "position")
    if value is None:
        return None
    line = _field(value, "line")
    character = _field(value, "character")
    if not isinstance(line, int) or not isinstance(character, int):
        return None
    return types.Position(line=line, character=character)


def _field(value: Any, *names: str) -> Any:
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
        return None
    for name in names:
        result = getattr(value, name, None)
        if result is not None:
            return result
    return None


def _primitive_scaffold_error(
    message: str, *, document_version: int | None = None
) -> dict[str, object]:
    return {
        "insertText": "",
        "focusOffset": 0,
        "documentVersion": document_version,
        "error": message,
    }


def _empty_primitive_explorer() -> dict[str, object]:
    return {
        "mode": "authored",
        "profile": "",
        "backend": "",
        "profiles": [],
        "backends": [],
        "generation": 0,
        "stale": False,
        "primitives": [],
        "selectedPrimitive": None,
        "slots": [],
    }


def _primitive_explorer_payload(
    explorer: PrimitiveExplorer, workspace: AuthoringWorkspace
) -> dict[str, object]:
    texts: dict[Path, str] = {}
    return {
        "mode": explorer.mode,
        "profile": explorer.profile,
        "backend": explorer.backend,
        "profiles": list(explorer.profiles),
        "backends": list(explorer.backends),
        "generation": workspace.generation,
        "stale": explorer.stale,
        "selectedPrimitive": explorer.selected_primitive,
        "primitives": [
            {
                "name": primitive.name,
                "signatures": list(primitive.signatures),
                "definitions": [
                    _location_payload(span, workspace, texts)
                    for span in primitive.definitions
                ],
                "availableSlots": primitive.available_slots,
                "totalSlots": primitive.total_slots,
                "calls": list(primitive.calls),
                "calledBy": list(primitive.called_by),
            }
            for primitive in explorer.primitives
        ],
        "slots": [
            {
                "extension": slot.extension,
                "type": slot.type_tag,
                "status": slot.status,
                "detail": slot.detail,
                "available": slot.available,
                "origins": list(slot.origins),
                # Retain these aliases for older clients of the custom method.
                "unavailableReason": slot.detail,
                "implementations": [
                    {
                        "primitive": implementation.primitive,
                        "signature": implementation.signature,
                        "parameters": list(implementation.parameters),
                        "extension": implementation.extension,
                        "typeGroup": implementation.type_group,
                        "selectorPath": list(implementation.selector_path),
                        "origin": implementation.origin,
                        "location": _location_payload(
                            implementation.source, workspace, texts
                        ),
                    }
                    for implementation in slot.implementations
                ],
            }
            for slot in explorer.slots
        ],
    }


def _location_payload(
    span: SourceSpan,
    workspace: AuthoringWorkspace,
    texts: dict[Path, str],
) -> dict[str, object]:
    path = span.path.resolve()
    text = texts.get(path)
    if text is None:
        text = workspace.document_text(path) or ""
        texts[path] = text
    range_ = span_to_range(span, text)
    return {
        "uri": path_to_uri(span.path),
        "range": {
            "start": {
                "line": range_.start.line,
                "character": range_.start.character,
            },
            "end": {
                "line": range_.end.line,
                "character": range_.end.character,
            },
        },
    }


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


__all__ = (
    "PRIMITIVE_SCAFFOLD_CHOICES_METHOD",
    "PRIMITIVE_SCAFFOLD_METHOD",
    "PRIMITIVE_EXPLORER_METHOD",
    "SERVER_NAME",
    "SERVER_VERSION",
    "SPECIALIZATION_CONTEXT_METHOD",
    "create_server",
)
