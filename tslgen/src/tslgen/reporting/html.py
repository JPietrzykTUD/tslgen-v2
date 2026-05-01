from __future__ import annotations

from html import escape
from pathlib import PurePosixPath

from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import Artifact, ArtifactSet
from tslgen.reporting.coverage import (
    BackendCoverageRow,
    CandidateDependencyReport,
    PipelineCoverageReport,
    PrimitiveCoverageRow,
    SelectionCoverageSummary,
)


HTML_REPORT_SCHEMA_VERSION = 1
DEFAULT_COVERAGE_HTML_PATH = PurePosixPath("reports/coverage.html")


def render_coverage_report_html(report: PipelineCoverageReport) -> str:
    """Render a deterministic legacy-style HTML summary for coverage data."""
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>TSL Coverage Report</title>",
        "</head>",
        "<body>",
        "  <h1>TSL Coverage Report</h1>",
        *_summary_section(report),
        *_selection_section(report.selection),
        *_primitive_section(report.primitive_rows),
        *_candidate_dependency_section(report.candidate_dependencies),
        *_backend_section(report.backend_rows),
        *_diagnostic_section(report),
        *_deferred_section(report.deferred_categories),
        "</body>",
        "</html>",
    ]
    return "\n".join(lines) + "\n"


def coverage_report_html_artifact(
    report: PipelineCoverageReport,
    *,
    logical_path: str | PurePosixPath = DEFAULT_COVERAGE_HTML_PATH,
) -> Artifact:
    return Artifact(
        logical_path=PurePosixPath(logical_path),
        content=render_coverage_report_html(report),
        metadata=_report_artifact_metadata(report),
    )


def coverage_report_html_artifact_set(
    report: PipelineCoverageReport,
    *,
    logical_path: str | PurePosixPath = DEFAULT_COVERAGE_HTML_PATH,
) -> ArtifactSet:
    metadata = _report_artifact_metadata(report)
    return ArtifactSet(
        (coverage_report_html_artifact(report, logical_path=logical_path),),
        metadata=metadata,
    )


def _summary_section(report: PipelineCoverageReport) -> tuple[str, ...]:
    rows = (
        ("Total primitives", report.total_primitives),
        ("Primitives with candidates", report.primitives_with_candidates),
        ("Primitives without candidates", report.primitives_without_candidates),
        ("Total candidates", report.total_candidates),
        ("Candidates with opaque bodies", report.candidates_with_opaque_bodies),
        ("Candidates without bodies", report.candidates_without_bodies),
        ("Rendered artifacts", report.rendered_artifacts),
        ("Required dependency primitives", report.required_dependency_primitives),
        (
            "Unplanned dependency primitives",
            _joined(report.unplanned_dependency_primitives),
        ),
    )
    return (
        '  <section id="summary">',
        "    <h2>Summary</h2>",
        "    <table>",
        "      <tbody>",
        *(
            f"        <tr><th scope=\"row\">{_text(label)}</th><td>{_text(value)}</td></tr>"
            for label, value in rows
        ),
        "      </tbody>",
        "    </table>",
        "  </section>",
    )


def _selection_section(
    selection: SelectionCoverageSummary | None,
) -> tuple[str, ...]:
    if selection is None:
        return (
            '  <section id="selection">',
            "    <h2>Selection Context</h2>",
            "    <p>No selection context was available.</p>",
            "  </section>",
        )

    rows = (
        ("Requested backend", selection.requested_backend or "none"),
        ("Requested primitives", _joined(selection.requested_primitives)),
        ("Requested templates", _joined(selection.requested_templates)),
        ("Requested extensions", _joined(selection.requested_extensions)),
        ("Allowed extensions", _joined(selection.allowed_extensions)),
        ("Normalized CPU flags", _joined(selection.normalized_cpu_flags)),
        ("Variant count", selection.variant_count),
        ("Implementation plan count", selection.implementation_plan_count),
    )
    return (
        '  <section id="selection">',
        "    <h2>Selection Context</h2>",
        "    <table>",
        "      <tbody>",
        *(
            f"        <tr><th scope=\"row\">{_text(label)}</th><td>{_text(value)}</td></tr>"
            for label, value in rows
        ),
        "      </tbody>",
        "    </table>",
        "  </section>",
    )


