from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.candidate_dependencies import (
    CandidateDependencyClosure,
    candidate_dependency_graph_from_primitive_graph,
    compute_candidate_dependency_closure,
)
from tslgen.analysis.dependencies import DependencyClosure, plan_dependency_closure
from tslgen.analysis.selection import SelectionPlan, SelectionRequest, plan_selection
from tslgen.backends.registry import BackendRegistry, default_backend_registry
from tslgen.config.model import SourceConfig
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result
from tslgen.domain.backends import BackendManifestSet
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.artifact_writer import write_artifacts as _write_artifacts
from tslgen.io.artifacts import Artifact, ArtifactPlan, ArtifactSet
from tslgen.io.manifests import load_backend_manifests
from tslgen.io.sources import SourceSet, load_sources
from tslgen.io.write_report import ArtifactWriteOptions, ArtifactWriteReport
from tslgen.reporting.coverage import (
    CandidateDependencyReport,
    PipelineCoverageReport,
    coverage_report_from_pipeline_result,
    coverage_report_to_json,
)
from tslgen.reporting.html import (
    coverage_report_html_artifact_set,
    render_coverage_report_html,
)
from tslgen.rendering.render_plan import build_artifact_plan
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_sources
from tslgen.validation.catalog_validator import ValidatedCatalog, validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    source_config: SourceConfig
    selection_request: SelectionRequest = field(default_factory=SelectionRequest)
    backend_manifests: BackendManifestSet | None = None
    backend_manifest_paths: tuple[Path, ...] = ()
    render_backend: str | None = None
    backend_registry: BackendRegistry = field(default_factory=default_backend_registry)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "backend_manifest_paths",
            tuple(Path(path) for path in self.backend_manifest_paths),
        )
        if self.render_backend == "":
            raise ValueError("render backend must be non-empty when provided")


@dataclass(frozen=True, slots=True)
class PipelineResult:
    diagnostics: tuple[Diagnostic, ...] = ()
    sources: SourceSet | None = None
    parsed: ParsedDocumentSet | None = None
    catalog: Catalog | None = None
    validated_catalog: ValidatedCatalog | None = None
    reference_catalog: ReferenceValidatedCatalog | None = None
    selection_plan: SelectionPlan | None = None
    candidate_selection: CandidateSelection | None = None
    dependency_closure: DependencyClosure | None = None
    candidate_dependency_closure: CandidateDependencyClosure | None = None
    backend_manifests: BackendManifestSet | None = None
    artifact_plan: ArtifactPlan | None = None
    artifacts: ArtifactSet | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            sort_diagnostics(self.diagnostics),
        )

    @property
    def is_ok(self) -> bool:
        return not has_errors(self.diagnostics)


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    diagnostics: list[Diagnostic] = []

    loaded = load_sources(config.source_config)
    diagnostics.extend(loaded.diagnostics)
    if not loaded.is_ok:
        return PipelineResult(diagnostics=tuple(diagnostics))
    sources = loaded.unwrap()

    parsed_result = parse_sources(sources)
    diagnostics.extend(parsed_result.diagnostics)
    if not parsed_result.is_ok:
        return PipelineResult(diagnostics=tuple(diagnostics), sources=sources)
    parsed = parsed_result.unwrap()

    catalog_result = build_catalog(parsed)
    diagnostics.extend(catalog_result.diagnostics)
    if not catalog_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
        )
    catalog = catalog_result.unwrap()

    validated_result = validate_catalog(catalog)
    diagnostics.extend(validated_result.diagnostics)
    if not validated_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
        )
    validated = validated_result.unwrap()

    reference_result = validate_references(validated)
    diagnostics.extend(reference_result.diagnostics)
    if not reference_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
        )
    reference_catalog = reference_result.unwrap()

    selection_result = plan_selection(reference_catalog, config.selection_request)
    diagnostics.extend(selection_result.diagnostics)
    if not selection_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
        )
    selection_plan = selection_result.unwrap()

    candidate_result = select_implementation_candidates(selection_plan, catalog)
    diagnostics.extend(candidate_result.diagnostics)
    if not candidate_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
        )
    candidates = candidate_result.unwrap()

    dependency_result = plan_dependency_closure(candidates, catalog)
    diagnostics.extend(dependency_result.diagnostics)
    if not dependency_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
            candidate_selection=candidates,
        )
    dependency_closure = dependency_result.unwrap()

    candidate_dependency_result = _plan_candidate_dependency_closure(
        dependency_closure,
    )
    diagnostics.extend(candidate_dependency_result.diagnostics)
    if not candidate_dependency_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
            candidate_selection=candidates,
            dependency_closure=dependency_closure,
        )
    candidate_dependency_closure = candidate_dependency_result.unwrap()

    manifests = _resolve_manifests(config, diagnostics)
    if has_errors(diagnostics) or config.render_backend is None:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
            candidate_selection=candidates,
            dependency_closure=dependency_closure,
            candidate_dependency_closure=candidate_dependency_closure,
            backend_manifests=manifests,
        )

    if manifests is None:
        diagnostics.append(
            Diagnostic.error(
                "TSL-PIPELINE-MANIFESTS-MISSING",
                "rendering requires backend manifests in PipelineConfig",
            )
        )
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
            candidate_selection=candidates,
            dependency_closure=dependency_closure,
            candidate_dependency_closure=candidate_dependency_closure,
        )

    artifact_plan_result = build_artifact_plan(
        manifests,
        config.render_backend,
        candidates,
        dependency_closure,
    )
    diagnostics.extend(artifact_plan_result.diagnostics)
    if not artifact_plan_result.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
            candidate_selection=candidates,
            dependency_closure=dependency_closure,
            candidate_dependency_closure=candidate_dependency_closure,
            backend_manifests=manifests,
        )
    artifact_plan = artifact_plan_result.unwrap()

    rendered = config.backend_registry.render(
        config.render_backend,
        artifact_plan,
        candidates,
    )
    diagnostics.extend(rendered.diagnostics)
    if not rendered.is_ok:
        return PipelineResult(
            diagnostics=tuple(diagnostics),
            sources=sources,
            parsed=parsed,
            catalog=catalog,
            validated_catalog=validated,
            reference_catalog=reference_catalog,
            selection_plan=selection_plan,
            candidate_selection=candidates,
            dependency_closure=dependency_closure,
            candidate_dependency_closure=candidate_dependency_closure,
            backend_manifests=manifests,
            artifact_plan=artifact_plan,
        )

    return PipelineResult(
        diagnostics=tuple(diagnostics),
        sources=sources,
        parsed=parsed,
        catalog=catalog,
        validated_catalog=validated,
        reference_catalog=reference_catalog,
        selection_plan=selection_plan,
        candidate_selection=candidates,
        dependency_closure=dependency_closure,
        candidate_dependency_closure=candidate_dependency_closure,
        backend_manifests=manifests,
        artifact_plan=artifact_plan,
        artifacts=rendered.unwrap(),
    )


