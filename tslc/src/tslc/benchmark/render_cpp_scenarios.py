"""Render C++ timing loops from fully resolved benchmark scenarios."""

from __future__ import annotations

from dataclasses import dataclass
import json

from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkImmediateScenario,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkIndexedLoadScenario,
    BenchmarkMaskDensityScenario,
    BenchmarkMaskResultScenario,
    BenchmarkReductionCorrectnessCase,
    BenchmarkReductionScenario,
    BenchmarkRegisterScenario,
    BenchmarkScenario,
    BenchmarkTiming,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
    BenchmarkVectorScalarScenario,
)


@dataclass(frozen=True, slots=True)
class _CppTimingParts:
    """Already-rendered C++ fragments placed by the shared timing skeleton."""

    input_members: str
    make_inputs_body: str
    result_setup: str
    loop_body: str
    result_consume: str
    constants: str = ""


def render_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: (
        BenchmarkRegisterScenario
        | BenchmarkMaskDensityScenario
        | BenchmarkMaskResultScenario
        | BenchmarkReductionScenario
        | BenchmarkVectorScalarScenario
        | BenchmarkImmediateScenario
        | BenchmarkIndexedLoadScenario
    ),
) -> str:
    if isinstance(scenario, (BenchmarkRegisterScenario, BenchmarkMaskResultScenario)):
        return _render_vector_operand_scenario(
            index, scenario_index, candidate_set, scenario
        )
    if isinstance(scenario, BenchmarkVectorScalarScenario):
        return _render_vector_scalar_scenario(
            index, scenario_index, candidate_set, scenario
        )
    if isinstance(scenario, BenchmarkImmediateScenario):
        return _render_immediate_scenario(
            index, scenario_index, candidate_set, scenario
        )
    if isinstance(scenario, BenchmarkIndexedLoadScenario):
        return _render_indexed_load_scenario(
            index, scenario_index, candidate_set, scenario
        )
    if isinstance(scenario, BenchmarkReductionScenario):
        return _render_reduction_scenario(index, scenario_index, candidate_set, scenario)
    return _render_mask_density_scenario(index, scenario_index, candidate_set, scenario)


def _render_vector_operand_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkRegisterScenario | BenchmarkMaskResultScenario,
) -> str:
    if any(
        generator not in {
            "bounded_random",
            "bounded_nonzero",
            "bounded_shift_count",
        }
        for generator in scenario.operand_generators
    ):
        raise ValueError("C++ benchmark renderer does not support the operand generator")
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(
        correctness,
        (BenchmarkVectorCorrectnessCase, BenchmarkVectorMaskCorrectnessCase),
    ):
        raise ValueError("vector-operand scenarios require vector correctness cases")
    timing = scenario.timing
    inputs = len(scenario.operand_generators)
    input_initializers = "\n".join(
        _render_register_operand_input(
            index,
            scenario_index,
            parameter,
            generator,
            candidate_set.key.lanes,
            correctness.from_array_name,
        )
        for parameter, generator in enumerate(scenario.operand_generators)
    )
    arguments = [
        f"inputs.vectors[{parameter}][position]" for parameter in range(inputs)
    ]
    if isinstance(scenario, BenchmarkRegisterScenario) and scenario.kind == "latency":
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
    return _render_timing_scenario(
        index,
        scenario_index,
        candidate_set,
        scenario,
        _CppTimingParts(
            input_members=(
                f"    Reg_{index} vectors[{inputs}]"
                f"[kBatch_{index}_{scenario_index}]{{}};"
            ),
            make_inputs_body=(
                f"    std::uint64_t state = {timing.seed}ULL;\n"
                f"{input_initializers}"
            ),
            result_setup=result_setup,
            loop_body=loop_body,
            result_consume=result_consume,
        ),
    )


def _render_register_operand_input(
    index: int,
    scenario_index: int,
    parameter: int,
    generator: str,
    lanes: int | None,
    from_array_name: str,
) -> str:
    if lanes is None:
        raise ValueError("register benchmark input requires a fixed lane count")
    generator_function = _operand_generator_function(generator)
    return f'''    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        typename tsl::array_for<Vec_{index}>::type lanes{{}};
        for (std::size_t lane = 0; lane < {lanes}; ++lane)
            lanes[lane] = tsl::benchmark::{generator_function}<Base_{index}>(state);
        inputs.vectors[{parameter}][position] =
            tsl::{from_array_name}<Vec_{index}>(lanes);
    }}'''


