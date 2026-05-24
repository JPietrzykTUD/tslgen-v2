from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from _helpers import assert_diagnostic, fixture_path
from tslgen.analysis.selection import SelectionRequest
from tslgen.api import PipelineConfig, run_pipeline
from tslgen.config.model import SourceConfig
from tslgen.domain.backends import ArtifactSpec, BackendManifest, BackendManifestSet
from tslgen.reporting.coverage import (
    LegacyCoverageRowAdapterRequest,
    LegacyCoverageSelectedRowFact,
    PipelineCoverageReport,
    PrimitiveCoverageRow,
    adapt_legacy_coverage_row,
    coverage_report_from_pipeline_result,
    coverage_report_to_json,
    legacy_coverage_row_to_json,
    selected_legacy_coverage_request,
    selected_legacy_coverage_row_to_json,
)
from tslgen.reporting.html import render_coverage_report_html


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


def selected_legacy_report(
    row: PrimitiveCoverageRow | None = None,
) -> PipelineCoverageReport:
    return PipelineCoverageReport(
        primitive_rows=(
            row
            if row is not None
            else PrimitiveCoverageRow(
                primitive_name="add",
                declaration_count=1,
                variant_count=1,
                candidate_count=1,
                candidates_with_opaque_bodies=1,
                templates=("v:=(v,v)",),
                candidate_backends=("cpp",),
                target_extensions=("avx2",),
                source_extensions=("avx2",),
                type_tags=("f32",),
                primitive_classes=("fundamental",),
                has_tsil=True,
                has_intrinsic=False,
                has_lang_block=False,
                effective_present=True,
            ),
        )
    )


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

    def test_selected_legacy_coverage_row_matches_golden_fixture(self) -> None:
        result = selected_legacy_coverage_row_to_json(
            selected_legacy_report(),
            selected_legacy_coverage_request(),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        rendered = result.unwrap()
        expected = fixture_path(
            "golden",
            "parity",
            "reports",
            "add_avx2_f32_coverage_row.json",
        ).read_text(encoding="utf-8")
        self.assertEqual(rendered, expected)

        payload = json.loads(rendered, object_pairs_hook=OrderedDict)
        self.assertEqual(
            tuple(payload.keys()),
            (
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
            ),
        )
        self.assertEqual(
            payload,
            OrderedDict(
                (
                    ("effective_present", "true"),
                    ("extension", "avx2"),
                    ("has_intrinsic", "false"),
                    ("has_lang_block", "false"),
                    ("has_tsil", "true"),
                    ("language", "cpp"),
                    ("missing_effective", "false"),
                    ("missing_intrinsic", "true"),
                    ("missing_lang_block", "true"),
                    ("missing_tsil", "false"),
                    ("primitive", "add"),
                    ("primitive_class", "fundamental"),
                    ("template", "v:=(v,v)"),
                    ("type", "f32"),
                )
            ),
        )

    def test_selected_legacy_coverage_row_has_provenance_fixture(self) -> None:
        provenance = fixture_path(
            "golden",
            "parity",
            "reports",
            "add_avx2_f32_coverage_row.provenance.md",
        ).read_text(encoding="utf-8")

        self.assertIn("frozen/out/reports/primitive_coverage.json:57762-57777", provenance)
        self.assertIn("frozen/tools/report_primitive_coverage.py:242-266", provenance)
        self.assertIn("COVERAGE-ADD-AVX2-F32-ROW", provenance)
        self.assertIn("not loaded from `frozen/` at runtime", provenance)

    def test_selected_legacy_coverage_row_serialization_is_deterministic(self) -> None:
        report = selected_legacy_report()
        request = selected_legacy_coverage_request()

        first = selected_legacy_coverage_row_to_json(report, request)
        second = selected_legacy_coverage_row_to_json(report, request)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_selected_legacy_coverage_row_adapter_exposes_typed_fact(self) -> None:
        fact_result = adapt_legacy_coverage_row(
            selected_legacy_report(),
            selected_legacy_coverage_request(),
        )

        self.assertTrue(fact_result.is_ok, fact_result.diagnostics)
        fact = fact_result.unwrap()
        self.assertEqual(fact.primitive, "add")
        self.assertEqual(fact.extension, "avx2")
        self.assertEqual(fact.language, "cpp")
        self.assertEqual(fact.type_tag, "f32")
        self.assertEqual(fact.primitive_class, "fundamental")
        self.assertEqual(fact.template, "v:=(v,v)")
        self.assertTrue(fact.has_tsil)
        self.assertFalse(fact.has_intrinsic)
        self.assertFalse(fact.has_lang_block)
        self.assertTrue(fact.effective_present)
        self.assertFalse(fact.missing_tsil)
        self.assertTrue(fact.missing_intrinsic)
        self.assertTrue(fact.missing_lang_block)
        self.assertFalse(fact.missing_effective)

    def test_selected_legacy_coverage_row_rejects_unsupported_request(self) -> None:
        result = adapt_legacy_coverage_row(
            selected_legacy_report(),
            LegacyCoverageRowAdapterRequest(
                primitive="sub",
                extension="avx2",
                language="cpp",
                type_tag="f32",
            ),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-UNSUPPORTED-REQUEST",
            severity="error",
        )

    def test_selected_legacy_coverage_row_reports_missing_row(self) -> None:
        result = adapt_legacy_coverage_row(
            PipelineCoverageReport(
                primitive_rows=(
                    PrimitiveCoverageRow(
                        primitive_name="sub",
                        declaration_count=1,
                    ),
                )
            ),
            selected_legacy_coverage_request(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-MISSING-ROW",
            severity="error",
        )

    def test_selected_legacy_coverage_row_reports_ambiguous_row(self) -> None:
        row = selected_legacy_report().primitive_rows[0]
        result = adapt_legacy_coverage_row(
            PipelineCoverageReport(primitive_rows=(row, row)),
            selected_legacy_coverage_request(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-AMBIGUOUS-ROW",
            severity="error",
        )

    def test_selected_legacy_coverage_row_requires_typed_report_fields(self) -> None:
        row = replace(
            selected_legacy_report().primitive_rows[0],
            target_extensions=(),
        )
        result = adapt_legacy_coverage_row(
            selected_legacy_report(row),
            selected_legacy_coverage_request(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-MISSING-REPORT-FIELD",
            severity="error",
        )

    def test_selected_legacy_coverage_row_rejects_aggregate_row_fields(self) -> None:
        base_row = selected_legacy_report().primitive_rows[0]
        aggregate_cases = (
            replace(base_row, target_extensions=("avx2", "sse")),
            replace(base_row, candidate_backends=("cpp", "rust")),
            replace(base_row, type_tags=("f32", "si32")),
        )

        for row in aggregate_cases:
            with self.subTest(row=row):
                result = adapt_legacy_coverage_row(
                    selected_legacy_report(row),
                    selected_legacy_coverage_request(),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LEGACY-COVERAGE-AGGREGATE-ROW",
                    severity="error",
                )

    def test_selected_legacy_coverage_row_requires_boolean_report_fields(self) -> None:
        row = replace(
            selected_legacy_report().primitive_rows[0],
            has_intrinsic=None,
        )
        result = adapt_legacy_coverage_row(
            selected_legacy_report(row),
            selected_legacy_coverage_request(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-MISSING-REPORT-FIELD",
            severity="error",
        )

    def test_selected_legacy_coverage_row_requires_class_and_template_metadata(self) -> None:
        row = replace(
            selected_legacy_report().primitive_rows[0],
            primitive_classes=(),
            templates=(),
        )
        result = adapt_legacy_coverage_row(
            selected_legacy_report(row),
            selected_legacy_coverage_request(),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            tuple(diagnostic.code for diagnostic in result.diagnostics),
            (
                "TSL-LEGACY-COVERAGE-MISSING-METADATA",
                "TSL-LEGACY-COVERAGE-MISSING-METADATA",
            ),
        )

    def test_selected_legacy_coverage_row_rejects_raw_legacy_evidence(self) -> None:
        result = selected_legacy_coverage_row_to_json(
            {
                "primitive": "add",
                "extension": "avx2",
                "language": "cpp",
                "type": "f32",
            },
            selected_legacy_coverage_request(),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-RAW-EVIDENCE",
            severity="error",
        )

        serialized = legacy_coverage_row_to_json({"primitive": "add"})
        self.assertFalse(serialized.is_ok)
        assert_diagnostic(
            self,
            serialized.diagnostics[0],
            code="TSL-LEGACY-COVERAGE-RAW-EVIDENCE",
            severity="error",
        )

    def test_selected_legacy_coverage_row_serialization_does_not_read_sources(self) -> None:
        fact = adapt_legacy_coverage_row(
            selected_legacy_report(),
            selected_legacy_coverage_request(),
        ).unwrap()

        with patch(
            "pathlib.Path.read_text",
            side_effect=AssertionError("adapter serialization must not read files"),
        ):
            result = legacy_coverage_row_to_json(fact)

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertIn('"primitive": "add"', result.unwrap())

    def test_selected_legacy_coverage_row_serializer_rejects_unsupported_fact(self) -> None:
        unsupported_facts: tuple[LegacyCoverageSelectedRowFact, ...] = (
            replace(
                adapt_legacy_coverage_row(
                    selected_legacy_report(),
                    selected_legacy_coverage_request(),
                ).unwrap(),
                primitive="sub",
            ),
            replace(
                adapt_legacy_coverage_row(
                    selected_legacy_report(),
                    selected_legacy_coverage_request(),
                ).unwrap(),
                extension="sse",
            ),
            replace(
                adapt_legacy_coverage_row(
                    selected_legacy_report(),
                    selected_legacy_coverage_request(),
                ).unwrap(),
                language="rust",
            ),
            replace(
                adapt_legacy_coverage_row(
                    selected_legacy_report(),
                    selected_legacy_coverage_request(),
                ).unwrap(),
                type_tag="si32",
            ),
        )

        for fact in unsupported_facts:
            with self.subTest(fact=fact):
                result = legacy_coverage_row_to_json(fact)

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-LEGACY-COVERAGE-UNSUPPORTED-FACT",
                    severity="error",
                )

    def test_existing_redesign_report_json_and_html_remain_stable(self) -> None:
        report = PipelineCoverageReport(
            primitive_rows=(
                PrimitiveCoverageRow(
                    primitive_name="slice_add",
                    declaration_count=1,
                    templates=("binary",),
                    candidate_backends=("cpp",),
                    target_extensions=("scalar",),
                    type_tags=("si32",),
                    primitive_classes=("fundamental",),
                    has_tsil=True,
                    has_intrinsic=False,
                    has_lang_block=False,
                    effective_present=True,
                ),
            )
        )

        json_payload = json.loads(coverage_report_to_json(report))
        primitive_row = json_payload["primitive_rows"][0]
        self.assertNotIn("primitive_classes", primitive_row)
        self.assertNotIn("has_tsil", primitive_row)
        self.assertNotIn("has_intrinsic", primitive_row)
        self.assertNotIn("has_lang_block", primitive_row)
        self.assertNotIn("effective_present", primitive_row)

        html = render_coverage_report_html(report)
        self.assertIn("slice_add", html)
        self.assertNotIn("primitive_classes", html)


if __name__ == "__main__":
    unittest.main()
