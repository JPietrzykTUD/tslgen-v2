"""Render concrete C++ candidate harnesses from resolved benchmark scenarios."""

from __future__ import annotations

import json

from tslc.backend.cpp import implementation_name
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkMaskCorrectnessCase,
    BenchmarkMaskDensityScenario,
    BenchmarkRegisterScenario,
    BenchmarkTiming,
    BenchmarkVectorCorrectnessCase,
)
from tslc.value_tests.literals import cpp_literal_list
from tslc.value_tests.render_cpp_helpers import uint_literal


def render_candidate_set(index: int, candidate_set: BenchmarkCandidateSet) -> str:
    """Render one candidate set without inferring any workload semantics."""

    correctness = "\n\n".join(
        _render_correctness(index, candidate_index, candidate_set)
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    scenarios = "\n\n".join(
        _render_scenario(index, scenario_index, candidate_set, scenario)
        for scenario_index, scenario in enumerate(candidate_set.scenarios)
    )
    scenario_runs = "\n".join(
        f"    run_scenario_{index}_{scenario_index}(set_samples, candidates, options);"
        for scenario_index, _scenario in enumerate(candidate_set.scenarios)
    )
    candidate_names = ", ".join(
        _cpp_string(candidate.variant_id) for candidate in candidate_set.candidates
    )
    scenario_names = ", ".join(
        _cpp_string(scenario.scenario_id) for scenario in candidate_set.scenarios
    )
    correctness_calls = " && ".join(
        f"correct_{index}_{candidate_index}()"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    stable_id = _cpp_string(candidate_set.stable_id)
    return f'''using Vec_{index} = {vector_type(candidate_set)};
using Reg_{index} = typename Vec_{index}::register_type;
using Mask_{index} = typename Vec_{index}::mask_type;
using Imask_{index} = typename Vec_{index}::imask_type;
using Base_{index} = typename Vec_{index}::base_type;
using Result_{index} = {_result_type(candidate_set, index)};

{_render_invoke(index, candidate_set)}

{correctness}

{scenarios}

bool benchmark_set_{index}(std::vector<RawSample>& all_samples,
                           std::vector<Decision>& decisions,
                           Options const& options) {{
    if (!({correctness_calls})) {{
        std::cerr << "candidate correctness failed for " << {stable_id} << '\\n';
        return false;
    }}
    const std::array<std::string, {len(candidate_set.candidates)}> candidates = {{{candidate_names}}};
    const std::array<std::string, {len(candidate_set.scenarios)}> scenarios = {{{scenario_names}}};
    std::vector<RawSample> set_samples;
{scenario_runs}
    all_samples.insert(all_samples.end(), set_samples.begin(), set_samples.end());
    decisions.push_back(tsl::benchmark::reduce_candidate_set(
        {stable_id}, std::vector<std::string>(candidates.begin(), candidates.end()),
        std::vector<std::string>(scenarios.begin(), scenarios.end()), set_samples,
        options.threshold));
    return true;
}}'''


def _render_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkRegisterScenario | BenchmarkMaskDensityScenario,
) -> str:
    if isinstance(scenario, BenchmarkRegisterScenario):
        return _render_register_scenario(index, scenario_index, candidate_set, scenario)
    return _render_mask_density_scenario(index, scenario_index, candidate_set, scenario)


def _render_register_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkRegisterScenario,
) -> str:
    if any(generator != "bounded_random" for generator in scenario.operand_generators):
        raise ValueError("C++ benchmark renderer does not support the operand generator")
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkVectorCorrectnessCase):
        raise ValueError("register scenarios require vector correctness cases")
    timing = scenario.timing
    inputs = len(scenario.operand_generators)
    input_type = f"Inputs_{index}_{scenario_index}"
    make_inputs = f"make_inputs_{index}_{scenario_index}"
    measure_template = f"measure_candidate_{index}_{scenario_index}"
    arguments = [
        f"inputs.vectors[{parameter}][position]" for parameter in range(inputs)
    ]
    if scenario.kind == "latency":
        assert scenario.dependency_parameter is not None
        arguments[scenario.dependency_parameter] = "current"
        initial = f"inputs.vectors[{scenario.dependency_parameter}][0]"
        loop_body = (
            f"            current = invoke_{index}<Candidate>({', '.join(arguments)});"
        )
        result_setup = f"    Reg_{index} current = {initial};"
        result_consume = f"    tsl::benchmark::do_not_optimize(current);"
    else:
        loop_body = (
            f"            result = invoke_{index}<Candidate>({', '.join(arguments)});\n"
            "            tsl::benchmark::do_not_optimize(result);"
        )
        result_setup = f"    Result_{index} result{{}};"
        result_consume = f"    tsl::benchmark::do_not_optimize(result);"
    return f'''constexpr std::size_t kBatch_{index}_{scenario_index} = {timing.batch_size};

struct {input_type} {{
    Reg_{index} vectors[{inputs}][kBatch_{index}_{scenario_index}]{{}};
}};

{input_type} {make_inputs}() {{
    {input_type} inputs;
    std::uint64_t state = {timing.seed}ULL;
    for (std::size_t argument = 0; argument < {inputs}; ++argument) {{
        for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
            typename tsl::array_for<Vec_{index}>::type lanes{{}};
            for (std::size_t lane = 0; lane < {candidate_set.key.lanes}; ++lane)
                lanes[lane] = tsl::benchmark::next_value<Base_{index}>(state);
            inputs.vectors[argument][position] =
                tsl::{correctness.from_array_name}<Vec_{index}>(lanes);
        }}
    }}
    tsl::benchmark::do_not_optimize(inputs);
    return inputs;
}}

template <std::size_t Candidate>
std::uint64_t {measure_template}({input_type} const& inputs,
                                 std::size_t iterations) {{
{result_setup}
    const auto begin = tsl::benchmark::clock::now();
    for (std::size_t iteration = 0; iteration < iterations; ++iteration) {{
        for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
{loop_body}
        }}
    }}
    const auto end = tsl::benchmark::clock::now();
{result_consume}
    return tsl::benchmark::elapsed_ns(begin, end);
}}

{_render_measure_dispatch(index, scenario_index, candidate_set, input_type)}

{_render_scenario_runner(index, scenario_index, candidate_set, scenario.scenario_id, timing, input_type, make_inputs)}'''