def _render_vector_scalar_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkVectorScalarScenario,
) -> str:
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkVectorScalarCorrectnessCase):
        raise ValueError("vector-scalar scenarios require vector/scalar correctness")
    lanes = candidate_set.key.lanes
    if lanes is None:
        raise ValueError("vector-scalar benchmark input requires a fixed lane count")
    vector_generator = _operand_generator_function(scenario.vector_generator)
    scalar_generator = _operand_generator_function(scenario.scalar_generator)
    timing = scenario.timing
    if scenario.kind == "latency":
        result_setup = f"    Reg_{index} current = inputs.vectors[0];"
        loop_body = (
            f"            current = invoke_{index}<Candidate>(current, inputs.scalars[position]);"
        )
        result_consume = "    tsl::benchmark::do_not_optimize(current);"
    else:
        result_setup = f"    Result_{index} result{{}};"
        loop_body = (
            f"            result = invoke_{index}<Candidate>("
            "inputs.vectors[position], inputs.scalars[position]);\n"
            "            tsl::benchmark::do_not_optimize(result);"
        )
        result_consume = "    tsl::benchmark::do_not_optimize(result);"
    return _render_timing_scenario(
        index,
        scenario_index,
        candidate_set,
        scenario,
        _CppTimingParts(
            input_members=f'''    Reg_{index} vectors[kBatch_{index}_{scenario_index}]{{}};
    Base_{index} scalars[kBatch_{index}_{scenario_index}]{{}};''',
            make_inputs_body=f'''    std::uint64_t state = {timing.seed}ULL;
    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        typename tsl::array_for<Vec_{index}>::type lanes{{}};
        for (std::size_t lane = 0; lane < {lanes}; ++lane)
            lanes[lane] = tsl::benchmark::{vector_generator}<Base_{index}>(state);
        inputs.vectors[position] =
            tsl::{correctness.from_array_name}<Vec_{index}>(lanes);
        inputs.scalars[position] =
            tsl::benchmark::{scalar_generator}<Base_{index}>(state);
    }}''',
            result_setup=result_setup,
            loop_body=loop_body,
            result_consume=result_consume,
        ),
    )


def _operand_generator_function(generator: str) -> str:
    return {
        "bounded_random": "next_value",
        "bounded_nonzero": "next_nonzero_value",
        "bounded_shift_count": "next_shift_count",
    }[generator]


def _render_immediate_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkImmediateScenario,
) -> str:
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkImmediateCorrectnessCase):
        raise ValueError("immediate scenarios require immediate correctness")
    lanes = candidate_set.key.lanes
    if lanes is None:
        raise ValueError("immediate benchmark input requires a fixed lane count")
    generator = _operand_generator_function(scenario.operand_generator)
    timing = scenario.timing
    if scenario.kind == "latency":
        result_setup = f"    Reg_{index} current = inputs.vectors[0];"
        loop_body = f"            current = invoke_{index}<Candidate>(current);"
        result_consume = "    tsl::benchmark::do_not_optimize(current);"
    else:
        result_setup = f"    Result_{index} result{{}};"
        loop_body = (
            f"            result = invoke_{index}<Candidate>(inputs.vectors[position]);\n"
            "            tsl::benchmark::do_not_optimize(result);"
        )
        result_consume = "    tsl::benchmark::do_not_optimize(result);"
    return _render_timing_scenario(
        index,
        scenario_index,
        candidate_set,
        scenario,
        _CppTimingParts(
            input_members=(
                f"    Reg_{index} vectors[kBatch_{index}_{scenario_index}]{{}};"
            ),
            make_inputs_body=f'''    std::uint64_t state = {timing.seed}ULL;
    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        typename tsl::array_for<Vec_{index}>::type lanes{{}};
        for (std::size_t lane = 0; lane < {lanes}; ++lane)
            lanes[lane] = tsl::benchmark::{generator}<Base_{index}>(state);
        inputs.vectors[position] =
            tsl::{correctness.from_array_name}<Vec_{index}>(lanes);
    }}''',
            result_setup=result_setup,
            loop_body=loop_body,
            result_consume=result_consume,
        ),
    )


def _render_indexed_load_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkIndexedLoadScenario,
) -> str:
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkIndexedLoadCorrectnessCase):
        raise ValueError("indexed-load scenarios require indexed-load correctness")
    immediate = candidate_set.key.immediate
    if immediate is None:
        raise ValueError("indexed-load scenarios require a concrete scale")
    timing = scenario.timing
    return _render_timing_scenario(
        index,
        scenario_index,
        candidate_set,
        scenario,
        _CppTimingParts(
            constants=f'''constexpr std::size_t kMemoryBytes_{index}_{scenario_index} = {scenario.memory_bytes};
constexpr std::size_t kElements_{index}_{scenario_index} =
    kMemoryBytes_{index}_{scenario_index} / sizeof(Base_{index});
constexpr std::size_t kScale_{index}_{scenario_index} = {immediate};
static_assert(kElements_{index}_{scenario_index} > 0);
static_assert(kScale_{index}_{scenario_index} > 0);''',
            input_members=f'''    alignas(64) Base_{index} memory[kElements_{index}_{scenario_index}]{{}};
    IndexReg_{index} indices[kBatch_{index}_{scenario_index}]{{}};''',
            make_inputs_body=f'''    std::uint64_t state = {timing.seed}ULL;
    for (std::size_t element = 0; element < kElements_{index}_{scenario_index}; ++element)
        inputs.memory[element] = tsl::benchmark::next_value<Base_{index}>(state);
    constexpr std::size_t max_index =
        (kMemoryBytes_{index}_{scenario_index} - sizeof(Base_{index})) /
        kScale_{index}_{scenario_index};
    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        typename tsl::array_for<IndexVec_{index}>::type lanes{{}};
        for (std::size_t lane = 0; lane < {scenario.index_lanes}; ++lane)
            lanes[lane] = static_cast<IndexBase_{index}>(
                tsl::benchmark::splitmix64(state) % (max_index + 1));
        inputs.indices[position] =
            tsl::{correctness.from_array_name}<IndexVec_{index}>(lanes);
    }}''',
            result_setup=f"    Result_{index} result{{}};",
            loop_body=(
                f"            result = invoke_{index}<Candidate>("
                "inputs.memory, inputs.indices[position]);\n"
                "            tsl::benchmark::do_not_optimize(result);"
            ),
            result_consume="    tsl::benchmark::do_not_optimize(result);",
        ),
    )


