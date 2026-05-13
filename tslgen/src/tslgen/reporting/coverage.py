from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.analysis.candidate_dependencies import (
    CandidateDependencyClosure,
    CandidateDependencyEdge,
    CandidateDependencyIssue,
)
from tslgen.analysis.dependencies import DependencyClosure
from tslgen.analysis.selection import SelectionPlan
from tslgen.core.diagnostics import Diagnostic, DiagnosticSeverity
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.io.artifacts import ArtifactPlan, ArtifactSet


_ANY_BACKEND = "any"
_CANDIDATE_DEPENDENCY_DIAGNOSTIC_PREFIX = "TSL-CANDIDATE-DEPENDENCY-"
_DEFAULT_DEFERRED_CATEGORIES = (
    "artifact_writing",
    "backend_capability_evaluation",
    "full_template_rendering",
    "production_test_generation",
    "tsil_lowering",
)
_LEGACY_COVERAGE_ROW_FIELD_ORDER = (
    "effective_present",
    "extension",
    "has_intrinsic",
    "has_lang_block",
    "has_tsil",
    "language",
    "missing_effective",
    "missing_intrinsic",
    "missing_lang_block",
    "missing_tsil",
    "primitive",
    "primitive_class",
    "template",
    "type",
)
_SELECTED_LEGACY_COVERAGE_REQUEST = ("add", "avx2", "cpp", "f32")
_SELECTED_LEGACY_PRIMITIVE_CLASS = "fundamental"
_SELECTED_LEGACY_TEMPLATE = "v:=(v,v)"


class PipelineResultLike(Protocol):
    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]: ...

    @property
    def catalog(self) -> Catalog | None: ...

    @property
    def selection_plan(self) -> SelectionPlan | None: ...

    @property
    def candidate_selection(self) -> CandidateSelection | None: ...

    @property
    def dependency_closure(self) -> DependencyClosure | None: ...

    @property
    def candidate_dependency_closure(self) -> CandidateDependencyClosure | None: ...

    @property
    def artifact_plan(self) -> ArtifactPlan | None: ...

    @property
    def artifacts(self) -> ArtifactSet | None: ...


@dataclass(frozen=True, slots=True)
class LegacyCoverageRowAdapterRequest:
    primitive: str
    extension: str
    language: str
    type_tag: str

    def __post_init__(self) -> None:
        for field_name in ("primitive", "extension", "language", "type_tag"):
            if not getattr(self, field_name):
                raise ValueError(
                    f"legacy coverage row request {field_name} must be non-empty"
                )

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.primitive, self.extension, self.language, self.type_tag)


@dataclass(frozen=True, slots=True)
class LegacyCoverageSelectedRowFact:
    primitive: str
    extension: str
    language: str
    type_tag: str
    primitive_class: str
    template: str
    has_tsil: bool
    has_intrinsic: bool
    has_lang_block: bool
    effective_present: bool

    def __post_init__(self) -> None:
        for field_name in (
            "primitive",
            "extension",
            "language",
            "type_tag",
            "primitive_class",
            "template",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"legacy coverage row {field_name} must be non-empty")

    @property
    def missing_tsil(self) -> bool:
        return not self.has_tsil

    @property
    def missing_intrinsic(self) -> bool:
        return not self.has_intrinsic

    @property
    def missing_lang_block(self) -> bool:
        return not self.has_lang_block

    @property
    def missing_effective(self) -> bool:
        return not self.effective_present

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.primitive, self.extension, self.language, self.type_tag)


@dataclass(frozen=True, slots=True)
class DiagnosticCount:
    severity: DiagnosticSeverity
    code: str
    count: int

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("diagnostic count code must be non-empty")
        if self.count < 1:
            raise ValueError("diagnostic count must be positive")

    @property
    def key(self) -> tuple[str, str]:
        return (self.severity, self.code)


@dataclass(frozen=True, slots=True)
class SelectionCoverageSummary:
    requested_backend: str | None
    requested_primitives: tuple[str, ...] = ()
    requested_templates: tuple[str, ...] = ()
    requested_extensions: tuple[str, ...] = ()
    allowed_extensions: tuple[str, ...] = ()
    normalized_cpu_flags: tuple[str, ...] = ()
    variant_count: int = 0
    implementation_plan_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requested_primitives",
            tuple(sorted(self.requested_primitives)),
        )
        object.__setattr__(
            self,
            "requested_templates",
            tuple(sorted(self.requested_templates)),
        )
        object.__setattr__(
            self,
            "requested_extensions",
            tuple(sorted(self.requested_extensions)),
        )
        object.__setattr__(
            self,
            "allowed_extensions",
            tuple(sorted(self.allowed_extensions)),
        )
        object.__setattr__(
            self,
            "normalized_cpu_flags",
            tuple(sorted(self.normalized_cpu_flags)),
        )
        if self.variant_count < 0:
            raise ValueError("variant count must not be negative")
        if self.implementation_plan_count < 0:
            raise ValueError("implementation plan count must not be negative")