def _render_mask_density_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkMaskDensityScenario,
) -> str:
    timing = scenario.timing
    input_type = f"Inputs_{index}_{scenario_index}"
    make_inputs = f"make_inputs_{index}_{scenario_index}"
    measure_template = f"measure_candidate_{index}_{scenario_index}"
    arguments = [
        "inputs.values[position]" if parameter == scenario.parameter_index else ""
        for parameter, _kind in enumerate(candidate_set.specialization.param_kinds)
    ]
    if any(not argument for argument in arguments):
        raise ValueError("mask-density scenario does not provide every call argument")
    return f'''constexpr std::size_t kBatch_{index}_{scenario_index} = {timing.batch_size};

struct {input_type} {{
    Imask_{index} values[kBatch_{index}_{scenario_index}]{{}};
}};

{input_type} {make_inputs}() {{
    {input_type} inputs;
    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        const std::uint64_t bits = tsl::benchmark::rotating_mask_bits(
            {candidate_set.key.lanes}, {scenario.active_lanes}, position);
        inputs.values[position] = static_cast<Imask_{index}>(bits);
    }}
    tsl::benchmark::do_not_optimize(inputs);
    return inputs;
}}

template <std::size_t Candidate>
std::uint64_t {measure_template}({input_type} const& inputs,
                                 std::size_t iterations) {{
    Result_{index} result{{}};
    const auto begin = tsl::benchmark::clock::now();
    for (std::size_t iteration = 0; iteration < iterations; ++iteration) {{
        for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
            result = invoke_{index}<Candidate>({', '.join(arguments)});
            tsl::benchmark::do_not_optimize(result);
        }}
    }}
    const auto end = tsl::benchmark::clock::now();
    tsl::benchmark::do_not_optimize(result);
    return tsl::benchmark::elapsed_ns(begin, end);
}}

{_render_measure_dispatch(index, scenario_index, candidate_set, input_type)}

{_render_scenario_runner(index, scenario_index, candidate_set, scenario.scenario_id, timing, input_type, make_inputs)}'''


