"""Render authored benchmark correctness checks as C++."""

from __future__ import annotations

import json

from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkImmediateCorrectnessCase,
    BenchmarkIndexedLoadCorrectnessCase,
    BenchmarkMaskCorrectnessCase,
    BenchmarkReductionCorrectnessCase,
    BenchmarkVectorCorrectnessCase,
    BenchmarkVectorMaskCorrectnessCase,
    BenchmarkVectorScalarCorrectnessCase,
)
from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.render_cpp_helpers import uint_literal


def render_correctness(
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
        elif isinstance(case, BenchmarkVectorMaskCorrectnessCase):
            case_blocks.append(
                _render_vector_mask_correctness_case(
                    index,
                    candidate_index,
                    candidate_set,
                    case,
                )
            )
        elif isinstance(case, BenchmarkReductionCorrectnessCase):
            case_blocks.append(
                _render_reduction_correctness_case(
                    index,
                    candidate_index,
                    candidate_set,
                    case,
                )
            )
        elif isinstance(case, BenchmarkVectorScalarCorrectnessCase):
            case_blocks.append(
                _render_vector_scalar_correctness_case(
                    index,
                    candidate_index,
                    candidate_set,
                    case,
                )
            )
        elif isinstance(case, BenchmarkImmediateCorrectnessCase):
            case_blocks.append(
                _render_immediate_correctness_case(
                    index,
                    candidate_index,
                    candidate_set,
                    case,
                )
            )
        elif isinstance(case, BenchmarkIndexedLoadCorrectnessCase):
            case_blocks.append(
                _render_indexed_load_correctness_case(
                    index,
                    candidate_index,
                    candidate_set,
                    case,
                )
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


def _render_vector_scalar_correctness_case(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkVectorScalarCorrectnessCase,
) -> str:
    values = cpp_literal_list(case.vector_input, candidate_set.key.type_tag)
    scalar = cpp_literal(case.scalar_input, candidate_set.key.type_tag)
    expected = cpp_literal_list(case.expected, candidate_set.key.type_tag)
    return f'''{{
    typename tsl::array_for<Vec_{index}>::type input = {{{values}}};
    const auto value = tsl::{case.from_array_name}<Vec_{index}>(input);
    const Base_{index} scalar = {scalar};
    const auto result = invoke_{index}<{candidate_index}>(value, scalar);
    const auto actual = tsl::{case.to_array_name}<Vec_{index}>(result);
    const Base_{index} expected[] = {{{expected}}};
    failures += tsl::test::check_lanes<Base_{index}>(
        {_cpp_string(case.case_name)}, actual, expected, {len(case.expected)});
}}'''


def _render_immediate_correctness_case(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkImmediateCorrectnessCase,
) -> str:
    values = cpp_literal_list(case.vector_input, candidate_set.key.type_tag)
    expected = cpp_literal_list(case.expected, candidate_set.key.type_tag)
    return f'''{{
    typename tsl::array_for<Vec_{index}>::type input = {{{values}}};
    const auto value = tsl::{case.from_array_name}<Vec_{index}>(input);
    const auto result = invoke_{index}<{candidate_index}>(value);
    const auto actual = tsl::{case.to_array_name}<Vec_{index}>(result);
    const Base_{index} expected[] = {{{expected}}};
    failures += tsl::test::check_lanes<Base_{index}>(
        {_cpp_string(case.case_name)}, actual, expected, {len(case.expected)});
}}'''


def _render_indexed_load_correctness_case(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkIndexedLoadCorrectnessCase,
) -> str:
    memory = cpp_literal_list(case.memory_values, candidate_set.key.type_tag)
    indices = cpp_literal_list(case.index_values, case.index_type_tag)
    expected = cpp_literal_list(case.expected, candidate_set.key.type_tag)
    return f'''{{
    Base_{index} memory[] = {{{memory}}};
    typename tsl::array_for<IndexVec_{index}>::type index_lanes = {{{indices}}};
    const auto index_value =
        tsl::{case.from_array_name}<IndexVec_{index}>(index_lanes);
    const auto result = invoke_{index}<{candidate_index}>(memory, index_value);
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


def _render_vector_mask_correctness_case(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkVectorMaskCorrectnessCase,
) -> str:
    arrays = "\n".join(
        f"    typename tsl::array_for<Vec_{index}>::type input_{argument} = "
        f"{{{cpp_literal_list(values, candidate_set.key.type_tag)}}};\n"
        f"    const auto value_{argument} = "
        f"tsl::{case.from_array_name}<Vec_{index}>(input_{argument});"
        for argument, values in enumerate(case.vector_inputs)
    )
    arguments = ", ".join(
        f"value_{argument}" for argument, _values in enumerate(case.vector_inputs)
    )
    expected = uint_literal(case.expected_mask)
    return f'''{{
{arrays}
    const auto result = invoke_{index}<{candidate_index}>({arguments});
    const Imask_{index} actual = static_cast<Imask_{index}>(
        tsl::{case.to_integral_name}<Vec_{index}>(result));
    const Imask_{index} expected = static_cast<Imask_{index}>({expected});
    failures += tsl::test::check_scalar<Imask_{index}>(
        {_cpp_string(case.case_name)}, actual, expected);
}}'''


def _render_reduction_correctness_case(
    index: int,
    candidate_index: int,
    candidate_set: BenchmarkCandidateSet,
    case: BenchmarkReductionCorrectnessCase,
) -> str:
    values = cpp_literal_list(case.vector_input, candidate_set.key.type_tag)
    expected = cpp_literal(case.expected, candidate_set.key.type_tag)
    return f'''{{
    typename tsl::array_for<Vec_{index}>::type input = {{{values}}};
    const auto value = tsl::{case.from_array_name}<Vec_{index}>(input);
    const Base_{index} actual = invoke_{index}<{candidate_index}>(value);
    const Base_{index} expected = {expected};
    failures += tsl::test::check_scalar<Base_{index}>(
        {_cpp_string(case.case_name)}, actual, expected);
}}'''


def _cpp_string(value: str) -> str:
    return json.dumps(value)


def _indent(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in value.splitlines())


__all__ = ("render_correctness",)

