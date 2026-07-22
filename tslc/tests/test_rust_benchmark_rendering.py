"""Rust benchmark reporting, policy production, and opt-in native evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.rust_benchmark_context import RUST_BENCHMARK_CODEGEN_CONTRACT
from tslc.backend.rust_policy_consumption import (
    plan_rust_policy_consumption,
    plan_rust_policy_coverage,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelectionPlan,
    plan_rust_policy_selection,
)
from tslc.backend.rust_static_selection import plan_rust_static_selection
from tslc.benchmark.model import (
    BenchmarkReductionCorrectnessCase,
    BenchmarkReductionScenario,
)
from tslc.benchmark.render_rust import rust_benchmark_artifacts
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors
from tslc.render.rust_policy_consumption import (
    EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
    plan_rust_policy_consumption_render,
)


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


@pytest.fixture(scope="module")
def rust_immediate_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["permute_lanes"],
        profiles=["sse2"],
        type_tags=["si32", "ui32", "si64", "ui64", "f32", "f64"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def rust_avx2_reduction_benchmark_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["hadd", "hand", "hmax", "hmin", "hor"],
        profiles=["avx2"],
        type_tags=[
            "si8",
            "si16",
            "si32",
            "si64",
            "ui8",
            "ui16",
            "ui32",
            "ui64",
        ],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def rust_avx2_reduction_build_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["hadd", "hand", "hmax", "hmin", "hor"],
        profiles=["avx2"],
        type_tags=["si32"],
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


def test_rust_immediate_reports_bind_const_calls_and_policy_reason(
    rust_immediate_benchmark_result,
) -> None:
    plan = rust_immediate_benchmark_result.rendered.benchmarks
    profile = plan.profile("rust", "sse2")
    assert profile is not None
    assert {
        (candidate_set.key.type_tag, candidate_set.key.immediate)
        for candidate_set in profile.candidate_sets
    } == {
        ("f32", "78"),
        ("f64", "255"),
        ("si32", "27"),
        ("si64", "1"),
        ("ui32", "78"),
        ("ui64", "0"),
    }

    artifacts = _artifacts(rust_immediate_benchmark_result)
    source = artifacts["rust/src/tsl_variant_bench_sse2.rs"]
    for immediate in (0, 1, 27, 78, 255):
        assert f"Permute_lanes_immImpl<{immediate}>>::apply(value_0)" in source
        assert (
            f"Permute_lanes_imm_scalar_lanes_fallbackImpl<{immediate}>>::apply"
            "(value_0)"
        ) in source
    assert "vectors: [Vec<Reg_0>; 1]" in source
    assert "current = invoke_0_0(std::hint::black_box(current));" in source
    assert "let expected: [Base_0; 4] = [3.0, 4.0, 1.0, 2.0];" in source
    assert source.count("policy_supported: false") == 6
    assert "const POLICY_OUTPUT_SUPPORTED: bool = false;" in source
    assert "Write a consumable context-bound Rust policy" not in source

    manifest = json.loads(artifacts["rust/bench/manifest_sse2.json"])
    assert {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    } == {"immediate"}
    assert all(
        len(candidate_set["scenarios"]) == 2
        for candidate_set in manifest["candidate_sets"]
    )

    selection = plan_rust_policy_selection(
        rust_immediate_benchmark_result.emitted_profiles
    )
    policy = plan_rust_policy_coverage(plan, selection).profile("sse2")
    assert policy is not None
    assert len(policy.decisions) == 6
    assert {decision.status for decision in policy.decisions} == {"report_only"}
    assert {decision.reason for decision in policy.decisions} == {
        "immediate specializations are report-only"
    }
    assert {decision.key.immediate for decision in policy.decisions} == {
        "0",
        "1",
        "27",
        "78",
        "255",
    }
    assert all(not decision.mapping_choices for decision in policy.decisions)


def test_rust_avx2_reduction_reports_are_exact_and_report_only(
    rust_avx2_reduction_benchmark_result,
) -> None:
    plan = rust_avx2_reduction_benchmark_result.rendered.benchmarks
    profile = plan.profile("rust", "avx2")
    assert profile is not None
    assert len(profile.candidate_sets) == 40
    assert all(
        len(candidate_set.candidates) == 2
        and len(candidate_set.scenarios) == 1
        and isinstance(candidate_set.scenarios[0], BenchmarkReductionScenario)
        and all(
            isinstance(case, BenchmarkReductionCorrectnessCase)
            for case in candidate_set.correctness_cases
        )
        for candidate_set in profile.candidate_sets
    )

    artifacts = _artifacts(rust_avx2_reduction_benchmark_result)
    source = artifacts["rust/src/tsl_variant_bench_avx2.rs"]
    assert source.count("type Result_") == 40
    assert source.count("policy_supported: false") == 40
    assert "const POLICY_OUTPUT_SUPPORTED: bool = false;" in source
    assert "Write a consumable context-bound Rust policy" not in source
    assert "let expected: Base_" in source
    for primitive in ("Hadd", "Hand", "Hmax", "Hmin", "Hor"):
        assert f"::primitives::{primitive}Impl>::apply(value_0)" in source
        assert (
            f"::primitives::{primitive}_generic_fallbackImpl>::apply(value_0)"
            in source
        )

    manifest = json.loads(artifacts["rust/bench/manifest_avx2.json"])
    assert len(manifest["candidate_sets"]) == 40
    assert {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    } == {"reduction"}

    selection = plan_rust_policy_selection(
        rust_avx2_reduction_benchmark_result.emitted_profiles
    )
    policy = plan_rust_policy_coverage(plan, selection).profile("avx2")
    assert policy is not None
    assert len(policy.decisions) == 40
    assert {decision.status for decision in policy.decisions} == {"report_only"}
    assert {decision.reason for decision in policy.decisions} == {
        "scalar-result reduction specializations are report-only"
    }
    assert all(not decision.mapping_choices for decision in policy.decisions)


def test_rust_benchmark_artifacts_are_opt_in_and_deterministic(
    rust_benchmark_result,
) -> None:
    artifacts = _artifacts(rust_benchmark_result)
    expected = {
        "rust/bench/coverage.json",
        "rust/bench/manifest_sse2.json",
        "rust/bench/policy_consumption_sse2.json",
        "rust/bench/policy_consumption_sse2.rs",
        "rust/src/tsl_benchmark_core.rs",
        "rust/src/tsl_benchmark_reducer.rs",
        "rust/src/tsl_benchmark_policy.rs",
        "rust/src/tsl_benchmark_self_test.rs",
        "rust/src/tsl_variant_bench_sse2.rs",
    }
    assert expected <= artifacts.keys()
    assert "rust/benches/tsl_variant_bench_sse2.rs" in artifacts
    assert "variant_benchmarks = []" in artifacts["rust/Cargo.toml"]
    assert (
        'required-features = ["variant_benchmarks"]'
        in artifacts["rust/Cargo.toml"]
    )
    assert "[dependencies]" not in artifacts["rust/Cargo.toml"]
    assert "std::process::exit(tsl::tsl_variant_bench_sse2::main());" in artifacts[
        "rust/benches/tsl_variant_bench_sse2.rs"
    ]
    benchmark_source = artifacts["rust/src/tsl_variant_bench_sse2.rs"]
    assert "const POLICY_OUTPUT_SUPPORTED: bool = true;" in benchmark_source
    assert "Write a consumable context-bound Rust policy" in benchmark_source

    selection = plan_rust_policy_selection(
        rust_benchmark_result.emitted_profiles
    )
    consumption = plan_rust_policy_consumption_render(
        plan_rust_policy_consumption(
            rust_benchmark_result.rendered.benchmarks,
            selection,
        ),
        plan_rust_static_selection(rust_benchmark_result.emitted_profiles),
    )
    rendered_once = rust_benchmark_artifacts(
        rust_benchmark_result.rendered.benchmarks,
        load_default_render_assets(),
        "text/rust",
        consumption_plan=consumption,
    )
    rendered_again = rust_benchmark_artifacts(
        rust_benchmark_result.rendered.benchmarks,
        load_default_render_assets(),
        "text/rust",
        consumption_plan=consumption,
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
        consumption_plan=plan_rust_policy_consumption_render(
            plan_rust_policy_consumption(
                rust_benchmark_result.rendered.benchmarks,
                demoted,
            ),
            plan_rust_static_selection(rust_benchmark_result.emitted_profiles),
        ),
    )
    source = next(
        artifact.content
        for artifact in rendered
        if artifact.logical_path == "rust/src/tsl_variant_bench_sse2.rs"
    )

    assert "detail::primitives::MulImpl>::apply" in source
    assert "detail::primitives::Mul_defaultImpl>::apply" not in source


def test_rust_policy_support_uses_actual_selection_membership(
    rust_benchmark_result,
) -> None:
    selection_plan = plan_rust_policy_selection(
        rust_benchmark_result.emitted_profiles
    )
    selection_profile = selection_plan.profile("sse2")
    benchmark_profile = rust_benchmark_result.rendered.benchmarks.profile(
        "rust", "sse2"
    )
    assert selection_profile is not None
    assert benchmark_profile is not None
    supported_keys = {selection.key for selection in selection_profile.selections}
    expected_specs = [
        (
            "CandidateSetSpec { "
            f"stable_id: \"{candidate_set.stable_id}\", "
            f"candidates: &CANDIDATES_{index}, scenarios: &SCENARIOS_{index}, "
            f"policy_supported: {str(candidate_set.key in supported_keys).lower()} "
            "},"
        )
        for index, candidate_set in enumerate(benchmark_profile.candidate_sets)
    ]
    source = _artifacts(rust_benchmark_result)[
        "rust/src/tsl_variant_bench_sse2.rs"
    ]
    rendered_specs = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("CandidateSetSpec { stable_id:")
    ]

    assert rendered_specs == expected_specs


def test_rust_runtime_produces_backend_scoped_policy_without_consuming_it(
    rust_benchmark_result,
) -> None:
    artifacts = _artifacts(rust_benchmark_result)
    runtime = artifacts["rust/src/tsl_benchmark_core.rs"]
    reducer = artifacts["rust/src/tsl_benchmark_reducer.rs"]
    policy_runtime = artifacts["rust/src/tsl_benchmark_policy.rs"]
    self_test_runtime = artifacts["rust/src/tsl_benchmark_self_test.rs"]
    source = artifacts["rust/src/tsl_variant_bench_sse2.rs"]
    library = artifacts["rust/src/lib.rs"]
    cargo_manifest = artifacts["rust/Cargo.toml"]
    manifest = json.loads(artifacts["rust/bench/manifest_sse2.json"])
    coverage = json.loads(artifacts["rust/bench/coverage.json"])

    assert "std::time::{Duration, Instant}" in runtime
    assert "splitmix64" in runtime
    assert "candidate_order" in runtime
    assert "calibrate" in runtime
    assert "std::hint::black_box" in self_test_runtime
    assert "runtime_self_test" in self_test_runtime
    assert "report-only reducer self-test failed" in self_test_runtime
    assert "runtime_self_test" not in policy_runtime
    assert "report-only reducer self-test failed" not in policy_runtime
    assert "reduce_candidate_set" in reducer
    assert "validate_sample_inventory" in reducer
    assert "RustPolicyDocument" in policy_runtime
    assert 'pub const RUST_BACKEND_ID: &str = "rust";' in policy_runtime
    assert '{{\\"backend\\":\\"{}\\"' in policy_runtime
    assert "{:.8}" not in policy_runtime
    assert "let decisions = reduce_profile(&CANDIDATE_SETS" in source
    assert "write_reports(" in source
    assert (
        "use crate::tsl_benchmark_self_test::runtime_self_test;" in source
    )
    assert "pub mod tsl_benchmark_self_test;" in library
    assert "policy_supported: true" in source
    assert "TSL_RUST_VARIANT_POLICY_FILE" not in (
        runtime + reducer + policy_runtime + self_test_runtime
    )
    assert "Explicit two-phase autotune" in source
    assert "env -u CARGO_ENCODED_RUSTFLAGS -u TSL_RUST_VARIANT_POLICY_FILE" in source
    assert 'const BENCHMARK_TARGET: &str = "tsl_variant_bench_sse2";' in source
    assert 'const CARGO_FEATURES: &str = "variant_benchmarks";' in source
    assert 'let artifact_subdirectory = "tsl-benchmark/sse2";' in source
    assert '${{CARGO_TARGET_DIR:-$PWD/target}}/{artifact_subdirectory}' in source
    assert "if options.help" in source
    assert (
        'name = "tsl_variant_bench_sse2"\n'
        'path = "benches/tsl_variant_bench_sse2.rs"\n'
        'harness = false\n'
        'required-features = ["variant_benchmarks"]'
    ) in cargo_manifest
    assert "is_x86_feature_detected!(\"sse\")" in source
    assert "is_x86_feature_detected!(\"sse2\")" in source
    assert '#[cfg(target_arch = "x86_64")]' in source
    assert '#[cfg(not(target_arch = "x86_64"))]' in source
    assert 'target_arch = "x86",' not in source
    assert 'const BUILD_HOST: &str = env!("TSL_BUILD_HOST");' in source
    assert 'const BUILD_TARGET: &str = env!("TSL_BUILD_TARGET");' in source
    assert 'rustc_verbose_version: env!("TSL_RUSTC_VERBOSE_VERSION")' in source
    assert 'cargo_profile: env!("TSL_RUST_CARGO_PROFILE")' in source
    assert 'encoded_rustflags: env!("TSL_RUST_ENCODED_RUSTFLAGS")' in source
    assert 'benchmark_codegen_contract: "profile.bench:v1;' in source
    build_script = artifacts["rust/build.rs"]
    assert build_script.index('CARGO_FEATURE_VARIANT_BENCHMARKS') < build_script.index(
        'let rustc = required("RUSTC")'
    )
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


def test_documented_rust_workflow_tracks_codegen_contract() -> None:
    guide = (
        Path(__file__).parents[2] / "docs" / "variant-benchmarking.md"
    ).read_text(encoding="utf-8")
    expected = (
        "export RUSTFLAGS='"
        + " ".join(
            RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags_for(
                ("sse", "sse2")
            )
        )
        + "'"
    )

    assert expected in guide


def test_rust_benchmark_codegen_contract_rejects_duplicate_target_features() -> None:
    with pytest.raises(ValueError, match="target features must be unique"):
        RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags_for(("sse2", "sse2"))


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
        consumption_plan=EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
    )
    artifacts = {artifact.logical_path: artifact.content for artifact in rendered}

    source = artifacts["rust/src/tsl_variant_bench_skylake_oneapi.rs"]
    manifest = json.loads(
        artifacts["rust/bench/manifest_skylake_oneapi.json"]
    )
    assert 'const PROFILE: &str = "skylake\\u{2d}oneapi";' in source
    assert 'const BENCHMARK_TARGET: &str = "tsl_variant_bench_skylake_oneapi";' in source
    assert 'const CARGO_FEATURES: &str = "variant_benchmarks";' in source
    assert "Explicit two-phase autotune" not in source
    assert "const POLICY_OUTPUT_SUPPORTED: bool = false;" in source
    assert "Write a consumable context-bound Rust policy" not in source
    assert (
        "Policy consumption is unavailable for this report-only benchmark profile."
        in source
    )
    assert manifest["profile"] == "skylake-oneapi"


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_environment = None
    if environment is not None:
        process_environment = os.environ.copy()
        for name, value in environment.items():
            if value is None:
                process_environment.pop(name, None)
            else:
                process_environment[name] = value
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
    )


def _rust_policy_environment(
    context: str,
    target_features: tuple[str, ...] = ("sse", "sse2"),
) -> dict[str, str | None]:
    cleared = {
        "CARGO_BUILD_INCREMENTAL",
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_BUILD_TARGET",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_INCREMENTAL",
        "RUSTC",
        "RUSTC_LINKER",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTFLAGS",
        "TSL_RUST_VARIANT_POLICY_FILE",
    }
    cleared.update(
        name
        for name in os.environ
        if name.startswith("CARGO_PROFILE_")
        or (
            name.startswith("CARGO_TARGET_")
            and name.endswith(("_LINKER", "_RUSTFLAGS"))
        )
    )
    return {
        **{name: None for name in cleared},
        "RUSTFLAGS": " ".join(
            RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags_for(
                target_features
            )
        ),
        "CARGO_INCREMENTAL": (
            RUST_BENCHMARK_CODEGEN_CONTRACT.policy_incremental_environment
        ),
        "TSL_RUST_BENCHMARK_CONTEXT": context,
    }


def _assert_gnu_linux_hot_loop(
    crate: Path,
    common: tuple[str, ...],
    environment: dict[str, str | None],
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
            "variant_benchmarks",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
        environment=environment,
    )
    assert assembly.returncode == 0, assembly.stderr
    assembly_files = sorted(
        (crate / "target" / "release" / "deps").glob("tsl-*.s"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    assert assembly_files
    marker_pattern = re.compile(
        r"\.section\s+\.text\.[^\n]*tsl_variant_bench_sse2[^\n]*measure_0_0"
    )
    for assembly_file in assembly_files:
        assembly_text = assembly_file.read_text()
        marker = marker_pattern.search(assembly_text)
        if marker is not None:
            break
    else:
        pytest.fail("generated assembly does not contain the benchmark hot loop")
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


def _assert_gnu_linux_immediate_hot_loop(
    crate: Path,
    common: tuple[str, ...],
    environment: dict[str, str | None],
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
            "variant_benchmarks",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
        environment=environment,
    )
    assert assembly.returncode == 0, assembly.stderr
    assembly_files = sorted(
        (crate / "target" / "release" / "deps").glob("tsl-*.s"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    assert assembly_files
    marker_pattern = re.compile(
        r"\.section\s+\.text\.[^\n]*tsl_variant_bench_sse2[^\n]*measure_0_0"
    )
    for assembly_file in assembly_files:
        assembly_text = assembly_file.read_text()
        marker = marker_pattern.search(assembly_text)
        if marker is not None:
            break
    else:
        pytest.fail("generated assembly does not contain the immediate hot loop")
    function = assembly_text[
        marker.start() : assembly_text.index(".Lfunc_end", marker.start())
    ]
    candidate_branch = re.search(
        r"(?:test|cmp)[bwlq][^\n]*\n\s+j(?:e|ne)\s+(\.LBB\d+_\d+)",
        function,
    )
    assert candidate_branch is not None
    second_path = function.index(f"{candidate_branch.group(1)}:")
    assert "shufps\t$78" in function[candidate_branch.end() : second_path]
    assert "shufps\t$78" in function[second_path:]
    assert not re.search(
        r"callq[^\n]*(?:Permute_lanes_imm|invoke_0)",
        function,
    )


def _assert_gnu_linux_avx2_reduction_hot_loop(
    crate: Path,
    common: tuple[str, ...],
    environment: dict[str, str | None],
    *,
    set_index: int,
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
            "variant_benchmarks",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
        environment=environment,
    )
    assert assembly.returncode == 0, assembly.stderr
    assembly_files = sorted(
        (crate / "target" / "release" / "deps").glob("tsl-*.s"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    assert assembly_files
    marker_pattern = re.compile(
        rf"\.section\s+\.text\.[^\n]*tsl_variant_bench_avx2[^\n]*"
        rf"measure_{set_index}_0"
    )
    for assembly_file in assembly_files:
        assembly_text = assembly_file.read_text()
        marker = marker_pattern.search(assembly_text)
        if marker is not None:
            break
    else:
        pytest.fail("generated assembly does not contain the AVX2 reduction hot loop")
    hot_loop = assembly_text[
        marker.start() : assembly_text.index(".Lfunc_end", marker.start())
    ]
    assert hot_loop.count("vpaddd") >= 6
    assert "vpshufd\t$78" in hot_loop
    assert "vpshufd\t$238" in hot_loop
    assert not re.search(r"callq[^\n]*(?:Hadd|invoke_)", hot_loop)


@pytest.mark.generated_build
def test_generated_rust_immediate_benchmark_runs_report_only_and_has_hot_loop(
    rust_immediate_benchmark_result,
    tmp_path: Path,
) -> None:
    if shutil.which("cargo") is None or shutil.which("rustc") is None:
        pytest.skip("cargo and rustc are required")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("the sse2 immediate benchmark requires a native x86-64 host")

    generated = tmp_path / "generated"
    report = write_artifacts(rust_immediate_benchmark_result.artifacts, generated)
    assert not has_errors(report.diagnostics), report.diagnostics
    crate = generated / "rust"
    common = ("--manifest-path", str(crate / "Cargo.toml"))
    policy_environment = _rust_policy_environment(
        "sse2-immediate-generated-test-context"
    )

    for command in (
        ("cargo", "check", *common),
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--no-run",
        ),
    ):
        completed = _run(command, cwd=crate, environment=policy_environment)
        assert completed.returncode == 0, completed.stderr

    profile = rust_immediate_benchmark_result.rendered.benchmarks.profile(
        "rust", "sse2"
    )
    assert profile is not None
    results_path = generated / "immediate-samples.jsonl"
    summary_path = generated / "immediate-summary.txt"
    policy_path = generated / "immediate-policy.json"
    completed = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--",
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(results_path),
            "--summary",
            str(summary_path),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert completed.returncode == 0, completed.stderr
    rows = [json.loads(line) for line in results_path.read_text().splitlines()]
    expected = Counter(
        (
            candidate_set.stable_id,
            scenario.scenario_id,
            candidate.variant_id,
            round_index,
        )
        for candidate_set in profile.candidate_sets
        for scenario in candidate_set.scenarios
        for candidate in candidate_set.candidates
        for round_index in range(3)
    )
    assert Counter(
        (
            row["stable_id"],
            row["scenario"],
            row["candidate"],
            row["round"],
        )
        for row in rows
    ) == expected
    summary = summary_path.read_text()
    assert summary.count("policy default (report_only)") == 6
    rejected_policy = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--",
            "--policy-json",
            str(policy_path),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert rejected_policy.returncode != 0
    assert "is report-only and cannot produce a consumable Rust policy" in (
        rejected_policy.stderr
    )
    assert not policy_path.exists()

    if platform.system() == "Linux":
        _assert_gnu_linux_immediate_hot_loop(crate, common, policy_environment)


@pytest.mark.generated_build
def test_generated_rust_avx2_reductions_run_report_only_and_have_hot_loop(
    rust_avx2_reduction_build_result,
    tmp_path: Path,
) -> None:
    if shutil.which("cargo") is None or shutil.which("rustc") is None:
        pytest.skip("cargo and rustc are required")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("the AVX2 reduction benchmark requires a native x86-64 host")

    generated = tmp_path / "generated"
    report = write_artifacts(
        rust_avx2_reduction_build_result.artifacts,
        generated,
    )
    assert not has_errors(report.diagnostics), report.diagnostics
    crate = generated / "rust"
    common = ("--manifest-path", str(crate / "Cargo.toml"))
    policy_environment = _rust_policy_environment(
        "avx2-reduction-generated-test-context",
        (
            "avx",
            "avx2",
            "rdrand",
            "sse",
            "sse2",
            "sse4.1",
            "sse4.2",
            "ssse3",
        ),
    )

    for command in (
        ("cargo", "check", *common),
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_avx2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--no-run",
        ),
    ):
        completed = _run(command, cwd=crate, environment=policy_environment)
        assert completed.returncode == 0, completed.stderr

    profile = rust_avx2_reduction_build_result.rendered.benchmarks.profile(
        "rust", "avx2"
    )
    assert profile is not None
    assert {
        candidate_set.key.primitive_name for candidate_set in profile.candidate_sets
    } == {"hadd", "hand", "hmax", "hmin", "hor"}
    assert {
        candidate_set.key.type_tag for candidate_set in profile.candidate_sets
    } == {"si32"}
    results_path = generated / "avx2-reduction-samples.jsonl"
    summary_path = generated / "avx2-reduction-summary.txt"
    policy_path = generated / "avx2-reduction-policy.json"
    completed = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_avx2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--",
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(results_path),
            "--summary",
            str(summary_path),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    if completed.returncode != 0 and "requires CPU features" in completed.stderr:
        pytest.skip(completed.stderr.strip())
    assert completed.returncode == 0, completed.stderr

    rows = [json.loads(line) for line in results_path.read_text().splitlines()]
    expected = Counter(
        (
            candidate_set.stable_id,
            scenario.scenario_id,
            candidate.variant_id,
            round_index,
        )
        for candidate_set in profile.candidate_sets
        for scenario in candidate_set.scenarios
        for candidate in candidate_set.candidates
        for round_index in range(3)
    )
    assert Counter(
        (
            row["stable_id"],
            row["scenario"],
            row["candidate"],
            row["round"],
        )
        for row in rows
    ) == expected
    summary = summary_path.read_text()
    assert summary.count("policy default (report_only)") == len(
        profile.candidate_sets
    )
    rejected_policy = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_avx2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--",
            "--policy-json",
            str(policy_path),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert rejected_policy.returncode != 0
    assert "is report-only and cannot produce a consumable Rust policy" in (
        rejected_policy.stderr
    )
    assert not policy_path.exists()

    if platform.system() == "Linux":
        representative = next(
            index
            for index, candidate_set in enumerate(profile.candidate_sets)
            if candidate_set.key.primitive_name == "hadd"
            and candidate_set.key.type_tag == "si32"
        )
        _assert_gnu_linux_avx2_reduction_hot_loop(
            crate,
            common,
            policy_environment,
            set_index=representative,
        )


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
    policy_environment = _rust_policy_environment(
        "slice3-generated-test-context"
    )

    for command in (
        ("cargo", "check", *common),
        ("cargo", "test", *common),
        (
            "cargo",
            "test",
            *common,
            "--no-default-features",
            "--features",
            "variant_benchmarks",
        ),
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            *common,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks",
            "--no-run",
        ),
    ):
        completed = _run(command, cwd=crate, environment=policy_environment)
        assert completed.returncode == 0, completed.stderr

    base_bench = (
        "cargo",
        "bench",
        "--profile",
        "bench",
        *common,
        "--bench",
        "tsl_variant_bench_sse2",
        "--no-default-features",
        "--features",
        "variant_benchmarks",
        "--",
    )
    help_run = _run(
        (*base_bench, "--help"),
        cwd=crate,
        environment=policy_environment,
    )
    assert help_run.returncode == 0, help_run.stderr
    assert "Explicit two-phase autotune" in help_run.stdout
    assert (
        "env -u CARGO_ENCODED_RUSTFLAGS -u TSL_RUST_VARIANT_POLICY_FILE"
        in help_run.stdout
    )
    assert (
        "RUSTFLAGS='"
        + " ".join(
            RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags_for(
                ("sse", "sse2")
            )
        )
        + "'"
        in help_run.stdout
    )
    assert (
        'artifact_dir="${CARGO_TARGET_DIR:-$PWD/target}/tsl-benchmark/sse2"'
        in help_run.stdout
    )
    assert 'TSL_RUST_VARIANT_POLICY_FILE="$artifact_dir/policy.json"' in (
        help_run.stdout
    )
    assert "cargo build --profile bench" in help_run.stdout
    self_test = _run(
        (*base_bench, "--self-test"),
        cwd=crate,
        environment=policy_environment,
    )
    assert self_test.returncode == 0, self_test.stderr

    if os.name != "nt":
        alias_root = generated / "output-alias-root"
        alias_inner = generated / "output-alias-target" / "inner"
        alias_inner.mkdir(parents=True)
        (alias_root / "link").parent.mkdir()
        (alias_root / "link").symlink_to(alias_inner, target_is_directory=True)
        alias_output = generated / "output-alias-target" / "evidence.txt"
        alias_run = _run(
            (
                *base_bench,
                "--rounds",
                "3",
                "--minimum-sample-ns",
                "1000",
                "--results",
                str(alias_root / "link" / ".." / "evidence.txt"),
                "--summary",
                str(alias_root / ".." / "output-alias-target" / "evidence.txt"),
            ),
            cwd=crate,
            environment=policy_environment,
        )
        assert alias_run.returncode != 0
        assert "benchmark output paths must be distinct" in alias_run.stderr
        assert not alias_output.exists()
        assert not tuple(alias_output.parent.glob(".*.tsl-tmp"))
        assert not tuple(alias_output.parent.glob(".*.tsl-backup"))

    profile_plan = rust_benchmark_result.rendered.benchmarks.profile("rust", "sse2")
    assert profile_plan is not None
    selection_profile = plan_rust_policy_selection(
        rust_benchmark_result.emitted_profiles
    ).profile("sse2")
    assert selection_profile is not None
    supported_keys = {selection.key for selection in selection_profile.selections}
    supported_stable_ids = {
        candidate_set.stable_id
        for candidate_set in profile_plan.candidate_sets
        if candidate_set.key in supported_keys
    }
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
        "tune_context",
        "cpu_id",
        "stable_id",
        "scenario",
        "candidate",
        "round",
        "iterations",
        "elapsed_ns",
    }
    identity_sequences = []
    thresholds = (0.050000001, 0.050000002)
    expected_scenario_settings = [
        {
            "stable_id": candidate_set.stable_id,
            "scenario": scenario.scenario_id,
            "rounds": 3,
            "minimum_sample_ns": 1000,
        }
        for candidate_set in profile_plan.candidate_sets
        for scenario in candidate_set.scenarios
    ]
    for run_index in range(2):
        results_path = generated / f"samples-{run_index}.jsonl"
        summary_path = generated / f"summary-{run_index}.txt"
        policy_path = generated / f"policy-{run_index}.json"
        short_run = _run(
            (
                *base_bench,
                "--rounds",
                "3",
                "--minimum-sample-ns",
                "1000",
                "--threshold",
                str(thresholds[run_index]),
                "--results",
                str(results_path),
                "--summary",
                str(summary_path),
                "--policy-json",
                str(policy_path),
            ),
            cwd=crate,
            environment=policy_environment,
        )
        assert short_run.returncode == 0, short_run.stderr
        rows = [json.loads(line) for line in results_path.read_text().splitlines()]
        assert rows
        assert {row["backend"] for row in rows} == {"rust"}
        assert {row["profile"] for row in rows} == {"sse2"}
        assert {row["manifest_hash"] for row in rows} == {
            profile_plan.manifest_hash
        }
        assert all(row["cpu_id"].startswith("x86:") for row in rows)
        expected_tune_context_keys = {
            "rustc_verbose_version",
            "cargo_verbose_version",
            "host",
            "target",
            "linker",
            "rustc_wrapper",
            "rustc_workspace_wrapper",
            "target_cpu",
            "target_features",
            "required_features",
            "cargo_features",
            "cargo_profile",
            "opt_level",
            "debug_assertions",
            "overflow_checks",
            "lto",
            "codegen_units",
            "panic",
            "incremental",
            "debug",
            "rustflags",
            "encoded_rustflags",
            "profile_overrides",
            "benchmark_codegen_contract",
            "external_context",
            "threshold",
            "rounds_override",
            "minimum_sample_ns_override",
            "scenario_settings",
        }
        assert all(set(row["tune_context"]) == expected_tune_context_keys for row in rows)
        assert all(
            row["tune_context"]["rustc_verbose_version"].startswith("rustc ")
            and row["tune_context"]["cargo_verbose_version"].startswith("cargo ")
            and row["tune_context"]["host"] == row["tune_context"]["target"]
            and row["tune_context"]["linker"]
            and row["tune_context"]["rustc_wrapper"] == ""
            and row["tune_context"]["rustc_workspace_wrapper"] == ""
            and row["tune_context"]["target_cpu"] == "rustc-default"
            and {"sse", "sse2"}
            <= set(row["tune_context"]["target_features"].split(","))
            and row["tune_context"]["required_features"] == "sse,sse2"
            and "CARGO_FEATURE_SSE2=1" not in row["tune_context"]["cargo_features"]
            and "CARGO_FEATURE_VARIANT_BENCHMARKS=1"
            in row["tune_context"]["cargo_features"]
            and row["tune_context"]["cargo_profile"] == "release"
            and row["tune_context"]["opt_level"] == "3"
            and row["tune_context"]["debug_assertions"] == "false"
            and row["tune_context"]["overflow_checks"] == "false"
            and row["tune_context"]["lto"] == "false"
            and row["tune_context"]["codegen_units"] == "1"
            and row["tune_context"]["panic"] == "unwind"
            and row["tune_context"]["incremental"] == "0"
            and row["tune_context"]["debug"] == "false"
            and row["tune_context"]["rustflags"] == ""
            and row["tune_context"]["encoded_rustflags"].split("\x1f")
            == list(
                RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags_for(
                    ("sse", "sse2")
                )
            )
            and row["tune_context"]["profile_overrides"]
            == "CARGO_INCREMENTAL=0"
            and row["tune_context"]["external_context"]
            == "slice3-generated-test-context"
            and row["tune_context"]["threshold"]
            == pytest.approx(thresholds[run_index])
            and row["tune_context"]["rounds_override"] == 3
            and row["tune_context"]["minimum_sample_ns_override"] == 1000
            and row["tune_context"]["scenario_settings"]
            == expected_scenario_settings
            and row["tune_context"]["benchmark_codegen_contract"]
            == RUST_BENCHMARK_CODEGEN_CONTRACT.identity
            for row in rows
        )
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

        summary = summary_path.read_text(encoding="utf-8")
        assert "Rust TSL variant benchmark summary" in summary
        assert "backend: rust" in summary
        assert f"manifest: {profile_plan.manifest_hash}" in summary

        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        assert set(policy) == {
            "schema_version",
            "protocol_version",
            "backend",
            "profile",
            "manifest_hash",
            "tune_context",
            "cpu_id",
            "decisions",
        }
        assert policy["schema_version"] == 2
        assert policy["protocol_version"] == 1
        assert policy["backend"] == "rust"
        assert policy["profile"] == "sse2"
        assert policy["manifest_hash"] == profile_plan.manifest_hash
        assert policy["cpu_id"].startswith("x86:")
        assert policy["tune_context"] == rows[0]["tune_context"]
        assert [decision["stable_id"] for decision in policy["decisions"]] == [
            candidate_set.stable_id for candidate_set in profile_plan.candidate_sets
        ]
        assert len({decision["stable_id"] for decision in policy["decisions"]}) == len(
            policy["decisions"]
        )
        for decision, candidate_set in zip(
            policy["decisions"], profile_plan.candidate_sets
        ):
            assert decision["selected"] in {
                candidate.variant_id for candidate in candidate_set.candidates
            }
            if candidate_set.stable_id not in supported_stable_ids:
                assert decision["selected"] == "default"
                assert decision["status"] == "report_only"
                assert decision["minimum_improvement"] == 0.0
            elif decision["status"] != "selected":
                assert decision["selected"] == "default"
    assert identity_sequences[0] == identity_sequences[1]
    assert thresholds[0] != thresholds[1]
    assert json.loads((generated / "policy-0.json").read_text())["tune_context"][
        "threshold"
    ] != json.loads((generated / "policy-1.json").read_text())["tune_context"][
        "threshold"
    ]

    replacement = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--threshold",
            str(thresholds[0]),
            "--results",
            str(generated / "samples-0.jsonl"),
            "--summary",
            str(generated / "summary-0.txt"),
            "--policy-json",
            str(generated / "policy-0.json"),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert replacement.returncode == 0, replacement.stderr
    assert json.loads((generated / "policy-0.json").read_text())["backend"] == "rust"
    assert not tuple(generated.glob(".*.tsl-tmp"))
    assert not tuple(generated.glob(".*.tsl-backup"))

    encoded_results = generated / "encoded-results.jsonl"
    encoded_summary = generated / "encoded-summary.txt"
    encoded_context = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(encoded_results),
            "--summary",
            str(encoded_summary),
        ),
        cwd=crate,
        environment={
            **_rust_policy_environment("slice3-encoded-context"),
            "RUSTFLAGS": "-Ctarget-cpu=native --codegen=target-cpu=x86-64",
        },
    )
    assert encoded_context.returncode == 0, encoded_context.stderr
    encoded_tune_context = json.loads(encoded_results.read_text().splitlines()[0])[
        "tune_context"
    ]
    assert encoded_tune_context["target_cpu"] == "x86-64"
    assert encoded_tune_context["rustflags"] == ""
    encoded_flags = encoded_tune_context["encoded_rustflags"].split("\x1f")
    assert "-Ctarget-cpu=native" in encoded_flags
    assert "--codegen=target-cpu=x86-64" in encoded_flags
    assert encoded_tune_context["external_context"] == "slice3-encoded-context"

    rejected_results = generated / "override-results.jsonl"
    rejected_summary = generated / "override-summary.txt"
    rejected_policy = generated / "override-policy.json"
    rejected_override = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(rejected_results),
            "--summary",
            str(rejected_summary),
            "--policy-json",
            str(rejected_policy),
        ),
        cwd=crate,
        environment={
            **policy_environment,
            "CARGO_PROFILE_BENCH_LTO": "true",
        },
    )
    assert rejected_override.returncode != 0
    assert "requires the exact compiler-owned codegen guard" in (
        rejected_override.stderr
    )
    assert not rejected_results.exists()
    assert not rejected_summary.exists()
    assert not rejected_policy.exists()

    for label, override in (
        ("cargo", {"CARGO_INCREMENTAL": "1"}),
        ("cargo-build", {"CARGO_BUILD_INCREMENTAL": "true"}),
    ):
        incremental_results = generated / f"{label}-incremental-results.jsonl"
        incremental_summary = generated / f"{label}-incremental-summary.txt"
        incremental_policy = generated / f"{label}-incremental-policy.json"
        rejected_incremental = _run(
            (
                *base_bench,
                "--rounds",
                "3",
                "--minimum-sample-ns",
                "1000",
                "--results",
                str(incremental_results),
                "--summary",
                str(incremental_summary),
                "--policy-json",
                str(incremental_policy),
            ),
            cwd=crate,
            environment={**policy_environment, **override},
        )
        assert rejected_incremental.returncode != 0
        assert "requires the exact compiler-owned codegen guard" in (
            rejected_incremental.stderr
        )
        assert not incremental_results.exists()
        assert not incremental_summary.exists()
        assert not incremental_policy.exists()

    precedence_results = generated / "incremental-precedence-results.jsonl"
    precedence_summary = generated / "incremental-precedence-summary.txt"
    precedence = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(precedence_results),
            "--summary",
            str(precedence_summary),
        ),
        cwd=crate,
        environment={
            **policy_environment,
            "CARGO_INCREMENTAL": "0",
            "CARGO_BUILD_INCREMENTAL": "true",
        },
    )
    assert precedence.returncode == 0, precedence.stderr
    precedence_context = json.loads(precedence_results.read_text().splitlines()[0])[
        "tune_context"
    ]
    assert precedence_context["incremental"] == "0"
    assert precedence_context["profile_overrides"] == (
        "CARGO_BUILD_INCREMENTAL=true;CARGO_INCREMENTAL=0"
    )
    assert not tuple(generated.glob(".*.tsl-tmp"))
    assert not tuple(generated.glob(".*.tsl-backup"))

    atomic_results = generated / "atomic-results.jsonl"
    atomic_policy = generated / "atomic-policy.json"
    missing_summary = generated / "missing-output-directory" / "summary.txt"
    rejected_publication = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(atomic_results),
            "--summary",
            str(missing_summary),
            "--policy-json",
            str(atomic_policy),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert rejected_publication.returncode != 0
    assert "cannot stage benchmark summary" in rejected_publication.stderr
    assert not atomic_results.exists()
    assert not atomic_policy.exists()
    assert not tuple(generated.glob(".*.tsl-tmp"))

    directory_results = generated / "directory-results.jsonl"
    directory_summary = generated / "directory-summary"
    directory_summary.mkdir()
    directory_policy = generated / "directory-policy.json"
    rejected_destination = _run(
        (
            *base_bench,
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--results",
            str(directory_results),
            "--summary",
            str(directory_summary),
            "--policy-json",
            str(directory_policy),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert rejected_destination.returncode != 0
    assert "destination must be a regular file" in rejected_destination.stderr
    assert not directory_results.exists()
    assert directory_summary.is_dir()
    assert not directory_policy.exists()
    assert not tuple(generated.glob(".*.tsl-tmp"))
    assert not tuple(generated.glob(".*.tsl-backup"))

    # The assembly parser intentionally targets the GNU/Linux format exercised
    # by generated-build CI; other native hosts still run all functional proof.
    if platform.system() == "Linux":
        _assert_gnu_linux_hot_loop(crate, common, policy_environment)

    failed_results = generated / "failed.jsonl"
    failed_summary = generated / "failed-summary.txt"
    failed_policy = generated / "failed-policy.json"
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
            "--summary",
            str(failed_summary),
            "--policy-json",
            str(failed_policy),
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert failed.returncode != 0
    assert "correctness failed" in failed.stderr
    assert not failed_results.exists()
    assert not failed_summary.exists()
    assert not failed_policy.exists()
