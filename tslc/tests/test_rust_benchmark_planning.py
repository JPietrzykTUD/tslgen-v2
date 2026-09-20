"""Backend-parameterized benchmark planning with Rust plan-only evidence."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import BackendHelperPlan
from tslc.backend.registry import (
    backend_capability,
    load_backend_policy_inputs,
    supports_backend,
)
from tslc.benchmark.identity import (
    implementation_body_hash,
    specialization_key,
    specialization_stable_id,
)
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkProjectPlan,
    BenchmarkReductionCorrectnessCase,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkVectorCorrectnessCase,
)
from tslc.benchmark.planner import (
    BenchmarkPlanner,
    BenchmarkScenarioAdmission,
)
from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.semantics import (
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
    CONTIGUOUS_VECTOR_STORE_REQUIREMENT,
    MASK_FROM_INTEGRAL_REQUIREMENT,
    MASK_TO_INTEGRAL_REQUIREMENT,
    VECTOR_FROM_ARRAY_REQUIREMENT,
    VECTOR_TO_ARRAY_REQUIREMENT,
)
from tslc.compiler_assets import load_default_render_assets
from tslc.diagnostics import has_errors
from tslc.value_tests.model import ValueTestProjectPlan

RUST_POLICY_INPUTS = load_backend_policy_inputs(("rust",))


def test_benchmark_planner_uses_semantically_resolved_harness_names(
    catalog: Catalog,
) -> None:
    requirements = (
        VECTOR_FROM_ARRAY_REQUIREMENT,
        VECTOR_TO_ARRAY_REQUIREMENT,
        MASK_TO_INTEGRAL_REQUIREMENT,
        MASK_FROM_INTEGRAL_REQUIREMENT,
        CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
        CONTIGUOUS_VECTOR_STORE_REQUIREMENT,
    )
    providers = tuple(
        catalog.resolve_primitive_provider(item) for item in requirements
    )
    assert all(isinstance(provider, Primitive) for provider in providers)
    names_by_identity = {
        id(provider): f"benchmark_provider_{index}"
        for index, provider in enumerate(providers)
    }
    renamed = replace(
        catalog,
        primitives=tuple(
            replace(primitive, name=names_by_identity[id(primitive)])
            if id(primitive) in names_by_identity
            else primitive
            for primitive in catalog.primitives
        ),
    )

    planner = BenchmarkPlanner(renamed, backend_id="rust")

    assert (
        planner._harness.from_array,
        planner._harness.to_array,
        planner._harness.to_integral,
        planner._harness.to_mask,
        planner._harness.load,
        planner._harness.store,
    ) == tuple(f"benchmark_provider_{index}" for index in range(len(requirements)))


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
    rust_helper_plan: BackendHelperPlan,
) -> None:
    result = rust_benchmark_planning_result
    plan = result.rendered.benchmarks

    assert tuple(profile.backend_id for profile in plan.profiles) == ("cpp", "rust")
    rust_candidate_set = _mul_candidate_set(plan, "rust")
    rust_profile = plan.profile("rust", "sse2")
    assert rust_profile is not None
    assert (
        rust_profile.manifest_hash
        == "70249b3d3619f003e3d8d71b628601623dfa979f63a53cfa5e2182d312772de6"
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
        policy_inputs=RUST_POLICY_INPUTS,
        helper_plan=rust_helper_plan,
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
        "731814af5f813d0234c58586d9d2dfd283bf3557bbca495539c10ed31caab6a0",
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
            header_group=candidate_set.key.header_group,
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


def test_cpp_manifest_identity_is_deterministic(
    rust_benchmark_planning_result,
) -> None:
    profile = rust_benchmark_planning_result.rendered.benchmarks.profile(
        "cpp", "sse2"
    )
    assert profile is not None
    assert (
        profile.manifest_hash
        == "b01c9c62dadac2f013bffc6b4a7e33285a597bd57560ccf7406efc46885c5204"
    )
    candidate_set = _mul_candidate_set(
        rust_benchmark_planning_result.rendered.benchmarks, "cpp"
    )
    assert candidate_set.stable_id == "sse2_mul_sse_si8_7255aba5c341"
    assert tuple(candidate.body_hash for candidate in candidate_set.candidates) == (
        "a9f066cceee43b05e8deabaf96db9ba0bc8b7879176bd28925d41afaab914b4d",
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
        == "1f54410763f34c03a9a3cf929dee2a0af56929a26a922637dfc26b8a2866e34e"
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
        assert profile.feature_detection_strategy == "x86_builtin"


def test_profile_scenario_admission_prevents_cartesian_expansion(
    rust_non_register_benchmark_planning_result,
    catalog: Catalog,
) -> None:
    result = rust_non_register_benchmark_planning_result
    plan = BenchmarkPlanner(
        catalog,
        backend_id="rust",
        supported_admissions=frozenset(
            {
                BenchmarkScenarioAdmission("avx2", "register"),
                BenchmarkScenarioAdmission("sse2", "reduction"),
            }
        ),
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


def test_rust_avx2_admits_reduction_reports(
    rust_non_register_benchmark_planning_result,
) -> None:
    plan = rust_non_register_benchmark_planning_result.rendered.benchmarks
    profile = plan.profile("rust", "avx2")
    assert profile is not None
    assert len(profile.candidate_sets) == 1

    candidate_set = profile.candidate_sets[0]
    assert candidate_set.key.primitive_name == "hadd"
    assert candidate_set.key.type_tag == "si32"
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

    hadd = next(
        entry
        for entry in plan.coverage
        if entry.backend_id == "rust" and entry.primitive_name == "hadd"
    )
    assert hadd.status == "emitted"


def test_rust_avx2_does_not_admit_register_scenarios(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["avx2"],
        type_tags=["si8"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    profile = result.rendered.benchmarks.profile("rust", "avx2")
    assert profile is not None
    assert profile.candidate_sets == ()

    mul = next(
        entry
        for entry in result.rendered.benchmarks.coverage
        if entry.backend_id == "rust" and entry.primitive_name == "mul"
    )
    assert mul.status == "unsupported"
    assert (
        mul.reason
        == "backend benchmark support does not include the 'register' scenario family"
    )


def test_rust_sse2_admission_uses_live_profile_context(
    rust_benchmark_planning_result,
    catalog: Catalog,
) -> None:
    result = rust_benchmark_planning_result
    source_profile = result.emitted_profiles[0]
    machine_profile = source_profile.profile
    source_plan = result.rendered.benchmarks.profile("rust", "sse2")
    assert source_plan is not None
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
            RUST_POLICY_INPUTS,
        )
        assert plan is not None
        profile = plan.profile("rust", "sse2")
        assert profile is not None
        assert profile.candidate_sets
        assert profile.manifest_hash != source_plan.manifest_hash
        assert profile.backend_feature_spellings == tuple(
            sorted(
                (
                    mutated_profile.feature_spelling(feature, "rust")
                    for feature in mutated_profile.features
                )
            )
        )
        assert plan.coverage
        assert any(entry.status == "emitted" for entry in plan.coverage)


def test_rust_benchmark_reports_unadmitted_profiles(
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
        == "backend benchmark support does not include profile 'neon'"
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
    assert all(entry.slot_hash == "" for entry in first.coverage)

    grouped_key = specialization_key(
        backend_id="future",
        profile=fake_profile,
        specialization=candidate_set.specialization,
        primitive_specializations=fake_profile.specializations("future")["mul"],
        header_group="future_group",
    )
    assert grouped_key.header_group == "future_group"
    assert specialization_stable_id(grouped_key) != candidate_set.stable_id

    grouped = BenchmarkPlanner(
        catalog,
        backend_id="future",
        extension_header_group=(
            lambda extension: "future_group" if extension is not None else None
        ),
    ).plan((fake_profile,), fake_value_tests)
    assert not any(entry.status == "emitted" for entry in grouped.coverage)
    assert {
        entry.reason
        for entry in grouped.coverage
        if entry.primitive_name == "mul"
    } == {
        "opt-in header-group extensions are not supported by benchmark planning"
    }

    identified = BenchmarkPlanner(
        catalog,
        backend_id="future",
        slot_identity=lambda profile_name, spec: (
            f"future:{profile_name}:{spec.primitive_name}"
        ),
    ).plan((fake_profile,), fake_value_tests)
    assert identified.coverage
    assert all(
        entry.slot_hash
        == f"future:{entry.profile_name}:{entry.primitive_name}"
        for entry in identified.coverage
    )
