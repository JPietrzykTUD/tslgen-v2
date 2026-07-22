"""Render Rust benchmark reports and backend-scoped policy production."""

from __future__ import annotations

import json

from tslc.backend.rust_benchmark_context import (
    RUST_BENCHMARK_CODEGEN_CONTRACT,
    RUST_BENCHMARK_POLICY_SCHEMA_VERSION,
    RUST_POLICY_CONSUMPTION_SCHEMA_VERSION,
)
from tslc.backend.rust_policy_consumption import (
    RustPolicyConsumptionDecision,
    RustPolicyConsumptionProfile,
)
from tslc.benchmark._render_rust_common import rust_string_literal
from tslc.benchmark.model import (
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkScenario,
)
from tslc.benchmark.planner import BENCHMARK_PROTOCOL_VERSION
from tslc.benchmark.render_rust_candidate import render_candidate_set
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.render._common import text
from tslc.render.rust_benchmark_layout import (
    RustBenchmarkLayout,
    RustBenchmarkLayoutPlan,
    plan_rust_benchmark_layout,
)
from tslc.render.rust_policy_consumption import (
    RustPolicyConsumptionRenderPlan,
    RustPolicyConsumptionRenderProfile,
)


def rust_benchmark_artifacts(
    plan: BenchmarkProjectPlan,
    assets: RenderAssets,
    media_type: str,
    *,
    consumption_plan: RustPolicyConsumptionRenderPlan,
    layout_plan: RustBenchmarkLayoutPlan | None = None,
) -> list[Artifact]:
    profiles = plan.profiles_for("rust")
    if not profiles:
        return []
    if layout_plan is None:
        layout_plan = plan_rust_benchmark_layout(
            tuple(profile.profile_name for profile in profiles)
        )
    if any(layout_plan.profile(profile.profile_name) is None for profile in profiles):
        raise ValueError("Rust benchmark layout plan lacks a benchmark profile")
    artifacts = [
        text(
            "rust/src/tsl_benchmark_core.rs",
            assets.text("tsl_benchmark_core.rs"),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_benchmark_reducer.rs",
            assets.text("tsl_benchmark_reducer.rs"),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_benchmark_policy.rs",
            assets.text("tsl_benchmark_policy.rs"),
            media_type=media_type,
        ),
        text(
            "rust/src/tsl_benchmark_self_test.rs",
            assets.text("tsl_benchmark_self_test.rs"),
            media_type=media_type,
        ),
        text(
            "rust/bench/coverage.json",
            _render_coverage(plan),
            media_type="application/json",
        ),
    ]
    for profile in profiles:
        layout = layout_plan.profile(profile.profile_name)
        if layout is None:
            raise ValueError("Rust benchmark rendering requires a layout profile")
        consumption = consumption_plan.profile(profile.profile_name)
        artifacts.extend(
            (
                text(
                    f"rust/src/{layout.benchmark_target}.rs",
                    _render_source(profile, layout, consumption, assets),
                    media_type=media_type,
                ),
                text(
                    f"rust/bench/manifest_{layout.profile_slug}.json",
                    _render_manifest(profile),
                    media_type="application/json",
                ),
            )
        )
        if consumption is not None:
            artifacts.extend(
                (
                    text(
                        f"rust/{consumption.names.descriptor_path}",
                        _render_policy_consumption(consumption.profile),
                        media_type="application/json",
                    ),
                    text(
                        f"rust/{consumption.names.mapping_source_path}",
                        _render_policy_mappings(consumption.profile),
                        media_type=media_type,
                    ),
                )
            )
    return artifacts


