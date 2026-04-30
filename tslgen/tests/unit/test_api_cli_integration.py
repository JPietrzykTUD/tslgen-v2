from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _helpers import assert_diagnostic
from tslgen.api import (
    PipelineConfig,
    coverage_report,
    coverage_report_html,
    coverage_report_html_artifacts,
    coverage_report_json,
    run_pipeline,
    write_artifacts,
)
from tslgen.cli import run as run_cli
from tslgen.config.cli_adapter import parse_cli_config, parse_cli_invocation
from tslgen.config.model import SourceConfig
from tslgen.analysis.selection import SelectionRequest
from tslgen.domain.backends import ArtifactSpec, BackendManifest, BackendManifestSet
from tslgen.io.artifacts import artifact_digest_map


SIMPLE_PRIMITIVE = """prim<v:=(v,v)> slice_add(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires [sse]
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


def cpp_manifest_set() -> BackendManifestSet:
    return BackendManifestSet(
        (
            BackendManifest(
                version=1,
                backend_id="cpp",
                language_id="cpp",
                artifacts=(
                    ArtifactSpec(
                        kind="generated",
                        logical_name="generated",
                        extension="hpp",
                    ),
                ),
            ),
        )
    )


def pipeline_config_for(primitive_path: Path) -> PipelineConfig:
    return PipelineConfig(
        source_config=SourceConfig(
            explicit_paths=(*BASE_SOURCE_PATHS, primitive_path),
            include_standard_library=False,
        ),
        selection_request=SelectionRequest(
            backend="cpp",
            primitive_names=("slice_add",),
            extension_names=("scalar",),
            cpu_flags=("sse",),
            include_support_extensions=False,
        ),
        backend_manifests=cpp_manifest_set(),
        render_backend="cpp",
    )


def write_cpp_manifest(directory: Path) -> Path:
    manifest_path = directory / "backend_cpp.yaml"
    manifest_path.write_text(
        """version: 1
backend: cpp
artifact:
  name: generated
  extension: hpp
