from __future__ import annotations

from tslgen.analysis.candidates import CandidateSelection
from tslgen.analysis.dependencies import DependencyClosure
from tslgen.core.diagnostics import Diagnostic
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.backends import (
    ACTIVE_BACKEND_IDS,
    BackendManifestSet,
    backend_id_list_text,
    is_active_backend_id,
)
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import (
    ArtifactDescriptor,
    ArtifactPlan,
    artifact_plan_from_descriptors,
)


def build_artifact_plan(
    manifests: BackendManifestSet,
    backend_id: str,
    selection: CandidateSelection,
    dependency_closure: DependencyClosure | None = None,
) -> Result[ArtifactPlan]:
    manifest = manifests.manifests_by_id.get(backend_id)
    if manifest is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-ARTIFACT-UNKNOWN-BACKEND",
                    f"artifact plan requested unknown backend {backend_id!r}",
                ),
            )
        )
    if not is_active_backend_id(manifest.backend_id):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-ARTIFACT-UNSUPPORTED-BACKEND",
                    f"artifact plan requested inactive backend "
                    f"{manifest.backend_id!r}; active backends: "
                    f"{backend_id_list_text(ACTIVE_BACKEND_IDS)}",
                ),
            )
        )
    if not is_active_backend_id(manifest.language_id):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-ARTIFACT-UNSUPPORTED-LANGUAGE",
                    f"artifact plan for backend {manifest.backend_id!r} "
                    f"references inactive language id {manifest.language_id!r}; "
                    f"active languages: {backend_id_list_text(ACTIVE_BACKEND_IDS)}",
                ),
            )
        )

    candidate_ids = _candidate_ids(selection, dependency_closure)
    dependency_names = (
        dependency_closure.required_primitive_names
        if dependency_closure is not None
        else ()
    )
    metadata = _plan_metadata(manifest.language_id, dependency_closure)
    descriptors = tuple(
        ArtifactDescriptor(
            backend_id=manifest.backend_id,
            kind=artifact.kind,
            logical_path=artifact.target_path,
            candidate_ids=candidate_ids,
            dependency_primitive_names=dependency_names,
            metadata=FrozenMap(
                {
                    "artifact_kind": artifact.kind,
                    "language_id": manifest.language_id,
                }
            ),
        )
        for artifact in manifest.artifacts
    )
    return artifact_plan_from_descriptors(
        manifest.backend_id,
        descriptors,
        metadata=metadata,
    )


def _candidate_ids(
    selection: CandidateSelection,
    dependency_closure: DependencyClosure | None,
) -> tuple[str, ...]:
    if dependency_closure is not None:
        return dependency_closure.required_candidate_ids
    return tuple(candidate.candidate_id for candidate in selection.candidates)


def _plan_metadata(
    language_id: str,
    dependency_closure: DependencyClosure | None,
) -> FrozenMap[str, CatalogValue]:
    values: dict[str, CatalogValue] = {"language_id": language_id}
    if dependency_closure is not None:
        values["root_candidate_ids"] = dependency_closure.root_candidate_ids
        values["unplanned_primitive_names"] = (
            dependency_closure.unplanned_primitive_names
        )
    return FrozenMap(values)