def _render_source(
    profile: BenchmarkProfilePlan,
    layout: RustBenchmarkLayout,
    consumption: RustPolicyConsumptionRenderProfile | None,
    assets: RenderAssets,
) -> str:
    profile_module = f"tsl_{layout.profile_slug}"
    selected_keys = {
        decision.key
        for decision in (() if consumption is None else consumption.profile.decisions)
        if decision.status == "supported"
    }
    declarations = "\n\n".join(
        render_candidate_set(
            index,
            candidate_set,
            profile_module=profile_module,
            policy_supported_keys=frozenset(selected_keys),
        )
        for index, candidate_set in enumerate(profile.candidate_sets)
    )
    correctness_calls = "\n".join(
        f"    correct_candidate_set_{index}()?;"
        for index, _candidate_set in enumerate(profile.candidate_sets)
    )
    scenario_calls = "\n".join(
        f"    run_candidate_set_{index}(&options, &mut samples)?;"
        for index, _candidate_set in enumerate(profile.candidate_sets)
    )
    candidate_set_specs = "\n".join(
        "    CandidateSetSpec { "
        f"stable_id: {rust_string_literal(candidate_set.stable_id)}, "
        f"candidates: &CANDIDATES_{index}, scenarios: &SCENARIOS_{index}, "
        f"policy_supported: {str(candidate_set.key in selected_keys).lower()} "
        "},"
        for index, candidate_set in enumerate(profile.candidate_sets)
    )
    required_features = ",".join(profile.backend_feature_spellings)
    return assets.fill(
        "rust_benchmark.rs.tmpl",
        profile_slug=layout.profile_slug,
        protocol_version=str(BENCHMARK_PROTOCOL_VERSION),
        policy_schema_version=str(RUST_BENCHMARK_POLICY_SCHEMA_VERSION),
        profile_name=_rust_profile_literal(profile.profile_name),
        benchmark_target=rust_string_literal(layout.benchmark_target),
        cargo_features=rust_string_literal(layout.cargo_features_argument),
        manifest_hash=rust_string_literal(profile.manifest_hash),
        required_features=rust_string_literal(required_features),
        policy_output_supported=str(consumption is not None).lower(),
        policy_json_help=(
            '    println!("  --policy-json PATH        Write a consumable '
            'context-bound Rust policy");'
            if consumption is not None
            else ""
        ),
        required_policy_rustflags="&["
        + ", ".join(
            rust_string_literal(flag)
            for flag in RUST_BENCHMARK_CODEGEN_CONTRACT.policy_rustflags
        )
        + "]",
        required_policy_incremental_environment=rust_string_literal(
            RUST_BENCHMARK_CODEGEN_CONTRACT.policy_incremental_environment
        ),
        benchmark_codegen_contract=rust_string_literal(
            RUST_BENCHMARK_CODEGEN_CONTRACT.identity
        ),
        native_cpu_check=_render_native_cpu_check(profile),
        declarations=declarations,
        candidate_set_count=str(len(profile.candidate_sets)),
        candidate_set_specs=candidate_set_specs,
        correctness_calls=correctness_calls,
        scenario_calls=scenario_calls,
        policy_help=(
            assets.fill(
                "rust_benchmark_policy_help.rs.tmpl",
                artifact_subdirectory=rust_string_literal(
                    layout.artifact_subdirectory
                ),
                context_example=rust_string_literal(layout.context_example),
            ).rstrip()
            if consumption is not None
            else assets.text("rust_benchmark_report_only_help.rs").rstrip()
        ),
    )


def _render_native_cpu_check(profile: BenchmarkProfilePlan) -> str:
    features = profile.backend_feature_spellings
    if not features:
        return "fn native_cpu_supported() -> bool { true }"
    if profile.profile_family == "x86":
        checks = " && ".join(
            f"std::arch::is_x86_feature_detected!({rust_string_literal(feature)})"
            for feature in features
        )
        return f'''fn native_cpu_supported() -> bool {{
    #[cfg(target_arch = "x86_64")]
    {{
        {checks}
    }}
    #[cfg(not(target_arch = "x86_64"))]
    {{
        false
    }}
}}'''
    return "fn native_cpu_supported() -> bool { false }"


def _rust_profile_literal(profile_name: str) -> str:
    # Profile identity stays canonical at runtime, while punctuation remains
    # escaped in generated Rust source whose identifier-sanitization invariant
    # deliberately rejects raw profile-name hyphens.
    return rust_string_literal(profile_name).replace("-", r"\u{2d}")