@dataclass(frozen=True, slots=True)
class PrimitiveCoverageRow:
    primitive_name: str
    declaration_count: int
    variant_count: int = 0
    candidate_count: int = 0
    candidates_with_opaque_bodies: int = 0
    candidates_without_bodies: int = 0
    rendered_candidate_count: int = 0
    direct_dependency_count: int = 0
    is_required_by_dependency_closure: bool = False
    unplanned_dependency_count: int = 0
    templates: tuple[str, ...] = ()
    candidate_backends: tuple[str, ...] = ()
    target_extensions: tuple[str, ...] = ()
    source_extensions: tuple[str, ...] = ()
    type_tags: tuple[str, ...] = ()
    primitive_classes: tuple[str, ...] = ()
    has_tsil: bool | None = None
    has_intrinsic: bool | None = None
    has_lang_block: bool | None = None
    effective_present: bool | None = None
    direct_dependency_names: tuple[str, ...] = ()
    rendered_artifact_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.primitive_name:
            raise ValueError("primitive coverage row name must be non-empty")
        for field_name in (
            "declaration_count",
            "variant_count",
            "candidate_count",
            "candidates_with_opaque_bodies",
            "candidates_without_bodies",
            "rendered_candidate_count",
            "direct_dependency_count",
            "unplanned_dependency_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must not be negative")
        object.__setattr__(self, "templates", tuple(sorted(self.templates)))
        object.__setattr__(
            self,
            "candidate_backends",
            tuple(sorted(self.candidate_backends)),
        )
        object.__setattr__(
            self,
            "target_extensions",
            tuple(sorted(self.target_extensions)),
        )
        object.__setattr__(
            self,
            "source_extensions",
            tuple(sorted(self.source_extensions)),
        )
        object.__setattr__(self, "type_tags", tuple(sorted(self.type_tags)))
        object.__setattr__(
            self,
            "primitive_classes",
            tuple(sorted(self.primitive_classes)),
        )
        object.__setattr__(
            self,
            "direct_dependency_names",
            tuple(sorted(self.direct_dependency_names)),
        )
        object.__setattr__(
            self,
            "rendered_artifact_paths",
            tuple(sorted(self.rendered_artifact_paths)),
        )

    @property
    def has_candidates(self) -> bool:
        return self.candidate_count > 0

    @property
    def has_rendered_candidates(self) -> bool:
        return self.rendered_candidate_count > 0

    @property
    def key(self) -> str:
        return self.primitive_name


@dataclass(frozen=True, slots=True)
class BackendCoverageRow:
    backend_id: str
    planned_artifact_count: int = 0
    rendered_artifact_count: int = 0
    rendered_candidate_count: int = 0
    planned_artifact_paths: tuple[str, ...] = ()
    rendered_artifact_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("backend coverage row id must be non-empty")
        for field_name in (
            "planned_artifact_count",
            "rendered_artifact_count",
            "rendered_candidate_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must not be negative")
        object.__setattr__(
            self,
            "planned_artifact_paths",
            tuple(sorted(self.planned_artifact_paths)),
        )
        object.__setattr__(
            self,
            "rendered_artifact_paths",
            tuple(sorted(self.rendered_artifact_paths)),
        )

    @property
    def key(self) -> str:
        return self.backend_id


@dataclass(frozen=True, slots=True)
class CandidateDependencyEdgeRow:
    source_candidate_id: str
    source_primitive_name: str
    target_candidate_id: str
    target_primitive_name: str
    raw_target: str
    type_arguments: tuple[str, ...] = ()
    is_self_reference: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "source_candidate_id",
            "source_primitive_name",
            "target_candidate_id",
            "target_primitive_name",
            "raw_target",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        object.__setattr__(self, "type_arguments", tuple(self.type_arguments))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.source_candidate_id,
            self.target_candidate_id,
            self.target_primitive_name,
            self.raw_target,
            self.type_arguments,
            self.is_self_reference,
        )


@dataclass(frozen=True, slots=True)
class CandidateDependencyIssueRow:
    source_candidate_id: str
    source_primitive_name: str
    target_primitive_name: str
    reason: str
    fallback_primitive_name: str
    raw_target: str
    type_arguments: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "source_candidate_id",
            "source_primitive_name",
            "target_primitive_name",
            "reason",
            "fallback_primitive_name",
            "raw_target",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        object.__setattr__(self, "type_arguments", tuple(self.type_arguments))
        object.__setattr__(self, "candidate_ids", tuple(sorted(self.candidate_ids)))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.source_candidate_id,
            self.target_primitive_name,
            self.reason,
            self.raw_target,
            self.type_arguments,
            self.candidate_ids,
            self.detail,
        )


@dataclass(frozen=True, slots=True)
class CandidateDependencyReport:
    is_available: bool = False
    edge_rows: tuple[CandidateDependencyEdgeRow, ...] = ()
    issue_rows: tuple[CandidateDependencyIssueRow, ...] = ()
    root_candidate_ids: tuple[str, ...] = ()
    required_candidate_ids: tuple[str, ...] = ()
    required_primitive_names: tuple[str, ...] = ()
    fallback_primitive_names: tuple[str, ...] = ()
    ambiguous_primitive_names: tuple[str, ...] = ()
    unresolved_primitive_names: tuple[str, ...] = ()
    unsupported_primitive_names: tuple[str, ...] = ()
    diagnostic_counts: tuple[DiagnosticCount, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "edge_rows",
            tuple(sorted(self.edge_rows, key=lambda row: row.key)),
        )
        object.__setattr__(
            self,
            "issue_rows",
            tuple(sorted(self.issue_rows, key=lambda row: row.key)),
        )
        for field_name in (
            "root_candidate_ids",
            "required_candidate_ids",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "required_primitive_names",
            "fallback_primitive_names",
            "ambiguous_primitive_names",
            "unresolved_primitive_names",
            "unsupported_primitive_names",
        ):
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(getattr(self, field_name))),
            )
        object.__setattr__(
            self,
            "diagnostic_counts",
            tuple(sorted(self.diagnostic_counts, key=lambda item: item.key)),
        )

    @property
    def edge_count(self) -> int:
        return len(self.edge_rows)

    @property
    def issue_count(self) -> int:
        return len(self.issue_rows)

    @property
    def diagnostic_count(self) -> int:
        return sum(item.count for item in self.diagnostic_counts)


