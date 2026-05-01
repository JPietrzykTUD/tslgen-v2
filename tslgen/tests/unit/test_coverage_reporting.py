from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.selection import SelectionRequest
from tslgen.api import PipelineConfig, run_pipeline
from tslgen.config.model import SourceConfig
from tslgen.domain.backends import ArtifactSpec, BackendManifest, BackendManifestSet
from tslgen.reporting.coverage import (
    PipelineCoverageReport,
    PrimitiveCoverageRow,
    coverage_report_from_pipeline_result,
    coverage_report_to_json,
)


DEPENDENCY_PRIMITIVES = """prim<v:=(v,v)> helper(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "emit_return(left);"

prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
        implementation:
          tsil "call<primitive=helper>; emit_return(left + right);"
"""


SVE_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    sve:
      si32:
        requires []
        implementation:
          tsil "emit_return(left + right);"
"""


BASE_SOURCE_PATHS = (
    Path("tsldata/detail/flags.tsl"),
    Path("tsldata/detail/types.tsl"),
    Path("tsldata/detail/lane_sets.tsl"),
    Path("tsldata/extensions/extension.tsl"),
    Path("tsldata/detail/templates.tsl"),
)


def manifest_set(backend_id: str, extension: str) -> BackendManifestSet:
    return BackendManifestSet(
        (
            BackendManifest(
                version=1,
                backend_id=backend_id,
                language_id=backend_id,
                artifacts=(
                    ArtifactSpec(
                        kind="generated",
                        logical_name="generated",
                        extension=extension,
                    ),
                ),
            ),
        )
    )


def pipeline_config_for(
    primitive_path: Path,
    *,
    backend_id: str = "cpp",
    artifact_extension: str = "hpp",
    extension_names: tuple[str, ...] = ("scalar",),
    primitive_names: tuple[str, ...] = ("slice_add",),
) -> PipelineConfig:
    return PipelineConfig(
        source_config=SourceConfig(
            explicit_paths=(*BASE_SOURCE_PATHS, primitive_path),
            include_standard_library=False,
        ),
        selection_request=SelectionRequest(
            backend=backend_id,
            primitive_names=primitive_names,
            extension_names=extension_names,
            cpu_flags=("sse",),
            include_support_extensions=False,
        ),
        backend_manifests=manifest_set(backend_id, artifact_extension),
        render_backend=backend_id,
    )


def row_by_name(report: PipelineCoverageReport, name: str) -> PrimitiveCoverageRow:
    for row in report.primitive_rows:
        if row.primitive_name == name:
            return row
    raise AssertionError(f"missing primitive coverage row for {name!r}")


class CoverageReportingTests(unittest.TestCase):
    def test_report_summarizes_successful_pipeline_outputs(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "coverage_slice.tsl"
            primitive_path.write_text(DEPENDENCY_PRIMITIVES, encoding="utf-8")

            result = run_pipeline(pipeline_config_for(primitive_path))

            self.assertTrue(result.is_ok, result.diagnostics)
            report = coverage_report_from_pipeline_result(result)
            self.assertEqual(report.total_primitives, 2)
            self.assertEqual(report.primitives_with_candidates, 1)
            self.assertEqual(report.primitives_without_candidates, 1)
            self.assertEqual(report.total_candidates, 1)
            self.assertEqual(report.candidates_with_opaque_bodies, 1)
            self.assertEqual(report.candidates_without_bodies, 0)
            self.assertEqual(report.rendered_artifacts, 1)
            self.assertEqual(report.unplanned_dependency_primitives, ("helper",))
            self.assertIsNotNone(result.candidate_dependency_closure)
            self.assertTrue(report.candidate_dependencies.is_available)
            self.assertEqual(report.candidate_dependencies.edge_count, 0)
            self.assertEqual(report.candidate_dependencies.issue_count, 1)
            self.assertEqual(
                report.candidate_dependencies.fallback_primitive_names,
                ("helper",),
            )
            self.assertEqual(
                report.candidate_dependencies.unresolved_primitive_names,
                ("helper",),
            )
            self.assertEqual(
                tuple(
                    item.code
                    for item in report.candidate_dependencies.diagnostic_counts
                ),
                ("TSL-CANDIDATE-DEPENDENCY-MISSING",),
            )

            selection = report.selection
            self.assertIsNotNone(selection)
            assert selection is not None
            self.assertEqual(selection.requested_backend, "cpp")
            self.assertEqual(selection.allowed_extensions, ("scalar",))
            self.assertEqual(selection.variant_count, 1)

            slice_row = row_by_name(report, "slice_add")
            self.assertTrue(slice_row.has_candidates)
            self.assertTrue(slice_row.has_rendered_candidates)
            self.assertEqual(slice_row.direct_dependency_names, ("helper",))
            self.assertEqual(slice_row.unplanned_dependency_count, 1)
            self.assertEqual(slice_row.candidate_backends, ("cpp",))
            self.assertEqual(slice_row.target_extensions, ("scalar",))
            self.assertEqual(slice_row.type_tags, ("si32",))
            self.assertEqual(slice_row.rendered_artifact_paths, ("generated.hpp",))

            helper_row = row_by_name(report, "helper")
            self.assertFalse(helper_row.has_candidates)
            self.assertTrue(helper_row.is_required_by_dependency_closure)

            self.assertEqual(len(report.backend_rows), 1)
            backend_row = report.backend_rows[0]
            self.assertEqual(backend_row.backend_id, "cpp")
            self.assertEqual(backend_row.planned_artifact_count, 1)
            self.assertEqual(backend_row.rendered_artifact_count, 1)
            self.assertEqual(backend_row.rendered_candidate_count, 1)

    def test_report_exposes_candidate_dependency_edge_rows(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "coverage_slice.tsl"
            primitive_path.write_text(DEPENDENCY_PRIMITIVES, encoding="utf-8")

            result = run_pipeline(
                pipeline_config_for(
                    primitive_path,
                    primitive_names=("slice_add", "helper"),
                )
            )

            self.assertTrue(result.is_ok, result.diagnostics)
            report = coverage_report_from_pipeline_result(result)
            self.assertTrue(report.candidate_dependencies.is_available)
            self.assertEqual(report.candidate_dependencies.edge_count, 1)
            self.assertEqual(report.candidate_dependencies.issue_count, 0)
            edge = report.candidate_dependencies.edge_rows[0]
            self.assertEqual(edge.source_primitive_name, "slice_add")
            self.assertEqual(edge.target_primitive_name, "helper")
            self.assertEqual(edge.raw_target, "helper")
            self.assertEqual(edge.type_arguments, ())
            self.assertEqual(report.candidate_dependencies.fallback_primitive_names, ())
            self.assertEqual(report.unplanned_dependency_primitives, ())

    def test_report_identifies_missing_implementation_by_selection_context(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "coverage_sve_slice.tsl"
            primitive_path.write_text(SVE_PRIMITIVE, encoding="utf-8")

            result = run_pipeline(
                pipeline_config_for(
                    primitive_path,
                    backend_id="rust",
                    artifact_extension="rs",
                    extension_names=("sve",),
                )
            )

            self.assertFalse(result.is_ok)
            assert_diagnostic(
                self,
                result.diagnostics[0],
                code="TSL-CANDIDATE-NONE",
                severity="error",
            )
            report = coverage_report_from_pipeline_result(result)
            self.assertEqual(report.total_primitives, 1)
            self.assertEqual(report.primitives_with_candidates, 0)
            self.assertEqual(report.primitives_without_candidates, 1)
            self.assertEqual(report.total_candidates, 0)

            selection = report.selection
            self.assertIsNotNone(selection)
            assert selection is not None
            self.assertEqual(selection.requested_backend, "rust")
            self.assertEqual(selection.requested_extensions, ("sve",))
            self.assertEqual(selection.allowed_extensions, ("sve",))
            self.assertEqual(selection.variant_count, 1)

            row = row_by_name(report, "slice_add")
            self.assertEqual(row.variant_count, 1)
            self.assertEqual(row.candidate_count, 0)
            self.assertEqual(row.candidate_backends, ())

            self.assertEqual(len(report.diagnostic_counts), 1)
            self.assertEqual(report.diagnostic_counts[0].code, "TSL-CANDIDATE-NONE")
            self.assertEqual(report.diagnostic_counts[0].count, 1)

    def test_report_json_output_is_deterministic(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "coverage_slice.tsl"
            primitive_path.write_text(DEPENDENCY_PRIMITIVES, encoding="utf-8")
            config = pipeline_config_for(primitive_path)

            first = coverage_report_from_pipeline_result(run_pipeline(config))
            second = coverage_report_from_pipeline_result(run_pipeline(config))

            first_json = coverage_report_to_json(first)
            second_json = coverage_report_to_json(second)
            self.assertEqual(first_json, second_json)

            payload = json.loads(first_json)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["summary"]["total_primitives"], 2)
            self.assertEqual(
                payload["summary"]["unplanned_dependency_primitives"],
                ["helper"],
            )
            self.assertEqual(
                payload["summary"]["candidate_dependency_fallback_primitives"],
                ["helper"],
            )
            self.assertEqual(payload["summary"]["candidate_dependency_edges"], 0)
            self.assertEqual(payload["summary"]["candidate_dependency_issues"], 1)
            self.assertEqual(
                payload["candidate_dependencies"]["unresolved_primitive_names"],
                ["helper"],
            )
            self.assertEqual(
                payload["candidate_dependencies"]["issues"][0]["reason"],
                "missing",
            )
            self.assertEqual(
                [row["primitive_name"] for row in payload["primitive_rows"]],
                ["helper", "slice_add"],
            )

    def test_report_json_marks_candidate_dependencies_unavailable(self) -> None:
        payload = json.loads(
            coverage_report_to_json(PipelineCoverageReport(primitive_rows=()))
        )

        self.assertFalse(payload["candidate_dependencies"]["available"])
        self.assertEqual(payload["candidate_dependencies"]["edges"], [])
        self.assertEqual(payload["candidate_dependencies"]["issues"], [])
        self.assertEqual(
            payload["summary"]["candidate_dependency_fallback_primitives"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
