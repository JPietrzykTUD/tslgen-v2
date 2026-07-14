"""Render standalone C++ benchmark and policy tools from typed benchmark plans."""

from __future__ import annotations

import json

from tslc.backend.cpp import (
    variant_enum_name,
    variant_selector_name,
)
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkImmediateScenario,
    BenchmarkIndexedLoadScenario,
    BenchmarkMaskDensityScenario,
    BenchmarkMaskResultScenario,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkVectorScalarScenario,
)
from tslc.benchmark.planner import BENCHMARK_PROTOCOL_VERSION
from tslc.benchmark.render_cpp_candidate import (
    index_vector_type,
    render_candidate_set,
    vector_type,
)
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.render._common import slug, text


def cpp_benchmark_artifacts(
    plan: BenchmarkProjectPlan,
    assets: RenderAssets,
    media_type: str,
) -> list[Artifact]:
    profiles = plan.profiles_for("cpp")
    if not profiles:
        return []
    artifacts = [
        text(
            "cpp/include/tsl_benchmark_core.hpp",
            assets.text("tsl_benchmark_core.hpp"),
            media_type=media_type,
        ),
        text(
            "cpp/bench/coverage.json",
            _render_coverage(plan),
            media_type="application/json",
        ),
    ]
    for profile in profiles:
        profile_slug = slug(profile.profile_name)
        artifacts.extend(
            (
                text(
                    f"cpp/bench/tsl_variant_bench_{profile_slug}.cpp",
                    _render_source(profile, assets),
                    media_type=media_type,
                ),
                text(
                    f"cpp/bench/manifest_{profile_slug}.json",
                    _render_manifest(profile),
                    media_type="application/json",
                ),
            )
        )
    return artifacts


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
            if entry.backend_id == "cpp"
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
                    {
                        "id": candidate.variant_id,
                        "body_hash": candidate.body_hash,
                    }
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


def _scenario_manifest(
    scenario: (
        BenchmarkRegisterScenario
        | BenchmarkMaskDensityScenario
        | BenchmarkMaskResultScenario
        | BenchmarkReductionScenario
        | BenchmarkVectorScalarScenario
        | BenchmarkImmediateScenario
        | BenchmarkIndexedLoadScenario
    ),
) -> dict[str, object]:
    timing = scenario.timing
    payload: dict[str, object] = {
        "id": scenario.scenario_id,
        "kind": scenario.kind,
        "seed": timing.seed,
        "batch_size": timing.batch_size,
        "rounds": timing.rounds,
        "minimum_sample_ns": timing.minimum_sample_ns,
    }
    if isinstance(scenario, BenchmarkRegisterScenario):
        payload.update(
            {
                "family": "register",
                "operand_generators": scenario.operand_generators,
                "dependency_parameter": scenario.dependency_parameter,
            }
        )
    elif isinstance(scenario, BenchmarkImmediateScenario):
        payload.update(
            {
                "family": "immediate",
                "operand_generator": scenario.operand_generator,
                "dependency_parameter": scenario.dependency_parameter,
            }
        )
    elif isinstance(scenario, BenchmarkIndexedLoadScenario):
        payload.update(
            {
                "family": "indexed_load",
                "memory_bytes": scenario.memory_bytes,
                "index_lanes": scenario.index_lanes,
            }
        )
    elif isinstance(scenario, BenchmarkVectorScalarScenario):
        payload.update(
            {
                "family": "vector_scalar",
                "vector_generator": scenario.vector_generator,
                "scalar_generator": scenario.scalar_generator,
                "dependency_parameter": scenario.dependency_parameter,
            }
        )
    elif isinstance(scenario, BenchmarkMaskResultScenario):
        payload.update(
            {
                "family": "mask_result",
                "operand_generators": scenario.operand_generators,
            }
        )
    elif isinstance(scenario, BenchmarkMaskDensityScenario):
        payload.update(
            {
                "family": "mask_density",
                "parameter_index": scenario.parameter_index,
                "active_lanes": scenario.active_lanes,
            }
        )
    else:
        payload.update(
            {
                "family": "reduction",
                "operand_generator": scenario.operand_generator,
            }
        )
    return payload