@dataclass(frozen=True, slots=True)
class PipelineCoverageReport:
    primitive_rows: tuple[PrimitiveCoverageRow, ...]
    selection: SelectionCoverageSummary | None = None
    backend_rows: tuple[BackendCoverageRow, ...] = ()
    diagnostic_counts: tuple[DiagnosticCount, ...] = ()
    unplanned_dependency_primitives: tuple[str, ...] = ()
    candidate_dependencies: CandidateDependencyReport = field(
        default_factory=CandidateDependencyReport,
    )
    deferred_categories: tuple[str, ...] = _DEFAULT_DEFERRED_CATEGORIES

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "primitive_rows",
            tuple(sorted(self.primitive_rows, key=lambda row: row.key)),
        )
        object.__setattr__(
            self,
            "backend_rows",
            tuple(sorted(self.backend_rows, key=lambda row: row.key)),
        )
        object.__setattr__(
            self,
            "diagnostic_counts",
            tuple(sorted(self.diagnostic_counts, key=lambda item: item.key)),
        )
        object.__setattr__(
            self,
            "unplanned_dependency_primitives",
            tuple(sorted(self.unplanned_dependency_primitives)),
        )
        object.__setattr__(
            self,
            "deferred_categories",
            tuple(sorted(self.deferred_categories)),
        )

    @property
    def total_primitives(self) -> int:
        return len(self.primitive_rows)

    @property
    def primitives_with_candidates(self) -> int:
        return sum(1 for row in self.primitive_rows if row.has_candidates)

    @property
    def primitives_without_candidates(self) -> int:
        return sum(1 for row in self.primitive_rows if not row.has_candidates)

    @property
    def total_candidates(self) -> int:
        return sum(row.candidate_count for row in self.primitive_rows)

    @property
    def candidates_with_opaque_bodies(self) -> int:
        return sum(row.candidates_with_opaque_bodies for row in self.primitive_rows)

    @property
    def candidates_without_bodies(self) -> int:
        return sum(row.candidates_without_bodies for row in self.primitive_rows)

    @property
    def rendered_artifacts(self) -> int:
        return sum(row.rendered_artifact_count for row in self.backend_rows)

    @property
    def required_dependency_primitives(self) -> int:
        return sum(
            1
            for row in self.primitive_rows
            if row.is_required_by_dependency_closure
        )

    @property
    def candidate_dependency_edges(self) -> int:
        return self.candidate_dependencies.edge_count

    @property
    def candidate_dependency_issues(self) -> int:
        return self.candidate_dependencies.issue_count


def coverage_report_from_pipeline_result(
    result: PipelineResultLike,
) -> PipelineCoverageReport:
    return build_coverage_report(
        catalog=result.catalog,
        selection_plan=result.selection_plan,
        candidate_selection=result.candidate_selection,
        dependency_closure=result.dependency_closure,
        candidate_dependency_closure=result.candidate_dependency_closure,
        artifact_plan=result.artifact_plan,
        artifacts=result.artifacts,
        diagnostics=result.diagnostics,
    )


def build_coverage_report(
    *,
    catalog: Catalog | None = None,
    selection_plan: SelectionPlan | None = None,
    candidate_selection: CandidateSelection | None = None,
    dependency_closure: DependencyClosure | None = None,
    candidate_dependency_closure: CandidateDependencyClosure | None = None,
    artifact_plan: ArtifactPlan | None = None,
    artifacts: ArtifactSet | None = None,
    diagnostics: Iterable[Diagnostic] = (),
) -> PipelineCoverageReport:
    diagnostics_tuple = tuple(diagnostics)
    effective_plan = _effective_selection_plan(selection_plan, candidate_selection)
    candidates = candidate_selection.candidates if candidate_selection is not None else ()
    primitive_rows = _primitive_rows(
        catalog=catalog,
        selection_plan=effective_plan,
        candidates=candidates,
        dependency_closure=dependency_closure,
        artifact_plan=artifact_plan,
        artifacts=artifacts,
    )
    return PipelineCoverageReport(
        primitive_rows=primitive_rows,
        selection=_selection_summary(effective_plan),
        backend_rows=_backend_rows(artifact_plan, artifacts),
        diagnostic_counts=_diagnostic_counts(diagnostics_tuple),
        unplanned_dependency_primitives=(
            dependency_closure.unplanned_primitive_names
            if dependency_closure is not None
            else ()
        ),
        candidate_dependencies=_candidate_dependency_report(
            candidate_dependency_closure,
            diagnostics=diagnostics_tuple,
        ),
    )


def coverage_report_to_json(report: PipelineCoverageReport) -> str:
    return json.dumps(
        _report_dict(report),
        indent=2,
        sort_keys=True,
    ) + "\n"


def selected_legacy_coverage_request() -> LegacyCoverageRowAdapterRequest:
    return LegacyCoverageRowAdapterRequest(
        primitive=_SELECTED_LEGACY_COVERAGE_REQUEST[0],
        extension=_SELECTED_LEGACY_COVERAGE_REQUEST[1],
        language=_SELECTED_LEGACY_COVERAGE_REQUEST[2],
        type_tag=_SELECTED_LEGACY_COVERAGE_REQUEST[3],
    )