def _render_coverage(plan: BenchmarkProjectPlan) -> str:
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "backend": entry.backend_id,
                "profile": entry.profile_name,
                "primitive": entry.primitive_name,
                "source_primitive": entry.source_primitive_name,
                "extension": entry.extension_name,
                "type": entry.type_tag,
                "result_kind": entry.result_kind,
                "param_kinds": entry.param_kinds,
                "mask_policy": entry.mask_policy,
                "axis": dict(entry.axis),
                "variants": entry.variant_names,
                "status": entry.status,
                "reason": entry.reason,
            }
            for entry in plan.coverage
            if entry.backend_id == "rust"
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_manifest(profile: BenchmarkProfilePlan) -> str:
    payload = {
        "schema_version": 1,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "backend": profile.backend_id,
        "profile": profile.profile_name,
        "manifest_hash": profile.manifest_hash,
        "candidate_sets": [
            {
                "stable_id": candidate_set.stable_id,
                "key": {
                    "primitive": candidate_set.key.primitive_name,
                    "source_primitive": candidate_set.key.source_primitive_name,
                    "extension": candidate_set.key.extension_name,
                    "type": candidate_set.key.type_tag,
                    "lanes": candidate_set.key.lanes,
                    "immediate": candidate_set.key.immediate,
                    "simd_type_base_bindings": dict(
                        candidate_set.key.simd_type_base_bindings
                    ),
                },
                "candidates": [
                    {"id": candidate.variant_id, "body_hash": candidate.body_hash}
                    for candidate in candidate_set.candidates
                ],
                "scenarios": [
                    _scenario_manifest(scenario)
                    for scenario in candidate_set.scenarios
                ],
            }
            for candidate_set in profile.candidate_sets
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_policy_consumption(joined: RustPolicyConsumptionProfile) -> str:
    payload = {
        "schema_version": RUST_POLICY_CONSUMPTION_SCHEMA_VERSION,
        "policy_schema_version": RUST_BENCHMARK_POLICY_SCHEMA_VERSION,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "backend": joined.backend_id,
        "profile": joined.profile_name,
        "profile_family": joined.profile_family,
        "manifest_hash": joined.manifest_hash,
        "required_features": list(joined.required_features),
        "benchmark_codegen_contract": RUST_BENCHMARK_CODEGEN_CONTRACT.identity,
        "decisions": [
            _policy_consumption_decision(decision)
            for decision in joined.decisions
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_policy_mappings(joined: RustPolicyConsumptionProfile) -> str:
    entries = "\n".join(
        "\n".join(
            (
                "    crate::tsl_rust_variant_policy::GeneratedMapping {",
                f"        stable_id: {rust_string_literal(decision.stable_id)},",
                f"        candidate: {rust_string_literal(mapping.candidate_id)},",
                f"        source: {rust_string_literal(mapping.source)},",
                "    },",
            )
        )
        for decision in joined.decisions
        for mapping in decision.mapping_choices
    )
    return (
        "//! Compiler-rendered Rust variant mappings joined to benchmark identity.\n\n"
        "pub const MAPPINGS: &[crate::tsl_rust_variant_policy::GeneratedMapping] = &[\n"
        f"{entries}\n"
        "];\n"
    )


def _policy_consumption_decision(
    decision: RustPolicyConsumptionDecision,
) -> dict[str, object]:
    # Keep JSON projection local; the typed join above owns every semantic fact.
    return {
        "stable_id": decision.stable_id,
        "status": decision.status,
        "reason": decision.reason,
        "candidates": [
            {"id": candidate.candidate_id, "body_hash": candidate.body_hash}
            for candidate in decision.candidates
        ],
        "scenarios": [
            {
                "id": scenario.scenario_id,
                "family": scenario.family,
                "kind": scenario.kind,
                "seed": scenario.timing.seed,
                "batch_size": scenario.timing.batch_size,
                "rounds": scenario.timing.rounds,
                "minimum_sample_ns": scenario.timing.minimum_sample_ns,
            }
            for scenario in decision.scenarios
        ],
        "specialization_required_features": list(
            decision.specialization_required_features
        ),
        "mappings": [
            {"candidate": mapping.candidate_id}
            for mapping in decision.mapping_choices
        ],
    }


def _scenario_manifest(scenario: BenchmarkScenario) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": scenario.scenario_id,
        "kind": scenario.kind,
        "seed": scenario.timing.seed,
        "batch_size": scenario.timing.batch_size,
        "rounds": scenario.timing.rounds,
        "minimum_sample_ns": scenario.timing.minimum_sample_ns,
    }
    payload.update(scenario.manifest_fields())
    return payload


__all__ = (
    "RUST_BENCHMARK_POLICY_SCHEMA_VERSION",
    "RUST_POLICY_CONSUMPTION_SCHEMA_VERSION",
    "rust_benchmark_artifacts",
)
