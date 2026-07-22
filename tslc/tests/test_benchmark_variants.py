"""Typed benchmark planning, rendering, and optional native policy flow."""

from __future__ import annotations

from dataclasses import replace
import json
from hashlib import sha256
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import textwrap
from types import SimpleNamespace
from typing import cast, get_args

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.benchmark.model import (
    BenchmarkCandidate,
    BenchmarkCandidateSet,
    BenchmarkCorrectnessCase,
    BenchmarkMaskCorrectnessCase,
    BenchmarkMaskDensityScenario,
    BenchmarkMaskResultScenario,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkImmediateScenario,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkIndexedLoadScenario,
    BenchmarkReductionCorrectnessCase,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkScenario,
    BenchmarkTiming,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
    BenchmarkVectorScalarScenario,
    SpecializationKey,
)
from tslc.benchmark.render_cpp_scenarios import render_scenario
from tslc.diagnostics import has_errors
from tslc.lower.lowerer import LoweredSpecialization


def test_supported_benchmark_scenario_families_are_consistent() -> None:
    scenario_types = get_args(BenchmarkScenario)
    correctness_types = get_args(BenchmarkCorrectnessCase)

    assert {scenario_type.family for scenario_type in scenario_types} == {
        "register",
        "vector_scalar",
        "immediate",
        "indexed_load",
        "mask_density",
        "mask_result",
        "reduction",
    }
    assert {scenario_type.correctness_type for scenario_type in scenario_types} == set(
        correctness_types
    )
    assert all(
        scenario_type.family == scenario_type.correctness_type.family
        and callable(scenario_type.canonical_fields)
        and callable(scenario_type.validate_key)
        and callable(scenario_type.manifest_fields)
        for scenario_type in scenario_types
    )
    assert all(
        callable(correctness_type.canonical_fields)
        and callable(correctness_type.validate_key)
        for correctness_type in correctness_types
    )


def test_representative_timing_scenarios_are_byte_stable() -> None:
    timing = BenchmarkTiming(seed=7)
    samples = (
        _timing_sample(
            SpecializationKey(
                "cpp", "p", "add", "add", "e", "si32", "v", ("v", "v"), lanes=2
            ),
            BenchmarkVectorCorrectnessCase(
                "c", (("1", "2"), ("3", "4")), ("4", "6"), "from_array", "to_array"
            ),
            BenchmarkRegisterScenario(
                "throughput", "throughput", timing, ("bounded_random", "bounded_random")
            ),
        ),
        _timing_sample(
            SpecializationKey(
                "cpp", "p", "shift", "shift", "e", "si32", "v", ("v", "s"), lanes=2
            ),
            BenchmarkVectorScalarCorrectnessCase(
                "c", ("1", "2"), "1", ("2", "4"), "from_array", "to_array"
            ),
            BenchmarkVectorScalarScenario(
                "latency",
                "latency",
                timing,
                "bounded_random",
                "bounded_shift_count",
                0,
            ),
        ),
        _timing_sample(
            SpecializationKey(
                "cpp",
                "p",
                "shift_imm",
                "shift_imm",
                "e",
                "si32",
                "v",
                ("v", "sImm"),
                immediate="1",
                lanes=2,
            ),
            BenchmarkImmediateCorrectnessCase(
                "c", ("1", "2"), ("2", "4"), "from_array", "to_array"
            ),
            BenchmarkImmediateScenario(
                "latency", "latency", timing, "bounded_random", 0
            ),
        ),
        _timing_sample(
            SpecializationKey(
                "cpp",
                "p",
                "gather",
                "gather",
                "e",
                "si32",
                "v",
                ("cptr", "vidx", "sImm"),
                immediate="4",
                simd_type_base_bindings=(("Index", "si32"),),
                lanes=2,
            ),
            BenchmarkIndexedLoadCorrectnessCase(
                "c",
                ("1", "2"),
                ("0", "1"),
                ("1", "2"),
                "si32",
                "int32_t",
                "from_array",
                "to_array",
            ),
            BenchmarkIndexedLoadScenario("throughput", timing, 64, 2),
        ),
        _timing_sample(
            SpecializationKey(
                "cpp", "p", "to_mask", "to_mask", "e", "si32", "m", ("im",), lanes=2
            ),
            BenchmarkMaskCorrectnessCase("c", ("1",), "1", "to_integral"),
            BenchmarkMaskDensityScenario("balanced", timing, 0, 1),
        ),
        _timing_sample(
            SpecializationKey(
                "cpp", "p", "less", "less", "e", "si32", "m", ("v", "v"), lanes=2
            ),
            BenchmarkVectorMaskCorrectnessCase(
                "c", (("1", "2"), ("2", "1")), "1", "from_array", "to_integral"
            ),
            BenchmarkMaskResultScenario(
                "throughput", timing, ("bounded_random", "bounded_random")
            ),
        ),
        _timing_sample(
            SpecializationKey(
                "cpp", "p", "hadd", "hadd", "e", "si32", "s", ("v",), lanes=2
            ),
            BenchmarkReductionCorrectnessCase("c", ("1", "2"), "3", "from_array"),
            BenchmarkReductionScenario("throughput", timing, "bounded_random"),
        ),
    )
    assert {
        sample.scenarios[0].family: sha256(
            render_scenario(0, 0, sample, sample.scenarios[0]).encode("utf-8")
        ).hexdigest()
        for sample in samples
    } == {
        "register": "111c97f41c90e8f326ca08c8ec12e6ae2fe45bdd43d25b24f39e084ea4f14620",
        "vector_scalar": "30073bd5bfa3ad2f70629e31130305164ee94878f9cc51fee38880f35a4d4f99",
        "immediate": "d15fe29d6d4ee4b82679af613ff7fd9a77c61e0838ba853663f42b5497a9bb50",
        "indexed_load": "be417ff5f260515d47b95b8ebcb1e090d6ce5b774fee555bb2fe0142fe0c1a90",
        "mask_density": "42fbfbd543c40ea64196bd85b9f83a78a664ac34ea5425f48853dd7c849c3e84",
        "mask_result": "111c97f41c90e8f326ca08c8ec12e6ae2fe45bdd43d25b24f39e084ea4f14620",
        "reduction": "039fa946eb5547b4b112b8bbe02bc11713ae158a13e34fc11f7cc9b077a189e1",
    }