def adapt_legacy_coverage_row(
    report: object,
    request: LegacyCoverageRowAdapterRequest,
) -> Result[LegacyCoverageSelectedRowFact]:
    if not isinstance(report, PipelineCoverageReport):
        return Result.failure((_raw_evidence_diagnostic(report),))
    if request.key != _SELECTED_LEGACY_COVERAGE_REQUEST:
        return Result.failure((_unsupported_legacy_request_diagnostic(request),))

    primitive_rows = tuple(
        row for row in report.primitive_rows if row.primitive_name == request.primitive
    )
    if not primitive_rows:
        return Result.failure((_missing_legacy_row_diagnostic(request),))

    matching_rows = tuple(
        row
        for row in primitive_rows
        if _matches_exact_legacy_row_key(row, request)
    )
    if len(matching_rows) > 1:
        return Result.failure((_ambiguous_legacy_row_diagnostic(request),))
    if not matching_rows:
        if any(_contains_legacy_row_key(row, request) for row in primitive_rows):
            return Result.failure(
                (_aggregate_legacy_row_diagnostic(request, primitive_rows),)
            )
        return Result.failure(
            (_missing_required_report_fields_diagnostic(request, primitive_rows),)
        )

    row = matching_rows[0]
    diagnostics = _legacy_fact_diagnostics(row, request)
    if diagnostics:
        return Result.failure(diagnostics)

    return Result.ok(
        LegacyCoverageSelectedRowFact(
            primitive=request.primitive,
            extension=request.extension,
            language=request.language,
            type_tag=request.type_tag,
            primitive_class=row.primitive_classes[0],
            template=row.templates[0],
            has_tsil=_required_bool(row.has_tsil),
            has_intrinsic=_required_bool(row.has_intrinsic),
            has_lang_block=_required_bool(row.has_lang_block),
            effective_present=_required_bool(row.effective_present),
        )
    )


def legacy_coverage_row_to_json(
    fact: object,
) -> Result[str]:
    if not isinstance(fact, LegacyCoverageSelectedRowFact):
        return Result.failure((_raw_evidence_diagnostic(fact),))
    if fact.key != _SELECTED_LEGACY_COVERAGE_REQUEST:
        return Result.failure((_unsupported_legacy_fact_diagnostic(fact),))
    return Result.ok(json.dumps(_legacy_row_dict(fact), indent=2) + "\n")


def selected_legacy_coverage_row_to_json(
    report: object,
    request: LegacyCoverageRowAdapterRequest,
) -> Result[str]:
    fact_result = adapt_legacy_coverage_row(report, request)
    if not fact_result.is_ok:
        return Result.failure(fact_result.diagnostics)
    return legacy_coverage_row_to_json(fact_result.unwrap())


def _effective_selection_plan(
    selection_plan: SelectionPlan | None,
    candidate_selection: CandidateSelection | None,
) -> SelectionPlan | None:
    if selection_plan is not None:
        return selection_plan
    if candidate_selection is not None:
        return candidate_selection.plan
    return None


def _selection_summary(
    selection_plan: SelectionPlan | None,
) -> SelectionCoverageSummary | None:
    if selection_plan is None:
        return None
    request = selection_plan.request
    return SelectionCoverageSummary(
        requested_backend=request.backend,
        requested_primitives=request.primitive_names,
        requested_templates=request.template_names,
        requested_extensions=request.extension_names,
        allowed_extensions=selection_plan.allowed_extensions,
        normalized_cpu_flags=tuple(
            flag.name for flag in selection_plan.normalized_cpu_flags
        ),
        variant_count=len(selection_plan.variants),
        implementation_plan_count=len(selection_plan.implementation_plans),
    )


def _primitive_rows(
    *,
    catalog: Catalog | None,
    selection_plan: SelectionPlan | None,
    candidates: tuple[ImplementationCandidate, ...],
    dependency_closure: DependencyClosure | None,
    artifact_plan: ArtifactPlan | None,
    artifacts: ArtifactSet | None,
) -> tuple[PrimitiveCoverageRow, ...]:
    names = _primitive_names(catalog, selection_plan, candidates, dependency_closure)
    declaration_counts = _declaration_counts(catalog)
    variants_by_primitive = _variants_by_primitive(selection_plan)
    candidates_by_primitive = _candidates_by_primitive(candidates)
    rendered = _rendered_candidate_artifacts(artifact_plan, artifacts)
    direct_dependencies = _direct_dependencies_by_primitive(dependency_closure)
    required_names = (
        frozenset(dependency_closure.required_primitive_names)
        if dependency_closure is not None
        else frozenset()
    )
    unplanned_names = (
        frozenset(dependency_closure.unplanned_primitive_names)
        if dependency_closure is not None
        else frozenset()
    )

    rows: list[PrimitiveCoverageRow] = []
    for name in sorted(names):
        primitive_candidates = candidates_by_primitive.get(name, ())
        body_count = sum(1 for candidate in primitive_candidates if _has_body(candidate))
        rendered_paths = tuple(
            path
            for candidate in primitive_candidates
            for path in rendered.get(candidate.candidate_id, ())
        )
        dependencies = direct_dependencies.get(name, ())
        rows.append(
            PrimitiveCoverageRow(
                primitive_name=name,
                declaration_count=declaration_counts.get(name, 0),
                variant_count=len(variants_by_primitive.get(name, ())),
                candidate_count=len(primitive_candidates),
                candidates_with_opaque_bodies=body_count,
                candidates_without_bodies=len(primitive_candidates) - body_count,
                rendered_candidate_count=sum(
                    1
                    for candidate in primitive_candidates
                    if candidate.candidate_id in rendered
                ),
                direct_dependency_count=len(dependencies),
                is_required_by_dependency_closure=name in required_names,
                unplanned_dependency_count=sum(
                    1 for dependency in dependencies if dependency in unplanned_names
                ),
                templates=_templates(name, selection_plan, primitive_candidates),
                candidate_backends=tuple(
                    _backend_name(candidate.backend)
                    for candidate in primitive_candidates
                ),
                target_extensions=tuple(
                    candidate.target_extension for candidate in primitive_candidates
                ),
                source_extensions=tuple(
                    candidate.source_extension for candidate in primitive_candidates
                ),
                type_tags=tuple(candidate.type_tag for candidate in primitive_candidates),
                direct_dependency_names=dependencies,
                rendered_artifact_paths=rendered_paths,
            )
        )
    return tuple(rows)


