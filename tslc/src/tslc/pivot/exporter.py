"""Filesystem-independent orchestration for the explicit PIVOT export path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslc._pipeline_inputs import load_catalog_inputs
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.pivot.model import PivotExportResult
from tslc.pivot.planner import PivotPlanner
from tslc.pivot.profiles import profiles_for_distinct_feature_sets
from tslc.pivot.render_yaml import render_pivot_yaml


@dataclass(frozen=True, slots=True)
class PivotExportRequest:
    source_paths: tuple[Path, ...]
    machine_profiles_path: Path
    primitives: tuple[str, ...] | None = None
    profiles: tuple[str, ...] | None = None
    type_tags: tuple[str, ...] = DEFAULT_SCALAR_TYPE_TAGS


def export_pivot(request: PivotExportRequest) -> PivotExportResult:
    """Project one immutable corpus snapshot to PIVOT YAML artifacts.

    This deliberately does not construct a :class:`GenerationRequest`, enter the
    ordinary generation session, register a backend, or render a generated project.
    """

    catalog_inputs, diagnostics = load_catalog_inputs(
        request.source_paths,
        required_backends=("cpp",),
    )
    if catalog_inputs is None:
        return _empty(diagnostics)

    profile_result = load_machine_profiles_checked(
        request.machine_profiles_path,
        catalog_inputs.catalog.target_families,
    )
    diagnostics.extend(profile_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    requested_profiles = (
        tuple(sorted(profile_result.profiles))
        if request.profiles is None
        else tuple(sorted(set(request.profiles)))
    )
    profiles = []
    for name in requested_profiles:
        profile = profile_result.profiles.get(name)
        if profile is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIVOT-UNKNOWN-PROFILE",
                    message=f"no machine profile named {name!r}",
                )
            )
        else:
            profiles.append(profile)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    plan = PivotPlanner(catalog_inputs.catalog).plan(
        profiles_for_distinct_feature_sets(tuple(profiles)),
        primitive_names=request.primitives,
        type_tags=request.type_tags,
    )
    all_diagnostics = sort_diagnostics((*diagnostics, *plan.diagnostics))
    artifacts = ArtifactSet.create(
        tuple(
            Artifact(
                logical_path=f"{document.name}.yaml",
                content=render_pivot_yaml(document),
                media_type="application/yaml",
            )
            for document in plan.documents
        )
    )
    return PivotExportResult(
        artifacts=artifacts,
        documents=plan.documents,
        skipped=plan.skipped,
        diagnostics=all_diagnostics,
    )


def _empty(diagnostics: list[Diagnostic]) -> PivotExportResult:
    return PivotExportResult(
        artifacts=ArtifactSet.create(()),
        documents=(),
        skipped=(),
        diagnostics=sort_diagnostics(diagnostics),
    )


__all__ = ("PivotExportRequest", "export_pivot")
