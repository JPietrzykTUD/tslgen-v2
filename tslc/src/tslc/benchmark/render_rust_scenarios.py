"""Render fixed-width pure-register Rust benchmark timing loops."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.benchmark._render_rust_common import indent, rust_string_literal
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkRegisterScenario,
    BenchmarkVectorCorrectnessCase,
)


def render_scenario(
    set_index: int,
    scenario_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkRegisterScenario,
    *,
    profile_module: str,
) -> str:
    if not isinstance(scenario, BenchmarkRegisterScenario):
        raise ValueError("Rust benchmark renderer supports only register scenarios")
    correctness = candidate_set.correctness_cases[0]
    if not isinstance(correctness, BenchmarkVectorCorrectnessCase):
        raise ValueError("Rust register scenarios require vector correctness cases")
    lanes = candidate_set.key.lanes
    if lanes is None:
        raise ValueError("Rust register scenarios require a fixed lane count")
    generators = tuple(_generator_name(item) for item in scenario.operand_generators)
    input_type = f"Inputs_{set_index}_{scenario_index}"
    batch = scenario.timing.batch_size
    from_array = rust_raw_identifier(correctness.from_array_name)
    fill_inputs = "\n".join(
        f"for _position in 0..{batch} {{\n"
        f"    let mut lanes: <Vec_{set_index} as SimdVector>::Array = Default::default();\n"
        f"    for lane in 0..{lanes} {{\n"
        f"        lanes[lane] = crate::tsl_benchmark_core::{generator}"
        f"::<Base_{set_index}>(&mut state);\n"
        "    }\n"
        f"    vectors[{parameter}].push(crate::{profile_module}::{from_array}"
        f"::<Vec_{set_index}>(&lanes));\n"
        "}"
        for parameter, generator in enumerate(generators)
    )
    measures = "\n\n".join(
        _render_candidate_measure(
            set_index,
            scenario_index,
            candidate_index,
            candidate_set,
            scenario,
            input_type,
        )
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    dispatch = "\n".join(
        f"        {candidate_index} => Ok(measure_{set_index}_{scenario_index}_{candidate_index}"
        "(inputs, iterations)),"
        for candidate_index, _candidate in enumerate(candidate_set.candidates)
    )
    return f"""const BATCH_{set_index}_{scenario_index}: usize = {batch};

struct {input_type} {{
    vectors: [Vec<Reg_{set_index}>; {len(generators)}],
}}

fn make_inputs_{set_index}_{scenario_index}() -> {input_type} {{
    let mut state = {scenario.timing.seed}u64;
    let mut vectors: [Vec<Reg_{set_index}>; {len(generators)}] =
        std::array::from_fn(|_| Vec::with_capacity(BATCH_{set_index}_{scenario_index}));
{indent(fill_inputs, 4)}
    std::hint::black_box(&vectors);
    {input_type} {{ vectors }}
}}

{measures}

fn measure_{set_index}_{scenario_index}(
    candidate: usize,
    inputs: &{input_type},
    iterations: usize,
) -> Result<u64, String> {{
    match candidate {{
{dispatch}
        _ => Err(format!("invalid candidate index {{candidate}}")),
    }}
}}

fn run_scenario_{set_index}_{scenario_index}(
    options: &Options,
    samples: &mut Vec<RawSample>,
) -> Result<(), String> {{
    let inputs = make_inputs_{set_index}_{scenario_index}();
    for candidate in 0..CANDIDATES_{set_index}.len() {{
        let _ = measure_{set_index}_{scenario_index}(candidate, &inputs, 1)?;
    }}
    let minimum_sample_ns = options.minimum_sample_ns({scenario.timing.minimum_sample_ns}u64);
    let mut iterations = 1usize;
    for candidate in 0..CANDIDATES_{set_index}.len() {{
        iterations = iterations.max(crate::tsl_benchmark_core::calibrate(
            |count| measure_{set_index}_{scenario_index}(candidate, &inputs, count),
            minimum_sample_ns,
        )?);
    }}
    let rounds = options.rounds({scenario.timing.rounds});
    let mut schedule_state = {scenario.timing.seed}u64;
    for round in 0..rounds {{
        let schedule = crate::tsl_benchmark_core::splitmix64(&mut schedule_state);
        for candidate in crate::tsl_benchmark_core::candidate_order(
            CANDIDATES_{set_index}.len(), schedule,
        )? {{
            samples.push(RawSample {{
                stable_id: {rust_string_literal(candidate_set.stable_id)},
                scenario: {rust_string_literal(scenario.scenario_id)},
                candidate: CANDIDATES_{set_index}[candidate],
                round,
                iterations,
                elapsed_ns: measure_{set_index}_{scenario_index}(
                    candidate, &inputs, iterations,
                )?,
            }});
        }}
    }}
    Ok(())
}}"""


def _render_candidate_measure(
    set_index: int,
    scenario_index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    scenario: BenchmarkRegisterScenario,
    input_type: str,
) -> str:
    arguments = [
        f"inputs.vectors[{parameter}][position]"
        for parameter, _kind in enumerate(candidate_set.key.param_kinds)
    ]
    if scenario.kind == "latency":
        dependency = scenario.dependency_parameter
        if dependency is None:
            raise ValueError("Rust latency scenario requires a dependency parameter")
        arguments[dependency] = "current"
        setup = f"let mut current = inputs.vectors[{dependency}][0];"
        operation = (
            f"current = invoke_{set_index}_{candidate_index}({', '.join(arguments)});"
        )
        consume = "std::hint::black_box(current);"
    else:
        setup = "let mut result = inputs.vectors[0][0];"
        operation = (
            f"result = std::hint::black_box(invoke_{set_index}_{candidate_index}"
            f"({', '.join(arguments)}));"
        )
        consume = "std::hint::black_box(result);"
    return f"""fn measure_{set_index}_{scenario_index}_{candidate_index}(
    inputs: &{input_type},
    iterations: usize,
) -> u64 {{
    {setup}
    let begin = std::time::Instant::now();
    for _iteration in 0..iterations {{
        for position in 0..BATCH_{set_index}_{scenario_index} {{
            {operation}
        }}
    }}
    let end = std::time::Instant::now();
    {consume}
    crate::tsl_benchmark_core::elapsed_ns(begin, end)
}}"""


def _generator_name(generator: str) -> str:
    try:
        return {
            "bounded_random": "next_value",
            "bounded_nonzero": "next_nonzero_value",
            "bounded_shift_count": "next_shift_count",
        }[generator]
    except KeyError as error:
        raise ValueError(
            f"Rust benchmark renderer does not support operand generator {generator!r}"
        ) from error


__all__ = ("render_scenario",)