def _render_source(profile: BenchmarkProfilePlan, assets: RenderAssets) -> str:
    declarations = "\n\n".join(
        render_candidate_set(index, candidate_set)
        for index, candidate_set in enumerate(profile.candidate_sets)
    )
    runs = "\n".join(
        f"        if (!benchmark_set_{index}(samples, decisions, options)) return 2;"
        for index, _candidate_set in enumerate(profile.candidate_sets)
    )
    policy_branches = "\n".join(
        _render_policy_branch(candidate_set) for candidate_set in profile.candidate_sets
    )
    decision_reads = "\n".join(
        _render_policy_read(candidate_set) for candidate_set in profile.candidate_sets
    )
    manifest = _cpp_string(profile.manifest_hash)
    # Generated source identifiers/profile labels follow the same sanitized
    # spelling as the rest of the C++ project. The neutral manifest retains the
    # authored profile name.
    profile_name = _cpp_string(slug(profile.profile_name))
    return assets.fill(
        "cpp_benchmark.cpp.tmpl",
        profile_slug=slug(profile.profile_name),
        manifest=manifest,
        profile_name=profile_name,
        protocol_version=str(BENCHMARK_PROTOCOL_VERSION),
        declarations=declarations,
        policy_branches=policy_branches,
        candidate_set_count=str(len(profile.candidate_sets)),
        decision_reads=decision_reads,
        runs=runs,
    )


def _render_policy_branch(candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    vector = vector_type(candidate_set)
    selector_arguments = ", ".join(
        (
            vector,
            *((index_vector_type(candidate_set),) if spec.type_params else ()),
            *((candidate_set.key.immediate,) if candidate_set.key.immediate else ()),
            *(default for _name, _type, default in spec.generic_params),
            *(
                _policy_parameter_type(spec.param_kinds[position], vector)
                for position in candidate_set.key.overload_parameter_positions
            ),
        )
    )
    branches: list[str] = []
    for candidate in candidate_set.candidates[1:]:
        branches.append(
            f'''        if (decision.stable_id == {_cpp_string(candidate_set.stable_id)} &&
            decision.selected == {_cpp_string(candidate.variant_id)}) {{
            output << "template <>\\nstruct {variant_selector_name(spec.primitive_name)}<{selector_arguments}> {{\\n"
                   << "    static constexpr auto value = {variant_enum_name(spec.primitive_name)}::{candidate.variant_id};\\n"
                   << "}};\\n\\n";
            continue;
        }}'''
        )
    return "\n".join(branches)


def _policy_parameter_type(kind: str, vector: str) -> str:
    return {
        "v": f"typename ::tsl::reg_param<{vector}>::type",
        "s": f"typename {vector}::base_type",
        "m": f"typename {vector}::mask_type",
        "im": f"typename {vector}::imask_type",
        "usize": "std::size_t",
        "ptr": f"typename {vector}::base_type*",
        "ptr+": f"typename {vector}::base_type*",
        "cptr": f"typename {vector}::base_type const*",
        "cptr+": f"typename {vector}::base_type const*",
    }[kind]


def _render_policy_read(candidate_set: BenchmarkCandidateSet) -> str:
    candidates = " || ".join(
        f"selected == {_cpp_string(candidate.variant_id)}"
        for candidate in candidate_set.candidates
    )
    stable_id = _cpp_string(candidate_set.stable_id)
    return f'''    {{
        const std::string marker = "\\\"stable_id\\\":\\\"" + std::string({stable_id}) + "\\\"";
        const std::size_t position = document.find(marker);
        if (position == std::string::npos)
            throw std::runtime_error("policy has no decision for " + std::string({stable_id}));
        if (document.find(marker, position + marker.size()) != std::string::npos)
            throw std::runtime_error("policy repeats a decision for " + std::string({stable_id}));
        const std::size_t object_end = document.find('}}', position);
        if (object_end == std::string::npos)
            throw std::runtime_error("policy has an unterminated decision for " + std::string({stable_id}));
        const std::string selected =
            tsl::benchmark::json_string_field(document, "selected", position, object_end);
        if (!({candidates}))
            throw std::runtime_error("policy selects an unavailable candidate for " + std::string({stable_id}));
        decisions.push_back(Decision{{{stable_id}, selected, "validated", 0.0}});
    }}'''


def _cpp_string(value: str) -> str:
    return json.dumps(value)


__all__ = ("cpp_benchmark_artifacts",)
