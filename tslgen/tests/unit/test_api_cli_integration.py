from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _helpers import assert_diagnostic
from tslgen.api import PipelineConfig, run_pipeline
from tslgen.cli import run as run_cli
from tslgen.config.cli_adapter import parse_cli_config
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


if __name__ == "__main__":
    unittest.main()