def _primitive_names(
    catalog: Catalog | None,
    selection_plan: SelectionPlan | None,
    candidates: tuple[ImplementationCandidate, ...],
    dependency_closure: DependencyClosure | None,
) -> frozenset[str]:
    names: set[str] = set()
    if catalog is not None:
        names.update(primitive.name for primitive in catalog.primitives)
    if selection_plan is not None:
        names.update(variant.primitive_name for variant in selection_plan.variants)
    names.update(candidate.source_primitive_name for candidate in candidates)
    if dependency_closure is not None:
        names.update(dependency_closure.required_primitive_names)
        names.update(dependency_closure.unplanned_primitive_names)
    return frozenset(names)


def _declaration_counts(catalog: Catalog | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    if catalog is None:
        return counts
    for primitive in catalog.primitives:
        counts[primitive.name] = counts.get(primitive.name, 0) + 1
    return counts


def _variants_by_primitive(
    selection_plan: SelectionPlan | None,
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    if selection_plan is None:
        return {}
    for variant in selection_plan.variants:
        grouped.setdefault(variant.primitive_name, []).append(variant.variant_id)
    return {
        primitive_name: tuple(sorted(variant_ids))
        for primitive_name, variant_ids in grouped.items()
    }


def _candidates_by_primitive(
    candidates: tuple[ImplementationCandidate, ...],
) -> dict[str, tuple[ImplementationCandidate, ...]]:
    grouped: dict[str, list[ImplementationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source_primitive_name, []).append(candidate)
    return {
        primitive_name: tuple(sorted(items, key=lambda candidate: candidate.key))
        for primitive_name, items in grouped.items()
    }


def _rendered_candidate_artifacts(
    artifact_plan: ArtifactPlan | None,
    artifacts: ArtifactSet | None,
) -> dict[str, tuple[str, ...]]:
    if artifact_plan is None or artifacts is None:
        return {}

    rendered_paths = frozenset(artifacts.artifacts_by_path)
    grouped: dict[str, set[str]] = {}
    for descriptor in artifact_plan.descriptors:
        path = descriptor.logical_path.as_posix()
        if path not in rendered_paths:
            continue
        for candidate_id in descriptor.candidate_ids:
            grouped.setdefault(candidate_id, set()).add(path)
    return {
        candidate_id: tuple(sorted(paths))
        for candidate_id, paths in grouped.items()
    }


def _direct_dependencies_by_primitive(
    dependency_closure: DependencyClosure | None,
) -> dict[str, tuple[str, ...]]:
    if dependency_closure is None:
        return {}
    return {
        name: tuple(dependencies)
        for name, dependencies in (
            dependency_closure.graph.direct_primitive_dependencies.items()
        )
    }


def _templates(
    primitive_name: str,
    selection_plan: SelectionPlan | None,
    candidates: tuple[ImplementationCandidate, ...],
) -> tuple[str, ...]:
    values: set[str] = {candidate.template_name for candidate in candidates}
    if selection_plan is not None:
        values.update(
            variant.template_name
            for variant in selection_plan.variants
            if variant.primitive_name == primitive_name
        )
    return tuple(sorted(values))


def _backend_rows(
    artifact_plan: ArtifactPlan | None,
    artifacts: ArtifactSet | None,
) -> tuple[BackendCoverageRow, ...]:
    backend_ids = _backend_ids(artifact_plan, artifacts)
    rendered_paths = (
        frozenset(artifacts.artifacts_by_path)
        if artifacts is not None
        else frozenset()
    )
    rows: list[BackendCoverageRow] = []
    for backend_id in sorted(backend_ids):
        planned_descriptors = tuple(
            descriptor
            for descriptor in artifact_plan.descriptors
            if descriptor.backend_id == backend_id
        ) if artifact_plan is not None else ()
        rendered_artifacts = tuple(
            artifact
            for artifact in artifacts.artifacts
            if _artifact_backend_id(artifact.metadata.get("backend_id"), artifact_plan)
            == backend_id
        ) if artifacts is not None else ()
        rendered_candidate_ids = {
            candidate_id
            for descriptor in planned_descriptors
            if descriptor.logical_path.as_posix() in rendered_paths
            for candidate_id in descriptor.candidate_ids
        }
        rows.append(
            BackendCoverageRow(
                backend_id=backend_id,
                planned_artifact_count=len(planned_descriptors),
                rendered_artifact_count=len(rendered_artifacts),
                rendered_candidate_count=len(rendered_candidate_ids),
                planned_artifact_paths=tuple(
                    descriptor.logical_path.as_posix()
                    for descriptor in planned_descriptors
                ),
                rendered_artifact_paths=tuple(
                    artifact.logical_path.as_posix()
                    for artifact in rendered_artifacts
                ),
            )
        )
    return tuple(rows)


def _backend_ids(
    artifact_plan: ArtifactPlan | None,
    artifacts: ArtifactSet | None,
) -> frozenset[str]:
    backend_ids: set[str] = set()
    if artifact_plan is not None:
        backend_ids.add(artifact_plan.backend_id)
        backend_ids.update(descriptor.backend_id for descriptor in artifact_plan.descriptors)
    if artifacts is not None:
        for artifact in artifacts.artifacts:
            backend_ids.add(_artifact_backend_id(artifact.metadata.get("backend_id"), artifact_plan))
    return frozenset(backend_ids)


def _artifact_backend_id(
    metadata_backend: object,
    artifact_plan: ArtifactPlan | None,
) -> str:
    if isinstance(metadata_backend, str) and metadata_backend:
        return metadata_backend
    if artifact_plan is not None:
        return artifact_plan.backend_id
    return "unknown"


def _diagnostic_counts(
    diagnostics: Iterable[Diagnostic],
) -> tuple[DiagnosticCount, ...]:
    counts: dict[tuple[DiagnosticSeverity, str], int] = {}
    for diagnostic in diagnostics:
        key = (diagnostic.severity, diagnostic.code)
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        DiagnosticCount(severity=severity, code=code, count=count)
        for (severity, code), count in sorted(counts.items())
    )


def _has_body(candidate: ImplementationCandidate) -> bool:
    return candidate.implementation.body.has_payload


def _backend_name(backend: str | None) -> str:
    return backend if backend is not None else _ANY_BACKEND


def _candidate_dependency_report(
    closure: CandidateDependencyClosure | None,
    diagnostics: Iterable[Diagnostic],
) -> CandidateDependencyReport:
    diagnostic_counts = _diagnostic_counts(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.code.startswith(_CANDIDATE_DEPENDENCY_DIAGNOSTIC_PREFIX)
    )
    if closure is None:
        return CandidateDependencyReport(diagnostic_counts=diagnostic_counts)

    reachable_candidate_ids = frozenset(closure.required_candidate_ids)
    return CandidateDependencyReport(
        is_available=True,
        edge_rows=tuple(
            _candidate_dependency_edge_row(closure, edge)
            for edge in closure.graph.edges
            if edge.source_candidate_id in reachable_candidate_ids
        ),
        issue_rows=tuple(
            _candidate_dependency_issue_row(closure, issue)
            for issue in closure.graph.issues
            if issue.source_candidate_id in reachable_candidate_ids
        ),
        root_candidate_ids=closure.root_candidate_ids,
        required_candidate_ids=closure.required_candidate_ids,
        required_primitive_names=closure.required_primitive_names,
        fallback_primitive_names=closure.fallback_primitive_names,
        ambiguous_primitive_names=closure.ambiguous_primitive_names,
        unresolved_primitive_names=closure.unresolved_primitive_names,
        unsupported_primitive_names=closure.unsupported_primitive_names,
        diagnostic_counts=diagnostic_counts,
    )


def _candidate_dependency_edge_row(
    closure: CandidateDependencyClosure,
    edge: CandidateDependencyEdge,
) -> CandidateDependencyEdgeRow:
    candidates = closure.graph.primitive_graph.selection.candidates_by_id
    source = candidates[edge.source_candidate_id]
    target = candidates[edge.target_candidate_id]
    return CandidateDependencyEdgeRow(
        source_candidate_id=edge.source_candidate_id,
        source_primitive_name=source.source_primitive_name,
        target_candidate_id=edge.target_candidate_id,
        target_primitive_name=target.source_primitive_name,
        raw_target=edge.reference.raw_target,
        type_arguments=edge.reference.type_arguments,
        is_self_reference=edge.reference.is_self_reference,
    )


def _candidate_dependency_issue_row(
    closure: CandidateDependencyClosure,
    issue: CandidateDependencyIssue,
) -> CandidateDependencyIssueRow:
    candidate = closure.graph.primitive_graph.selection.candidates_by_id[
        issue.source_candidate_id
    ]
    return CandidateDependencyIssueRow(
        source_candidate_id=issue.source_candidate_id,
        source_primitive_name=candidate.source_primitive_name,
        target_primitive_name=issue.target_primitive_name,
        reason=issue.reason,
        fallback_primitive_name=issue.target_primitive_name,
        raw_target=issue.reference.raw_target,
        type_arguments=issue.reference.type_arguments,
        candidate_ids=issue.candidate_ids,
        detail=issue.detail,
    )


def _report_dict(report: PipelineCoverageReport) -> dict[str, Any]:
    return {
        "backend_rows": [_backend_row_dict(row) for row in report.backend_rows],
        "candidate_dependencies": _candidate_dependency_report_dict(
            report.candidate_dependencies,
        ),
        "deferred_categories": list(report.deferred_categories),
        "diagnostic_counts": [
            _diagnostic_count_dict(item) for item in report.diagnostic_counts
        ],
        "primitive_rows": [
            _primitive_row_dict(row) for row in report.primitive_rows
        ],
        "schema_version": 1,
        "selection": (
            _selection_dict(report.selection)
            if report.selection is not None
            else None
        ),
        "summary": {
            "candidate_dependency_diagnostics": (
                report.candidate_dependencies.diagnostic_count
            ),
            "candidate_dependency_edges": report.candidate_dependency_edges,
            "candidate_dependency_fallback_primitives": list(
                report.candidate_dependencies.fallback_primitive_names
            ),
            "candidate_dependency_issues": report.candidate_dependency_issues,
            "candidates_with_opaque_bodies": report.candidates_with_opaque_bodies,
            "candidates_without_bodies": report.candidates_without_bodies,
            "primitives_with_candidates": report.primitives_with_candidates,
            "primitives_without_candidates": report.primitives_without_candidates,
            "rendered_artifacts": report.rendered_artifacts,
            "required_dependency_primitives": report.required_dependency_primitives,
            "total_candidates": report.total_candidates,
            "total_primitives": report.total_primitives,
            "unplanned_dependency_primitives": list(
                report.unplanned_dependency_primitives
            ),
        },
    }


def _selection_dict(summary: SelectionCoverageSummary) -> dict[str, Any]:
    return {
        "allowed_extensions": list(summary.allowed_extensions),
        "implementation_plan_count": summary.implementation_plan_count,
        "normalized_cpu_flags": list(summary.normalized_cpu_flags),
        "requested_backend": summary.requested_backend,
        "requested_extensions": list(summary.requested_extensions),
        "requested_primitives": list(summary.requested_primitives),
        "requested_templates": list(summary.requested_templates),
        "variant_count": summary.variant_count,
    }


def _diagnostic_count_dict(item: DiagnosticCount) -> dict[str, Any]:
    return {
        "code": item.code,
        "count": item.count,
        "severity": item.severity,
    }


def _primitive_row_dict(row: PrimitiveCoverageRow) -> dict[str, Any]:
    return {
        "candidate_backends": list(row.candidate_backends),
        "candidate_count": row.candidate_count,
        "candidates_with_opaque_bodies": row.candidates_with_opaque_bodies,
        "candidates_without_bodies": row.candidates_without_bodies,
        "declaration_count": row.declaration_count,
        "direct_dependency_count": row.direct_dependency_count,
        "direct_dependency_names": list(row.direct_dependency_names),
        "has_candidates": row.has_candidates,
        "has_rendered_candidates": row.has_rendered_candidates,
        "is_required_by_dependency_closure": row.is_required_by_dependency_closure,
        "primitive_name": row.primitive_name,
        "rendered_artifact_paths": list(row.rendered_artifact_paths),
        "rendered_candidate_count": row.rendered_candidate_count,
        "source_extensions": list(row.source_extensions),
        "target_extensions": list(row.target_extensions),
        "templates": list(row.templates),
        "type_tags": list(row.type_tags),
        "unplanned_dependency_count": row.unplanned_dependency_count,
        "variant_count": row.variant_count,
    }


def _candidate_dependency_report_dict(
    report: CandidateDependencyReport,
) -> dict[str, Any]:
    return {
        "ambiguous_primitive_names": list(report.ambiguous_primitive_names),
        "available": report.is_available,
        "diagnostic_counts": [
            _diagnostic_count_dict(item) for item in report.diagnostic_counts
        ],
        "edges": [_candidate_dependency_edge_dict(row) for row in report.edge_rows],
        "fallback_primitive_names": list(report.fallback_primitive_names),
        "issues": [_candidate_dependency_issue_dict(row) for row in report.issue_rows],
        "required_candidate_ids": list(report.required_candidate_ids),
        "required_primitive_names": list(report.required_primitive_names),
        "root_candidate_ids": list(report.root_candidate_ids),
        "unresolved_primitive_names": list(report.unresolved_primitive_names),
        "unsupported_primitive_names": list(report.unsupported_primitive_names),
    }


def _candidate_dependency_edge_dict(
    row: CandidateDependencyEdgeRow,
) -> dict[str, Any]:
    return {
        "is_self_reference": row.is_self_reference,
        "raw_target": row.raw_target,
        "source_candidate_id": row.source_candidate_id,
        "source_primitive_name": row.source_primitive_name,
        "target_candidate_id": row.target_candidate_id,
        "target_primitive_name": row.target_primitive_name,
        "type_arguments": list(row.type_arguments),
    }


def _candidate_dependency_issue_dict(
    row: CandidateDependencyIssueRow,
) -> dict[str, Any]:
    return {
        "candidate_ids": list(row.candidate_ids),
        "detail": row.detail,
        "fallback_primitive_name": row.fallback_primitive_name,
        "raw_target": row.raw_target,
        "reason": row.reason,
        "source_candidate_id": row.source_candidate_id,
        "source_primitive_name": row.source_primitive_name,
        "target_primitive_name": row.target_primitive_name,
        "type_arguments": list(row.type_arguments),
    }


def _backend_row_dict(row: BackendCoverageRow) -> dict[str, Any]:
    return {
        "backend_id": row.backend_id,
        "planned_artifact_count": row.planned_artifact_count,
        "planned_artifact_paths": list(row.planned_artifact_paths),
        "rendered_artifact_count": row.rendered_artifact_count,
        "rendered_artifact_paths": list(row.rendered_artifact_paths),
        "rendered_candidate_count": row.rendered_candidate_count,
    }


def _legacy_row_dict(fact: LegacyCoverageSelectedRowFact) -> dict[str, str]:
    values = {
        "effective_present": _legacy_bool(fact.effective_present),
        "extension": fact.extension,
        "has_intrinsic": _legacy_bool(fact.has_intrinsic),
        "has_lang_block": _legacy_bool(fact.has_lang_block),
        "has_tsil": _legacy_bool(fact.has_tsil),
        "language": fact.language,
        "missing_effective": _legacy_bool(fact.missing_effective),
        "missing_intrinsic": _legacy_bool(fact.missing_intrinsic),
        "missing_lang_block": _legacy_bool(fact.missing_lang_block),
        "missing_tsil": _legacy_bool(fact.missing_tsil),
        "primitive": fact.primitive,
        "primitive_class": fact.primitive_class,
        "template": fact.template,
        "type": fact.type_tag,
    }
    return {field_name: values[field_name] for field_name in _LEGACY_COVERAGE_ROW_FIELD_ORDER}


def _legacy_bool(value: bool) -> str:
    return "true" if value else "false"


def _required_bool(value: bool | None) -> bool:
    if value is None:
        raise AssertionError("required legacy coverage row bool was not validated")
    return value


def _matches_exact_legacy_row_key(
    row: PrimitiveCoverageRow,
    request: LegacyCoverageRowAdapterRequest,
) -> bool:
    return (
        row.target_extensions == (request.extension,)
        and row.candidate_backends == (request.language,)
        and row.type_tags == (request.type_tag,)
    )


def _contains_legacy_row_key(
    row: PrimitiveCoverageRow,
    request: LegacyCoverageRowAdapterRequest,
) -> bool:
    return (
        request.extension in row.target_extensions
        and request.language in row.candidate_backends
        and request.type_tag in row.type_tags
    )


def _legacy_fact_diagnostics(
    row: PrimitiveCoverageRow,
    request: LegacyCoverageRowAdapterRequest,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if row.primitive_classes != (_SELECTED_LEGACY_PRIMITIVE_CLASS,):
        diagnostics.append(
            Diagnostic.error(
                "TSL-LEGACY-COVERAGE-MISSING-METADATA",
                (
                    "legacy coverage row adapter requires primitive class metadata "
                    f"{_SELECTED_LEGACY_PRIMITIVE_CLASS!r} for {request.key!r}"
                ),
            )
        )
    if row.templates != (_SELECTED_LEGACY_TEMPLATE,):
        diagnostics.append(
            Diagnostic.error(
                "TSL-LEGACY-COVERAGE-MISSING-METADATA",
                (
                    "legacy coverage row adapter requires template metadata "
                    f"{_SELECTED_LEGACY_TEMPLATE!r} for {request.key!r}"
                ),
            )
        )

    missing_bool_fields = tuple(
        field_name
        for field_name in (
            "has_tsil",
            "has_intrinsic",
            "has_lang_block",
            "effective_present",
        )
        if getattr(row, field_name) is None
    )
    if missing_bool_fields:
        diagnostics.append(
            Diagnostic.error(
                "TSL-LEGACY-COVERAGE-MISSING-REPORT-FIELD",
                (
                    "legacy coverage row adapter requires typed report boolean "
                    f"fields {missing_bool_fields!r} for {request.key!r}"
                ),
            )
        )
    return tuple(diagnostics)


def _aggregate_legacy_row_diagnostic(
    request: LegacyCoverageRowAdapterRequest,
    rows: tuple[PrimitiveCoverageRow, ...],
) -> Diagnostic:
    available = tuple(
        (
            row.target_extensions,
            row.candidate_backends,
            row.type_tags,
        )
        for row in rows
    )
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-AGGREGATE-ROW",
        (
            "legacy coverage row adapter requires one exact typed selected-row "
            f"fact for {request.key!r}; aggregate row fields were {available!r}"
        ),
    )


def _missing_required_report_fields_diagnostic(
    request: LegacyCoverageRowAdapterRequest,
    rows: tuple[PrimitiveCoverageRow, ...],
) -> Diagnostic:
    available = tuple(
        (
            row.target_extensions,
            row.candidate_backends,
            row.type_tags,
        )
        for row in rows
    )
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-MISSING-REPORT-FIELD",
        (
            "legacy coverage row adapter requires typed extension/language/type "
            f"fields for {request.key!r}; available row fields were {available!r}"
        ),
    )


def _unsupported_legacy_request_diagnostic(
    request: LegacyCoverageRowAdapterRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-UNSUPPORTED-REQUEST",
        (
            "legacy coverage row adapter only supports selected request "
            f"{_SELECTED_LEGACY_COVERAGE_REQUEST!r}; got {request.key!r}"
        ),
    )


def _unsupported_legacy_fact_diagnostic(
    fact: LegacyCoverageSelectedRowFact,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-UNSUPPORTED-FACT",
        (
            "legacy coverage row serializer only supports selected row "
            f"{_SELECTED_LEGACY_COVERAGE_REQUEST!r}; got {fact.key!r}"
        ),
    )


def _missing_legacy_row_diagnostic(
    request: LegacyCoverageRowAdapterRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-MISSING-ROW",
        f"accepted coverage report has no primitive row for {request.key!r}",
    )


def _ambiguous_legacy_row_diagnostic(
    request: LegacyCoverageRowAdapterRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-AMBIGUOUS-ROW",
        f"accepted coverage report has multiple matching rows for {request.key!r}",
    )


def _raw_evidence_diagnostic(value: object) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LEGACY-COVERAGE-RAW-EVIDENCE",
        (
            "legacy coverage row adapter requires accepted typed coverage/report "
            f"data, not {type(value).__name__}"
        ),
    )