def _render_measure_dispatch(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    input_type: str,
) -> str:
    cases = "\n".join(
        f"    case {candidate_index}: return measure_candidate_{index}_{scenario_index}<{candidate_index}>(inputs, iterations);"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    return f'''std::uint64_t measure_{index}_{scenario_index}(
    std::size_t candidate, {input_type} const& inputs, std::size_t iterations) {{
    switch (candidate) {{
{cases}
    default: throw std::runtime_error("invalid candidate index");
    }}
}}'''


def _render_scenario_runner(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario_id: str,
    timing: BenchmarkTiming,
    input_type: str,
    make_inputs: str,
) -> str:
    seed = timing.seed
    rounds = timing.rounds
    minimum_sample_ns = timing.minimum_sample_ns
    stable_id = _cpp_string(candidate_set.stable_id)
    scenario = _cpp_string(scenario_id)
    return f'''void run_scenario_{index}_{scenario_index}(
    std::vector<RawSample>& samples,
    std::array<std::string, {len(candidate_set.candidates)}> const& candidates,
    Options const& options) {{
    const {input_type} inputs = {make_inputs}();
    const std::size_t rounds = options.rounds_override == 0 ? {rounds} : options.rounds_override;
    const std::uint64_t minimum_ns = options.minimum_sample_ns_override == 0
        ? {minimum_sample_ns}ULL : options.minimum_sample_ns_override;
    for (std::size_t candidate = 0; candidate < candidates.size(); ++candidate)
        (void)measure_{index}_{scenario_index}(candidate, inputs, 1);
    const std::size_t iterations = tsl::benchmark::calibrate(
        [&](std::size_t count) {{ return measure_{index}_{scenario_index}(0, inputs, count); }},
        minimum_ns);
    std::uint64_t schedule_state = {seed}ULL;
    for (std::size_t round = 0; round < rounds; ++round) {{
        const std::uint64_t schedule = tsl::benchmark::splitmix64(schedule_state);
        const bool reverse = (schedule & 1U) != 0U;
        const std::size_t rotation = (schedule >> 1U) % candidates.size();
        for (std::size_t offset = 0; offset < candidates.size(); ++offset) {{
            const std::size_t ordered = reverse ? candidates.size() - 1 - offset : offset;
            const std::size_t candidate = (rotation + ordered) % candidates.size();
            samples.push_back(RawSample{{
                {stable_id}, {scenario}, candidates[candidate], round, iterations,
                measure_{index}_{scenario_index}(candidate, inputs, iterations)}});
        }}
    }}
}}'''


def _render_invoke(index: int, candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    params = ", ".join(
        f"{_parameter_type(kind, index)} value_{position}"
        for position, kind in enumerate(spec.param_kinds)
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
inline Result_{index} invoke_{index}({params}) {{
{chr(10).join(branches)}
    else {{
        static_assert(Candidate < {len(candidate_set.candidates)}, "invalid benchmark candidate");
        return Result_{index}{{}};
    }}
}}'''


def _render_correctness(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
) -> str:
    case_blocks: list[str] = []
    for case in candidate_set.correctness_cases:
        if isinstance(case, BenchmarkVectorCorrectnessCase):
            case_blocks.append(
                _render_vector_correctness_case(index, candidate_index, candidate_set, case)
            )
        elif isinstance(case, BenchmarkMaskCorrectnessCase):
            case_blocks.append(
                _render_mask_correctness_case(index, candidate_index, case)
            )
    return f'''bool correct_{index}_{candidate_index}() {{
    int failures = 0;
{_indent(chr(10).join(case_blocks), 4)}
    return failures == 0;
}}'''


def _render_vector_correctness_case(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkVectorCorrectnessCase,
) -> str:
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
    return f'''{{
{arrays}
    const auto result = invoke_{index}<{candidate_index}>({arguments});
    const auto actual = tsl::{case.to_array_name}<Vec_{index}>(result);
    const Base_{index} expected[] = {{{expected}}};
    failures += tsl::test::check_lanes<Base_{index}>(
        {_cpp_string(case.case_name)}, actual, expected, {len(case.expected)});
}}'''


def _render_mask_correctness_case(
    index: int,
    candidate_index: int,
    case: BenchmarkMaskCorrectnessCase,
) -> str:
    inputs = ", ".join(
        f"static_cast<Imask_{index}>({uint_literal(value)})"
        for value in case.mask_inputs
    )
    expected = uint_literal(case.expected_mask)
    return f'''{{
    const auto result = invoke_{index}<{candidate_index}>({inputs});
    const Imask_{index} actual = static_cast<Imask_{index}>(
        tsl::{case.to_integral_name}<Vec_{index}>(result));
    const Imask_{index} expected = static_cast<Imask_{index}>({expected});
    failures += tsl::test::check_scalar<Imask_{index}>(
        {_cpp_string(case.case_name)}, actual, expected);
}}'''


def _result_type(candidate_set: BenchmarkCandidateSet, index: int) -> str:
    return {"v": f"Reg_{index}", "m": f"Mask_{index}"}[
        candidate_set.specialization.result_kind
    ]


def _parameter_type(kind: str, index: int) -> str:
    return {
        "v": f"typename ::tsl::reg_param<Vec_{index}>::type",
        "m": f"Mask_{index}",
        "im": f"Imask_{index}",
    }[kind]


def vector_type(candidate_set: BenchmarkCandidateSet) -> str:
    spec = candidate_set.specialization
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    return f"::tsl::simd<{spec.base_type_spelling}, ::tsl::{spec.extension_name}>"


def _cpp_string(value: str) -> str:
    return json.dumps(value)


def _indent(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in value.splitlines())


__all__ = ("render_candidate_set", "vector_type")
