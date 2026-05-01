from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from tslgen.core.diagnostics import SourceSpan
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.values import CatalogValue


ACTIVE_BACKEND_IDS: tuple[str, ...] = ("cpp", "rust")
DEFERRED_BACKEND_IDS: tuple[str, ...] = ("c17",)


def is_active_backend_id(backend_id: str) -> bool:
    return backend_id in ACTIVE_BACKEND_IDS


def is_deferred_backend_id(backend_id: str) -> bool:
    return backend_id in DEFERRED_BACKEND_IDS


def backend_id_list_text(backend_ids: tuple[str, ...]) -> str:
    if not backend_ids:
        return "none"
    return ", ".join(repr(backend_id) for backend_id in backend_ids)


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    kind: str
    logical_name: str
    extension: str

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("artifact kind must be non-empty")
        if not self.logical_name:
            raise ValueError("artifact logical name must be non-empty")
        if not self.extension:
            raise ValueError("artifact extension must be non-empty")
        if self.extension.startswith("."):
            raise ValueError("artifact extension must not include a leading dot")
        path = PurePosixPath(self.logical_name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact logical name must be a relative path")

    @property
    def target_path(self) -> PurePosixPath:
        return PurePosixPath(f"{self.logical_name}.{self.extension}")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.target_path.as_posix(), self.kind, self.extension)


@dataclass(frozen=True, slots=True)
class BackendTemplatePolicy:
    primary_default: str | None = None
    primary_fallback: str | None = None
    specialization_default: str | None = None
    specialization_overrides: FrozenMap[str, str] = field(
        default_factory=FrozenMap.empty
    )
    wrappers: str | None = None
    trait: str | None = None
    extra_fields: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)


@dataclass(frozen=True, slots=True)
class BackendManifest:
    version: int
    backend_id: str
    language_id: str
    artifacts: tuple[ArtifactSpec, ...]
    template_policy: BackendTemplatePolicy = field(
        default_factory=BackendTemplatePolicy
    )
    source_name: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("backend manifest version must be positive")
        if not self.backend_id:
            raise ValueError("backend id must be non-empty")
        if not self.language_id:
            raise ValueError("backend language id must be non-empty")
        if not self.artifacts:
            raise ValueError("backend manifest must declare at least one artifact")
        artifacts = tuple(sorted(self.artifacts, key=lambda artifact: artifact.key))
        target_paths = [artifact.target_path.as_posix() for artifact in artifacts]
        if len(target_paths) != len(set(target_paths)):
            raise ValueError("backend manifest artifact target paths must be unique")
        object.__setattr__(self, "artifacts", artifacts)


@dataclass(frozen=True, slots=True)
class BackendManifestSet:
    manifests: tuple[BackendManifest, ...]
    manifests_by_id: FrozenMap[str, BackendManifest] = field(init=False)

    def __post_init__(self) -> None:
        manifests = tuple(sorted(self.manifests, key=lambda item: item.backend_id))
        object.__setattr__(self, "manifests", manifests)
        object.__setattr__(
            self,
            "manifests_by_id",
            FrozenMap((manifest.backend_id, manifest) for manifest in manifests),
        )

    @property
    def backend_ids(self) -> tuple[str, ...]:
        return tuple(manifest.backend_id for manifest in self.manifests)


@dataclass(frozen=True, slots=True)
class LanguageTypeEntry:
    source_type: str
    target_type: str
    fields: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        if not self.source_type:
            raise ValueError("language type source key must be non-empty")
        if not self.target_type:
            raise ValueError("language type target name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.source_type, self.target_type)


@dataclass(frozen=True, slots=True)
class LanguageTypeMap:
    backend_id: str
    entries: tuple[LanguageTypeEntry, ...]
    source_span: SourceSpan | None = None
    entries_by_type: FrozenMap[str, LanguageTypeEntry] = field(init=False)

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("language type map backend id must be non-empty")
        entries = tuple(sorted(self.entries, key=lambda entry: entry.key))
        object.__setattr__(self, "entries", entries)
        object.__setattr__(
            self,
            "entries_by_type",
            FrozenMap((entry.source_type, entry) for entry in entries),
        )


@dataclass(frozen=True, slots=True)
class TranslationSnippet:
    name: str
    template: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("translation snippet name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.name, self.template)


@dataclass(frozen=True, slots=True)
class TranslationMap:
    backend_id: str
    snippets: tuple[TranslationSnippet, ...]
    source_span: SourceSpan | None = None
    snippets_by_name: FrozenMap[str, TranslationSnippet] = field(init=False)

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("translation map backend id must be non-empty")
        snippets = tuple(sorted(self.snippets, key=lambda snippet: snippet.key))
        object.__setattr__(self, "snippets", snippets)
        object.__setattr__(
            self,
            "snippets_by_name",
            FrozenMap((snippet.name, snippet) for snippet in snippets),
        )


@dataclass(frozen=True, slots=True)
class BackendMetadataCatalog:
    language_maps: tuple[LanguageTypeMap, ...] = ()
    translation_maps: tuple[TranslationMap, ...] = ()
    language_maps_by_backend: FrozenMap[str, LanguageTypeMap] = field(init=False)
    translation_maps_by_backend: FrozenMap[str, TranslationMap] = field(init=False)

    def __post_init__(self) -> None:
        language_maps = tuple(
            sorted(self.language_maps, key=lambda item: item.backend_id)
        )
        translation_maps = tuple(
            sorted(self.translation_maps, key=lambda item: item.backend_id)
        )
        object.__setattr__(self, "language_maps", language_maps)
        object.__setattr__(self, "translation_maps", translation_maps)
        object.__setattr__(
            self,
            "language_maps_by_backend",
            FrozenMap((item.backend_id, item) for item in language_maps),
        )
        object.__setattr__(
            self,
            "translation_maps_by_backend",
            FrozenMap((item.backend_id, item) for item in translation_maps),
        )


@dataclass(frozen=True, slots=True)
class BackendMetadataBoundary:
    manifests: BackendManifestSet
    metadata: BackendMetadataCatalog
    active_backend_ids: tuple[str, ...] = ACTIVE_BACKEND_IDS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "active_backend_ids",
            tuple(sorted(self.active_backend_ids)),
        )
