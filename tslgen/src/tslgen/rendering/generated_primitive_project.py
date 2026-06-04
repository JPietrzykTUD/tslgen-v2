"""Compose generated-project skeleton artifacts with primitive artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.generated_project import GeneratedProjectRenderModel
from tslgen.io.artifacts import Artifact, ArtifactSet


@dataclass(frozen=True, slots=True)
class GeneratedPrimitiveProjectReplacementPath:
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class GeneratedPrimitiveProjectCompositionPolicy:
    replacement_paths: tuple[GeneratedPrimitiveProjectReplacementPath, ...]


@dataclass(frozen=True, slots=True)
class GeneratedPrimitiveProjectCompositionResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...] = ()


def scalar_profile_replacement_policy() -> GeneratedPrimitiveProjectCompositionPolicy:
    return GeneratedPrimitiveProjectCompositionPolicy(
        replacement_paths=(
            GeneratedPrimitiveProjectReplacementPath("cpp/include/profiles/scalar.hpp"),
            GeneratedPrimitiveProjectReplacementPath("rust/src/profiles/scalar.rs"),
        )
    )


def selected_profile_replacement_policy(
    model: GeneratedProjectRenderModel,
) -> GeneratedPrimitiveProjectCompositionPolicy:
    return GeneratedPrimitiveProjectCompositionPolicy(
        replacement_paths=tuple(
            GeneratedPrimitiveProjectReplacementPath(path)
            for path in (
                *(
                    f"cpp/include/profiles/{profile.file_stem}.hpp"
                    for profile in model.cpp.profiles
                ),
                *(
                    f"rust/src/profiles/{profile.file_stem}.rs"
                    for profile in model.rust.profiles
                ),
            )
        )
    )


def compose_generated_primitive_project_artifacts(
    skeleton_artifacts: ArtifactSet,
    primitive_artifacts: ArtifactSet,
    policy: GeneratedPrimitiveProjectCompositionPolicy,
) -> GeneratedPrimitiveProjectCompositionResult:
    diagnostics: list[Diagnostic] = []
    replacement_paths = frozenset(path.text for path in policy.replacement_paths)

    diagnostics.extend(
        _duplicate_input_diagnostics(
            "skeleton",
            skeleton_artifacts.artifacts,
            "TSL-GENERATED-PRIMITIVE-PROJECT-DUPLICATE-SKELETON-ARTIFACT",
        )
    )
    diagnostics.extend(
        _duplicate_input_diagnostics(
            "primitive",
            primitive_artifacts.artifacts,
            "TSL-GENERATED-PRIMITIVE-PROJECT-DUPLICATE-PRIMITIVE-ARTIFACT",
        )
    )
    diagnostics.extend(
        _unrelated_collision_diagnostics(
            skeleton_artifacts.artifacts,
            primitive_artifacts.artifacts,
            replacement_paths,
        )
    )
    if diagnostics:
        return GeneratedPrimitiveProjectCompositionResult(
            artifacts=ArtifactSet.create(()),
            diagnostics=_sort_diagnostics(diagnostics),
        )

    primitive_paths = frozenset(
        artifact.logical_path for artifact in primitive_artifacts.artifacts
    )
    composed = [
        artifact
        for artifact in skeleton_artifacts.artifacts
        if artifact.logical_path not in replacement_paths
        or artifact.logical_path not in primitive_paths
    ]
    composed.extend(primitive_artifacts.artifacts)
    return GeneratedPrimitiveProjectCompositionResult(
        artifacts=ArtifactSet.create(tuple(composed)),
    )


def _duplicate_input_diagnostics(
    label: str,
    artifacts: tuple[Artifact, ...],
    code: str,
) -> tuple[Diagnostic, ...]:
    counts: dict[str, int] = {}
    for artifact in artifacts:
        counts[artifact.logical_path] = counts.get(artifact.logical_path, 0) + 1
    return tuple(
        Diagnostic(
            severity="error",
            code=code,
            message=(
                f"{label} artifact logical path {logical_path!r} "
                "appears more than once"
            ),
        )
        for logical_path, count in counts.items()
        if count > 1
    )


def _unrelated_collision_diagnostics(
    skeleton_artifacts: tuple[Artifact, ...],
    primitive_artifacts: tuple[Artifact, ...],
    replacement_paths: frozenset[str],
) -> tuple[Diagnostic, ...]:
    skeleton_paths = frozenset(artifact.logical_path for artifact in skeleton_artifacts)
    primitive_paths = frozenset(artifact.logical_path for artifact in primitive_artifacts)
    return tuple(
        Diagnostic(
            severity="error",
            code="TSL-GENERATED-PRIMITIVE-PROJECT-DUPLICATE-LOGICAL-PATH",
            message=(
                f"primitive artifact logical path {logical_path!r} conflicts "
                "with a skeleton artifact and is not an allowed profile "
                "replacement path"
            ),
        )
        for logical_path in sorted((skeleton_paths & primitive_paths) - replacement_paths)
    )


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