def _render_reduction_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkReductionScenario,
) -> str:
    if scenario.operand_generator != "bounded_random":
        raise ValueError("C++ benchmark renderer does not support the operand generator")
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkReductionCorrectnessCase):
        raise ValueError("reduction scenarios require reduction correctness cases")
    timing = scenario.timing
    return _render_timing_scenario(
        index,
        scenario_index,
        candidate_set,
        scenario,
        _CppTimingParts(
            input_members=(
                f"    Reg_{index} vectors[kBatch_{index}_{scenario_index}]{{}};"
            ),
            make_inputs_body=f'''    std::uint64_t state = {timing.seed}ULL;
    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        typename tsl::array_for<Vec_{index}>::type lanes{{}};
        for (std::size_t lane = 0; lane < {candidate_set.key.lanes}; ++lane)
            lanes[lane] = tsl::benchmark::next_value<Base_{index}>(state);
        inputs.vectors[position] =
            tsl::{correctness.from_array_name}<Vec_{index}>(lanes);
    }}''',
            result_setup=f"    Result_{index} result{{}};",
            loop_body=(
                f"            result = invoke_{index}<Candidate>("
                "inputs.vectors[position]);\n"
                "            tsl::benchmark::do_not_optimize(result);"
            ),
            result_consume="    tsl::benchmark::do_not_optimize(result);",
        ),
    )


def _render_mask_density_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkMaskDensityScenario,
) -> str:
    timing = scenario.timing
    arguments = [
        "inputs.values[position]" if parameter == scenario.parameter_index else ""
        for parameter, _kind in enumerate(candidate_set.specialization.param_kinds)
    ]
    if any(not argument for argument in arguments):
        raise ValueError("mask-density scenario does not provide every call argument")
    return _render_timing_scenario(
        index,
        scenario_index,
        candidate_set,
        scenario,
        _CppTimingParts(
            input_members=(
                f"    Imask_{index} values[kBatch_{index}_{scenario_index}]{{}};"
            ),
            make_inputs_body=f'''    for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
        const std::uint64_t bits = tsl::benchmark::rotating_mask_bits(
            {candidate_set.key.lanes}, {scenario.active_lanes}, position);
        inputs.values[position] = static_cast<Imask_{index}>(bits);
    }}''',
            result_setup=f"    Result_{index} result{{}};",
            loop_body=(
                f"            result = invoke_{index}<Candidate>("
                f"{', '.join(arguments)});\n"
                "            tsl::benchmark::do_not_optimize(result);"
            ),
            result_consume="    tsl::benchmark::do_not_optimize(result);",
        ),
    )


def _render_timing_scenario(
    index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkScenario,
    parts: _CppTimingParts,
) -> str:
    timing = scenario.timing
    input_type = f"Inputs_{index}_{scenario_index}"
    make_inputs = f"make_inputs_{index}_{scenario_index}"
    measure_template = f"measure_candidate_{index}_{scenario_index}"
    constants = f"{parts.constants}\n" if parts.constants else ""
    return f'''constexpr std::size_t kBatch_{index}_{scenario_index} = {timing.batch_size};
{constants}
struct {input_type} {{
{parts.input_members}
}};

{input_type} {make_inputs}() {{
    {input_type} inputs;
{parts.make_inputs_body}
    tsl::benchmark::do_not_optimize(inputs);
    return inputs;
}}

template <std::size_t Candidate>
std::uint64_t {measure_template}({input_type} const& inputs,
                                 std::size_t iterations) {{
{parts.result_setup}
    const auto begin = tsl::benchmark::clock::now();
    for (std::size_t iteration = 0; iteration < iterations; ++iteration) {{
        for (std::size_t position = 0; position < kBatch_{index}_{scenario_index}; ++position) {{
{parts.loop_body}
        }}
    }}
    const auto end = tsl::benchmark::clock::now();
{parts.result_consume}
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


def _cpp_string(value: str) -> str:
    return json.dumps(value)


__all__ = ("render_scenario",)
