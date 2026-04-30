from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    backend_id: str
    kind: str
    logical_path: PurePosixPath
    candidate_ids: tuple[str, ...] = ()
    dependency_primitive_names: tuple[str, ...] = ()
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("artifact backend id must be non-empty")
        if not self.kind:
            raise ValueError("artifact kind must be non-empty")
        path = PurePosixPath(self.logical_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact logical path must be relative")
        object.__setattr__(self, "logical_path", path)
        object.__setattr__(self, "candidate_ids", tuple(sorted(self.candidate_ids)))
        object.__setattr__(
            self,
            "dependency_primitive_names",
            tuple(sorted(self.dependency_primitive_names)),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.backend_id,
            self.logical_path.as_posix(),
            self.kind,
            self.candidate_ids,
            self.dependency_primitive_names,
        )


@dataclass(frozen=True, slots=True)
class ArtifactPlan:
    backend_id: str
    descriptors: tuple[ArtifactDescriptor, ...]
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)
    descriptors_by_path: FrozenMap[str, ArtifactDescriptor] = field(init=False)

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("artifact plan backend id must be non-empty")
        descriptors = tuple(sorted(self.descriptors, key=lambda item: item.key))
        object.__setattr__(self, "descriptors", descriptors)
        object.__setattr__(
            self,
            "descriptors_by_path",
            FrozenMap(
                (descriptor.logical_path.as_posix(), descriptor)
                for descriptor in descriptors
            ),
    )


@dataclass(frozen=True, slots=True)
class Artifact:
    logical_path: PurePosixPath
    content: str
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        path = PurePosixPath(self.logical_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact logical path must be relative")
        object.__setattr__(self, "logical_path", path)

    @property
    def key(self) -> tuple[str, str]:
        return (self.logical_path.as_posix(), self.content_digest)

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactSet:
    artifacts: tuple[Artifact, ...]
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)
    artifacts_by_path: FrozenMap[str, Artifact] = field(init=False)

    def __post_init__(self) -> None:
        artifacts = tuple(sorted(self.artifacts, key=lambda artifact: artifact.key))
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(
            self,
            "artifacts_by_path",
            FrozenMap(
                (artifact.logical_path.as_posix(), artifact)
                for artifact in artifacts
            ),
        )


def artifact_plan_from_descriptors(
    backend_id: str,
    descriptors: tuple[ArtifactDescriptor, ...],
    *,
    metadata: FrozenMap[str, CatalogValue] | None = None,
) -> Result[ArtifactPlan]:
    diagnostics: list[Diagnostic] = []
    paths = [descriptor.logical_path.as_posix() for descriptor in descriptors]
    for path in sorted(path for path in set(paths) if paths.count(path) > 1):
        diagnostics.append(
            Diagnostic.error(
                "TSL-ARTIFACT-DUPLICATE-TARGET",
                f"artifact plan for backend {backend_id!r} defines duplicate "
                f"logical target {path!r}",
            )
        )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        ArtifactPlan(
            backend_id=backend_id,
            descriptors=descriptors,
            metadata=metadata or FrozenMap.empty(),
        ),
        diagnostics=ordered,
    )


def artifact_set_from_artifacts(
    artifacts: tuple[Artifact, ...],
    *,
    metadata: FrozenMap[str, CatalogValue] | None = None,
) -> Result[ArtifactSet]:
    diagnostics: list[Diagnostic] = []
    paths = [artifact.logical_path.as_posix() for artifact in artifacts]
    for path in sorted(path for path in set(paths) if paths.count(path) > 1):
        diagnostics.append(
            Diagnostic.error(
                "TSL-ARTIFACT-DUPLICATE-RENDERED-TARGET",
                f"rendered artifact set defines duplicate logical target {path!r}",
            )
        )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        ArtifactSet(
            artifacts=artifacts,
            metadata=metadata or FrozenMap.empty(),
        ),
        diagnostics=ordered,
    )


def descriptor_digest_map(plan: ArtifactPlan) -> FrozenMap[str, str]:
    digests: dict[str, str] = {}
    for descriptor in plan.descriptors:
        payload = {
            "backend_id": descriptor.backend_id,
            "candidate_ids": descriptor.candidate_ids,
            "dependency_primitive_names": descriptor.dependency_primitive_names,
            "kind": descriptor.kind,
            "logical_path": descriptor.logical_path.as_posix(),
            "metadata": _catalog_json_value(descriptor.metadata),
            "plan_metadata": _catalog_json_value(plan.metadata),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        digests[descriptor.logical_path.as_posix()] = hashlib.sha256(encoded).hexdigest()
    return FrozenMap(digests)


def artifact_digest_map(artifacts: ArtifactSet) -> FrozenMap[str, str]:
    return FrozenMap(
        (artifact.logical_path.as_posix(), artifact.content_digest)
        for artifact in artifacts.artifacts
    )


def _catalog_json_value(value: CatalogValue) -> Any:
    if isinstance(value, FrozenMap):
        return {key: _catalog_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_catalog_json_value(item) for item in value]
    return value
