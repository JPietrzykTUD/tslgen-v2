"""Backend-parameterized benchmark planning with Rust plan-only evidence."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capability, supports_backend
from tslc.benchmark.identity import (
    implementation_body_hash,
    specialization_key,
    specialization_stable_id,
)
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkProjectPlan,
    BenchmarkRegisterScenario,
    BenchmarkVectorCorrectnessCase,
)
from tslc.benchmark.planner import BenchmarkPlanner
from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors
from tslc.value_tests.model import ValueTestProjectPlan


@pytest.fixture(scope="module")
def rust_benchmark_planning_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["sse2"],
        type_tags=["si8"],
        backends=["cpp", "rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def rust_non_register_benchmark_planning_result(
    data_root: Path,
    machine_profiles_path: Path,
):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["hadd"],
        profiles=["avx2"],
        type_tags=["si32"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


def _mul_candidate_set(
    plan: BenchmarkProjectPlan,
    backend_id: str,
) -> BenchmarkCandidateSet:
    profile = plan.profile(backend_id, "sse2")
    assert profile is not None
    return next(
        candidate_set
        for candidate_set in profile.candidate_sets
        if candidate_set.key.primitive_name == "mul"
        and candidate_set.key.extension_name == "sse"
        and candidate_set.key.type_tag == "si8"
    )


def test_rust_backend_produces_typed_plan_and_report_artifacts(
    rust_benchmark_planning_result,
) -> None:
    result = rust_benchmark_planning_result
    plan = result.rendered.benchmarks

    assert tuple(profile.backend_id for profile in plan.profiles) == ("cpp", "rust")
    rust_candidate_set = _mul_candidate_set(plan, "rust")
    rust_profile = plan.profile("rust", "sse2")
    assert rust_profile is not None
    assert (
        rust_profile.manifest_hash
        == "fd66dfae26923d8a3185e959a7104e77cb0983717f5aa3904239e1ddef7ad5f5"
    )
    assert [candidate.variant_id for candidate in rust_candidate_set.candidates] == [
        "default",
        "generic_fallback",
    ]
    assert rust_candidate_set.correctness_cases
    assert all(
        isinstance(scenario, BenchmarkRegisterScenario)
        for scenario in rust_candidate_set.scenarios
    )
    assert any(
        entry.backend_id == "rust"
        and entry.primitive_name == "mul"
        and entry.extension_name == "sse"
        and entry.type_tag == "si8"
        and entry.status == "emitted"
        for entry in plan.coverage
    )
    assert any(
        artifact.logical_path == "rust/bench/manifest_sse2.json"
        for artifact in result.artifacts.artifacts
    )
    cargo_toml = next(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path == "rust/Cargo.toml"
    )
    assert "[[bench]]" in cargo_toml
    assert backend_capability("rust").render_artifacts(
        rust_benchmark_planning_result.emitted_profiles,
        rust_benchmark_planning_result.rendered.value_tests,
        plan,
        load_default_render_assets(),
    )


def test_cpp_and_rust_plans_reuse_correctness_and_scenario_owners(
    rust_benchmark_planning_result,
    catalog: Catalog,
) -> None:
    plan = rust_benchmark_planning_result.rendered.benchmarks
    cpp = _mul_candidate_set(plan, "cpp")
    rust = _mul_candidate_set(plan, "rust")

    assert replace(rust.key, backend_id="cpp") == cpp.key
    assert rust.correctness_cases == cpp.correctness_cases
    assert tuple(candidate.variant_id for candidate in rust.candidates) == tuple(
        candidate.variant_id for candidate in cpp.candidates
    )
    assert tuple(
        replace(scenario, timing=replace(scenario.timing, seed=0))
        for scenario in rust.scenarios
    ) == tuple(
        replace(scenario, timing=replace(scenario.timing, seed=0))
        for scenario in cpp.scenarios
    )
    assert rust.stable_id != cpp.stable_id
    assert tuple(candidate.body_hash for candidate in rust.candidates) != tuple(
        candidate.body_hash for candidate in cpp.candidates
    )
    assert rust.stable_id == "sse2_mul_sse_si8_0ca8e0838e70"
    assert tuple(candidate.body_hash for candidate in rust.candidates) == (
        "6071354eaedae27e059fc38432d28795b2e6d85c2214c87eaa37247faf8b18b7",
        "e4e9eb419a7aa1c6aff1ecf050ff70083f5e16e40d682612549823f6eddee74a",
    )

    rust_value_profile = rust_benchmark_planning_result.rendered.value_tests.profiles_for(
        "rust"
    )[0]
    owner_cases = {
        case.case_name: case
        for case in rust_value_profile.cases
        if case.kind == "generic_golden"
        and case.call_name == "mul"
        and case.type_tag == "si8"
    }
    assert all(
        isinstance(case, BenchmarkVectorCorrectnessCase)
        for case in rust.correctness_cases
    )
    assert {
        case.case_name: (case.vector_inputs, case.expected)
        for case in rust.correctness_cases
        if isinstance(case, BenchmarkVectorCorrectnessCase)
    } == {
        case_name: (case.inputs.vectors, case.expectation.values)
        for case_name, case in owner_cases.items()
    }

    source_primitive = catalog.primitives_named("mul")[0]
    latency = next(scenario for scenario in rust.scenarios if scenario.kind == "latency")
    assert latency.dependency_parameter is not None
    assert (
        rust.specialization.param_names[latency.dependency_parameter]
        == source_primitive.benchmark.latency_chain
    )


def test_shared_identity_helper_preserves_frozen_backend_keys(
    rust_benchmark_planning_result,
) -> None:
    result = rust_benchmark_planning_result
    profile = next(
        emitted
        for emitted in result.emitted_profiles
        if emitted.profile.name == "sse2"
    )
    expected_ids = {
        "cpp": "sse2_mul_sse_si8_7255aba5c341",
        "rust": "sse2_mul_sse_si8_0ca8e0838e70",
    }

    for backend_id in ("cpp", "rust"):
        candidate_set = _mul_candidate_set(result.rendered.benchmarks, backend_id)
        specialization = candidate_set.specialization
        rebuilt = specialization_key(
            backend_id=backend_id,
            profile=profile,
            specialization=specialization,
            primitive_specializations=profile.specializations(backend_id)["mul"],
        )

        assert rebuilt == candidate_set.key
        assert rebuilt.canonical_fields() == (
            backend_id,
            "sse2",
            "mul",
            "mul",
            "sse",
            "si8",
            "v",
            ("v", "v"),
            None,
            None,
            (),
            None,
            (),
            (),
            (),
            16,
            None,
        )
        assert specialization_stable_id(rebuilt) == expected_ids[backend_id]
        assert tuple(
            implementation_body_hash(body)
            for body in (
                specialization.body_text,
                *(variant.body_text for variant in specialization.variant_bodies),
            )
        ) == tuple(candidate.body_hash for candidate in candidate_set.candidates)


def test_cpp_manifest_identity_is_unchanged(
    rust_benchmark_planning_result,
) -> None:
    profile = rust_benchmark_planning_result.rendered.benchmarks.profile(
        "cpp", "sse2"
    )
    assert profile is not None
    assert (
        profile.manifest_hash
        == "3da475b457a00c498123b31b00faa0a54a217d2b645ac84ff8207e39d043e132"
    )
    candidate_set = _mul_candidate_set(
        rust_benchmark_planning_result.rendered.benchmarks, "cpp"
    )
    assert candidate_set.stable_id == "sse2_mul_sse_si8_7255aba5c341"
    assert tuple(candidate.body_hash for candidate in candidate_set.candidates) == (
        "f1c4f6a86618ec0606ce0d19c7de7e742a1e3c6d7e7a339d85a748e287239d74",
        "f259d2fe8b25f0131c537188b0ea01d2bb73d2af4a9a968c8a681880d4a7caae",
    )
    rendered_manifest = next(
        artifact.content
        for artifact in rust_benchmark_planning_result.artifacts.artifacts
        if artifact.logical_path == "cpp/bench/manifest_sse2.json"
    )
    assert len(rendered_manifest.encode("utf-8")) == 4583
    assert (
        sha256(rendered_manifest.encode("utf-8")).hexdigest()
        == "486bd0f68520cee4fef7f352ef5bd67166a08d89ef28edc2ebc39868db68bdc5"
    )


def test_profile_plan_owns_family_and_ordered_backend_feature_spellings(
    rust_benchmark_planning_result,
) -> None:
    plan = rust_benchmark_planning_result.rendered.benchmarks

    for backend_id in ("cpp", "rust"):
        profile = plan.profile(backend_id, "sse2")
        assert profile is not None
        assert profile.profile_family == "x86"
        assert profile.backend_feature_spellings == ("sse", "sse2")


def test_rust_register_only_support_reports_other_scenario_families(
    rust_non_register_benchmark_planning_result,
    catalog: Catalog,
) -> None:
    result = rust_non_register_benchmark_planning_result
    plan = BenchmarkPlanner(
        catalog,
        backend_id="rust",
        supported_scenario_families=frozenset({"register"}),
    ).plan(result.emitted_profiles, result.rendered.value_tests)
    profile = plan.profile("rust", "avx2")
    assert profile is not None
    assert profile.candidate_sets == ()
    assert profile.profile_family == "x86"
    assert profile.backend_feature_spellings == (
        "avx",
        "avx2",
        "rdrand",
        "sse",
        "sse2",
        "sse4.1",
        "sse4.2",
        "ssse3",
    )

    hadd = next(
        entry
        for entry in plan.coverage
        if entry.backend_id == "rust" and entry.primitive_name == "hadd"
    )
    assert hadd.status == "unsupported"
    assert (
        hadd.reason
        == "backend benchmark support does not include the 'reduction' scenario family"
    )
    assert not any(entry.status == "emitted" for entry in plan.coverage)


def test_rust_report_pilot_is_restricted_to_sse2(
    rust_non_register_benchmark_planning_result,
) -> None:
    plan = rust_non_register_benchmark_planning_result.rendered.benchmarks
    profile = plan.profile("rust", "avx2")
    assert profile is not None
    assert profile.candidate_sets == ()

    hadd = next(
        entry
        for entry in plan.coverage
        if entry.backend_id == "rust" and entry.primitive_name == "hadd"
    )
    assert hadd.status == "unsupported"
    assert (
        hadd.reason
        == "backend benchmark support does not include profile 'avx2'"
    )
    assert not any(entry.status == "emitted" for entry in plan.coverage)


def test_rust_sse2_pilot_requires_exact_profile_context(
    rust_benchmark_planning_result,
    catalog: Catalog,
) -> None:
    result = rust_benchmark_planning_result
    source_profile = result.emitted_profiles[0]
    machine_profile = source_profile.profile
    mutated_profiles = (
        replace(
            machine_profile,
            features=frozenset({"sse", "sse2", "avx2"}),
        ),
        replace(machine_profile, alternatives={"sse2": "avx2"}),
        replace(machine_profile, compile_modes=frozenset({"custom_mode"})),
        replace(
            machine_profile,
            backend_flags={"rust": ("-Ctarget-feature=+avx2",)},
        ),
    )

    for mutated_profile in mutated_profiles:
        emitted_profile = EmittedProfile(
            profile=mutated_profile,
            specializations_by_backend=source_profile.specializations_by_backend,
            extensions=source_profile.extensions,
            profile_family=source_profile.profile_family,
            immediate_split_names=frozenset(),
        )
        plan = backend_capability("rust").plan_benchmarks(
            catalog,
            (emitted_profile,),
            result.rendered.value_tests,
        )
        assert plan is not None
        profile = plan.profile("rust", "sse2")
        assert profile is not None
        assert profile.candidate_sets == ()
        assert plan.coverage
        assert {entry.status for entry in plan.coverage} == {"unsupported"}
        assert {entry.reason for entry in plan.coverage} == {
            "backend benchmark support requires the canonical feature/build "
            "context for profile 'sse2'"
        }


def test_rust_x86_pilot_reports_other_profile_families(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["abs"],
        profiles=["neon"],
        type_tags=["si8"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    profile = result.rendered.benchmarks.profile("rust", "neon")
    assert profile is not None
    assert profile.profile_family == "aarch64"
    assert profile.candidate_sets == ()

    coverage = result.rendered.benchmarks.coverage
    abs_entry = next(
        entry
        for entry in coverage
        if entry.backend_id == "rust"
        and entry.primitive_name == "abs"
        and entry.extension_name == "neon"
        and entry.type_tag == "si8"
    )
    assert abs_entry.status == "unsupported"
    assert (
        abs_entry.reason
        == "backend benchmark support does not include the 'aarch64' profile family"
    )
    assert not any(entry.status == "emitted" for entry in coverage)


def test_unregistered_backend_can_reuse_planner_without_name_dispatch(
    rust_benchmark_planning_result,
    catalog: Catalog,
) -> None:
    result = rust_benchmark_planning_result
    source_profile = result.emitted_profiles[0]
    fake_specializations = {
        primitive_name: tuple(
            replace(spec, backend_id="future") for spec in specializations
        )
        for primitive_name, specializations in source_profile.specializations(
            "rust"
        ).items()
    }
    fake_profile = EmittedProfile(
        profile=source_profile.profile,
        specializations_by_backend={"future": fake_specializations},
        extensions=source_profile.extensions,
        profile_family=source_profile.profile_family,
        immediate_split_names=frozenset(),
    )
    rust_value_profile = result.rendered.value_tests.profiles_for("rust")[0]
    fake_value_tests = ValueTestProjectPlan(
        profiles=(replace(rust_value_profile, backend_id="future"),)
    )
    planner = BenchmarkPlanner(catalog, backend_id="future")

    assert not supports_backend("future")
    first = planner.plan((fake_profile,), fake_value_tests)
    second = planner.plan((fake_profile,), fake_value_tests)
    candidate_set = _mul_candidate_set(first, "future")
    assert first == second
    assert candidate_set.key.backend_id == "future"
    assert [candidate.variant_id for candidate in candidate_set.candidates] == [
        "default",
        "generic_fallback",
    ]
