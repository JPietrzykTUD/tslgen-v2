"""Render standalone C++ benchmark and policy tools from typed benchmark plans."""

from __future__ import annotations

import json

from tslc.backend.cpp import (
    implementation_name,
    variant_enum_name,
    variant_selector_name,
)
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkProfilePlan,
    BenchmarkProjectPlan,
)
from tslc.benchmark.planner import BENCHMARK_PROTOCOL_VERSION
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact
from tslc.render._common import slug, text
from tslc.value_tests.literals import cpp_literal_list


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
                "extension": entry.extension_name,
                "type": entry.type_tag,
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
                },
                "candidates": [
                    {
                        "id": candidate.variant_id,
                        "body_hash": candidate.body_hash,
                    }
                    for candidate in candidate_set.candidates
                ],
                "scenarios": [
                    {
                        "id": scenario.scenario_id,
                        "kind": scenario.kind,
                        "seed": scenario.seed,
                        "batch_size": scenario.batch_size,
                        "rounds": scenario.rounds,
                        "minimum_sample_ns": scenario.minimum_sample_ns,
                    }
                    for scenario in candidate_set.scenarios
                ],
            }
            for candidate_set in profile.candidate_sets
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_source(profile: BenchmarkProfilePlan) -> str:
    declarations = "\n\n".join(
        _render_candidate_set(index, candidate_set)
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


def _render_candidate_set(index: int, candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    vector_type = _vector_type(candidate_set)
    inputs = len(spec.param_kinds)
    batch_size = candidate_set.scenarios[0].batch_size
    invoke = _render_invoke(index, candidate_set)
    correctness = "\n".join(
        _render_correctness(index, candidate_index, candidate_set)
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    throughput_args = ", ".join(
        f"inputs.vectors[{argument}][position]" for argument in range(inputs)
    )
    latency_args = ", ".join(
        ("current", *(f"inputs.vectors[{argument}][position]" for argument in range(1, inputs)))
    )
    measure_cases = "\n".join(
        f"    case {candidate_index}: return latency ? measure_latency_{index}<{candidate_index}>(inputs, iterations) : measure_throughput_{index}<{candidate_index}>(inputs, iterations);"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    candidate_names = ", ".join(
        _cpp_string(candidate.variant_id) for candidate in candidate_set.candidates
    )
    scenario_names = ", ".join(
        _cpp_string(scenario.scenario_id) for scenario in candidate_set.scenarios
    )
    scenario_seeds = ", ".join(
        f"{scenario.seed}ULL" for scenario in candidate_set.scenarios
    )
    rounds = candidate_set.scenarios[0].rounds
    minimum_ns = candidate_set.scenarios[0].minimum_sample_ns
    correctness_calls = " && ".join(
        f"correct_{index}_{candidate_index}()"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    stable_id = _cpp_string(candidate_set.stable_id)
    return f'''using Vec_{index} = {vector_type};
using Reg_{index} = typename Vec_{index}::register_type;
using Base_{index} = typename Vec_{index}::base_type;
constexpr std::size_t kBatch_{index} = {batch_size};

struct Inputs_{index} {{
    Reg_{index} vectors[{inputs}][kBatch_{index}]{{}};
}};

Inputs_{index} make_inputs_{index}() {{
    Inputs_{index} inputs;
    std::uint64_t state = {candidate_set.scenarios[0].seed}ULL;
    for (std::size_t argument = 0; argument < {inputs}; ++argument) {{
        for (std::size_t position = 0; position < kBatch_{index}; ++position) {{
            typename tsl::array_for<Vec_{index}>::type lanes{{}};
            for (std::size_t lane = 0; lane < {candidate_set.key.lanes}; ++lane)
                lanes[lane] = tsl::benchmark::next_value<Base_{index}>(state);
            inputs.vectors[argument][position] = tsl::{candidate_set.correctness_cases[0].from_array_name}<Vec_{index}>(lanes);
        }}
    }}
    tsl::benchmark::do_not_optimize(inputs);
    return inputs;
}}

{invoke}

{correctness}

template <std::size_t Candidate>
std::uint64_t measure_throughput_{index}(Inputs_{index} const& inputs,
                                        std::size_t iterations) {{
    Reg_{index} result{{}};
    const auto begin = tsl::benchmark::clock::now();
    for (std::size_t iteration = 0; iteration < iterations; ++iteration) {{
        for (std::size_t position = 0; position < kBatch_{index}; ++position) {{
            result = invoke_{index}<Candidate>({throughput_args});
            tsl::benchmark::do_not_optimize(result);
        }}
    }}
    const auto end = tsl::benchmark::clock::now();
    tsl::benchmark::do_not_optimize(result);
    return tsl::benchmark::elapsed_ns(begin, end);
}}

template <std::size_t Candidate>
std::uint64_t measure_latency_{index}(Inputs_{index} const& inputs,
                                     std::size_t iterations) {{
    Reg_{index} current = inputs.vectors[0][0];
    const auto begin = tsl::benchmark::clock::now();
    for (std::size_t iteration = 0; iteration < iterations; ++iteration) {{
        for (std::size_t position = 0; position < kBatch_{index}; ++position) {{
            current = invoke_{index}<Candidate>({latency_args});
        }}
    }}
    const auto end = tsl::benchmark::clock::now();
    tsl::benchmark::do_not_optimize(current);
    return tsl::benchmark::elapsed_ns(begin, end);
}}

std::uint64_t measure_{index}(std::size_t candidate, bool latency,
                             Inputs_{index} const& inputs, std::size_t iterations) {{
    switch (candidate) {{
{measure_cases}
    default: throw std::runtime_error("invalid candidate index");
    }}
}}

bool benchmark_set_{index}(std::vector<RawSample>& all_samples,
                           std::vector<Decision>& decisions,
                           Options const& options) {{
    if (!({correctness_calls})) {{
        std::cerr << "candidate correctness failed for " << {stable_id} << '\\n';
        return false;
    }}
    const Inputs_{index} inputs = make_inputs_{index}();
    const std::array<std::string, {len(candidate_set.candidates)}> candidates = {{{candidate_names}}};
    const std::array<std::string, {len(candidate_set.scenarios)}> scenarios = {{{scenario_names}}};
    const std::array<std::uint64_t, {len(candidate_set.scenarios)}> scenario_seeds = {{{scenario_seeds}}};
    const std::size_t rounds = options.rounds_override == 0 ? {rounds} : options.rounds_override;
    const std::uint64_t minimum_ns = options.minimum_sample_ns_override == 0
        ? {minimum_ns}ULL : options.minimum_sample_ns_override;
    std::vector<RawSample> set_samples;
    for (std::size_t scenario = 0; scenario < scenarios.size(); ++scenario) {{
        const bool latency = scenario == 1;
        std::uint64_t schedule_state = scenario_seeds[scenario];
        for (std::size_t candidate = 0; candidate < candidates.size(); ++candidate)
            (void)measure_{index}(candidate, latency, inputs, 1);
        const std::size_t iterations = tsl::benchmark::calibrate(
            [&](std::size_t count) {{ return measure_{index}(0, latency, inputs, count); }},
            minimum_ns);
        for (std::size_t round = 0; round < rounds; ++round) {{
            const std::uint64_t schedule = tsl::benchmark::splitmix64(schedule_state);
            const bool reverse = (schedule & 1U) != 0U;
            const std::size_t rotation = (schedule >> 1U) % candidates.size();
            for (std::size_t offset = 0; offset < candidates.size(); ++offset) {{
                const std::size_t ordered = reverse
                    ? candidates.size() - 1 - offset
                    : offset;
                const std::size_t candidate = (rotation + ordered) % candidates.size();
                set_samples.push_back(RawSample{{
                    {stable_id}, scenarios[scenario], candidates[candidate], round, iterations,
                    measure_{index}(candidate, latency, inputs, iterations)}});
            }}
        }}
    }}
    all_samples.insert(all_samples.end(), set_samples.begin(), set_samples.end());
    decisions.push_back(tsl::benchmark::reduce_candidate_set(
        {stable_id}, std::vector<std::string>(candidates.begin(), candidates.end()),
        std::vector<std::string>(scenarios.begin(), scenarios.end()), set_samples,
        options.threshold));
    return true;
}}'''


def _render_invoke(
    index: int,
    candidate_set: BenchmarkCandidateSet,
) -> str:
    spec = candidate_set.specialization
    params = ", ".join(
        f"typename tsl::reg_param<Vec_{index}>::type value_{position}"
        for position, _kind in enumerate(spec.param_kinds)
    )
    arguments = ", ".join(
        f"value_{position}" for position, _kind in enumerate(spec.param_kinds)
    )
    branches: list[str] = []
    for candidate_index, candidate in enumerate(candidate_set.candidates):
        implementation = implementation_name(
            spec.primitive_name,
            None if candidate.is_default else candidate.variant_id,
        )
        keyword = "if" if candidate_index == 0 else "else if"
        branches.append(
            f"    {keyword} constexpr (Candidate == {candidate_index}) {{\n"
            f"        return ::tsl::detail::primitives::{implementation}"
            f"<Vec_{index}>::apply({arguments});\n"
            "    }"
        )
    return f'''template <std::size_t Candidate>
inline Reg_{index} invoke_{index}({params}) {{
{chr(10).join(branches)}
    else {{
        static_assert(Candidate < {len(candidate_set.candidates)}, "invalid benchmark candidate");
        return Reg_{index}{{}};
    }}
}}'''


def _render_correctness(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
) -> str:
    case_blocks: list[str] = []
    for case_index, case in enumerate(candidate_set.correctness_cases):
        arrays = "\n".join(
            f"    typename tsl::array_for<Vec_{index}>::type input_{argument} = "
            f"{{{cpp_literal_list(values, candidate_set.key.type_tag)}}};\n"
            f"    const auto value_{argument} = tsl::{case.from_array_name}<Vec_{index}>(input_{argument});"
            for argument, values in enumerate(case.vector_inputs)
        )
        arguments = ", ".join(
            f"value_{argument}" for argument, _values in enumerate(case.vector_inputs)
        )
        expected = cpp_literal_list(case.expected, candidate_set.key.type_tag)
        case_blocks.append(
            f'''{{
{arrays}
    const auto result = invoke_{index}<{candidate_index}>({arguments});
    const auto actual = tsl::{case.to_array_name}<Vec_{index}>(result);
    const Base_{index} expected[] = {{{expected}}};
    failures += tsl::test::check_lanes<Base_{index}>(
        {_cpp_string(case.case_name)}, actual, expected, {len(case.expected)});
}}'''
        )
    return f'''bool correct_{index}_{candidate_index}() {{
    int failures = 0;
{_indent("\n".join(case_blocks), 4)}
    return failures == 0;
}}'''


def _render_policy_branch(candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    vector = _vector_type(candidate_set)
    branches: list[str] = []
    for candidate in candidate_set.candidates[1:]:
        branches.append(
            f'''        if (decision.stable_id == {_cpp_string(candidate_set.stable_id)} &&
            decision.selected == {_cpp_string(candidate.variant_id)}) {{
            output << "template <>\\nstruct {variant_selector_name(spec.primitive_name)}<{vector}> {{\\n"
                   << "    static constexpr auto value = {variant_enum_name(spec.primitive_name)}::{candidate.variant_id};\\n"
                   << "}};\\n\\n";
            continue;
        }}'''
        )
    return "\n".join(branches)


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


def _vector_type(candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    return f"::tsl::simd<{spec.base_type_spelling}, ::tsl::{spec.extension_name}>"


def _cpp_string(value: str) -> str:
    return json.dumps(value)


def _indent(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in value.splitlines())


__all__ = ("cpp_benchmark_artifacts",)
