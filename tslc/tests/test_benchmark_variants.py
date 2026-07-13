"""Typed benchmark planning, rendering, and optional native policy flow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import textwrap

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.benchmark.model import (
    BenchmarkMaskCorrectnessCase,
    BenchmarkMaskDensityScenario,
    BenchmarkRegisterScenario,
)
from tslc.diagnostics import has_errors


@pytest.fixture(scope="module")
def benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["scalar", "sse2", "avx2"],
        type_tags=["si8"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def mask_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_mask"],
        profiles=["scalar", "sse2", "avx2"],
        type_tags=["ui32"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def ambiguous_register_benchmark_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["max"],
        profiles=["wasm32-simd128"],
        type_tags=["f32"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


def test_planner_keeps_default_and_authored_fallback_with_correctness(
    benchmark_result,
) -> None:
    plan = benchmark_result.rendered.benchmarks
    avx2 = plan.profile("cpp", "avx2")
    assert avx2 is not None
    candidate_sets = {
        (candidate_set.key.extension_name, candidate_set.key.type_tag): candidate_set
        for candidate_set in avx2.candidate_sets
    }

    for extension in ("avx2", "sse"):
        candidate_set = candidate_sets[(extension, "si8")]
        assert [candidate.variant_id for candidate in candidate_set.candidates] == [
            "default",
            "generic_fallback",
        ]
        assert candidate_set.correctness_cases
        assert {scenario.kind for scenario in candidate_set.scenarios} == {
            "throughput",
            "latency",
        }
        assert all(
            isinstance(scenario, BenchmarkRegisterScenario)
            for scenario in candidate_set.scenarios
        )
        latency = next(
            scenario
            for scenario in candidate_set.scenarios
            if scenario.kind == "latency"
        )
        assert latency.dependency_parameter == 0
        assert all(
            len(values) == candidate_set.key.lanes
            for case in candidate_set.correctness_cases
            for values in (*case.vector_inputs, case.expected)
        )


def test_ambiguous_register_shape_without_metadata_omits_latency(
    ambiguous_register_benchmark_result,
) -> None:
    profile = ambiguous_register_benchmark_result.rendered.benchmarks.profile(
        "cpp", "wasm32-simd128"
    )
    assert profile is not None
    candidate_set = next(
        candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "wasm128"
    )

    assert [scenario.kind for scenario in candidate_set.scenarios] == ["throughput"]


def test_benchmark_manifest_and_source_are_typed_deterministic_artifacts(
    benchmark_result,
) -> None:
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_avx2.json"])
    coverage = json.loads(artifacts["cpp/bench/coverage.json"])
    profile = benchmark_result.rendered.benchmarks.profile("cpp", "avx2")
    assert profile is not None

    assert manifest["manifest_hash"] == profile.manifest_hash
    assert manifest["profile"] == "avx2"
    assert manifest["candidate_sets"]
    assert any(entry["status"] == "emitted" for entry in coverage["entries"])
    source = artifacts["cpp/bench/tsl_variant_bench_avx2.cpp"]
    assert "mul_impl<Vec_" in source
    assert "mul_impl_generic_fallback<Vec_" in source
    assert "check_lanes<Base_" in source
    assert "measure_candidate_" in source
    assert "run_scenario_" in source
    assert "scenario == 1" not in source
    assert "reduce_candidate_set" in source


def test_integral_mask_variants_get_resolved_density_scenarios(
    mask_benchmark_result,
) -> None:
    profile = mask_benchmark_result.rendered.benchmarks.profile(
        "cpp", "avx2"
    )
    assert profile is not None
    assert len(profile.candidate_sets) == 1
    candidate_set = profile.candidate_sets[0]

    assert candidate_set.key.primitive_name == "to_mask"
    assert all(
        isinstance(scenario, BenchmarkMaskDensityScenario)
        for scenario in candidate_set.scenarios
    )
    assert [scenario.active_lanes for scenario in candidate_set.scenarios] == [1, 4, 7]
    assert all(
        isinstance(case, BenchmarkMaskCorrectnessCase)
        for case in candidate_set.correctness_cases
    )

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in mask_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_avx2.json"])
    assert [
        scenario["family"]
        for scenario in manifest["candidate_sets"][0]["scenarios"]
    ] == ["mask_density", "mask_density", "mask_density"]
    source = artifacts["cpp/bench/tsl_variant_bench_avx2.cpp"]
    assert "rotating_mask_bits" in source
    assert "check_scalar<Imask_" in source


def test_cpp_selector_defaults_and_policy_include_order(benchmark_result) -> None:
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in benchmark_result.artifacts.artifacts
    }
    header = artifacts["cpp/include/tsl_avx2.hpp"]
    selector = "struct mul_selector"
    policy_include = "#  include <tsl/generated/tsl_variant_policy_autotuned.hpp>"
    wrapper = "inline typename Vec::register_type mul("

    assert "enum class mul_variant" in header
    assert "mul_variant::default_" in header
    assert "if constexpr (selector::value ==" in header
    assert header.index(selector) < header.index(policy_include) < header.index(wrapper)


def test_generated_cmake_keeps_benchmarks_opt_in(benchmark_result) -> None:
    cmake = next(
        artifact.content
        for artifact in benchmark_result.artifacts.artifacts
        if artifact.logical_path == "cpp/CMakeLists.txt"
    )
    assert 'option(TSL_BUILD_BENCHMARKS' in cmake
    assert 'option(TSL_AUTOTUNE_VARIANTS' in cmake
    assert 'set(TSL_VARIANT_POLICY_FILE "" CACHE FILEPATH' in cmake
    assert "target_link_libraries(tsl_variant_bench PRIVATE tsl_profile_${TSL_SELECTED_PROFILE})" in cmake
    assert "target_link_libraries(tsl_variant_bench PRIVATE tsl_generated)" not in cmake
    assert "add_dependencies(tsl_generated tsl_variant_policy)" in cmake
    assert "if(TSL_BUILD_BENCHMARKS OR _TSL_POLICY_REQUESTED)" in cmake


def test_unsupported_variant_shape_has_structured_coverage(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["gather_narrow_partial"],
        profiles=["skylake"],
        type_tags=["si32"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    entries = result.rendered.benchmarks.coverage
    assert len(entries) == 1
    assert entries[0].status == "unsupported"
    assert entries[0].primitive_name == "gather_narrow_partial"
    assert "cross-lane" in entries[0].reason


@pytest.mark.generated_build
def test_native_autotune_and_manual_policy_build_consumers(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["scalar", "sse2"],
        type_tags=["si8"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    generated = tmp_path / "generated"
    write_report = write_artifacts(result.artifacts, generated)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    environment = os.environ.copy()
    if _compiler_name(environment.get("CXX", "")) == "zig":
        environment["CXX"] = "c++"
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "CMakeLists.txt").write_text(
        textwrap.dedent(
            f"""
            cmake_minimum_required(VERSION 3.20)
            project(tsl_autotune_consumer LANGUAGES CXX)
            include(FetchContent)
            set(TSL_PROFILE auto CACHE STRING "" FORCE)
            set(TSL_BUILD_TESTS OFF CACHE BOOL "" FORCE)
            set(TSL_AUTOTUNE_VARIANTS ON CACHE BOOL "" FORCE)
            set(TSL_BENCHMARK_ROUNDS 3 CACHE STRING "" FORCE)
            set(TSL_BENCHMARK_MINIMUM_SAMPLE_NS 10000 CACHE STRING "" FORCE)
            FetchContent_Declare(tsl SOURCE_DIR "{(generated / 'cpp').as_posix()}")
            FetchContent_MakeAvailable(tsl)
            add_executable(autotune_consumer main.cpp)
            target_link_libraries(autotune_consumer PRIVATE tsl::tsl)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (consumer / "main.cpp").write_text(
        textwrap.dedent(
            """
            #include <cstdint>
            #include <tsl.hpp>

            int main() {
            #if defined(TSL_PROFILE_SSE2)
              using Vec = tsl::simd<std::int8_t, tsl::sse>;
            #else
              using Vec = tsl::simd<std::int8_t, tsl::scalar>;
            #endif
              typename Vec::register_type value{};
              auto result = tsl::mul<Vec>(value, value);
              (void)result;
              return 0;
            }
            """
        ).lstrip(),
        encoding="utf-8",
    )

    autotune = tmp_path / "autotune"
    configured = _run(
        (
            "cmake",
            "-S",
            str(consumer),
            "-B",
            str(autotune),
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    built = _run(
        ("cmake", "--build", str(autotune), "--target", "autotune_consumer"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout
    policies = tuple(autotune.rglob("tsl_variant_policy.json"))
    headers = tuple(autotune.rglob("tsl_variant_policy_autotuned.hpp"))
    assert len(policies) == 1
    assert len(headers) == 1
    policy = policies[0]
    reducer_check = _run(
        (str(autotune / "_deps/tsl-build/tsl_variant_bench"), "--self-test"),
        environment,
    )
    assert reducer_check.returncode == 0, reducer_check.stderr + reducer_check.stdout

    manual = tmp_path / "manual"
    configured = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(manual),
            "-DTSL_PROFILE=auto",
            "-DTSL_BUILD_TESTS=ON",
            f"-DTSL_VARIANT_POLICY_FILE={policy}",
            "-DTSL_BENCHMARK_ROUNDS=3",
            "-DTSL_BENCHMARK_MINIMUM_SAMPLE_NS=10000",
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    built = _run(
        ("cmake", "--build", str(manual), "--target", "tsl_smoke"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout


def _run(command: tuple[str, ...], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _compiler_name(command: str) -> str:
    parts = shlex.split(command)
    return Path(parts[0]).name if parts else ""
