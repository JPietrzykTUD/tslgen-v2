from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _golden import (
    assert_artifact_digest_map_stable,
    assert_artifact_set_matches_golden,
    golden_artifact,
)
from tslgen.io.artifact_writer import write_artifacts
from tslgen.io.write_report import ArtifactWriteOptions
from tslgen.reporting.coverage import (
    BackendCoverageRow,
    DiagnosticCount,
    PipelineCoverageReport,
    PrimitiveCoverageRow,
    SelectionCoverageSummary,
)
from tslgen.reporting.html import (
    coverage_report_html_artifact_set,
    render_coverage_report_html,
)


def representative_report() -> PipelineCoverageReport:
    return PipelineCoverageReport(
        primitive_rows=(
            PrimitiveCoverageRow(
                primitive_name="helper",
                declaration_count=1,
                is_required_by_dependency_closure=True,
            ),
            PrimitiveCoverageRow(
                primitive_name="slice_add",
                declaration_count=1,
                variant_count=1,
                candidate_count=1,
                candidates_with_opaque_bodies=1,
                rendered_candidate_count=1,
                direct_dependency_count=1,
                unplanned_dependency_count=1,
                templates=("binary",),
                candidate_backends=("cpp",),
                target_extensions=("scalar",),
                source_extensions=("scalar",),
                type_tags=("si32",),
                direct_dependency_names=("helper",),
                rendered_artifact_paths=("generated.hpp",),
            ),
        ),
        selection=SelectionCoverageSummary(
            requested_backend="cpp",
            requested_primitives=("slice_add",),
            requested_templates=("binary",),
            requested_extensions=("scalar",),
            allowed_extensions=("scalar",),
            normalized_cpu_flags=("sse",),
            variant_count=1,
            implementation_plan_count=1,
        ),
        backend_rows=(
            BackendCoverageRow(
                backend_id="cpp",
                planned_artifact_count=1,
                rendered_artifact_count=1,
                rendered_candidate_count=1,
                planned_artifact_paths=("generated.hpp",),
                rendered_artifact_paths=("generated.hpp",),
            ),
        ),
        diagnostic_counts=(
            DiagnosticCount(
                severity="warning",
                code="TSL-REPORT-WARNING",
                count=2,
            ),
        ),
        unplanned_dependency_primitives=("helper",),
        deferred_categories=("full_template_rendering", "tsil_lowering"),
    )


class CoverageHtmlReportingTests(unittest.TestCase):
    def test_html_report_matches_golden_artifact(self) -> None:
        artifact_set = coverage_report_html_artifact_set(representative_report())

        assert_artifact_set_matches_golden(
            self,
            artifact_set,
            (
                golden_artifact(
                    "reports/coverage.html",
                    "golden",
                    "reports",
                    "coverage_report.html",
                ),
            ),
        )
        artifact = artifact_set.artifacts_by_path["reports/coverage.html"]
        self.assertEqual(artifact.metadata["artifact_kind"], "coverage-html-report")
        self.assertEqual(artifact.metadata["content_type"], "text/html; charset=utf-8")
        self.assertEqual(artifact.metadata["primitive_count"], 2)
        self.assertEqual(artifact.metadata["diagnostic_count"], 2)

    def test_html_rendering_escapes_dynamic_report_values(self) -> None:
        report = PipelineCoverageReport(
            primitive_rows=(
                PrimitiveCoverageRow(
                    primitive_name='alpha<script data-x="1">',
                    declaration_count=1,
                    templates=("binary<&>",),
                    candidate_backends=("cpp<&>",),
                ),
            ),
            selection=SelectionCoverageSummary(
                requested_backend='cpp"unsafe"',
                requested_primitives=('alpha<script data-x="1">',),
            ),
            backend_rows=(
                BackendCoverageRow(
                    backend_id="cpp<&>",
                    planned_artifact_paths=("generated<&>.hpp",),
                ),
            ),
            diagnostic_counts=(
                DiagnosticCount(
                    severity="warning",
                    code='TSL-REPORT-<UNSAFE-"CODE">',
                    count=1,
                ),
            ),
            deferred_categories=("unsafe<&>",),
        )

        html = render_coverage_report_html(report)

        self.assertIn("alpha&lt;script data-x=&quot;1&quot;&gt;", html)
        self.assertIn("binary&lt;&amp;&gt;", html)
        self.assertIn("cpp&quot;unsafe&quot;", html)
        self.assertIn("TSL-REPORT-&lt;UNSAFE-&quot;CODE&quot;&gt;", html)
        self.assertNotIn('alpha<script data-x="1">', html)
        self.assertNotIn('TSL-REPORT-<UNSAFE-"CODE">', html)

    def test_html_artifact_is_deterministic_and_writer_compatible(self) -> None:
        first = coverage_report_html_artifact_set(representative_report())
        second = coverage_report_html_artifact_set(representative_report())

        self.assertEqual(first, second)
        assert_artifact_digest_map_stable(self, first, second)

        with TemporaryDirectory() as temp:
            write_report = write_artifacts(
                first,
                ArtifactWriteOptions(output_root=Path(temp)),
            )

            self.assertTrue(write_report.is_ok, write_report.diagnostics)
            self.assertEqual(write_report.written_paths, ("reports/coverage.html",))
            written = Path(temp) / "reports" / "coverage.html"
            self.assertEqual(
                written.read_text(encoding="utf-8"),
                first.artifacts_by_path["reports/coverage.html"].content,
            )

if __name__ == "__main__":
    unittest.main()
