"""Report-only Rust benchmark rendering and opt-in native evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.registry import backend_capability
from tslc.backend.rust_policy_selection import (
    RustPolicySelectionPlan,
    RustPolicySelectionProfile,
    plan_rust_policy_selection,
)
from tslc.benchmark.render_rust import rust_benchmark_artifacts
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors


@pytest.fixture(scope="module")
def rust_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["sse2"],
        type_tags=["si8"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


def _artifacts(result) -> dict[str, str]:
    return {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }


def test_rust_benchmark_artifacts_are_opt_in_and_deterministic(
    rust_benchmark_result,
) -> None:
    artifacts = _artifacts(rust_benchmark_result)
    expected = {
        "rust/bench/coverage.json",
        "rust/bench/manifest_sse2.json",
        "rust/src/tsl_benchmark_core.rs",
        "rust/src/tsl_variant_bench_sse2.rs",
    }
    assert expected <= artifacts.keys()
    assert "rust/benches/tsl_variant_bench_sse2.rs" in artifacts
    assert "variant_benchmarks = []" in artifacts["rust/Cargo.toml"]
    assert (
        'required-features = ["variant_benchmarks", "sse2"]'
        in artifacts["rust/Cargo.toml"]
    )
    assert "[dependencies]" not in artifacts["rust/Cargo.toml"]
    assert "std::process::exit(tsl::tsl_variant_bench_sse2::main());" in artifacts[
        "rust/benches/tsl_variant_bench_sse2.rs"
    ]

    capability = backend_capability("rust")
    rendered_once = capability.render_benchmark_artifacts(
        rust_benchmark_result.rendered.benchmarks,
        rust_benchmark_result.emitted_profiles,
        load_default_render_assets(),
    )
    rendered_again = capability.render_benchmark_artifacts(
        rust_benchmark_result.rendered.benchmarks,
        rust_benchmark_result.emitted_profiles,
        load_default_render_assets(),
    )
    assert rendered_once == rendered_again
    assert {artifact.logical_path for artifact in rendered_once} == expected


def test_rust_candidate_calls_and_correctness_keep_backend_ownership(
    rust_benchmark_result,
) -> None:
    artifacts = _artifacts(rust_benchmark_result)
    source = artifacts["rust/src/tsl_variant_bench_sse2.rs"]
    profile = artifacts["rust/src/tsl_sse2.rs"]

    assert (
        "<Simd<i8, Sse> as "
        "crate::tsl_sse2::detail::primitives::Mul_defaultImpl>::apply"
    ) in source
    assert (
        "crate::tsl_sse2::detail::primitives::Mul_generic_fallbackImpl>::apply"
    ) in source
    assert "Shift_left_generic_fallbackImplArg<Simd<u16, Sse>>" in source
    assert "crate::tsl_sse2::from_array::<Vec_0>" in source
    assert "crate::tsl_sse2::to_array::<Vec_0>" in source
    assert "pub fn mul<S: detail::primitives::MulImpl>" in profile
    assert "<S as detail::primitives::MulImpl>::apply(factor1, factor2)" in profile

    run = source[source.index("fn run(arguments:") :]
    correctness = run.index("correct_candidate_set_0()?;")
    samples = run.index("let mut samples")
    timing = run.index("run_candidate_set_0(&options")
    assert correctness < samples < timing
    profile_plan = rust_benchmark_result.rendered.benchmarks.profile("rust", "sse2")
    assert profile_plan is not None
    assert run.count("correct_candidate_set_") == len(profile_plan.candidate_sets)


def test_rust_default_call_uses_actual_selection_membership(
    rust_benchmark_result,
) -> None:
    plan = plan_rust_policy_selection(rust_benchmark_result.emitted_profiles)
    profile = plan.profile("sse2")
    assert profile is not None
    selected_key = profile.selections[0].key
    demoted_coverage = tuple(
        replace(
            entry,
            status="report_only",
            reason="coherence collision",
        )
        if entry.key == selected_key
        else entry
        for entry in profile.coverage
    )
    demoted = RustPolicySelectionPlan(
        profiles=(
            replace(
                profile,
                selections=(),
                coverage=demoted_coverage,
            ),
        )
    )

    rendered = rust_benchmark_artifacts(
        rust_benchmark_result.rendered.benchmarks,
        load_default_render_assets(),
        "text/rust",
        selection_plan=demoted,
    )
    source = next(
        artifact.content
        for artifact in rendered
        if artifact.logical_path == "rust/src/tsl_variant_bench_sse2.rs"
    )

    assert "detail::primitives::MulImpl>::apply" in source
    assert "detail::primitives::Mul_defaultImpl>::apply" not in source


def test_rust_runtime_and_report_schema_are_policy_free(
    rust_benchmark_result,
) -> None:
    artifacts = _artifacts(rust_benchmark_result)
    runtime = artifacts["rust/src/tsl_benchmark_core.rs"]
    source = artifacts["rust/src/tsl_variant_bench_sse2.rs"]
    manifest = json.loads(artifacts["rust/bench/manifest_sse2.json"])
    coverage = json.loads(artifacts["rust/bench/coverage.json"])

    assert "std::time::{Duration, Instant}" in runtime
    assert "splitmix64" in runtime
    assert "candidate_order" in runtime
    assert "calibrate" in runtime
    assert "std::hint::black_box" in runtime
    assert "runtime_self_test" in runtime
    assert "policy" not in runtime.lower()
    assert "policy" not in source.lower()
    assert "is_x86_feature_detected!(\"sse\")" in source
    assert "is_x86_feature_detected!(\"sse2\")" in source
    assert '#[cfg(target_arch = "x86_64")]' in source
    assert '#[cfg(not(target_arch = "x86_64"))]' in source
    assert 'target_arch = "x86",' not in source
    assert 'const BUILD_HOST: &str = env!("TSL_BUILD_HOST");' in source
    assert 'const BUILD_TARGET: &str = env!("TSL_BUILD_TARGET");' in source
    assert "native_build_matches(BUILD_HOST, BUILD_TARGET)" in source
    assert "let mut iterations = 1usize;" in source
    assert (
        "|count| measure_0_0(candidate, &inputs, count)" in source
    )
    assert manifest["backend"] == "rust"
    assert manifest["profile"] == "sse2"
    profile_plan = rust_benchmark_result.rendered.benchmarks.profile("rust", "sse2")
    assert profile_plan is not None
    assert manifest["manifest_hash"] == profile_plan.manifest_hash
    assert {entry["status"] for entry in coverage["entries"]} == {"emitted"}
    assert all(
        scenario["family"] == "register"
        for candidate_set in manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    )


def test_rust_report_keeps_canonical_profile_identity(
    rust_benchmark_result,
) -> None:
    plan = rust_benchmark_result.rendered.benchmarks
    profile = plan.profile("rust", "sse2")
    assert profile is not None
    renamed = replace(profile, profile_name="skylake-oneapi")
    rendered = rust_benchmark_artifacts(
        replace(plan, profiles=(renamed,)),
        load_default_render_assets(),
        "text/rust",
        selection_plan=RustPolicySelectionPlan(
            profiles=(
                RustPolicySelectionProfile(
                    profile_name="skylake-oneapi",
                    selections=(),
                    coverage=(),
                ),
            )
        ),
    )
    artifacts = {artifact.logical_path: artifact.content for artifact in rendered}

    source = artifacts["rust/src/tsl_variant_bench_skylake_oneapi.rs"]
    manifest = json.loads(
        artifacts["rust/bench/manifest_skylake_oneapi.json"]
    )
    assert 'const PROFILE: &str = "skylake\\u{2d}oneapi";' in source
    assert manifest["profile"] == "skylake-oneapi"


def _run(command: tuple[str, ...], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_gnu_linux_hot_loop(
    crate: Path,
    common: tuple[str, ...],
) -> None:
    assembly = _run(
        (
            "cargo",
            "rustc",
            *common,
            "--lib",
            "--release",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
    )
    assert assembly.returncode == 0, assembly.stderr
    assembly_files = sorted(
        (crate / "target" / "release" / "deps").glob("tsl-*.s"),
        key=lambda path: path.stat().st_size,
        reverse=True,
    )
    assert assembly_files
    assembly_text = assembly_files[0].read_text()
    marker = re.search(
        r"\.section\s+\.text\.[^\n]*tsl_variant_bench_sse2[^\n]*measure_0_0",
        assembly_text,
    )
    assert marker is not None
    function = assembly_text[
        marker.start() : assembly_text.index(".Lfunc_end", marker.start())
    ]
    candidate_branch = re.search(
        r"(?:test|cmp)[bwlq][^\n]*\n\s+j(?:e|ne)\s+(\.LBB\d+_\d+)",
        function,
    )
    assert candidate_branch is not None
    second_path = function.index(f"{candidate_branch.group(1)}:")
    assert "pmullw" in function[candidate_branch.end() : second_path]
    assert "pmullw" in function[second_path:]
    assert not re.search(r"callq[^\n]*(?:MulImpl|invoke_0)", function)


@pytest.mark.generated_build
def test_generated_rust_benchmark_builds_runs_and_has_hot_loop_evidence(
    rust_benchmark_result,
    tmp_path: Path,
) -> None:
    if shutil.which("cargo") is None or shutil.which("rustc") is None:
        pytest.skip("cargo and rustc are required")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("the sse2 benchmark pilot requires a native x86-64 host")

    generated = tmp_path / "generated"
    report = write_artifacts(rust_benchmark_result.artifacts, generated)
    assert not has_errors(report.diagnostics), report.diagnostics
    crate = generated / "rust"
    common = ("--manifest-path", str(crate / "Cargo.toml"))

    for command in (
        ("cargo", "check", *common),
        ("cargo", "test", *common),
        (
            "cargo",
            "test",
            *common,
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
        ),
        (
            "cargo",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
            "--no-run",
        ),
    ):
        completed = _run(command, cwd=crate)
        assert completed.returncode == 0, completed.stderr

    base_bench = (
        "cargo",
        "bench",
        *common,
        "--bench",
        "tsl_variant_bench_sse2",
        "--no-default-features",
        "--features",
        "variant_benchmarks,sse2",
        "--",
    )
    self_test = _run((*base_bench, "--self-test"), cwd=crate)
    assert self_test.returncode == 0, self_test.stderr

    profile_plan = rust_benchmark_result.rendered.benchmarks.profile("rust", "sse2")
    assert profile_plan is not None
    expected_identities = Counter(
        (
            candidate_set.stable_id,
            scenario.scenario_id,
            candidate.variant_id,
            round_index,
        )
        for candidate_set in profile_plan.candidate_sets
        for scenario in candidate_set.scenarios
        for candidate in candidate_set.candidates
        for round_index in range(3)
    )
    expected_fields = {
        "backend",
        "protocol_version",
        "profile",
        "manifest_hash",
        "stable_id",
        "scenario",
        "candidate",
        "round",
        "iterations",
        "elapsed_ns",
    }
    identity_sequences = []
    for run_index in range(2):
        results_path = generated / f"samples-{run_index}.jsonl"
        short_run = _run(
            (
                *base_bench,
                "--rounds",
                "3",
                "--minimum-sample-ns",
                "1000",
                "--results",
                str(results_path),
            ),
            cwd=crate,
        )
        assert short_run.returncode == 0, short_run.stderr
        rows = [json.loads(line) for line in results_path.read_text().splitlines()]
        assert rows
        assert {row["backend"] for row in rows} == {"rust"}
        assert {row["profile"] for row in rows} == {"sse2"}
        assert {row["manifest_hash"] for row in rows} == {
            profile_plan.manifest_hash
        }
        assert all(
            row["iterations"] > 0 and row["elapsed_ns"] > 0 for row in rows
        )
        assert all(set(row) == expected_fields for row in rows)
        identities = [
            (
                row["stable_id"],
                row["scenario"],
                row["candidate"],
                row["round"],
            )
            for row in rows
        ]
        assert Counter(identities) == expected_identities
        identity_sequences.append(identities)
    assert identity_sequences[0] == identity_sequences[1]

    # The assembly parser intentionally targets the GNU/Linux format exercised
    # by generated-build CI; other native hosts still run all functional proof.
    if platform.system() == "Linux":
        _assert_gnu_linux_hot_loop(crate, common)

    failed_results = generated / "failed.jsonl"
    benchmark_source = crate / "src" / "tsl_variant_bench_sse2.rs"
    source = benchmark_source.read_text()
    changed = source.replace(
        "let expected: [Base_0; 16] = [1, 4, 9,",
        "let expected: [Base_0; 16] = [2, 4, 9,",
        1,
    )
    assert changed != source
    benchmark_source.write_text(changed)
    failed = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(failed_results),
        ),
        cwd=crate,
    )
    assert failed.returncode != 0
    assert "correctness failed" in failed.stderr
    assert not failed_results.exists()
