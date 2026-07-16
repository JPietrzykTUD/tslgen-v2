"""Public, side-effect-free authoring checks and editor overlay state."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from tslc.backend.registry import registered_backend_ids
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.catalog.validation import validate_catalog
from tslc.catalog_index import CatalogIndex, CatalogIndexCache, build_catalog_index
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslc.sources import SourceDocument, SourceLoader, expand_source_paths
from tslc.syntax.ast import OuterTslParseResult, ParsedOuterTslDocument
from tslc.syntax.parser import TslParser


@dataclass(frozen=True, slots=True)
class SourceOverlay:
    path: Path
    text: str
    version: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocumentState:
    path: Path
    digest: str
    document: ParsedOuterTslDocument | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class CheckResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]
    skipped: tuple[object, ...] = ()
    source_paths: tuple[Path, ...] = ()
    parsed: OuterTslParseResult | None = None
    index: CatalogIndex | None = None


# Compatibility for callers written against the initial check API.
CatalogCheckResult = CheckResult


class ParsedDocumentCache:
    """Workspace-scoped parsed-document reuse keyed by path and content digest."""

    def __init__(self, grammar_text: str | None = None) -> None:
        self._grammar_text = grammar_text or load_default_tsl_grammar()
        self._parser = TslParser(self._grammar_text)
        self.index_cache = CatalogIndexCache()
        self._states: dict[Path, ParsedDocumentState] = {}
        self._last_reparsed: tuple[Path, ...] = ()

    @property
    def states(self) -> tuple[ParsedDocumentState, ...]:
        return tuple(self._states[path] for path in sorted(self._states, key=_path_key))

    @property
    def last_reparsed(self) -> tuple[Path, ...]:
        return self._last_reparsed

    def invalidate(self) -> None:
        self._states.clear()
        self.index_cache = CatalogIndexCache()
        self._last_reparsed = ()

    def parse(self, documents: tuple[SourceDocument, ...]) -> OuterTslParseResult:
        normalized = _normalize_documents(documents)
        current_paths = {document.path for document in normalized}
        for stale in tuple(path for path in self._states if path not in current_paths):
            del self._states[stale]

        reparsed: list[Path] = []
        for source in normalized:
            cached = self._states.get(source.path)
            if cached is not None and cached.digest == source.digest:
                continue
            result = self._parser.parse((source,))
            parsed_document = result.documents[0] if result.documents else None
            self._states[source.path] = ParsedDocumentState(
                path=source.path,
                digest=source.digest,
                document=parsed_document,
                diagnostics=result.diagnostics,
            )
            reparsed.append(source.path)
        self._last_reparsed = tuple(reparsed)
        return self.result()

    def result(self) -> OuterTslParseResult:
        states = self.states
        return OuterTslParseResult(
            documents=tuple(
                state.document for state in states if state.document is not None
            ),
            diagnostics=sort_diagnostics(
                diagnostic
                for state in states
                for diagnostic in state.diagnostics
            ),
        )


def check_catalog(
    source_paths: Iterable[Path | str],
    *,
    backends: Iterable[str] = registered_backend_ids(),
    overlays: Iterable[SourceOverlay] = (),
    cache: ParsedDocumentCache | None = None,
) -> CheckResult:
    """Validate a complete corpus without profiles, selection, or rendering."""

    expanded = expand_source_paths(source_paths)
    loaded = SourceLoader().load(expanded)
    if has_errors(loaded.diagnostics):
        return CheckResult(
            catalog=None,
            diagnostics=sort_diagnostics(loaded.diagnostics),
            source_paths=expanded,
        )
    documents, overlay_diagnostics = apply_overlays(
        loaded.documents, tuple(overlays)
    )
    if has_errors(overlay_diagnostics):
        return CheckResult(
            catalog=None,
            diagnostics=sort_diagnostics(overlay_diagnostics),
            source_paths=expanded,
        )
    result = check_documents(
        documents,
        required_backends=tuple(backends),
        cache=cache,
    )
    return CheckResult(
        catalog=result.catalog,
        diagnostics=sort_diagnostics((*overlay_diagnostics, *result.diagnostics)),
        skipped=result.skipped,
        source_paths=expanded,
        parsed=result.parsed,
        index=result.index,
    )


def apply_overlays(
    documents: tuple[SourceDocument, ...],
    overlays: tuple[SourceOverlay, ...],
) -> tuple[tuple[SourceDocument, ...], tuple[Diagnostic, ...]]:
    """Replace normalized disk documents with deterministic in-memory text."""

    by_path: dict[Path, SourceDocument] = {}
    diagnostics: list[Diagnostic] = []
    for document in sorted(documents, key=lambda item: _path_key(item.path.resolve())):
        path = document.path.resolve()
        if path in by_path:
            diagnostics.append(_duplicate_path(path, "source document"))
            continue
        by_path[path] = SourceDocument(path, document.text, document.digest, document.kind)

    seen_overlays: set[Path] = set()
    for overlay in sorted(overlays, key=lambda item: _path_key(item.path.resolve())):
        path = overlay.path.resolve()
        if path in seen_overlays:
            diagnostics.append(_duplicate_path(path, "source overlay"))
            continue
        seen_overlays.add(path)
        by_path[path] = SourceDocument(
            path=path,
            text=overlay.text,
            digest=sha256(overlay.text.encode("utf-8")).hexdigest(),
            kind="tsl",
        )
    return (
        tuple(by_path[path] for path in sorted(by_path, key=_path_key)),
        sort_diagnostics(diagnostics),
    )


def check_documents(
    documents: tuple[SourceDocument, ...],
    *,
    required_backends: tuple[str, ...] = registered_backend_ids(),
    cache: ParsedDocumentCache | None = None,
) -> CheckResult:
    """Parse and validate already-loaded source documents without filesystem I/O."""

    normalized = _normalize_documents(documents)
    parsed = (
        cache.parse(normalized)
        if cache is not None
        else TslParser(load_default_tsl_grammar()).parse(normalized)
    )
    result = check_parsed_documents(
        parsed,
        required_backends=required_backends,
        index_cache=cache.index_cache if cache is not None else None,
    )
    return CheckResult(
        catalog=result.catalog,
        diagnostics=result.diagnostics,
        skipped=result.skipped,
        source_paths=tuple(document.path for document in normalized),
        parsed=parsed,
        index=result.index,
    )


def check_parsed_documents(
    parsed: OuterTslParseResult,
    *,
    required_backends: tuple[str, ...] = registered_backend_ids(),
    index_cache: CatalogIndexCache | None = None,
) -> CheckResult:
    """Promote and validate one deterministic complete parsed corpus."""

    diagnostics: list[Diagnostic] = list(parsed.diagnostics)
    if has_errors(diagnostics):
        return CheckResult(None, sort_diagnostics(diagnostics), parsed=parsed)
    built = CatalogBuilder().build(parsed)
    diagnostics.extend(built.diagnostics)
    if built.catalog is None or has_errors(diagnostics):
        return CheckResult(None, sort_diagnostics(diagnostics), parsed=parsed)
    diagnostics.extend(
        validate_catalog(
            built.catalog,
            parsed,
            required_backends=required_backends,
            supported_backends=registered_backend_ids(),
        )
    )
    catalog = None if has_errors(diagnostics) else built.catalog
    return CheckResult(
        catalog,
        sort_diagnostics(diagnostics),
        parsed=parsed,
        index=(
            build_catalog_index(catalog, parsed, cache=index_cache)
            if catalog is not None
            else None
        ),
    )


def _normalize_documents(
    documents: tuple[SourceDocument, ...],
) -> tuple[SourceDocument, ...]:
    by_path: dict[Path, SourceDocument] = {}
    for document in documents:
        path = document.path.resolve()
        if path in by_path:
            # The filesystem and overlay boundary owns a user-facing duplicate
            # diagnostic. This pure helper keeps the first value deterministic.
            continue
        by_path[path] = SourceDocument(path, document.text, document.digest, document.kind)
    return tuple(by_path[path] for path in sorted(by_path, key=_path_key))


def _duplicate_path(path: Path, kind: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-AUTHORING-DUPLICATE-PATH",
        message=f"duplicate normalized {kind} path {path}",
        location=SourceLocation(path, 1, 1),
    )


def _path_key(path: Path) -> str:
    return path.as_posix()


__all__ = (
    "CatalogCheckResult",
    "CheckResult",
    "ParsedDocumentCache",
    "ParsedDocumentState",
    "SourceOverlay",
    "apply_overlays",
    "check_catalog",
    "check_documents",
    "check_parsed_documents",
)
