from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.values import CatalogValue


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