""",
        encoding="utf-8",
    )
    return manifest_path


def cli_args_for(
    primitive_path: Path,
    manifest_path: Path,
    *extra: str,
) -> tuple[str, ...]:
    source_args = tuple(
        item
        for path in (*BASE_SOURCE_PATHS, primitive_path)
        for item in ("--source", path.as_posix())
    )
    return (
        *source_args,
        "--manifest",
        manifest_path.as_posix(),
        "--backend",
        "cpp",
        "--render-backend",
        "cpp",
        "--primitive",
        "slice_add",
        "--extension",
        "scalar",
        "--cpu-flag",
        "sse",
        "--no-support-extensions",
        *extra,
    )


class ApiCliIntegrationTests(unittest.TestCase):
    def test_api_runs_cpp_summary_pipeline_from_explicit_config(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")

            result = run_pipeline(pipeline_config_for(primitive_path))

            self.assertTrue(result.is_ok, result.diagnostics)
            self.assertIsNotNone(result.artifacts)
            assert result.artifacts is not None
            self.assertEqual(
                tuple(
                    artifact.logical_path.as_posix()
                    for artifact in result.artifacts.artifacts
                ),
                ("generated.hpp",),
            )
            self.assertEqual(
                tuple(path.name for path in Path(temp).iterdir()),
                ("api_slice.tsl",),
            )

    def test_api_propagates_selection_diagnostics(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            config = PipelineConfig(
                source_config=SourceConfig(
                    explicit_paths=(*BASE_SOURCE_PATHS, primitive_path),
                    include_standard_library=False,
                ),
                selection_request=SelectionRequest(
                    primitive_names=("missing_primitive",),
                ),
                backend_manifests=cpp_manifest_set(),
                render_backend="cpp",
            )

            result = run_pipeline(config)

            self.assertFalse(result.is_ok)
            assert_diagnostic(
                self,
                result.diagnostics[0],
                code="TSL-SELECT-UNKNOWN-PRIMITIVE",
                severity="error",
            )
            self.assertIsNone(result.artifacts)

    def test_api_output_is_deterministic(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            config = pipeline_config_for(primitive_path)

            first = run_pipeline(config)
            second = run_pipeline(config)

            self.assertTrue(first.is_ok, first.diagnostics)
            self.assertTrue(second.is_ok, second.diagnostics)
            self.assertEqual(first.diagnostics, second.diagnostics)
            assert first.artifacts is not None
            assert second.artifacts is not None
            self.assertEqual(
                artifact_digest_map(first.artifacts),
                artifact_digest_map(second.artifacts),
            )

    def test_api_requires_manifests_for_rendering(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            config = PipelineConfig(
                source_config=SourceConfig(
                    explicit_paths=(*BASE_SOURCE_PATHS, primitive_path),
                    include_standard_library=False,
                ),
                selection_request=SelectionRequest(
                    backend="cpp",
                    primitive_names=("slice_add",),
                    extension_names=("scalar",),
                    cpu_flags=("sse",),
                    include_support_extensions=False,
                ),
                render_backend="cpp",
            )

            result = run_pipeline(config)

            self.assertFalse(result.is_ok)
            assert_diagnostic(
                self,
                result.diagnostics[0],
                code="TSL-PIPELINE-MANIFESTS-MISSING",
                severity="error",
            )

    def test_api_exposes_coverage_report_helpers(self) -> None:
        with TemporaryDirectory() as temp:
            primitive_path = Path(temp) / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            result = run_pipeline(pipeline_config_for(primitive_path))

            self.assertTrue(result.is_ok, result.diagnostics)
            report = coverage_report(result)
            report_json = coverage_report_json(report)
            report_html = coverage_report_html(result)
            report_artifacts = coverage_report_html_artifacts(result)

            payload = json.loads(report_json)
            self.assertEqual(payload["summary"]["total_primitives"], 1)
            self.assertIn("<h1>TSL Coverage Report</h1>", report_html)
            self.assertEqual(
                tuple(
                    artifact.logical_path.as_posix()
                    for artifact in report_artifacts.artifacts
                ),
                ("reports/coverage.html",),
            )

    def test_api_write_artifacts_helper_uses_writer_boundary(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            result = run_pipeline(pipeline_config_for(primitive_path))

            self.assertTrue(result.is_ok, result.diagnostics)
            assert result.artifacts is not None
            report = write_artifacts(result.artifacts, output_root, dry_run=True)

            self.assertTrue(report.is_ok, report.diagnostics)
            self.assertEqual(report.would_write_paths, ("generated.hpp",))
            self.assertFalse((output_root / "generated.hpp").exists())

    def test_cli_parse_success_without_hardware_detection(self) -> None:
        calls = 0

        def hardware_flags() -> tuple[str, ...]:
            nonlocal calls
            calls += 1
            return ("sse",)

        result = parse_cli_config(
            ("--source", "input.tsl", "--cpu-flag", "sse"),
            hardware_flags_provider=hardware_flags,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(calls, 0)
        config = result.unwrap()
        self.assertEqual(config.source_config.explicit_paths, (Path("input.tsl"),))
        self.assertEqual(config.selection_request.cpu_flags, ("sse",))

    def test_cli_invocation_parses_report_and_write_options(self) -> None:
        result = parse_cli_invocation(
            (
                "--source",
                "input.tsl",
                "--coverage-report",
                "html",
                "--output-root",
                "out",
                "--dry-run",
                "--no-skip-unchanged",
            ),
            hardware_flags_provider=lambda: (),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        config = result.unwrap()
        self.assertEqual(config.coverage_report_format, "html")
        self.assertEqual(config.output_root, Path("out"))
        self.assertTrue(config.write_dry_run)
        self.assertFalse(config.write_skip_unchanged)
        self.assertEqual(config.pipeline_config.source_config.explicit_paths, (Path("input.tsl"),))

    def test_cli_rejects_write_options_without_output_root(self) -> None:
        result = parse_cli_invocation(
            ("--source", "input.tsl", "--dry-run"),
            hardware_flags_provider=lambda: (),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CLI-WRITE-OPTIONS",
            severity="error",
        )

    def test_cli_rejects_unknown_report_format_cleanly(self) -> None:
        result = parse_cli_invocation(
            ("--source", "input.tsl", "--coverage-report", "xml"),
            hardware_flags_provider=lambda: (),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CLI-ARGUMENTS",
            severity="error",
        )
        self.assertIn("invalid choice", result.diagnostics[0].message)

    def test_cli_hardware_autodetect_is_injected(self) -> None:
        calls = 0

        def hardware_flags() -> tuple[str, ...]:
            nonlocal calls
            calls += 1
            return ("sse", "avx2")

        result = parse_cli_config(
            ("--source", "input.tsl", "--hardware-auto"),
            hardware_flags_provider=hardware_flags,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(calls, 1)
        self.assertEqual(result.unwrap().selection_request.cpu_flags, ("sse", "avx2"))

    def test_cli_rejects_hardware_auto_with_explicit_flags(self) -> None:
        result = parse_cli_config(
            ("--source", "input.tsl", "--hardware-auto", "--cpu-flag", "sse"),
            hardware_flags_provider=lambda: ("sse",),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CLI-HARDWARE-CONFLICT",
            severity="error",
        )

    def test_cli_rejects_unknown_options(self) -> None:
        result = parse_cli_config(("--bogus",), hardware_flags_provider=lambda: ())

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-CLI-ARGUMENTS",
            severity="error",
        )

    def test_cli_run_returns_nonzero_on_pipeline_errors(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        exit_code = run_cli(
            ("--source", "missing-input.tsl", "--primitive", "slice_add"),
            stdout=stdout,
            stderr=stderr,
            hardware_flags_provider=lambda: (),
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("TSL-SRC-MISSING", stderr.getvalue())

    def test_cli_prints_json_coverage_report_without_writing(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--coverage-report",
                    "json",
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["summary"]["total_primitives"], 1)
            self.assertFalse((temp_path / "generated.hpp").exists())

    def test_cli_prints_json_report_and_writes_artifacts_without_stdout_mix(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--coverage-report",
                    "json",
                    "--output-root",
                    output_root.as_posix(),
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["summary"]["total_primitives"], 1)
            self.assertTrue((output_root / "generated.hpp").exists())
            self.assertIn("written generated.hpp ", stderr.getvalue())
            self.assertNotIn("written generated.hpp ", stdout.getvalue())

    def test_cli_prints_html_coverage_report_without_writing(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--coverage-report",
                    "html",
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("<h1>TSL Coverage Report</h1>", stdout.getvalue())
            self.assertFalse((temp_path / "generated.hpp").exists())

    def test_cli_prints_html_report_and_writes_artifacts_without_stdout_mix(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--coverage-report",
                    "html",
                    "--output-root",
                    output_root.as_posix(),
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            html = stdout.getvalue()
            self.assertTrue(html.startswith("<!doctype html>\n"))
            self.assertIn("<h1>TSL Coverage Report</h1>", html)
            self.assertTrue((output_root / "generated.hpp").exists())
            self.assertIn("written generated.hpp ", stderr.getvalue())
            self.assertNotIn("written generated.hpp ", html)

    def test_cli_writes_rendered_artifacts_through_writer(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--output-root",
                    output_root.as_posix(),
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue((output_root / "generated.hpp").exists())
            self.assertIn("written generated.hpp ", stdout.getvalue())

            second_stdout = StringIO()
            second_exit = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--output-root",
                    output_root.as_posix(),
                ),
                stdout=second_stdout,
                stderr=StringIO(),
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(second_exit, 0)
            self.assertIn("skipped_unchanged generated.hpp ", second_stdout.getvalue())

    def test_cli_dry_run_write_does_not_touch_output_root(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--output-root",
                    output_root.as_posix(),
                    "--dry-run",
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse((output_root / "generated.hpp").exists())
            self.assertIn("would_write generated.hpp ", stdout.getvalue())

    def test_cli_dry_run_with_json_report_reports_writes_on_stderr_only(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            stdout = StringIO()
            stderr = StringIO()

            exit_code = run_cli(
                cli_args_for(
                    primitive_path,
                    manifest_path,
                    "--coverage-report",
                    "json",
                    "--output-root",
                    output_root.as_posix(),
                    "--dry-run",
                ),
                stdout=stdout,
                stderr=stderr,
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(exit_code, 0)
            json.loads(stdout.getvalue())
            self.assertFalse((output_root / "generated.hpp").exists())
            self.assertIn("would_write generated.hpp ", stderr.getvalue())
            self.assertNotIn("would_write generated.hpp ", stdout.getvalue())

    def test_cli_no_skip_unchanged_rewrites_existing_artifact(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            primitive_path = temp_path / "api_slice.tsl"
            output_root = temp_path / "out"
            primitive_path.write_text(SIMPLE_PRIMITIVE, encoding="utf-8")
            manifest_path = write_cpp_manifest(temp_path)
            base_args = cli_args_for(
                primitive_path,
                manifest_path,
                "--output-root",
                output_root.as_posix(),
            )

            first_stdout = StringIO()
            first_exit = run_cli(
                base_args,
                stdout=first_stdout,
                stderr=StringIO(),
                hardware_flags_provider=lambda: (),
            )
            second_stdout = StringIO()
            second_exit = run_cli(
                (*base_args, "--no-skip-unchanged"),
                stdout=second_stdout,
                stderr=StringIO(),
                hardware_flags_provider=lambda: (),
            )

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            self.assertIn("written generated.hpp ", first_stdout.getvalue())
            self.assertIn("written generated.hpp ", second_stdout.getvalue())
            self.assertNotIn("skipped_unchanged", second_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