def coverage_report(result: PipelineResult) -> PipelineCoverageReport:
    return coverage_report_from_pipeline_result(result)


def candidate_dependency_report(
    report_or_result: PipelineCoverageReport | PipelineResult,
) -> CandidateDependencyReport:
    return _coverage_report_value(report_or_result).candidate_dependencies


def coverage_report_json(
    report_or_result: PipelineCoverageReport | PipelineResult,
) -> str:
    return coverage_report_to_json(_coverage_report_value(report_or_result))


def coverage_report_html(
    report_or_result: PipelineCoverageReport | PipelineResult,
) -> str:
    return render_coverage_report_html(_coverage_report_value(report_or_result))


def coverage_report_html_artifacts(
    report_or_result: PipelineCoverageReport | PipelineResult,
    *,
    logical_path: str | PurePosixPath = PurePosixPath("reports/coverage.html"),
) -> ArtifactSet:
    return coverage_report_html_artifact_set(
        _coverage_report_value(report_or_result),
        logical_path=logical_path,
    )


def write_artifacts(
    artifacts: ArtifactSet | Iterable[Artifact],
    output_root: Path,
    *,
    dry_run: bool = False,
    skip_unchanged: bool = True,
) -> ArtifactWriteReport:
    return _write_artifacts(
        artifacts,
        ArtifactWriteOptions(
            output_root=output_root,
            dry_run=dry_run,
            skip_unchanged=skip_unchanged,
        ),
    )


def _coverage_report_value(
    report_or_result: PipelineCoverageReport | PipelineResult,
) -> PipelineCoverageReport:
    if isinstance(report_or_result, PipelineCoverageReport):
        return report_or_result
    return coverage_report(report_or_result)


def _plan_candidate_dependency_closure(
    dependency_closure: DependencyClosure,
) -> Result[CandidateDependencyClosure]:
    graph_result = candidate_dependency_graph_from_primitive_graph(
        dependency_closure.graph,
    )
    if not graph_result.is_ok:
        return Result.failure(graph_result.diagnostics)

    closure_result = compute_candidate_dependency_closure(
        graph_result.unwrap(),
        root_candidate_ids=dependency_closure.root_candidate_ids,
    )
    diagnostics = sort_diagnostics(
        (*graph_result.diagnostics, *closure_result.diagnostics),
    )
    if not closure_result.is_ok:
        return Result.failure(diagnostics)
    return Result.ok(closure_result.unwrap(), diagnostics=diagnostics)


def _resolve_manifests(
    config: PipelineConfig,
    diagnostics: list[Diagnostic],
) -> BackendManifestSet | None:
    if config.backend_manifests is not None and config.backend_manifest_paths:
        diagnostics.append(
            Diagnostic.error(
                "TSL-PIPELINE-MANIFEST-CONFLICT",
                "PipelineConfig must provide backend manifests or manifest paths, "
                "not both",
            )
        )
        return None
    if config.backend_manifests is not None:
        return config.backend_manifests
    if not config.backend_manifest_paths:
        return None
    loaded = load_backend_manifests(config.backend_manifest_paths)
    diagnostics.extend(loaded.diagnostics)
    if not loaded.is_ok:
        return None
    return loaded.unwrap()
