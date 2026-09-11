"""Tests for the repository-local support compile-cost measurement."""

from __future__ import annotations

from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


def _measurement_module() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[2]
        / "supplementary/benchmarks/measure_support_compile_cost.py"
    )
    spec = importlib.util.spec_from_file_location("support_compile_cost", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_timing_comparison_uses_observed_sample_spread() -> None:
    module = _measurement_module()
    baseline = module.summarize_timings(
        (
            module.TimingSample(1.0, 0.8),
            module.TimingSample(1.1, 0.9),
            module.TimingSample(1.2, 1.0),
        )
    )
    candidate = module.summarize_timings(
        (
            module.TimingSample(1.4, 1.1),
            module.TimingSample(1.5, 1.2),
            module.TimingSample(1.6, 1.3),
        )
    )

    comparison = module.compare_timings(baseline, candidate)

    assert comparison.baseline_wall_seconds == pytest.approx(1.1)
    assert comparison.candidate_wall_seconds == pytest.approx(1.5)
    assert comparison.baseline_cpu_seconds == pytest.approx(0.9)
    assert comparison.candidate_cpu_seconds == pytest.approx(1.2)
    assert comparison.cpu_delta_percent == pytest.approx(100.0 / 3.0)
    assert comparison.observed_spread_seconds == pytest.approx(0.2)
    assert comparison.classification == "regression_outside_observed_spread"


def test_generated_project_validation_reports_exact_missing_inputs(
    tmp_path: Path,
) -> None:
    module = _measurement_module()

    with pytest.raises(module.MeasurementError) as exc:
        module._validate_generated_project(tmp_path)

    message = str(exc.value)
    assert str(tmp_path / ".tslc-manifest.json") in message
    assert str(tmp_path / "cpp/include/tsl_algorithm.hpp") in message
    assert str(tmp_path / "rust/Cargo.toml") in message


def test_cpp_workloads_keep_algorithm_prerequisites_explicit() -> None:
    module = _measurement_module()

    assert module._cpp_source("core", "tsl_scalar.hpp").startswith(
        "#include <tsl_core.hpp>\n"
    )
    assert module._cpp_source("primitives", "tsl_scalar.hpp").startswith(
        "#include <tsl_scalar.hpp>\n"
    )
    algorithm = module._cpp_source("algorithms", "tsl_scalar.hpp")
    assert algorithm.startswith(
        "#include <tsl_scalar.hpp>\n#include <tsl_algorithm.hpp>\n"
    )


def test_downstream_consumer_depends_on_the_generated_rust_crate(
    tmp_path: Path,
) -> None:
    module = _measurement_module()
    generated = tmp_path / "generated"

    manifest = module._write_consumer(tmp_path / "consumer", generated)

    assert f'path = "{(generated / "rust").as_posix()}"' in manifest.read_text(
        encoding="utf-8"
    )


def test_markdown_records_non_gating_method_and_exact_results() -> None:
    module = _measurement_module()
    summary = asdict(
        module.summarize_timings(
            (module.TimingSample(1.0, 0.8), module.TimingSample(1.2, 0.9))
        )
    )
    comparison = asdict(
        module.compare_timings(
            module.summarize_timings(
                (module.TimingSample(1.0, 0.8), module.TimingSample(1.2, 0.9))
            ),
            module.summarize_timings(
                (module.TimingSample(0.8, 0.7), module.TimingSample(0.9, 0.8))
            ),
        )
    )
    result = {
        "repetitions": 2,
        "provenance": {
            "captured_at_utc": "2026-09-11T00:00:00+00:00",
            "baseline": {"revision": "base", "manifest_sha256": "a" * 64},
            "candidate": {"revision": "final", "manifest_sha256": "b" * 64},
            "host": {
                "platform": "test-os",
                "machine": "test-cpu",
                "cpu_count": 4,
                "python": "3.test",
            },
        },
        "cpp": {
            "tools": {"gcc": {"version": "gcc test"}},
            "preprocessed_volume": [
                {
                    "revision": "baseline",
                    "compiler": "gcc",
                    "profile": "scalar",
                    "workload": "core",
                    "bytes": 10,
                    "lines": 2,
                }
            ],
            "clang_token_records": [],
            "timings": [summary],
            "comparisons": [
                {
                    "compiler": "gcc",
                    "profile": "scalar",
                    "workload": "core",
                    **comparison,
                }
            ],
        },
        "rust": {
            "tools": {
                "stable": {
                    "rustc_version": "rustc test",
                    "cargo_version": "cargo test",
                }
            },
            "skipped_toolchains": (),
            "timings": [summary],
            "comparisons": [
                {"toolchain": "stable", "task": "check", **comparison}
            ],
        },
    }

    report = module.render_markdown(result)

    assert "informational and non-gating" in report
    assert "compiler's `-E -P` output" in report
    assert "Cargo still compiles the generated" in report
    assert "improvement_outside_observed_spread" in report