def _primitive_section(
    rows: tuple[PrimitiveCoverageRow, ...],
) -> tuple[str, ...]:
    return (
        '  <section id="primitive-coverage">',
        "    <h2>Primitive Coverage</h2>",
        "    <table>",
        "      <thead>",
        "        <tr>"
        "<th>Primitive</th><th>Declarations</th><th>Variants</th>"
        "<th>Candidates</th><th>Opaque bodies</th><th>Missing bodies</th>"
        "<th>Rendered candidates</th><th>Dependencies</th>"
        "<th>Unplanned dependencies</th><th>Templates</th><th>Backends</th>"
        "<th>Target extensions</th><th>Type tags</th><th>Rendered artifacts</th>"
        "</tr>",
        "      </thead>",
        "      <tbody>",
        *(_primitive_row(row) for row in rows),
        "      </tbody>",
        "    </table>",
        "  </section>",
    )


def _primitive_row(row: PrimitiveCoverageRow) -> str:
    cells = (
        row.primitive_name,
        row.declaration_count,
        row.variant_count,
        row.candidate_count,
        row.candidates_with_opaque_bodies,
        row.candidates_without_bodies,
        row.rendered_candidate_count,
        _joined(row.direct_dependency_names),
        row.unplanned_dependency_count,
        _joined(row.templates),
        _joined(row.candidate_backends),
        _joined(row.target_extensions),
        _joined(row.type_tags),
        _joined(row.rendered_artifact_paths),
    )
    return _table_row(cells)


def _candidate_dependency_section(report: CandidateDependencyReport) -> tuple[str, ...]:
    summary_rows = (
        ("Available", "yes" if report.is_available else "no"),
        ("Root candidates", _joined(report.root_candidate_ids)),
        ("Required candidates", _joined(report.required_candidate_ids)),
        ("Required primitives", _joined(report.required_primitive_names)),
        ("Fallback primitives", _joined(report.fallback_primitive_names)),
        ("Ambiguous primitives", _joined(report.ambiguous_primitive_names)),
        ("Unresolved primitives", _joined(report.unresolved_primitive_names)),
        ("Unsupported primitives", _joined(report.unsupported_primitive_names)),
        ("Candidate dependency diagnostics", report.diagnostic_count),
    )
    return (
        '  <section id="candidate-dependencies">',
        "    <h2>Candidate Dependencies</h2>",
        "    <table>",
        "      <tbody>",
        *(
            f"        <tr><th scope=\"row\">{_text(label)}</th><td>{_text(value)}</td></tr>"
            for label, value in summary_rows
        ),
        "      </tbody>",
        "    </table>",
        *_candidate_dependency_edges(report),
        *_candidate_dependency_issues(report),
        *_candidate_dependency_diagnostics(report),
        "  </section>",
    )


def _candidate_dependency_edges(
    report: CandidateDependencyReport,
) -> tuple[str, ...]:
    if not report.edge_rows:
        return ("    <p>No candidate-specific dependency edges were available.</p>",)
    return (
        "    <h3>Edges</h3>",
        "    <table>",
        "      <thead>",
        "        <tr><th>Source candidate</th><th>Source primitive</th>"
        "<th>Target candidate</th><th>Target primitive</th><th>Raw target</th>"
        "<th>Type arguments</th><th>Self reference</th></tr>",
        "      </thead>",
        "      <tbody>",
        *(
            _table_row(
                (
                    row.source_candidate_id,
                    row.source_primitive_name,
                    row.target_candidate_id,
                    row.target_primitive_name,
                    row.raw_target,
                    _joined(row.type_arguments),
                    "yes" if row.is_self_reference else "no",
                )
            )
            for row in report.edge_rows
        ),
        "      </tbody>",
        "    </table>",
    )


