"""Render core C++ value-test cases."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests.render_cpp_helpers import (
    append_call_args as _append_call_args,
    scalar_expected as _scalar_expected,
    scalar_result_type as _scalar_result_type,
)

# The golden and masked case shapes (fixed `generic<N>` and scalable SVE alike) are rendered
# by the shared lane-model renderers in `lane_model`; the renderers below cover the remaining
# fixed-lane case shapes.


def _mask_to_vector(case: ValueTestCasePlan) -> str:
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {case.mask_inputs[0]}ull;",
        f"  typename Vec::register_type result = tsl::{case.call_name}<Vec>(mask);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _immediate(case: ValueTestCasePlan) -> str:
    lines = [f"int {case.function_name}() {{"]
    arg_names = []
    for position, values in enumerate(case.vector_inputs):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(f"  static const {case.base_spelling} in{position}[{case.lanes}] = {{{literals}}};")
        lines.append(
            f"  typename tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>::register_type "
            f"a{position};"
        )
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) a{position}[i] = in{position}[i];"
        )
        arg_names.append(f"a{position}")
    expected = cpp_literal_list(case.expected, case.type_tag)
    targs = [f"tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>"]
    if case.immediate_value is not None:
        targs.append(case.immediate_value)
    targs.extend(case.generic_defaults)
    lines.append(f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};")
    lines.append(
        f"  auto result = tsl::{case.call_name}<{', '.join(targs)}>({', '.join(arg_names)});"
    )
    lines.append(
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});'
    )
    lines.append("}")
    return "\n".join(lines)

def _compile_only(case: ValueTestCasePlan) -> str:
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _append_call_args(lines, case)
    call = f"tsl::{case.call_name}<Vec>({', '.join(args)})"
    if case.result_kind == "void":
        lines.append(f"  {call};")
    else:
        lines.append(f"  auto result = {call};")
        lines.append("  (void)result;")
    lines.append("  return 0;")
    lines.append("}")
    return "\n".join(lines)

def _array_to_vector(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename tsl::array_for<Vec>::type values;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) values[i] = in0[i];",
        f"  typename Vec::register_type result = tsl::{case.call_name}<Vec>(values);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _broadcast(case: ValueTestCasePlan) -> str:
    value = cpp_literal(case.scalar_input or "0", case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  {case.base_spelling} value = {value};",
        f"  typename Vec::register_type result = tsl::{case.call_name}<Vec>(value);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _scalar_vector(case: ValueTestCasePlan) -> str:
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _append_call_args(lines, case)
    lines.append(f"  typename Vec::register_type result = tsl::{case.call_name}<Vec>({', '.join(args)});")
    lines.append(f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};")
    lines.append(
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});'
    )
    lines.append("}")
    return "\n".join(lines)

def _vector_to_array(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v[i] = in0[i];",
        f"  typename tsl::array_for<Vec>::type result = tsl::{case.call_name}<Vec>(v);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _scalar_result(case: ValueTestCasePlan) -> str:
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _append_call_args(lines, case)
    template_args = ["Vec"]
    if case.index_value is not None:
        template_args.append(case.index_value)
    result_type = _scalar_result_type(case)
    expected = _scalar_expected(case, result_type)
    lines.append(
        f"  auto result = tsl::{case.call_name}<{', '.join(template_args)}>({', '.join(args)});"
    )
    lines.append(f"  {result_type} expected = {expected};")
    lines.append(
        f'  return tsl::test::check_scalar<{result_type}>("{case.case_name}", result, expected);'
    )
    lines.append("}")
    return "\n".join(lines)

def _lane_list(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename tsl::array_for<Vec>::type values;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) values[i] = in0[i];",
        f"  typename Vec::register_type result = tsl::{case.call_name}<Vec>(values);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _reduction(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal(case.expected[0], case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v[i] = in0[i];",
        f"  {case.base_spelling} result = tsl::{case.call_name}<Vec>(v);",
        f"  static const {case.base_spelling} expected = {expected};",
        f'  return tsl::test::check_scalar<{case.base_spelling}>('
        f'"{case.case_name}", result, expected);',
        "}",
    ]
    return "\n".join(lines)

__all__ = (
    "_mask_to_vector",
    "_immediate",
    "_compile_only",
    "_array_to_vector",
    "_broadcast",
    "_scalar_vector",
    "_vector_to_array",
    "_scalar_result",
    "_lane_list",
    "_reduction",
)