def _timing_sample(
    key: SpecializationKey,
    correctness: BenchmarkCorrectnessCase,
    scenario: BenchmarkScenario,
) -> BenchmarkCandidateSet:
    specialization = cast(
        LoweredSpecialization,
        SimpleNamespace(param_kinds=key.param_kinds),
    )
    return BenchmarkCandidateSet(
        key=key,
        specialization=specialization,
        candidates=(BenchmarkCandidate("default", "hash"),),
        correctness_cases=(correctness,),
        scenarios=(scenario,),
        stable_id="stable",
    )


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
        profiles=["scalar", "sse2", "avx2", "wasm32-simd128"],
        type_tags=["si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64", "f32", "f64"],
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
        primitives=["max", "min"],
        profiles=["wasm32-simd128"],
        type_tags=["si64", "ui64", "f32"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def reduction_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["hadd", "hmax", "hmin", "hand", "hor"],
        profiles=["avx2"],
        type_tags=["si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def modulo_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mod"],
        profiles=["avx2"],
        type_tags=["si32"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def bit_count_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["popcnt", "lzc"],
        profiles=["avx2"],
        type_tags=["ui8", "ui32", "f32"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def division_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["div"],
        profiles=["neon", "wasm32-simd128"],
        type_tags=["si8", "ui8", "si16", "ui16", "si32", "ui32", "si64", "ui64"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def comparison_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "less_than",
            "greater_than",
            "less_than_or_equal",
            "greater_than_or_equal",
        ],
        profiles=["wasm32-simd128"],
        type_tags=["ui64"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def shift_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left", "shift_right"],
        profiles=["avx2", "wasm32-simd128"],
        type_tags=[
            "si8",
            "ui8",
            "si16",
            "ui16",
            "si32",
            "ui32",
            "si64",
            "ui64",
            "f32",
            "f64",
        ],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def exact_immediate_benchmark_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["permute_lanes"],
        profiles=["sse2"],
        type_tags=["si32", "ui32", "si64", "ui64", "f32", "f64"],
        backends=["cpp", "rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def indexed_load_benchmark_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["from_array", "gather_narrow_partial", "to_array"],
        profiles=["skylake"],
        type_tags=["si32", "si64"],
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
    candidate_sets = [
        candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "wasm128"
        and candidate_set.key.primitive_name in {"max", "min"}
    ]

    assert {
        (candidate_set.key.primitive_name, candidate_set.key.type_tag)
        for candidate_set in candidate_sets
    } == {
        (primitive, type_tag)
        for primitive in ("max", "min")
        for type_tag in ("si64", "ui64", "f32")
    }
    assert all(
        [scenario.kind for scenario in candidate_set.scenarios] == ["throughput"]
        for candidate_set in candidate_sets
    )


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
    assert {candidate_set.key.type_tag for candidate_set in profile.candidate_sets} == {
        "si32",
        "ui32",
    }
    for candidate_set in profile.candidate_sets:
        assert candidate_set.key.primitive_name == "to_mask"
        assert all(
            isinstance(scenario, BenchmarkMaskDensityScenario)
            for scenario in candidate_set.scenarios
        )
        assert [scenario.active_lanes for scenario in candidate_set.scenarios] == [
            1,
            4,
            7,
        ]
        assert all(
            isinstance(case, BenchmarkMaskCorrectnessCase)
            for case in candidate_set.correctness_cases
        )

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in mask_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_avx2.json"])
    assert {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    } == {"mask_density"}
    source = artifacts["cpp/bench/tsl_variant_bench_avx2.cpp"]
    assert "rotating_mask_bits" in source
    assert "check_scalar<Imask_" in source

    wasm = mask_benchmark_result.rendered.benchmarks.profile(
        "cpp", "wasm32-simd128"
    )
    assert wasm is not None
    wasm_sets = {
        candidate_set.key.type_tag: candidate_set
        for candidate_set in wasm.candidate_sets
        if candidate_set.key.extension_name == "wasm128"
        and candidate_set.key.primitive_name == "to_mask"
    }
    assert set(wasm_sets) == {
        "si8",
        "ui8",
        "si16",
        "ui16",
        "si32",
        "ui32",
        "si64",
        "ui64",
        "f32",
        "f64",
    }
    assert all(
        [candidate.variant_id for candidate in candidate_set.candidates]
        == ["default", "generic_fallback"]
        for candidate_set in wasm_sets.values()
    )


def test_scalar_reduction_variants_get_independent_throughput_scenarios(
    reduction_benchmark_result,
) -> None:
    profile = reduction_benchmark_result.rendered.benchmarks.profile("cpp", "avx2")
    assert profile is not None
    expected_types = {
        "si8",
        "ui8",
        "si16",
        "ui16",
        "si32",
        "ui32",
        "si64",
        "ui64",
    }
    for primitive in {"hadd", "hmax", "hmin", "hand", "hor"}:
        assert {
            candidate_set.key.type_tag
            for candidate_set in profile.candidate_sets
            if candidate_set.key.extension_name == "avx2"
            and candidate_set.key.primitive_name == primitive
        } == expected_types
    candidate_sets = {
        candidate_set.key.primitive_name: candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "avx2"
        and (
            (
                candidate_set.key.primitive_name in {"hadd", "hmax", "hmin"}
                and candidate_set.key.type_tag == "si32"
            )
            or (
                candidate_set.key.primitive_name in {"hand", "hor"}
                and candidate_set.key.type_tag == "ui32"
            )
        )
    }

    assert set(candidate_sets) == {"hadd", "hmax", "hmin", "hand", "hor"}
    for candidate_set in candidate_sets.values():
        assert [candidate.variant_id for candidate in candidate_set.candidates] == [
            "default",
            "generic_fallback",
        ]
        assert all(
            isinstance(case, BenchmarkReductionCorrectnessCase)
            for case in candidate_set.correctness_cases
        )
        assert all(
            isinstance(scenario, BenchmarkReductionScenario)
            for scenario in candidate_set.scenarios
        )
        assert [scenario.kind for scenario in candidate_set.scenarios] == [
            "throughput"
        ]

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in reduction_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_avx2.json"])
    assert {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        if candidate_set["key"]["primitive"]
        in {"hadd", "hmax", "hmin", "hand", "hor"}
        for scenario in candidate_set["scenarios"]
    } == {"reduction"}
    source = artifacts["cpp/bench/tsl_variant_bench_avx2.cpp"]
    assert "check_scalar<Base_" in source


def test_modulo_divisor_uses_resolved_nonzero_operand_generator(
    modulo_benchmark_result,
) -> None:
    profile = modulo_benchmark_result.rendered.benchmarks.profile("cpp", "avx2")
    assert profile is not None
    candidate_sets = {
        candidate_set.key.extension_name: candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.primitive_name == "mod"
        and candidate_set.key.extension_name in {"sse", "avx2"}
    }

    assert set(candidate_sets) == {"sse", "avx2"}
    for candidate_set in candidate_sets.values():
        assert [candidate.variant_id for candidate in candidate_set.candidates] == [
            "default",
            "generic_fallback",
        ]
        assert all(
            isinstance(scenario, BenchmarkRegisterScenario)
            for scenario in candidate_set.scenarios
        )
        assert all(
            scenario.operand_generators == ("bounded_random", "bounded_nonzero")
            for scenario in candidate_set.scenarios
        )
        latency = next(
            scenario
            for scenario in candidate_set.scenarios
            if scenario.kind == "latency"
        )
        assert latency.dependency_parameter == 0

    source = next(
        artifact.content
        for artifact in modulo_benchmark_result.artifacts.artifacts
        if artifact.logical_path == "cpp/bench/tsl_variant_bench_avx2.cpp"
    )
    assert "next_nonzero_value<Base_" in source


def test_bit_count_candidates_preserve_material_algorithm_alternatives(
    bit_count_benchmark_result,
) -> None:
    profile = bit_count_benchmark_result.rendered.benchmarks.profile("cpp", "avx2")
    assert profile is not None
    candidate_sets = {
        (candidate_set.key.primitive_name, candidate_set.key.type_tag): candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "avx2"
        and candidate_set.key.primitive_name in {"popcnt", "lzc"}
    }

    expected_variants = {
        ("popcnt", "ui8"): ["default", "sse_halves", "generic_fallback"],
        ("popcnt", "ui32"): ["default", "generic_fallback"],
        ("lzc", "ui8"): ["default", "generic_fallback"],
        ("lzc", "ui32"): ["default", "generic_fallback"],
        ("lzc", "f32"): ["default", "sse_halves", "generic_fallback"],
    }
    assert set(candidate_sets) == set(expected_variants)
    for key, variant_ids in expected_variants.items():
        candidate_set = candidate_sets[key]
        assert [
            candidate.variant_id for candidate in candidate_set.candidates
        ] == variant_ids
        assert all(
            isinstance(scenario, BenchmarkRegisterScenario)
            for scenario in candidate_set.scenarios
        )
        assert {scenario.kind for scenario in candidate_set.scenarios} == {
            "throughput",
            "latency",
        }


def test_integer_division_candidates_use_nonzero_divisors(
    division_benchmark_result,
) -> None:
    expected_extensions = {
        "neon": "neon",
        "wasm32-simd128": "wasm128",
    }
    for profile_name, extension_name in expected_extensions.items():
        profile = division_benchmark_result.rendered.benchmarks.profile(
            "cpp", profile_name
        )
        assert profile is not None
        candidate_sets = {
            candidate_set.key.type_tag: candidate_set
            for candidate_set in profile.candidate_sets
            if candidate_set.key.primitive_name == "div"
            and candidate_set.key.extension_name == extension_name
        }
        assert set(candidate_sets) == {
            "si8",
            "ui8",
            "si16",
            "ui16",
            "si32",
            "ui32",
            "si64",
            "ui64",
        }
        for candidate_set in candidate_sets.values():
            assert [
                candidate.variant_id for candidate in candidate_set.candidates
            ] == ["default", "generic_fallback"]
            assert all(
                scenario.operand_generators == (
                    "bounded_random",
                    "bounded_nonzero",
                )
                for scenario in candidate_set.scenarios
            )
            latency = next(
                scenario
                for scenario in candidate_set.scenarios
                if scenario.kind == "latency"
            )
            assert latency.dependency_parameter == 0


def test_vector_comparison_candidates_get_mask_result_throughput(
    comparison_benchmark_result,
) -> None:
    profile = comparison_benchmark_result.rendered.benchmarks.profile(
        "cpp", "wasm32-simd128"
    )
    assert profile is not None
    expected_primitives = {
        "less_than",
        "greater_than",
        "less_than_or_equal",
        "greater_than_or_equal",
    }
    candidate_sets = {
        candidate_set.key.primitive_name: candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "wasm128"
        and candidate_set.key.primitive_name in expected_primitives
    }

    assert set(candidate_sets) == expected_primitives
    for candidate_set in candidate_sets.values():
        assert candidate_set.key.result_kind == "m"
        assert candidate_set.key.param_kinds == ("v", "v")
        assert [
            candidate.variant_id for candidate in candidate_set.candidates
        ] == ["default", "generic_fallback"]
        assert all(
            isinstance(case, BenchmarkVectorMaskCorrectnessCase)
            for case in candidate_set.correctness_cases
        )
        assert all(
            isinstance(scenario, BenchmarkMaskResultScenario)
            for scenario in candidate_set.scenarios
        )
        assert [scenario.kind for scenario in candidate_set.scenarios] == [
            "throughput"
        ]

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in comparison_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_wasm32_simd128.json"])
    assert {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        if candidate_set["key"]["primitive"] in expected_primitives
        for scenario in candidate_set["scenarios"]
    } == {"mask_result"}
    source = artifacts["cpp/bench/tsl_variant_bench_wasm32_simd128.cpp"]
    assert "to_integral<Vec_" in source
    assert "check_scalar<Imask_" in source


def test_dynamic_scalar_shift_candidates_get_typed_mixed_scenarios(
    shift_benchmark_result,
) -> None:
    profile = shift_benchmark_result.rendered.benchmarks.profile(
        "cpp", "wasm32-simd128"
    )
    assert profile is not None
    candidate_sets = [
        candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "wasm128"
        and candidate_set.key.param_kinds == ("v", "s")
    ]

    assert {
        (candidate_set.key.primitive_name, candidate_set.key.type_tag)
        for candidate_set in candidate_sets
    } == {
        *(("shift_left", type_tag) for type_tag in ("f32", "f64")),
        *(("shift_right", type_tag) for type_tag in (
            "si8",
            "ui8",
            "si16",
            "ui16",
            "si32",
            "ui32",
            "si64",
            "ui64",
            "f32",
            "f64",
        )),
    }
    for candidate_set in candidate_sets:
        assert candidate_set.key.overload_parameter_positions == (1,)
        assert all(
            isinstance(case, BenchmarkVectorScalarCorrectnessCase)
            for case in candidate_set.correctness_cases
        )
        assert all(
            isinstance(scenario, BenchmarkVectorScalarScenario)
            for scenario in candidate_set.scenarios
        )
        assert [scenario.kind for scenario in candidate_set.scenarios] == [
            "throughput",
            "latency",
        ]
        assert all(
            scenario.vector_generator == "bounded_random"
            and scenario.scalar_generator == "bounded_shift_count"
            for scenario in candidate_set.scenarios
        )
        assert candidate_set.scenarios[1].dependency_parameter == 0
        if candidate_set.key.primitive_name == "shift_right":
            assert candidate_set.key.generic_values == (("PreserveSign", "true"),)

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in shift_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(
        artifacts["cpp/bench/manifest_wasm32_simd128.json"]
    )
    assert "vector_scalar" in {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    }
    source = artifacts["cpp/bench/tsl_variant_bench_wasm32_simd128.cpp"]
    assert "next_shift_count<Base_" in source
    assert "scalars[kBatch_" in source


def test_vector_shift_overloads_keep_distinct_policy_identity(
    shift_benchmark_result,
) -> None:
    profile = shift_benchmark_result.rendered.benchmarks.profile(
        "cpp", "wasm32-simd128"
    )
    assert profile is not None
    vector_sets = [
        candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.param_kinds == ("v", "v")
        and candidate_set.key.primitive_name in {"shift_left", "shift_right"}
    ]
    assert vector_sets
    assert all(
        candidate_set.key.overload_parameter_positions == (1,)
        for candidate_set in vector_sets
    )
    assert all(
        isinstance(scenario, BenchmarkRegisterScenario)
        and scenario.operand_generators
        == ("bounded_random", "bounded_shift_count")
        for candidate_set in vector_sets
        for scenario in candidate_set.scenarios
    )
    stable_ids = {candidate_set.stable_id for candidate_set in vector_sets}
    assert len(stable_ids) == len(vector_sets)

    source = next(
        artifact.content
        for artifact in shift_benchmark_result.artifacts.artifacts
        if artifact.logical_path
        == "cpp/bench/tsl_variant_bench_wasm32_simd128.cpp"
    )
    assert "typename ::tsl::reg_param<" in source


def test_immediate_shift_candidates_are_planned_per_authored_value(
    shift_benchmark_result,
) -> None:
    profile = shift_benchmark_result.rendered.benchmarks.profile(
        "cpp", "wasm32-simd128"
    )
    assert profile is not None
    candidate_sets = [
        candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.extension_name == "wasm128"
        and candidate_set.key.primitive_name == "shift_right_imm"
    ]

    assert {candidate_set.key.type_tag for candidate_set in candidate_sets} == {
        "si8",
        "ui8",
        "si16",
        "ui16",
        "si32",
        "ui32",
        "si64",
        "ui64",
        "f32",
        "f64",
    }
    assert all(candidate_set.key.immediate is not None for candidate_set in candidate_sets)
    assert all(
        candidate_set.key.param_kinds == ("v", "sImm")
        and candidate_set.key.generic_values == (("PreserveSign", "true"),)
        for candidate_set in candidate_sets
    )
    assert all(
        isinstance(case, BenchmarkImmediateCorrectnessCase)
        for candidate_set in candidate_sets
        for case in candidate_set.correctness_cases
    )
    assert all(
        isinstance(scenario, BenchmarkImmediateScenario)
        for candidate_set in candidate_sets
        for scenario in candidate_set.scenarios
    )
    assert all(
        [scenario.kind for scenario in candidate_set.scenarios]
        == ["throughput", "latency"]
        for candidate_set in candidate_sets
    )
    assert len({candidate_set.stable_id for candidate_set in candidate_sets}) == len(
        candidate_sets
    )

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in shift_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(
        artifacts["cpp/bench/manifest_wasm32_simd128.json"]
    )
    immediate_records = [
        candidate_set
        for candidate_set in manifest["candidate_sets"]
        if candidate_set["key"]["primitive"] == "shift_right_imm"
    ]
    assert immediate_records
    assert all(record["key"]["immediate"] is not None for record in immediate_records)
    assert {
        scenario["family"]
        for record in immediate_records
        for scenario in record["scenarios"]
    } == {"immediate"}
    source = artifacts["cpp/bench/tsl_variant_bench_wasm32_simd128.cpp"]
    assert "shift_right_imm_impl<Vec_" in source


def test_cross_lane_immediates_require_exact_width_correctness(
    exact_immediate_benchmark_result,
) -> None:
    plan = exact_immediate_benchmark_result.rendered.benchmarks
    cpp = plan.profile("cpp", "sse2")
    rust = plan.profile("rust", "sse2")
    assert cpp is not None
    assert rust is not None
    candidate_sets = [
        candidate_set
        for candidate_set in cpp.candidate_sets
        if candidate_set.key.primitive_name == "permute_lanes_imm"
        and candidate_set.key.extension_name == "sse"
    ]

    assert {
        (candidate_set.key.type_tag, candidate_set.key.immediate)
        for candidate_set in candidate_sets
    } == {
        ("f32", "78"),
        ("f64", "255"),
        ("si32", "27"),
        ("si64", "1"),
        ("ui32", "78"),
        ("ui64", "0"),
    }
    assert all(
        len(case.vector_input) == candidate_set.key.lanes
        and len(case.expected) == candidate_set.key.lanes
        for candidate_set in candidate_sets
        for case in candidate_set.correctness_cases
    )
    assert {
        case.case_name
        for candidate_set in candidate_sets
        for case in candidate_set.correctness_cases
        if candidate_set.key.type_tag == "si32"
    } == {"permute_lanes_si32_sse_sse_exact_reverse"}
    assert all(
        isinstance(scenario, BenchmarkImmediateScenario)
        for candidate_set in candidate_sets
        for scenario in candidate_set.scenarios
    )

    rust_candidate_sets = [
        candidate_set
        for candidate_set in rust.candidate_sets
        if candidate_set.key.primitive_name == "permute_lanes_imm"
        and candidate_set.key.extension_name == "sse"
    ]
    cpp_by_binding = {
        (candidate_set.key.type_tag, candidate_set.key.immediate): candidate_set
        for candidate_set in candidate_sets
    }
    rust_by_binding = {
        (candidate_set.key.type_tag, candidate_set.key.immediate): candidate_set
        for candidate_set in rust_candidate_sets
    }
    assert rust_by_binding.keys() == cpp_by_binding.keys()
    for binding, rust_candidate_set in rust_by_binding.items():
        cpp_candidate_set = cpp_by_binding[binding]
        assert replace(rust_candidate_set.key, backend_id="cpp") == cpp_candidate_set.key
        assert rust_candidate_set.correctness_cases == cpp_candidate_set.correctness_cases
        assert all(
            isinstance(scenario, BenchmarkImmediateScenario)
            for scenario in rust_candidate_set.scenarios
        )
    rust_entries = [
        entry
        for entry in plan.coverage
        if entry.backend_id == "rust"
        and entry.primitive_name == "permute_lanes_imm"
        and entry.extension_name == "sse"
    ]
    assert len(rust_entries) == 6
    assert {entry.status for entry in rust_entries} == {"emitted"}
    assert {entry.reason for entry in rust_entries} == {""}

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in exact_immediate_benchmark_result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_sse2.json"])
    assert {
        scenario["family"]
        for candidate_set in manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    } == {"immediate"}
    source = artifacts["cpp/bench/tsl_variant_bench_sse2.cpp"]
    assert "permute_lanes_imm_impl<Vec_0, 78>::apply(value_0)" in source
    assert "permute_lanes_imm_impl_scalar_lanes_fallback<Vec_0, 78>" in source
    rust_manifest = json.loads(artifacts["rust/bench/manifest_sse2.json"])
    assert {
        scenario["family"]
        for candidate_set in rust_manifest["candidate_sets"]
        for scenario in candidate_set["scenarios"]
    } == {"immediate"}


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
    assert "if(_TSL_POLICY_REQUESTED AND CMAKE_CROSSCOMPILING)" in cmake
    assert "${CMAKE_CXX_COMPILER_ARG1} -dumpmachine" in cmake
    assert 'MATCHES "(wasm|wasi)"' in cmake
    assert "check_cxx_source_runs(" in cmake
    assert "_TSL_POLICY_COMPILER_RUNS_NATIVELY" in cmake
    assert "require a C++ compiler that produces runnable host executables" in cmake
    assert cmake.index("if(_TSL_POLICY_REQUESTED)") < cmake.index(
        'if(_TSL_REQUESTED_PROFILE STREQUAL "auto")'
    )
    assert "Cross-compiling tsl_variant_bench" in cmake


def test_indexed_load_variant_gets_hot_l1_throughput_scenario(
    indexed_load_benchmark_result,
) -> None:
    result = indexed_load_benchmark_result
    entries = result.rendered.benchmarks.coverage
    assert len(entries) == 1
    assert entries[0].status == "emitted"
    assert entries[0].primitive_name == "gather_narrow_partial"
    profile = result.rendered.benchmarks.profile("cpp", "skylake")
    assert profile is not None
    assert len(profile.candidate_sets) == 1
    candidate_set = profile.candidate_sets[0]
    assert candidate_set.key.extension_name == "avx512"
    assert candidate_set.key.type_tag == "si32"
    assert candidate_set.key.immediate == "4"
    assert candidate_set.key.simd_type_base_bindings == (("IndicesType", "si64"),)
    assert candidate_set.key.generic_values == (("N", "1"),)
    assert [candidate.variant_id for candidate in candidate_set.candidates] == [
        "default",
        "scalar_lanes_fallback",
    ]
    assert all(
        isinstance(case, BenchmarkIndexedLoadCorrectnessCase)
        and len(case.index_values) == 8
        and len(case.expected) == 16
        for case in candidate_set.correctness_cases
    )
    assert len(candidate_set.scenarios) == 1
    scenario = candidate_set.scenarios[0]
    assert isinstance(scenario, BenchmarkIndexedLoadScenario)
    assert scenario.kind == "throughput"
    assert scenario.memory_bytes == 4096
    assert scenario.index_lanes == 8

    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }
    manifest = json.loads(artifacts["cpp/bench/manifest_skylake.json"])
    assert manifest["candidate_sets"][0]["scenarios"][0]["family"] == "indexed_load"
    source = artifacts["cpp/bench/tsl_variant_bench_skylake.cpp"]
    assert "using IndexVec_0 = ::tsl::simd<int64_t, ::tsl::avx512>;" in source
    assert "throughput_hot_l1" in source


@pytest.mark.generated_build
def test_native_clang_autotune_and_non_default_policy_build_consumer(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        pytest.skip("the deterministic non-default policy probe uses SSE2")
    clangxx = _native_clangxx()
    if clangxx is None:
        pytest.skip("a native Linux Clang C++ compiler is required")
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
    environment.pop("CXX", None)
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
            #include <iostream>
            #include <tsl.hpp>

            #if !defined(TSL_HAS_AUTOTUNED_VARIANT_POLICY)
            #  error "the autotuned consumer did not receive the policy definition"
            #endif

            int main() {
            #if defined(TSL_PROFILE_SSE2)
              using Vec = tsl::simd<std::int8_t, tsl::sse>;
            #else
              using Vec = tsl::simd<std::int8_t, tsl::scalar>;
            #endif
              typename Vec::register_type value{};
              auto result = tsl::mul<Vec>(value, value);
              (void)result;
              constexpr auto selected = tsl::detail::variants::mul_selector<Vec>::value;
              if constexpr (selected == tsl::detail::variants::mul_variant::default_) {
                std::cout << "default\\n";
              } else if constexpr (
                  selected == tsl::detail::variants::mul_variant::generic_fallback) {
                std::cout << "generic_fallback\\n";
              } else {
                return 2;
              }
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
            f"-DCMAKE_CXX_COMPILER={clangxx}",
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

    assert result.rendered is not None
    sse2 = result.rendered.benchmarks.profile("cpp", "sse2")
    assert sse2 is not None
    selected_set = next(
        candidate_set
        for candidate_set in sse2.candidate_sets
        if candidate_set.key.primitive_name == "mul"
        and candidate_set.key.extension_name == "sse"
        and candidate_set.key.type_tag == "si8"
    )
    forced_policy = tmp_path / "forced_non_default_policy.json"
    policy_document = json.loads(policy.read_text(encoding="utf-8"))
    selected_decision = next(
        decision
        for decision in policy_document["decisions"]
        if decision["stable_id"] == selected_set.stable_id
    )
    compiled_policy = _run((str(autotune / "autotune_consumer"),), environment)
    assert compiled_policy.returncode == 0, (
        compiled_policy.stderr + compiled_policy.stdout
    )
    assert compiled_policy.stdout.strip() == selected_decision["selected"]

    selected_decision.update(
        selected="generic_fallback",
        status="selected",
        minimum_improvement=1.0,
    )
    forced_policy.write_text(
        json.dumps(policy_document, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    policy_consumer = tmp_path / "policy_consumer"
    policy_consumer.mkdir()
    (policy_consumer / "CMakeLists.txt").write_text(
        textwrap.dedent(
            f"""
            cmake_minimum_required(VERSION 3.20)
            project(tsl_policy_consumer LANGUAGES CXX)
            include(FetchContent)
            set(TSL_PROFILE sse2 CACHE STRING "" FORCE)
            set(TSL_BUILD_TESTS OFF CACHE BOOL "" FORCE)
            set(TSL_VARIANT_POLICY_FILE "{forced_policy.as_posix()}" CACHE FILEPATH "" FORCE)
            set(TSL_BENCHMARK_ROUNDS 3 CACHE STRING "" FORCE)
            set(TSL_BENCHMARK_MINIMUM_SAMPLE_NS 10000 CACHE STRING "" FORCE)
            FetchContent_Declare(tsl SOURCE_DIR "{(generated / 'cpp').as_posix()}")
            FetchContent_MakeAvailable(tsl)
            add_executable(policy_consumer main.cpp)
            target_link_libraries(policy_consumer PRIVATE tsl::tsl)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (policy_consumer / "main.cpp").write_text(
        textwrap.dedent(
            """
            #include <cstdint>
            #include <tsl.hpp>

            #if !defined(TSL_HAS_AUTOTUNED_VARIANT_POLICY)
            #  error "the policy-enabled consumer did not receive the policy definition"
            #endif

            using Vec = tsl::simd<std::int8_t, tsl::sse>;
            static_assert(
                tsl::detail::variants::mul_selector<Vec>::value ==
                tsl::detail::variants::mul_variant::generic_fallback
            );

            int main() {
              typename Vec::register_type value{};
              auto result = tsl::mul<Vec>(value, value);
              (void)result;
              return 0;
            }
            """
        ).lstrip(),
        encoding="utf-8",
    )

    manual = tmp_path / "policy_build"
    configured = _run(
        (
            "cmake",
            "-S",
            str(policy_consumer),
            "-B",
            str(manual),
            f"-DCMAKE_CXX_COMPILER={clangxx}",
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    built = _run(
        ("cmake", "--build", str(manual), "--target", "policy_consumer"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout
    executed = _run((str(manual / "policy_consumer"),), environment)
    assert executed.returncode == 0, executed.stderr + executed.stdout


@pytest.mark.generated_build
def test_policy_configure_rejects_wasi_clang_as_non_native(
    benchmark_result,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    wasi_clangxx = _wasi_clangxx()
    if wasi_clangxx is None:
        pytest.skip("WASI SDK clang++ is required")

    generated = tmp_path / "generated"
    write_report = write_artifacts(benchmark_result.artifacts, generated)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    environment = os.environ.copy()
    environment.pop("CXX", None)
    configured = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(tmp_path / "build"),
            f"-DCMAKE_CXX_COMPILER={wasi_clangxx}",
            "-DTSL_PROFILE=auto",
            "-DTSL_BUILD_TESTS=OFF",
            "-DTSL_AUTOTUNE_VARIANTS=ON",
        ),
        environment,
    )
    assert configured.returncode != 0
    output = " ".join((configured.stderr + configured.stdout).split())
    assert "require a C++ compiler that produces runnable host executables" in output
    assert "reports non-native target" in output
    assert "wasm" in output


@pytest.mark.generated_build
@pytest.mark.parametrize(
    "result_fixture",
    ["reduction_benchmark_result", "bit_count_benchmark_result"],
)
def test_avx2_benchmark_source_compiles(
    request: pytest.FixtureRequest,
    result_fixture: str,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    result = request.getfixturevalue(result_fixture)
    generated = tmp_path / "generated"
    write_report = write_artifacts(result.artifacts, generated)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    environment = os.environ.copy()
    if _compiler_name(environment.get("CXX", "")) == "zig":
        environment["CXX"] = "c++"
    build = tmp_path / "build"
    configured = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(build),
            "-DTSL_PROFILE=avx2",
            "-DTSL_BUILD_TESTS=OFF",
            "-DTSL_BUILD_BENCHMARKS=ON",
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    built = _run(
        ("cmake", "--build", str(build), "--target", "tsl_variant_bench"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout


@pytest.mark.generated_build
def test_exact_immediate_benchmark_source_compiles(
    exact_immediate_benchmark_result,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    generated = tmp_path / "generated"
    write_report = write_artifacts(exact_immediate_benchmark_result.artifacts, generated)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    environment = os.environ.copy()
    if _compiler_name(environment.get("CXX", "")) == "zig":
        environment["CXX"] = "c++"
    build = tmp_path / "build"
    configured = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(build),
            "-DTSL_PROFILE=sse2",
            "-DTSL_BUILD_TESTS=OFF",
            "-DTSL_BUILD_BENCHMARKS=ON",
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    built = _run(
        ("cmake", "--build", str(build), "--target", "tsl_variant_bench"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout


@pytest.mark.generated_build
def test_indexed_load_benchmark_source_compiles(
    indexed_load_benchmark_result,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    generated = tmp_path / "generated"
    write_report = write_artifacts(indexed_load_benchmark_result.artifacts, generated)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    environment = os.environ.copy()
    if _compiler_name(environment.get("CXX", "")) == "zig":
        environment["CXX"] = "c++"
    build = tmp_path / "build"
    configured = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(build),
            "-DTSL_PROFILE=skylake",
            "-DTSL_BUILD_TESTS=OFF",
            "-DTSL_BUILD_BENCHMARKS=ON",
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    built = _run(
        ("cmake", "--build", str(build), "--target", "tsl_variant_bench"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout


@pytest.mark.generated_build
def test_neon_benchmark_cross_compiles_and_runs_functionally_under_qemu(
    division_benchmark_result,
    machine_profiles,
    tmp_path: Path,
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake is required")
    compiler = shutil.which("aarch64-linux-gnu-g++")
    qemu = os.environ.get("TSLC_QEMU_AARCH64") or shutil.which("qemu-aarch64")
    sysroot = Path("/usr/aarch64-linux-gnu")
    if compiler is None or qemu is None or not sysroot.is_dir():
        pytest.skip("the AArch64 compiler, QEMU, and sysroot are required")
    runner = machine_profiles["neon"].runner
    assert runner is not None
    assert runner.kind == "qemu-aarch64"

    generated = tmp_path / "generated"
    write_report = write_artifacts(division_benchmark_result.artifacts, generated)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    environment = os.environ.copy()
    environment["CXX"] = compiler
    build = tmp_path / "build"
    configured = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(build),
            "-DCMAKE_SYSTEM_NAME=Linux",
            "-DCMAKE_SYSTEM_PROCESSOR=aarch64",
            "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
            "-DTSL_PROFILE=neon",
            "-DTSL_BUILD_TESTS=OFF",
            "-DTSL_BUILD_BENCHMARKS=ON",
        ),
        environment,
    )
    assert configured.returncode == 0, configured.stderr + configured.stdout
    assert "Cross-compiling tsl_variant_bench" in configured.stdout

    built = _run(
        ("cmake", "--build", str(build), "--target", "tsl_variant_bench"),
        environment,
    )
    assert built.returncode == 0, built.stderr + built.stdout

    results = tmp_path / "neon_results.jsonl"
    executed = _run(
        (
            qemu,
            "-L",
            str(sysroot),
            "-cpu",
            runner.profile,
            *runner.args,
            str(build / "tsl_variant_bench"),
            "--results",
            str(results),
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--threshold",
            "0.05",
        ),
        environment,
    )
    assert executed.returncode == 0, executed.stderr + executed.stdout
    records = tuple(
        json.loads(line)
        for line in results.read_text(encoding="utf-8").splitlines()
        if line
    )
    assert records
    assert {record["profile"] for record in records} == {"neon"}
    assert {record["candidate"] for record in records} == {
        "default",
        "generic_fallback",
    }

    policy_build = tmp_path / "policy_build"
    rejected = _run(
        (
            "cmake",
            "-S",
            str(generated / "cpp"),
            "-B",
            str(policy_build),
            "-DCMAKE_SYSTEM_NAME=Linux",
            "-DCMAKE_SYSTEM_PROCESSOR=aarch64",
            "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
            "-DTSL_PROFILE=neon",
            "-DTSL_BUILD_TESTS=OFF",
            "-DTSL_AUTOTUNE_VARIANTS=ON",
        ),
        environment,
    )
    assert rejected.returncode != 0
    assert "policy generation and validation are native-only" in (
        rejected.stderr + rejected.stdout
    )


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


def _native_clangxx() -> str | None:
    candidates = ("/usr/bin/clang++", shutil.which("clang++"))
    for candidate in candidates:
        if candidate is None or not Path(candidate).is_file():
            continue
        target = subprocess.run(
            (candidate, "-dumpmachine"),
            check=False,
            capture_output=True,
            text=True,
        )
        if (
            target.returncode == 0
            and "linux" in target.stdout
            and "wasm" not in target.stdout
        ):
            # Clang selects C++ driver behavior from argv[0], so preserve the
            # clang++ symlink instead of resolving it to the clang binary.
            return str(Path(candidate).absolute())
    return None


def _wasi_clangxx() -> str | None:
    sdk_root = Path(os.environ.get("WASI_SDK_PATH", "/opt/wasi-sdk"))
    candidate = sdk_root / "bin" / "clang++"
    if not candidate.is_file():
        return None
    target = subprocess.run(
        (str(candidate), "-dumpmachine"),
        check=False,
        capture_output=True,
        text=True,
    )
    if target.returncode == 0 and "wasm" in target.stdout:
        return str(candidate)
    return None
