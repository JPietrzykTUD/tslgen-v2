"""Workspace overlays, parsed-document reuse, and stale-result suppression."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, RLock
from types import MappingProxyType

from tslc.authoring import CheckResult, ParsedDocumentCache, SourceOverlay, check_catalog
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.machine_profiles import (
    MachineProfile,
    load_machine_profiles_checked,
    target_feature_names,
)
from tslc.catalog.model import Catalog
from tslc.catalog_index import CatalogIndex, build_catalog_index
from tslc.diagnostics import Diagnostic
from tslc.project_config import ProjectConfig, discover_config, load_project_config
from tslc.syntax.ast import OuterTslParseResult


@dataclass(frozen=True, slots=True)
class AuthoringConfig:
    root: Path
    source_roots: tuple[Path, ...]
    machine_profiles_path: Path | None
    backends: tuple[str, ...]
    preferred_profiles: tuple[str, ...] = ()
    target_features: tuple[str, ...] = ()
    profiles: Mapping[str, MachineProfile] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class OpenDocument:
    path: Path
    text: str
    version: int | None


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    generation: int
    catalog: Catalog | None
    index: CatalogIndex | None
    diagnostics: tuple[Diagnostic, ...]
    source_paths: tuple[Path, ...]
    versions: Mapping[Path, int | None]
    target_features: tuple[str, ...] = ()
    parsed: OuterTslParseResult | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "versions", MappingProxyType(dict(self.versions)))


class AuthoringWorkspace:
    """Mutable editor session state around pure compiler authoring checks."""

    def __init__(self, config: AuthoringConfig) -> None:
        self.config = config
        self.cache = ParsedDocumentCache()
        self._lock = RLock()
        self._check_lock = Lock()
        self._documents: dict[Path, OpenDocument] = {}
        self._generation = 0
        self._closed = False
        self._latest = WorkspaceSnapshot(
            0, None, None, (), (), {}, config.target_features
        )

    @classmethod
    def from_root(
        cls,
        root: Path,
        *,
        config_path: Path | None = None,
        source_roots: tuple[Path, ...] | None = None,
        machine_profiles_path: Path | None = None,
        backends: tuple[str, ...] | None = None,
    ) -> "AuthoringWorkspace":
        root = root.resolve()
        project = _load_config(root, config_path)
        configured_sources = source_roots or (
            project.sources if project is not None else _layout_sources(root)
        )
        if not configured_sources:
            raise ValueError(
                f"no TSL corpus configured under {root}; create tslc.toml or provide source roots"
            )
        selected_profiles = (
            machine_profiles_path.resolve()
            if machine_profiles_path is not None
            else project.machine_profiles
            if project is not None
            else _layout_profiles(root)
        )
        profiles = _configured_profiles(selected_profiles)
        return cls(
            AuthoringConfig(
                root=root,
                source_roots=tuple(path.resolve() for path in configured_sources),
                machine_profiles_path=selected_profiles,
                backends=backends or (
                    project.backends if project is not None else registered_backend_ids()
                ),
                preferred_profiles=(
                    project.authoring_profiles if project is not None else ()
                ),
                target_features=target_feature_names(profiles),
                profiles=profiles,
            )
        )

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def latest(self) -> WorkspaceSnapshot:
        with self._lock:
            return self._latest

    @property
    def open_documents(self) -> tuple[OpenDocument, ...]:
        with self._lock:
            return tuple(
                self._documents[path]
                for path in sorted(self._documents, key=lambda item: item.as_posix())
            )

    def open(self, path: Path, text: str, version: int | None) -> int:
        return self._replace(path, text, version)

    def change(self, path: Path, text: str, version: int | None) -> int:
        return self._replace(path, text, version)

    def close_document(self, path: Path) -> int:
        with self._lock:
            self._documents.pop(path.resolve(), None)
            self._generation += 1
            return self._generation

    def document_text(self, path: Path) -> str | None:
        path = path.resolve()
        with self._lock:
            opened = self._documents.get(path)
            if opened is not None:
                return opened.text
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def document_version(self, path: Path) -> int | None:
        with self._lock:
            opened = self._documents.get(path.resolve())
            return None if opened is None else opened.version

    def check(self, generation: int | None = None) -> WorkspaceSnapshot | None:
        """Check one generation; return None if it was superseded."""

        with self._check_lock:
            with self._lock:
                requested = self._generation if generation is None else generation
                if self._closed or requested != self._generation:
                    return None
                overlays = tuple(
                    SourceOverlay(item.path, item.text, item.version)
                    for item in self.open_documents
                )
                config = self.config
            result = check_catalog(
                config.source_roots,
                backends=config.backends,
                overlays=overlays,
                cache=self.cache,
            )
            if result.index is None and self.latest.index is None and overlays:
                # A server can first see a workspace through an already-dirty buffer.
                # Preserve its overlay diagnostics, but seed navigation from the valid
                # saved corpus so definition/hover do not start empty.
                baseline = check_catalog(
                    config.source_roots,
                    backends=config.backends,
                    cache=self.cache,
                )
                if baseline.index is not None:
                    result = replace(
                        result,
                        catalog=baseline.catalog,
                        index=(
                            build_catalog_index(
                                baseline.catalog,
                                result.parsed,
                                cache=self.cache.index_cache,
                            )
                            if baseline.catalog is not None
                            and result.parsed is not None
                            else baseline.index
                        ),
                    )
            return self._accept(requested, result)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._generation += 1

    def _replace(self, path: Path, text: str, version: int | None) -> int:
        path = path.resolve()
        with self._lock:
            self._documents[path] = OpenDocument(path, text, version)
            self._generation += 1
            return self._generation

    def _accept(self, generation: int, result: CheckResult) -> WorkspaceSnapshot | None:
        with self._lock:
            if self._closed or generation != self._generation:
                return None
            previous = self._latest
            catalog = result.catalog if result.catalog is not None else previous.catalog
            index = result.index if result.index is not None else previous.index
            versions = {item.path: item.version for item in self._documents.values()}
            paths = tuple(
                sorted(
                    {*(path.resolve() for path in result.source_paths), *versions},
                    key=lambda item: item.as_posix(),
                )
            )
            snapshot = WorkspaceSnapshot(
                generation,
                catalog,
                index,
                result.diagnostics,
                paths,
                versions,
                self.config.target_features,
                result.parsed,
            )
            self._latest = snapshot
            return snapshot


def _load_config(root: Path, path: Path | None) -> ProjectConfig | None:
    selected = path or discover_config(root)
    return load_project_config(selected) if selected is not None else None


def _layout_sources(root: Path) -> tuple[Path, ...]:
    candidate = root / "tsldata"
    return (candidate,) if candidate.is_dir() else ()


def _layout_profiles(root: Path) -> Path | None:
    candidate = root / "supplementary" / "buildsystem" / "machine_profiles.json"
    return candidate if candidate.is_file() else None


def _configured_profiles(path: Path | None) -> Mapping[str, MachineProfile]:
    if path is None:
        return MappingProxyType({})
    return load_machine_profiles_checked(path).profiles


__all__ = (
    "AuthoringConfig",
    "AuthoringWorkspace",
    "OpenDocument",
    "WorkspaceSnapshot",
)