def _candidate_dependency_issues(
    report: CandidateDependencyReport,
) -> tuple[str, ...]:
    if not report.issue_rows:
        return ("    <p>No candidate-specific dependency issues were available.</p>",)
    return (
        "    <h3>Issues And Fallbacks</h3>",
        "    <table>",
        "      <thead>",
        "        <tr><th>Source candidate</th><th>Source primitive</th>"
        "<th>Target primitive</th><th>Reason</th><th>Fallback primitive</th>"
        "<th>Raw target</th><th>Type arguments</th><th>Candidate ids</th>"
        "<th>Detail</th></tr>",
        "      </thead>",
        "      <tbody>",
        *(
            _table_row(
                (
                    row.source_candidate_id,
                    row.source_primitive_name,
                    row.target_primitive_name,
                    row.reason,
                    row.fallback_primitive_name,
                    row.raw_target,
                    _joined(row.type_arguments),
                    _joined(row.candidate_ids),
                    row.detail,
                )
            )
            for row in report.issue_rows
        ),
        "      </tbody>",
        "    </table>",
    )


def _candidate_dependency_diagnostics(
    report: CandidateDependencyReport,
) -> tuple[str, ...]:
    if not report.diagnostic_counts:
        return (
            "    <p>No candidate-specific dependency diagnostics were available.</p>",
        )
    return (
        "    <h3>Diagnostics</h3>",
        "    <table>",
        "      <thead>",
        "        <tr><th>Severity</th><th>Code</th><th>Count</th></tr>",
        "      </thead>",
        "      <tbody>",
        *(
            _table_row((item.severity, item.code, item.count))
            for item in report.diagnostic_counts
        ),
        "      </tbody>",
        "    </table>",
    )


def _backend_section(rows: tuple[BackendCoverageRow, ...]) -> tuple[str, ...]:
    return (
        '  <section id="backend-coverage">',
        "    <h2>Backend Coverage</h2>",
        "    <table>",
        "      <thead>",
        "        <tr><th>Backend</th><th>Planned artifacts</th>"
        "<th>Rendered artifacts</th><th>Rendered candidates</th>"
        "<th>Planned paths</th><th>Rendered paths</th></tr>",
        "      </thead>",
        "      <tbody>",
        *(_backend_row(row) for row in rows),
        "      </tbody>",
        "    </table>",
        "  </section>",
    )


def _backend_row(row: BackendCoverageRow) -> str:
    cells = (
        row.backend_id,
        row.planned_artifact_count,
        row.rendered_artifact_count,
        row.rendered_candidate_count,
        _joined(row.planned_artifact_paths),
        _joined(row.rendered_artifact_paths),
    )
    return _table_row(cells)


def _diagnostic_section(report: PipelineCoverageReport) -> tuple[str, ...]:
    return (
        '  <section id="diagnostics">',
        "    <h2>Diagnostics Summary</h2>",
        "    <table>",
        "      <thead>",
        "        <tr><th>Severity</th><th>Code</th><th>Count</th></tr>",
        "      </thead>",
        "      <tbody>",
        *(
            _table_row((item.severity, item.code, item.count))
            for item in report.diagnostic_counts
        ),
        "      </tbody>",
        "    </table>",
        "  </section>",
    )


def _deferred_section(categories: tuple[str, ...]) -> tuple[str, ...]:
    return (
        '  <section id="deferred-categories">',
        "    <h2>Deferred Categories</h2>",
        "    <ul>",
        *(f"      <li>{_text(category)}</li>" for category in categories),
        "    </ul>",
        "  </section>",
    )


def _report_artifact_metadata(
    report: PipelineCoverageReport,
) -> FrozenMap[str, CatalogValue]:
    return FrozenMap[str, CatalogValue](
        {
            "artifact_kind": "coverage-html-report",
            "content_type": "text/html; charset=utf-8",
            "diagnostic_count": sum(item.count for item in report.diagnostic_counts),
            "html_report_schema_version": HTML_REPORT_SCHEMA_VERSION,
            "primitive_count": report.total_primitives,
            "report_schema_version": 1,
        }
    )


def _table_row(cells: tuple[object, ...]) -> str:
    return "        <tr>" + "".join(f"<td>{_text(cell)}</td>" for cell in cells) + "</tr>"


def _joined(values: tuple[str, ...]) -> str:
    if not values:
        return "none"
    return ", ".join(values)


def _text(value: object) -> str:
    return escape(str(value), quote=True)
