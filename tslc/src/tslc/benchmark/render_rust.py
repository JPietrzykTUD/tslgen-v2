"""Render Rust benchmark reports and backend-scoped policy production."""

from __future__ import annotations

import json

from tslc.backend.rust_benchmark_context import RUST_BENCHMARK_CODEGEN_CONTRACT
from tslc.backend.rust_policy_selection import (
    RustPolicySelectionPlan,
    RustPolicySelectionProfile,
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
from tslc.render._common import slug, text

RUST_BENCHMARK_POLICY_SCHEMA_VERSION = 1


def rust_benchmark_artifacts(
    plan: BenchmarkProjectPlan,
    assets: RenderAssets,
    media_type: str,
    *,
    selection_plan: RustPolicySelectionPlan,
) -> list[Artifact]:
    profiles = plan.profiles_for("rust")
    if not profiles:
        return []
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
        policy_selection = selection_plan.profile(profile.profile_name)
        if policy_selection is None:
            raise ValueError(
                "Rust benchmark rendering requires complete policy-selection profiles"
            )
        profile_slug = slug(profile.profile_name)
        artifacts.extend(
            (
                text(
                    f"rust/src/tsl_variant_bench_{profile_slug}.rs",
                    _render_source(profile, policy_selection, assets),
                    media_type=media_type,
                ),
                text(
                    f"rust/bench/manifest_{profile_slug}.json",
                    _render_manifest(profile),
                    media_type="application/json",
                ),
            )
        )
    return artifacts


def _render_source(
    profile: BenchmarkProfilePlan,
    policy_selection: RustPolicySelectionProfile,
    assets: RenderAssets,
) -> str:
    profile_slug = slug(profile.profile_name)
    profile_module = f"tsl_{profile_slug}"
    declarations = "\n\n".join(
        render_candidate_set(
            index,
            candidate_set,
            profile_module=profile_module,
            policy_selection=policy_selection,
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
    selected_keys = {selection.key for selection in policy_selection.selections}
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
        profile_slug=profile_slug,
        protocol_version=str(BENCHMARK_PROTOCOL_VERSION),
        policy_schema_version=str(RUST_BENCHMARK_POLICY_SCHEMA_VERSION),
        profile_name=_rust_profile_literal(profile.profile_name),
        manifest_hash=rust_string_literal(profile.manifest_hash),
        required_features=rust_string_literal(required_features),
        benchmark_codegen_contract=rust_string_literal(
            RUST_BENCHMARK_CODEGEN_CONTRACT.identity
        ),
        native_cpu_check=_render_native_cpu_check(profile),
        declarations=declarations,
        candidate_set_count=str(len(profile.candidate_sets)),
        candidate_set_specs=candidate_set_specs,
        correctness_calls=correctness_calls,
        scenario_calls=scenario_calls,
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


__all__ = ("RUST_BENCHMARK_POLICY_SCHEMA_VERSION", "rust_benchmark_artifacts")
