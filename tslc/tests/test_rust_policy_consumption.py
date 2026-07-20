"""Pure evidence for the Rust benchmark/policy-selection join."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import textwrap

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.backend.rust_benchmark_context import RUST_BENCHMARK_CODEGEN_CONTRACT
from tslc.backend.rust_policy_consumption import (
    RustPolicyConsumptionProfile,
    join_rust_policy_consumption_profile,
    plan_rust_policy_coverage,
    plan_rust_policy_consumption,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelection,
    RustPolicySelectionPlan,
    RustPolicySelectionProfile,
    plan_rust_policy_selection,
)
from tslc.benchmark.model import BenchmarkProfilePlan, BenchmarkProjectPlan
from tslc.diagnostics import has_errors
from tslc.pipeline import GenerationResult


@pytest.fixture(scope="module")
def rust_policy_project(
    data_root: Path,
    machine_profiles_path: Path,
) -> GenerationResult:
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
def rust_policy_inputs(
    rust_policy_project,
) -> tuple[BenchmarkProfilePlan, RustPolicySelectionProfile]:
    result = rust_policy_project
    benchmark = result.rendered.benchmarks.profile("rust", "sse2")
    selection = plan_rust_policy_selection(result.emitted_profiles).profile("sse2")
    assert benchmark is not None
    assert selection is not None
    return benchmark, selection


def test_join_preserves_ordered_policy_and_benchmark_facts(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs
    rendered: list[tuple[str, str]] = []

    def render_mapping(choice: RustPolicySelection) -> str:
        rendered.append((choice.key.primitive_name, choice.selected_candidate))
        return f"mapping:{choice.key.primitive_name}:{choice.selected_candidate}"

    joined = join_rust_policy_consumption_profile(
        benchmark,
        replace(selection, coverage=tuple(reversed(selection.coverage))),
        render_mapping=render_mapping,
    )

    assert joined == RustPolicyConsumptionProfile(
        backend_id="rust",
        profile_name="sse2",
        profile_family=benchmark.profile_family,
        manifest_hash=benchmark.manifest_hash,
        required_features=benchmark.backend_feature_spellings,
        decisions=joined.decisions,
    )
    assert [decision.stable_id for decision in joined.decisions] == [
        candidate_set.stable_id for candidate_set in benchmark.candidate_sets
    ]
    assert [decision.status for decision in joined.decisions] == [
        "supported",
        "report_only",
        "report_only",
    ]

    supported = joined.decisions[0]
    candidate_set = benchmark.candidate_sets[0]
    assert [(item.candidate_id, item.body_hash) for item in supported.candidates] == [
        (candidate.variant_id, candidate.body_hash)
        for candidate in candidate_set.candidates
    ]
    assert [
        (scenario.scenario_id, scenario.family, scenario.kind, scenario.timing)
        for scenario in supported.scenarios
    ] == [
        (scenario.scenario_id, scenario.family, scenario.kind, scenario.timing)
        for scenario in candidate_set.scenarios
    ]
    assert supported.specialization_required_features == tuple(
        sorted(candidate_set.specialization.required_features)
    )
    assert [
        (choice.candidate_id, choice.source) for choice in supported.mapping_choices
    ] == [
        ("default", "mapping:mul:default"),
        ("generic_fallback", "mapping:mul:generic_fallback"),
    ]
    assert all(not decision.mapping_choices for decision in joined.decisions[1:])
    assert rendered == [
        ("mul", "default"),
        ("mul", "generic_fallback"),
    ]


def test_policy_coverage_retains_a_report_only_only_profile(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs
    demoted_coverage = tuple(
        replace(
            entry,
            status="report_only",
            reason="focused report-only coverage sentinel",
        )
        if entry.status == "supported"
        else entry
        for entry in selection.coverage
    )
    selection_plan = RustPolicySelectionPlan(
        profiles=(
            replace(
                selection,
                selections=(),
                coverage=demoted_coverage,
            ),
        )
    )
    benchmarks = BenchmarkProjectPlan(profiles=(benchmark,))

    coverage = plan_rust_policy_coverage(benchmarks, selection_plan)
    coverage_profile = coverage.profile("sse2")
    assert coverage_profile is not None
    assert len(coverage_profile.decisions) == len(benchmark.candidate_sets)
    assert {decision.status for decision in coverage_profile.decisions} == {
        "report_only"
    }
    assert coverage.gaps == ()

    consumption = plan_rust_policy_consumption(benchmarks, selection_plan)
    assert consumption.profiles == ()
    assert consumption.gaps == ()


def test_policy_coverage_rejects_a_foreign_report_only_profile(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs
    foreign_coverage = tuple(
        replace(
            entry,
            key=replace(entry.key, profile_name="foreign"),
            status="report_only",
            reason=(entry.reason or "foreign report-only sentinel"),
        )
        for entry in selection.coverage
    )
    foreign = RustPolicySelectionProfile(
        profile_name="foreign",
        selections=(),
        coverage=foreign_coverage,
    )

    with pytest.raises(
        ValueError,
        match="policy-selection profiles have no benchmark profile: 'foreign'",
    ):
        plan_rust_policy_coverage(
            BenchmarkProjectPlan(profiles=(benchmark,)),
            RustPolicySelectionPlan(profiles=(selection, foreign)),
        )


def test_join_rejects_profile_key_and_candidate_inventory_drift(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs

    with pytest.raises(ValueError, match="profiles do not match"):
        join_rust_policy_consumption_profile(
            replace(benchmark, profile_name="foreign"),
            selection,
            render_mapping=_mapping_source,
        )

    with pytest.raises(ValueError, match="missing policy coverage"):
        join_rust_policy_consumption_profile(
            benchmark,
            replace(
                selection,
                coverage=tuple(
                    entry
                    for entry in selection.coverage
                    if entry.key != benchmark.candidate_sets[0].key
                ),
                selections=(),
            ),
            render_mapping=_mapping_source,
        )

    extra_report_only = replace(
        selection.coverage[-1],
        key=replace(selection.coverage[-1].key, primitive_name="extra"),
    )
    joined = join_rust_policy_consumption_profile(
        benchmark,
        replace(selection, coverage=(*selection.coverage, extra_report_only)),
        render_mapping=_mapping_source,
    )
    assert len(joined.decisions) == len(benchmark.candidate_sets)

    supported = benchmark.candidate_sets[0]
    foreign_candidate = replace(
        supported.candidates[1],
        variant_id="foreign",
    )
    stale_set = replace(
        supported,
        candidates=(supported.candidates[0], foreign_candidate),
    )
    with pytest.raises(ValueError, match="candidate inventories do not match"):
        join_rust_policy_consumption_profile(
            replace(
                benchmark,
                candidate_sets=(stale_set, *benchmark.candidate_sets[1:]),
            ),
            selection,
            render_mapping=_mapping_source,
        )


def test_join_rejects_stale_mapping_facts_and_invalid_rendered_choices(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs
    supported = benchmark.candidate_sets[0]
    stale_set = replace(
        supported,
        specialization=replace(
            supported.specialization,
            required_features=frozenset({"sse"}),
        ),
    )
    with pytest.raises(ValueError, match="compiler selection facts do not match"):
        join_rust_policy_consumption_profile(
            replace(
                benchmark,
                candidate_sets=(stale_set, *benchmark.candidate_sets[1:]),
            ),
            selection,
            render_mapping=_mapping_source,
        )

    duplicate_id = replace(
        benchmark.candidate_sets[1],
        stable_id=benchmark.candidate_sets[0].stable_id,
    )
    with pytest.raises(ValueError, match="stable IDs must be unique"):
        join_rust_policy_consumption_profile(
            replace(
                benchmark,
                candidate_sets=(
                    benchmark.candidate_sets[0],
                    duplicate_id,
                    *benchmark.candidate_sets[2:],
                ),
            ),
            selection,
            render_mapping=_mapping_source,
        )

    with pytest.raises(ValueError, match="require an ID and source"):
        join_rust_policy_consumption_profile(
            benchmark,
            selection,
            render_mapping=lambda _selection: " ",
        )


def test_consumption_plan_keeps_missing_benchmark_evidence_default_only(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs
    without_supported = replace(
        benchmark,
        candidate_sets=benchmark.candidate_sets[1:],
    )
    plan = plan_rust_policy_consumption(
        BenchmarkProjectPlan(profiles=(without_supported,)),
        RustPolicySelectionPlan(profiles=(selection,)),
    )

    assert not plan.profiles
    assert [(gap.profile_name, gap.reason) for gap in plan.gaps] == [
        (
            "sse2",
            "policy-supported Rust selections lack benchmark candidate evidence",
        )
    ]


def test_consumption_plan_rejects_foreign_rust_benchmark_profile(
    rust_policy_inputs: tuple[BenchmarkProfilePlan, RustPolicySelectionProfile],
) -> None:
    benchmark, selection = rust_policy_inputs

    with pytest.raises(ValueError, match="no policy-selection profile: 'foreign'"):
        plan_rust_policy_consumption(
            BenchmarkProjectPlan(
                profiles=(benchmark, replace(benchmark, profile_name="foreign"))
            ),
            RustPolicySelectionPlan(profiles=(selection,)),
        )


def test_generated_policy_descriptor_and_static_seam_are_complete(
    rust_policy_project: GenerationResult,
) -> None:
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in rust_policy_project.artifacts.artifacts
    }
    descriptor = json.loads(
        artifacts["rust/bench/policy_consumption_sse2.json"]
    )
    manifest = json.loads(artifacts["rust/bench/manifest_sse2.json"])
    cargo_manifest = artifacts["rust/Cargo.toml"]

    assert "[profile.bench]" in cargo_manifest
    assert "[profile.release]" not in cargo_manifest
    assert cargo_manifest.count("codegen-units = 1") == 1

    assert set(descriptor) == {
        "schema_version",
        "policy_schema_version",
        "protocol_version",
        "backend",
        "profile",
        "profile_family",
        "manifest_hash",
        "required_features",
        "benchmark_codegen_contract",
        "decisions",
    }
    assert descriptor["schema_version"] == 1
    assert descriptor["policy_schema_version"] == 2
    assert descriptor["protocol_version"] == 1
    assert descriptor["backend"] == "rust"
    assert descriptor["profile"] == "sse2"
    assert descriptor["profile_family"] == "x86"
    assert descriptor["manifest_hash"] == manifest["manifest_hash"]
    assert descriptor["required_features"] == ["sse", "sse2"]
    assert descriptor["benchmark_codegen_contract"].startswith(
        "profile.bench:v1;"
    )
    assert [decision["stable_id"] for decision in descriptor["decisions"]] == [
        candidate_set["stable_id"] for candidate_set in manifest["candidate_sets"]
    ]
    supported = descriptor["decisions"][0]
    assert supported["status"] == "supported"
    assert [candidate["id"] for candidate in supported["candidates"]] == [
        "default",
        "generic_fallback",
    ]
    assert [mapping["candidate"] for mapping in supported["mappings"]] == [
        "default",
        "generic_fallback",
    ]
    assert all(set(mapping) == {"candidate"} for mapping in supported["mappings"])
    assert all(
        decision["status"] == "report_only" and not decision["mappings"]
        for decision in descriptor["decisions"][1:]
    )

    profile_source = artifacts["rust/src/tsl_sse2.rs"]
    assert (
        'include!(concat!(env!("OUT_DIR"), "/tsl_variant_policy_sse2.rs"));'
        in profile_source
    )
    assert "tsl_rust_variant_policy_sse2" not in profile_source
    assert "TSL_RUST_VARIANT_POLICY_MAPPING_SSE2" not in profile_source
    build_script = artifacts["rust/build.rs"]
    assert "cargo:rerun-if-env-changed={POLICY_ENVIRONMENT}" in build_script
    assert "TSL_RUST_VARIANT_POLICY_FILE" in build_script
    assert 'descriptor_relative_path: "bench/policy_consumption_sse2.json"' in (
        build_script
    )
    assert 'descriptor: include_str!("bench/policy_consumption_sse2.json")' in (
        build_script
    )
    assert '#[path = "bench/policy_consumption_sse2.rs"]' in build_script
    assert "mappings: tsl_rust_policy_data_sse2::MAPPINGS" in build_script
    assert 'materialized_mapping_file: "tsl_variant_policy_sse2.rs"' in (
        build_script
    )
    assert "materialize_default_mapping(" in build_script
    mapping_data = artifacts["rust/bench/policy_consumption_sse2.rs"]
    assert "sse2_mul_sse_si8_" in mapping_data
    assert "Mul_defaultImpl" in mapping_data
    assert "Mul_generic_fallbackImpl" in mapping_data
    assert "consume_policy(" in build_script
    assert "Command::new" in build_script
    assert '"CARGO",' in build_script
    for flag in RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags:
        assert json.dumps(flag) in build_script
    assert "std::env::vars()" in build_script
    assert ".tsl-rust-context-revalidate-always-missing" in build_script

    protocol_source = artifacts["rust/tsl_rust_variant_policy_protocol.rs"]
    assert "const DESCRIPTOR_SCHEMA_VERSION: u64 = 1;" in protocol_source
    assert "const POLICY_SCHEMA_VERSION: u64 = 2;" in protocol_source
    assert "const BENCHMARK_PROTOCOL_VERSION: u64 = 1;" in protocol_source
    assert "cargo bench" not in build_script


def _mapping_source(selection: RustPolicySelection) -> str:
    return f"mapping:{selection.selected_candidate}"


_CONSUMER_SOURCE = textwrap.dedent(
    """
    use tsl::primitive::Mul;
    use tsl::profile::{from_array, mul, to_array, Profile, Sse};
    use tsl::tsl_core::{ImplementationStateOf, Simd, SimdVector};

    type Vec = Simd<i8, Sse>;

    #[no_mangle]
    #[inline(never)]
    pub fn ordinary_mul(
        left: <Vec as SimdVector>::RegisterType,
        right: <Vec as SimdVector>::RegisterType,
    ) -> <Vec as SimdVector>::RegisterType {
        mul::<Vec>(left, right)
    }

    fn main() {
        let mut left: <Vec as SimdVector>::Array = Default::default();
        let mut right: <Vec as SimdVector>::Array = Default::default();
        for lane in 0..16 {
            left[lane] = (lane + 1) as i8;
            right[lane] = (lane + 1) as i8;
        }
        let actual = to_array::<Vec>(ordinary_mul(
            from_array::<Vec>(&left),
            from_array::<Vec>(&right),
        ));
        for lane in 0..16 {
            assert_eq!(actual[lane], left[lane].wrapping_mul(right[lane]));
        }
        println!(
            "{:?}",
            <Profile as ImplementationStateOf<Mul, Vec>>::VALUE,
        );
    }
    """
).lstrip()


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_environment = os.environ.copy()
    if environment is not None:
        for name, value in environment.items():
            if value is None:
                process_environment.pop(name, None)
            else:
                process_environment[name] = value
    return subprocess.run(
        command,
        cwd=cwd,
        env=process_environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _clean_rust_environment(**values: str | None) -> dict[str, str | None]:
    cleared = {
        "CARGO_BUILD_INCREMENTAL",
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_BUILD_TARGET",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_INCREMENTAL",
        "CARGO_TARGET_DIR",
        "RUSTC",
        "RUSTC_LINKER",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTFLAGS",
        "TSL_RUST_VARIANT_POLICY_MAPPING_SSE2",
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
    return {**{name: None for name in cleared}, **values}


def _policy_codegen_environment(
    **values: str | None,
) -> dict[str, str | None]:
    return _clean_rust_environment(
        RUSTFLAGS=" ".join(RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags),
        CARGO_INCREMENTAL="0",
        **values,
    )


def _source_hashes(crate: Path) -> dict[str, str]:
    return {
        str(path.relative_to(crate)): sha256(path.read_bytes()).hexdigest()
        for path in sorted((crate / "src").glob("*.rs"))
    }


def _force_mul_candidate(
    policy: dict[str, object],
    candidate: str,
) -> None:
    tune_context = policy["tune_context"]
    assert isinstance(tune_context, dict)
    threshold = float(tune_context["threshold"])
    decisions = policy["decisions"]
    assert isinstance(decisions, list)
    matching = [
        decision
        for decision in decisions
        if isinstance(decision, dict)
        and str(decision["stable_id"]).startswith("sse2_mul_sse_si8_")
    ]
    assert len(matching) == 1
    decision = matching[0]
    decision["selected"] = candidate
    decision["status"] = "inconclusive" if candidate == "default" else "selected"
    decision["minimum_improvement"] = (
        0.0 if candidate == "default" else max(threshold, 0.1)
    )


def _write_policy(path: Path, policy: dict[str, object]) -> None:
    path.write_text(
        json.dumps(policy, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


@pytest.mark.generated_build
def test_generated_rust_policy_is_applied_fail_closed_and_invalidated(
    rust_policy_project: GenerationResult,
    tmp_path: Path,
) -> None:
    if shutil.which("cargo") is None or shutil.which("rustc") is None:
        pytest.skip("cargo and rustc are required")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("Rust policy consumption currently requires native x86-64")

    generated = tmp_path / "generated"
    report = write_artifacts(rust_policy_project.artifacts, generated)
    assert not has_errors(report.diagnostics), report.diagnostics
    crate = generated / "rust"
    examples = crate / "examples"
    examples.mkdir()
    (examples / "selection_probe.rs").write_text(
        _CONSUMER_SOURCE,
        encoding="utf-8",
    )
    source_hashes = _source_hashes(crate)
    manifest = str(crate / "Cargo.toml")
    cargo_target = generated / "custom-cargo-target"
    workflow_directory = cargo_target / "tsl-benchmark" / "sse2"
    workflow_directory.mkdir(parents=True)
    consumer = (
        "cargo",
        "run",
        "--manifest-path",
        manifest,
        "--profile",
        "bench",
        "--example",
        "selection_probe",
        "--no-default-features",
        "--features",
        "variant_benchmarks,sse2",
    )
    context = "slice5-two-phase-policy-consumer"

    def workflow_environment(**values: str | None) -> dict[str, str | None]:
        return _policy_codegen_environment(
            CARGO_TARGET_DIR=str(cargo_target),
            TSL_RUST_BENCHMARK_CONTEXT=context,
            **values,
        )

    default_environment = _clean_rust_environment(
        CARGO_TARGET_DIR=str(cargo_target),
        TSL_RUST_BENCHMARK_CONTEXT=context,
    )
    guarded_environment = workflow_environment()
    assert guarded_environment["TSL_RUST_VARIANT_POLICY_FILE"] is None

    ordinary = _run(consumer, cwd=crate, environment=default_environment)
    assert ordinary.returncode == 0, ordinary.stderr
    assert ordinary.stdout.strip() == "Fallback"

    forged_mapping = generated / "forged-policy-mapping.rs"
    forged_mapping.write_text(
        'compile_error!("FORGED_POLICY_MAPPING_COMPILED");\n',
        encoding="utf-8",
    )
    bypass_attempt = _run(
        consumer,
        cwd=crate,
        environment=_clean_rust_environment(
            TSL_RUST_BENCHMARK_CONTEXT=context,
            RUSTFLAGS="--cfg tsl_rust_variant_policy_sse2",
            TSL_RUST_VARIANT_POLICY_MAPPING_SSE2=str(forged_mapping),
        ),
    )
    assert bypass_attempt.returncode == 0, bypass_attempt.stderr
    assert bypass_attempt.stdout.strip() == "Fallback"
    assert "FORGED_POLICY_MAPPING_COMPILED" not in bypass_attempt.stderr

    policy_path = workflow_directory / "policy.json"
    samples_path = workflow_directory / "results.jsonl"
    summary_path = workflow_directory / "summary.txt"
    rejected_policy_path = workflow_directory / "rejected-policy.json"
    producer_override = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            "--manifest-path",
            manifest,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
            "--",
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--threshold",
            "0.05",
            "--results",
            str(workflow_directory / "rejected-results.jsonl"),
            "--summary",
            str(workflow_directory / "rejected-summary.txt"),
            "--policy-json",
            str(rejected_policy_path),
        ),
        cwd=crate,
        environment={
            **guarded_environment,
            "CARGO_PROFILE_BENCH_PACKAGE_TSL_INCREMENTAL": "true",
        },
    )
    assert producer_override.returncode != 0
    assert "requires the exact compiler-owned codegen guard" in (
        producer_override.stderr
    )
    assert not rejected_policy_path.exists()

    produced = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            "--manifest-path",
            manifest,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
            "--",
            "--rounds",
            "3",
            "--minimum-sample-ns",
            "1000",
            "--threshold",
            "0.05",
            "--results",
            str(samples_path),
            "--summary",
            str(summary_path),
            "--policy-json",
            str(policy_path),
        ),
        cwd=crate,
        environment=guarded_environment,
    )
    assert produced.returncode == 0, produced.stderr
    assert all(
        path.is_file() and path.is_relative_to(cargo_target)
        for path in (samples_path, summary_path, policy_path)
    )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    _force_mul_candidate(policy, "generic_fallback")
    _write_policy(policy_path, policy)
    policy_environment = workflow_environment(
        TSL_RUST_VARIANT_POLICY_FILE=str(policy_path),
    )

    forced = _run(consumer, cwd=crate, environment=policy_environment)
    assert forced.returncode == 0, forced.stderr
    assert forced.stdout.strip() == "Composed"

    configured = _run(
        (
            *consumer[:2],
            "--verbose",
            "--verbose",
            "--config",
            "profile.bench.codegen-units=8",
            "--config",
            "profile.bench.lto=true",
            "--config",
            "profile.bench.incremental=true",
            *consumer[2:],
        ),
        cwd=crate,
        environment={
            **policy_environment,
            "CARGO_TARGET_DIR": str(generated / "hostile-profile-target"),
        },
    )
    assert configured.returncode == 0, configured.stderr
    assert configured.stdout.splitlines()[-1] == "Composed"
    rustc_commands = [
        line
        for line in configured.stderr.splitlines()
        if "Running `" in line and "--crate-name tsl " in line
    ]
    assert rustc_commands
    rustc_command = rustc_commands[-1]
    for hostile, guarded in (
        ("-C codegen-units=8", "-Ccodegen-units=1"),
        ("-C linker-plugin-lto", "-Clinker-plugin-lto=no"),
    ):
        assert hostile in rustc_command
        assert rustc_command.rfind(guarded) > rustc_command.rfind(hostile)
    assert _source_hashes(crate) == source_hashes
    mappings = tuple(
        cargo_target.glob(
            "release/build/tsl-*/out/tsl_variant_policy_sse2.rs"
        )
    )
    assert mappings
    selected_mapping = max(mappings, key=lambda path: path.stat().st_mtime_ns)
    mapping_source = selected_mapping.read_text(encoding="utf-8")
    assert "Mul_generic_fallbackImpl" in mapping_source
    assert "Mul_defaultImpl" not in mapping_source
    assert not tuple((crate / "src").glob("*variant_policy*"))

    assembly = _run(
        (
            "cargo",
            "rustc",
            "--manifest-path",
            manifest,
            "--profile",
            "bench",
            "--example",
            "selection_probe",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
            "--",
            "--emit=asm",
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert assembly.returncode == 0, assembly.stderr
    assembly_files = sorted(
        (cargo_target / "release" / "examples").glob("selection_probe-*.s"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    assert assembly_files
    assembly_text = "\n".join(
        path.read_text(encoding="utf-8") for path in assembly_files
    )
    start = assembly_text.index("ordinary_mul:")
    optimized = assembly_text[start : assembly_text.index(".Lfunc_end", start)]
    assert "Mul_generic_fallbackImpl" in optimized
    assert "Mul_defaultImpl" not in optimized
    assert "primitives..MulImpl$GT$5apply" not in optimized
    assert not re.search(r"(?m)^\s*j[a-z]+\s", optimized)

    _force_mul_candidate(policy, "default")
    _write_policy(policy_path, policy)
    restored = _run(consumer, cwd=crate, environment=policy_environment)
    assert restored.returncode == 0, restored.stderr
    assert restored.stdout.strip() == "Fallback"

    invalid_cases: list[tuple[str, dict[str, object], str]] = []

    wrong_backend = deepcopy(policy)
    wrong_backend["backend"] = "cpp"
    invalid_cases.append(("wrong-backend", wrong_backend, "foreign backend"))

    wrong_profile = deepcopy(policy)
    wrong_profile["profile"] = "avx2"
    invalid_cases.append(("wrong-profile", wrong_profile, "foreign backend"))

    wrong_context = deepcopy(policy)
    wrong_context_tune = wrong_context["tune_context"]
    assert isinstance(wrong_context_tune, dict)
    wrong_context_tune["rustc_verbose_version"] = "foreign rustc"
    invalid_cases.append(("wrong-rustc", wrong_context, "differs from the consumer"))

    wrong_cargo = deepcopy(policy)
    wrong_cargo_tune = wrong_cargo["tune_context"]
    assert isinstance(wrong_cargo_tune, dict)
    wrong_cargo_tune["cargo_verbose_version"] = "foreign cargo"
    invalid_cases.append(("wrong-cargo", wrong_cargo, "differs from the consumer"))

    wrong_cpu = deepcopy(policy)
    cpu_fields = str(wrong_cpu["cpu_id"]).split(":")
    assert len(cpu_fields) == 5
    cpu_fields[-1] = str(int(cpu_fields[-1]) + 1)
    wrong_cpu["cpu_id"] = ":".join(cpu_fields)
    invalid_cases.append(("wrong-cpu", wrong_cpu, "different native CPU"))

    stale_inventory = deepcopy(policy)
    stale_inventory["manifest_hash"] = "0" * 64
    invalid_cases.append(
        ("stale-body-inventory", stale_inventory, "stale manifest/body inventory")
    )

    partial = deepcopy(policy)
    partial_decisions = partial["decisions"]
    assert isinstance(partial_decisions, list)
    partial["decisions"] = partial_decisions[:-1]
    invalid_cases.append(("partial", partial, "missing or unexpected decisions"))

    duplicate = deepcopy(policy)
    duplicate_decisions = duplicate["decisions"]
    assert isinstance(duplicate_decisions, list) and len(duplicate_decisions) > 1
    duplicate_decisions[-1] = deepcopy(duplicate_decisions[0])
    invalid_cases.append(("duplicate", duplicate, "duplicate, missing, or reordered"))

    unsupported = deepcopy(policy)
    unsupported_decisions = unsupported["decisions"]
    assert isinstance(unsupported_decisions, list)
    report_only = next(
        decision
        for decision in unsupported_decisions
        if isinstance(decision, dict) and decision["status"] == "report_only"
    )
    report_only["selected"] = "generic_fallback"
    report_only["status"] = "selected"
    report_only["minimum_improvement"] = 0.1
    invalid_cases.append(
        ("report-only", unsupported, "attempts to select report-only decision")
    )

    for label, invalid_policy, expected_error in invalid_cases:
        _write_policy(policy_path, invalid_policy)
        rejected = _run(consumer, cwd=crate, environment=policy_environment)
        assert rejected.returncode != 0, label
        assert "Rust variant policy validation failed" in rejected.stderr, label
        assert expected_error in rejected.stderr, label

    _write_policy(policy_path, policy)
    newline_path = _run(
        consumer,
        cwd=crate,
        environment=workflow_environment(
            TSL_RUST_VARIANT_POLICY_FILE=(
                f"{policy_path}\ncargo:rustc-cfg=tsl_injected"
            ),
        ),
    )
    assert newline_path.returncode != 0
    assert "path cannot contain line breaks in a Cargo directive" in (
        newline_path.stderr
    )

    first_revalidation = _run(consumer, cwd=crate, environment=policy_environment)
    second_revalidation = _run(consumer, cwd=crate, environment=policy_environment)
    assert first_revalidation.returncode == 0, first_revalidation.stderr
    assert second_revalidation.returncode == 0, second_revalidation.stderr
    assert "Compiling tsl" in second_revalidation.stderr

    bench_override = _run(
        (
            "cargo",
            "check",
            "--manifest-path",
            manifest,
            "--profile",
            "bench",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
        ),
        cwd=crate,
        environment={
            **policy_environment,
            "CARGO_PROFILE_BENCH_CODEGEN_UNITS": "1",
        },
    )
    assert bench_override.returncode != 0
    assert "lacks the exact compiler-owned codegen guard" in bench_override.stderr

    package_override = _run(
        (
            "cargo",
            "check",
            "--manifest-path",
            manifest,
            "--profile",
            "bench",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
        ),
        cwd=crate,
        environment={
            **policy_environment,
            "CARGO_PROFILE_BENCH_PACKAGE_TSL_INCREMENTAL": "true",
        },
    )
    assert package_override.returncode != 0
    assert "lacks the exact compiler-owned codegen guard" in package_override.stderr

    benchmark_with_policy = _run(
        (
            "cargo",
            "bench",
            "--profile",
            "bench",
            "--manifest-path",
            manifest,
            "--bench",
            "tsl_variant_bench_sse2",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
            "--no-run",
        ),
        cwd=crate,
        environment=policy_environment,
    )
    assert benchmark_with_policy.returncode != 0
    assert "must be unset for benchmark targets" in (
        benchmark_with_policy.stderr
    )

    policy_path.unlink()
    missing = _run(consumer, cwd=crate, environment=policy_environment)
    assert missing.returncode != 0
    assert "Rust variant policy validation failed" in missing.stderr
    assert "cannot inspect Rust variant policy" in missing.stderr

    unset = _run(consumer, cwd=crate, environment=default_environment)
    assert unset.returncode == 0, unset.stderr
    assert unset.stdout.strip() == "Fallback"
    assert _source_hashes(crate) == source_hashes

    (examples / "invalid_probe.rs").write_text(
        'compile_error!("POLICY_VALIDATION_REACHED_CONSUMER");\nfn main() {}\n',
        encoding="utf-8",
    )
    invalid_command = (
        "cargo",
        "check",
        "--manifest-path",
        manifest,
        "--profile",
        "bench",
        "--example",
        "invalid_probe",
        "--no-default-features",
        "--features",
        "variant_benchmarks,sse2",
    )
    _force_mul_candidate(policy, "generic_fallback")

    invalid_documents: list[tuple[str, dict[str, object], str]] = []

    def changed(label: str) -> dict[str, object]:
        document = json.loads(json.dumps(policy))
        invalid_documents.append((label, document, "Rust variant policy validation failed"))
        return document

    changed("schema")["schema_version"] = 3
    changed("protocol")["protocol_version"] = 2
    changed("backend")["backend"] = "cpp"
    changed("profile")["profile"] = "scalar"
    changed("manifest")["manifest_hash"] = "0" * 64
    changed("cpu")["cpu_id"] = "x86:WrongVendor0:6:1:1"
    changed("unknown-field")["unknown"] = True

    wrong_rustc = changed("rustc")
    assert isinstance(wrong_rustc["tune_context"], dict)
    wrong_rustc["tune_context"]["rustc_verbose_version"] = "rustc foreign"

    wrong_cargo = changed("cargo")
    assert isinstance(wrong_cargo["tune_context"], dict)
    wrong_cargo["tune_context"]["cargo_verbose_version"] = "cargo foreign"

    wrong_context = changed("external-context")
    assert isinstance(wrong_context["tune_context"], dict)
    wrong_context["tune_context"]["external_context"] = "foreign-context"

    wrong_features = changed("producer-features")
    assert isinstance(wrong_features["tune_context"], dict)
    wrong_features["tune_context"]["cargo_features"] = "CARGO_FEATURE_SSE2=1"

    partial = changed("partial")
    assert isinstance(partial["decisions"], list)
    partial["decisions"].pop()

    duplicate = changed("duplicate")
    assert isinstance(duplicate["decisions"], list)
    duplicate["decisions"][1] = json.loads(
        json.dumps(duplicate["decisions"][0])
    )

    report_only = changed("report-only-alternative")
    assert isinstance(report_only["decisions"], list)
    assert isinstance(report_only["decisions"][1], dict)
    report_only["decisions"][1].update(
        {
            "selected": "generic_fallback",
            "status": "selected",
            "minimum_improvement": 0.1,
        }
    )

    unavailable = changed("unavailable-candidate")
    assert isinstance(unavailable["decisions"], list)
    assert isinstance(unavailable["decisions"][0], dict)
    unavailable["decisions"][0]["selected"] = "policy_supplied_rust_source"

    stale_scenarios = changed("scenario-settings")
    assert isinstance(stale_scenarios["tune_context"], dict)
    assert isinstance(stale_scenarios["tune_context"]["scenario_settings"], list)
    stale_scenarios["tune_context"]["scenario_settings"].pop()

    for label, document, expected in invalid_documents:
        invalid_path = generated / f"invalid-{label}.json"
        _write_policy(invalid_path, document)
        completed = _run(
            invalid_command,
            cwd=crate,
            environment=workflow_environment(
                TSL_RUST_VARIANT_POLICY_FILE=str(invalid_path),
            ),
        )
        assert completed.returncode != 0, label
        assert expected in completed.stderr, (label, completed.stderr)
        assert "POLICY_VALIDATION_REACHED_CONSUMER" not in completed.stderr

    raw_invalid = {
        "malformed": "{",
        "duplicate-key": json.dumps(policy).replace(
            "{", '{"backend":"rust",', 1
        ),
        "overflow-float": json.dumps(policy).replace(
            '"minimum_improvement": 0.1',
            '"minimum_improvement": 1e400',
            1,
        ),
    }
    for label, content in raw_invalid.items():
        invalid_path = generated / f"invalid-{label}.json"
        invalid_path.write_text(content, encoding="utf-8")
        completed = _run(
            invalid_command,
            cwd=crate,
            environment=workflow_environment(
                TSL_RUST_VARIANT_POLICY_FILE=str(invalid_path),
            ),
        )
        assert completed.returncode != 0, label
        assert "Rust variant policy validation failed" in completed.stderr
        assert "POLICY_VALIDATION_REACHED_CONSUMER" not in completed.stderr

    missing_path = generated / "never-created-policy.json"
    missing_policy = _run(
        invalid_command,
        cwd=crate,
        environment=workflow_environment(
            TSL_RUST_VARIANT_POLICY_FILE=str(missing_path),
        ),
    )
    assert missing_policy.returncode != 0
    assert "cannot inspect Rust variant policy" in missing_policy.stderr
    assert "POLICY_VALIDATION_REACHED_CONSUMER" not in missing_policy.stderr

    empty_policy = _run(
        invalid_command,
        cwd=crate,
        environment=workflow_environment(
            TSL_RUST_VARIANT_POLICY_FILE="",
        ),
    )
    assert empty_policy.returncode != 0
    assert "present but empty" in empty_policy.stderr
    assert "POLICY_VALIDATION_REACHED_CONSUMER" not in empty_policy.stderr

    valid_path = generated / "valid-policy.json"
    _write_policy(valid_path, policy)
    valid_environment = workflow_environment(
        TSL_RUST_VARIANT_POLICY_FILE=str(valid_path),
    )
    extra_feature = _run(
        (*invalid_command[:-1], "variant_benchmarks,sse2,value_tests"),
        cwd=crate,
        environment=valid_environment,
    )
    assert extra_feature.returncode != 0
    assert "Cargo features do not match" in extra_feature.stderr
    assert "POLICY_VALIDATION_REACHED_CONSUMER" not in extra_feature.stderr

    no_profile = _run(
        invalid_command[:-2],
        cwd=crate,
        environment=valid_environment,
    )
    assert no_profile.returncode != 0
    assert "exactly one generated profile feature" in no_profile.stderr
    assert "POLICY_VALIDATION_REACHED_CONSUMER" not in no_profile.stderr

    policy_feature_build = _run(
        (
            "cargo",
            "check",
            "--manifest-path",
            manifest,
            "--profile",
            "bench",
            "--no-default-features",
            "--features",
            "variant_benchmarks,sse2",
        ),
        cwd=crate,
        environment=valid_environment,
    )
    assert policy_feature_build.returncode == 0, policy_feature_build.stderr

    canonical_flags = RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags
    for label, changed_environment in (
        (
            "missing-flag",
            {"RUSTFLAGS": " ".join(canonical_flags[:-1])},
        ),
        (
            "reordered-flags",
            {
                "RUSTFLAGS": " ".join(
                    (canonical_flags[1], canonical_flags[0], *canonical_flags[2:])
                )
            },
        ),
        (
            "extra-flag",
            {"RUSTFLAGS": " ".join((*canonical_flags, "-Ctarget-cpu=native"))},
        ),
        ("incremental", {"CARGO_INCREMENTAL": "1"}),
    ):
        changed_guard = _run(
            invalid_command,
            cwd=crate,
            environment={**valid_environment, **changed_environment},
        )
        assert changed_guard.returncode != 0, label
        assert "lacks the exact compiler-owned codegen guard" in (
            changed_guard.stderr
        ), label
        assert "POLICY_VALIDATION_REACHED_CONSUMER" not in changed_guard.stderr

    if os.name != "nt":
        symlink = generated / "policy-link.json"
        symlink.symlink_to(valid_path)
        linked = _run(
            invalid_command,
            cwd=crate,
            environment=workflow_environment(
                TSL_RUST_VARIANT_POLICY_FILE=str(symlink),
            ),
        )
        assert linked.returncode != 0
        assert "non-symlink regular file" in linked.stderr
        assert "POLICY_VALIDATION_REACHED_CONSUMER" not in linked.stderr
