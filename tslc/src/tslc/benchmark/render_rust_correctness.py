"""Render authored vector-input correctness checks for Rust benchmark candidates."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.benchmark._render_rust_common import indent, rust_string_literal
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkReductionCorrectnessCase,
    BenchmarkVectorCorrectnessCase,
)
from tslc.value_tests.literals import rust_literal, rust_literal_list


def render_correctness(
    set_index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    *,
    profile_module: str,
) -> str:
    blocks = []
    for case in candidate_set.correctness_cases:
        if not isinstance(
            case,
            (
                BenchmarkImmediateCorrectnessCase,
                BenchmarkReductionCorrectnessCase,
                BenchmarkVectorCorrectnessCase,
            ),
        ):
            raise ValueError(
                "Rust register, immediate, and reduction benchmarks require "
                "vector-input correctness cases"
            )
        if isinstance(case, BenchmarkReductionCorrectnessCase):
            blocks.append(
                _render_reduction_case(
                    set_index,
                    candidate_index,
                    candidate_set,
                    case,
                    profile_module=profile_module,
                )
            )
        else:
            blocks.append(
                _render_case(
                    set_index,
                    candidate_index,
                    candidate_set,
                    case,
                    profile_module=profile_module,
                )
            )
    return f"""fn correct_{set_index}_{candidate_index}() -> Result<(), String> {{
{indent(chr(10).join(blocks), 4)}
    Ok(())
}}"""


def _render_case(
    set_index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkImmediateCorrectnessCase | BenchmarkVectorCorrectnessCase,
    *,
    profile_module: str,
) -> str:
    lanes = candidate_set.key.lanes
    if lanes is None:
        raise ValueError("Rust vector correctness requires a fixed lane count")
    vector_inputs = (
        (case.vector_input,)
        if isinstance(case, BenchmarkImmediateCorrectnessCase)
        else case.vector_inputs
    )
    inputs: list[str] = []
    arguments: list[str] = []
    from_array = rust_raw_identifier(case.from_array_name)
    for argument, values in enumerate(vector_inputs):
        literals = rust_literal_list(values, candidate_set.key.type_tag)
        inputs.append(
            f"let values_{argument}: [Base_{set_index}; {lanes}] = [{literals}];\n"
            f"let mut input_{argument}: <Vec_{set_index} as SimdVector>::Array = "
            "Default::default();\n"
            f"for lane in 0..{lanes} {{ input_{argument}[lane] = values_{argument}[lane]; }}\n"
            f"let value_{argument} = crate::{profile_module}::{from_array}"
            f"::<Vec_{set_index}>(&input_{argument});"
        )
        arguments.append(f"value_{argument}")
    expected = rust_literal_list(case.expected, candidate_set.key.type_tag)
    to_array = rust_raw_identifier(case.to_array_name)
    return f"""{{
{indent(chr(10).join(inputs), 4)}
    let actual = crate::{profile_module}::{to_array}::<Vec_{set_index}>(
        invoke_{set_index}_{candidate_index}({', '.join(arguments)})
    );
    let expected: [Base_{set_index}; {lanes}] = [{expected}];
    for lane in 0..{lanes} {{
        if !actual[lane].lane_eq(expected[lane]) {{
            return Err(format!(
                "correctness failed for {{}} candidate {{}} case {{}} lane {{}}",
                {rust_string_literal(candidate_set.stable_id)},
                {rust_string_literal(candidate_set.candidates[candidate_index].variant_id)},
                {rust_string_literal(case.case_name)},
                lane,
            ));
        }}
    }}
}}"""


def _render_reduction_case(
    set_index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkReductionCorrectnessCase,
    *,
    profile_module: str,
) -> str:
    lanes = candidate_set.key.lanes
    if lanes is None:
        raise ValueError("Rust reduction correctness requires a fixed lane count")
    values = rust_literal_list(case.vector_input, candidate_set.key.type_tag)
    expected = rust_literal(case.expected, candidate_set.key.type_tag)
    from_array = rust_raw_identifier(case.from_array_name)
    return f"""{{
    let values: [Base_{set_index}; {lanes}] = [{values}];
    let mut input: <Vec_{set_index} as SimdVector>::Array = Default::default();
    for lane in 0..{lanes} {{ input[lane] = values[lane]; }}
    let value = crate::{profile_module}::{from_array}::<Vec_{set_index}>(&input);
    let actual = invoke_{set_index}_{candidate_index}(value);
    let expected: Base_{set_index} = {expected};
    if !actual.lane_eq(expected) {{
        return Err(format!(
            "correctness failed for {{}} candidate {{}} case {{}}",
            {rust_string_literal(candidate_set.stable_id)},
            {rust_string_literal(candidate_set.candidates[candidate_index].variant_id)},
            {rust_string_literal(case.case_name)},
        ));
    }}
}}"""


__all__ = ("render_correctness",)
