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
                    _render_source(profile),
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


def _render_source(profile: BenchmarkProfilePlan) -> str:
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
    return f'''#include "tsl_{slug(profile.profile_name)}.hpp"
#include "tsl_benchmark_core.hpp"
#include "tsl_test_core.hpp"

#include <array>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>

#ifndef TSL_BENCHMARK_TUNE_CONTEXT_HASH
#  define TSL_BENCHMARK_TUNE_CONTEXT_HASH "unspecified"
#endif

namespace {{

using tsl::benchmark::Decision;
using tsl::benchmark::RawSample;

constexpr char kManifestHash[] = {manifest};
constexpr char kProfile[] = {profile_name};
constexpr char kTuneContextHash[] = TSL_BENCHMARK_TUNE_CONTEXT_HASH;
constexpr int kProtocolVersion = {BENCHMARK_PROTOCOL_VERSION};

struct Options {{
    std::string results_path;
    std::string policy_json_path;
    std::string policy_header_path;
    std::string render_policy_path;
    double threshold = 0.05;
    std::size_t rounds_override = 0;
    std::uint64_t minimum_sample_ns_override = 0;
    bool self_test = false;
}};

{declarations}

std::string render_policy_header(std::vector<Decision> const& decisions) {{
    std::ostringstream output;
    output << "#pragma once\\n\\nnamespace tsl::detail::variants {{\\n\\n";
    for (auto const& decision : decisions) {{
        if (decision.selected == "default") continue;
{policy_branches}
        throw std::runtime_error("policy contains an unknown specialization or candidate: " +
                                 decision.stable_id + "/" + decision.selected);
    }}
    output << "}}  // namespace tsl::detail::variants\\n";
    return output.str();
}}

std::string render_policy_json(std::vector<Decision> const& decisions) {{
    std::ostringstream output;
    output << R"json({{"schema_version":1,"protocol_version":)json" << kProtocolVersion
           << R"json(,"manifest_hash":")json" << kManifestHash
           << R"json(","tune_context_hash":")json" << kTuneContextHash
           << R"json(","cpu_id":")json" << tsl::benchmark::json_escape(tsl::benchmark::cpu_id())
           << R"json(","decisions":[)json";
    for (std::size_t index = 0; index < decisions.size(); ++index) {{
        if (index != 0) output << ',';
        auto const& decision = decisions[index];
        output << R"json({{"stable_id":")json" << decision.stable_id
               << R"json(","selected":")json" << decision.selected
               << R"json(","status":")json" << decision.status
               << R"json(","minimum_improvement":)json" << std::setprecision(8)
               << decision.minimum_improvement << '}}';
    }}
    output << "]}}\\n";
    return output.str();
}}

std::vector<Decision> read_policy(std::string const& path) {{
    const std::string document = tsl::benchmark::read_file(path);
    if (document.find(R"json("schema_version":1)json") == std::string::npos ||
        tsl::benchmark::json_string_field(document, "manifest_hash") != kManifestHash ||
        tsl::benchmark::json_string_field(document, "tune_context_hash") != kTuneContextHash ||
        tsl::benchmark::json_string_field(document, "cpu_id") != tsl::benchmark::cpu_id()) {{
        throw std::runtime_error(
            "variant policy does not match this manifest, compiler context, and CPU");
    }}
    if (tsl::benchmark::substring_count(document, R"json("stable_id":)json") !=
        {len(profile.candidate_sets)}) {{
        throw std::runtime_error("variant policy has missing or unexpected decisions");
    }}
    std::vector<Decision> decisions;
{decision_reads}
    return decisions;
}}

void write_samples(std::vector<RawSample> const& samples, std::ostream& output) {{
    for (auto const& sample : samples) {{
        output << R"json({{"backend":"cpp","protocol_version":)json" << kProtocolVersion
               << R"json(,"profile":")json" << kProfile
               << R"json(","manifest_hash":")json" << kManifestHash
               << R"json(","tune_context_hash":")json" << kTuneContextHash
               << R"json(","cpu_id":")json" << tsl::benchmark::json_escape(tsl::benchmark::cpu_id())
               << R"json(","stable_id":")json" << sample.stable_id
               << R"json(","scenario":")json" << sample.scenario
               << R"json(","candidate":")json" << sample.candidate
               << R"json(","round":)json" << sample.round
               << R"json(,"iterations":)json" << sample.iterations
               << R"json(,"elapsed_ns":)json" << sample.elapsed << "}}\\n";
    }}
}}

Options parse_options(int argc, char** argv) {{
    Options options;
    for (int index = 1; index < argc; ++index) {{
        const std::string argument = argv[index];
        auto value = [&]() -> std::string {{
            if (++index >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[index];
        }};
        if (argument == "--results") options.results_path = value();
        else if (argument == "--policy-json") options.policy_json_path = value();
        else if (argument == "--policy-header") options.policy_header_path = value();
        else if (argument == "--render-policy") options.render_policy_path = value();
        else if (argument == "--threshold") options.threshold = std::stod(value());
        else if (argument == "--rounds") options.rounds_override = std::stoull(value());
        else if (argument == "--minimum-sample-ns")
            options.minimum_sample_ns_override = std::stoull(value());
        else if (argument == "--self-test") options.self_test = true;
        else throw std::runtime_error("unknown benchmark option: " + argument);
    }}
    if (options.threshold < 0.0 || options.threshold >= 1.0)
        throw std::runtime_error("--threshold must be in [0, 1)");
    if (options.rounds_override != 0 && options.rounds_override < 3)
        throw std::runtime_error("--rounds must be at least 3");
    return options;
}}

}}  // namespace

int main(int argc, char** argv) {{
    try {{
        const Options options = parse_options(argc, argv);
        if (options.self_test) {{
            tsl::benchmark::reducer_self_test();
            return 0;
        }}
        if (!options.render_policy_path.empty()) {{
            if (options.policy_header_path.empty())
                throw std::runtime_error("--render-policy requires --policy-header");
            tsl::benchmark::write_file(
                options.policy_header_path,
                render_policy_header(read_policy(options.render_policy_path)));
            return 0;
        }}
        std::vector<RawSample> samples;
        std::vector<Decision> decisions;
{runs}
        if (options.results_path.empty()) write_samples(samples, std::cout);
        else {{
            std::ofstream output(options.results_path);
            if (!output) throw std::runtime_error("cannot open results output");
            write_samples(samples, output);
        }}
        if (!options.policy_json_path.empty())
            tsl::benchmark::write_file(options.policy_json_path, render_policy_json(decisions));
        if (!options.policy_header_path.empty())
            tsl::benchmark::write_file(options.policy_header_path, render_policy_header(decisions));
        return 0;
    }} catch (std::exception const& error) {{
        std::cerr << "TSL benchmark error: " << error.what() << '\\n';
        return 1;
    }}
}}
'''




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
