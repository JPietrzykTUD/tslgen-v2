"""Focused tests for the sequential fresh-process benchmark report."""

from __future__ import annotations

from tslc.maintenance.performance_benchmark import (
    BENCHMARK_CASES,
    BenchmarkSample,
    benchmark_report,
    run_fresh_samples,
)


def test_benchmark_report_uses_medians_and_records_environment() -> None:
    samples = (
        BenchmarkSample("check", 3.0, 2.8, 120, 0, 0, 0, 0),
        BenchmarkSample("check", 1.0, 0.8, 100, 0, 0, 0, 0),
        BenchmarkSample("check", 2.0, 1.8, 110, 0, 0, 0, 0),
    )

    report = benchmark_report(BENCHMARK_CASES["check"], samples)

    assert report["median"] == {
        "wall_seconds": 2.0,
        "cpu_seconds": 1.8,
        "peak_rss_kib": 110,
    }
    environment = report["environment"]
    assert isinstance(environment, dict)
    assert environment["input_manifest_digest"]
    assert environment["logical_cpus"]


def test_fresh_sample_count_must_be_positive() -> None:
    try:
        run_fresh_samples(BENCHMARK_CASES["check"], 0)
    except ValueError as exc:
        assert str(exc) == "sample count must be positive"
    else:
        raise AssertionError("zero samples should fail before spawning a worker")
