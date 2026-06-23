"""Render C++ value-test plans."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal, cpp_literal_list, token_truthy
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProfilePlan


def render_cpp_values_runner(profile: ValueTestProfilePlan) -> str:
    functions = [_render_case(case) for case in profile.cases]
    body = "\n\n".join(functions)
    call_lines = "\n".join(f"  failures += {case.function_name}();" for case in profile.cases)
    return (
        "#include <tsl.hpp>\n"
        '#include "tsl_test_core.hpp"\n'
        "#include <cmath>\n"
        "#include <cstddef>\n"
        "#include <cstdint>\n"
        "#include <cstdio>\n\n"
        "namespace {\n\n"
        f"{body}\n\n"
        "}  // namespace\n\n"
        "int main() {\n"
        "  int failures = 0;\n"
        f"{call_lines}\n"
        "  if (failures != 0) {\n"
        '    std::fprintf(stderr, "%d lane failure(s)\\n", failures);\n'
        "    return 1;\n"
        "  }\n"
        "  return 0;\n"
        "}\n"
    )


def _render_case(case: ValueTestCasePlan) -> str:
    if case.kind == "generic_golden":
        return _generic_golden(case)
    if case.kind == "masked":
        return _masked(case)
    if case.kind == "store":
        return _store(case)
    if case.kind == "reduction":
        return _reduction(case)
    if case.kind == "load":
        return _load(case)
    if case.kind == "mask_logic":
        return _mask_logic(case)
    if case.kind == "vector_to_array":
        return _vector_to_array(case)
    if case.kind == "broadcast":
        return _broadcast(case)
    if case.kind == "immediate":
        return _immediate(case)
    if case.kind == "mask_to_vector":
        return _mask_to_vector(case)
    if case.kind == "convert":
        return _convert(case)
    if case.kind == "repr_cast":
        return _repr_cast(case)
    if case.kind == "extension_extract":
        return _extension_extract(case)
    if case.kind == "extension_insert":
        return _extension_insert(case)
    if case.kind == "differential":
        return _differential(case)
    raise ValueError(f"unsupported C++ value-test case kind {case.kind!r}")


def _generic_golden(case: ValueTestCasePlan) -> str:
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    arg_names = _append_vector_inputs(lines, case, "typename Vec::register_type", "v")
    call = f"tsl::{case.call_name}<Vec>({', '.join(arg_names)})"
    if case.result_kind == "m":
        bits = ", ".join("1" if token_truthy(v) else "0" for v in case.expected)
        lines.append(f"  typename Vec::mask_type result = {call};")
        lines.append(f"  static const int expected[{case.lanes}] = {{{bits}}};")
        lines.append(
            f'  return tsl::test::check_mask("{case.case_name}", result, expected, {case.lanes});'
        )
    else:
        expected = cpp_literal_list(case.expected, case.type_tag)
        lines.append(f"  typename Vec::register_type result = {call};")
        lines.append(f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};")
        lines.append(
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", result, expected, {case.lanes});'
        )
    lines.append("}")
    return "\n".join(lines)


def _masked(case: ValueTestCasePlan) -> str:
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {case.mask_inputs[0]}ull;",
    ]
    vector_names = _append_vector_inputs(lines, case, "typename Vec::register_type", "v")
    next_vector = iter(vector_names)
    call_args = ["mask" if kind == "m" else next(next_vector) for kind in case.param_kinds]
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines.append(f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};")
    lines.append(
        f"  typename Vec::register_type result = "
        f"tsl::{case.call_name}<Vec>({', '.join(call_args)});"
    )
    lines.append(
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});'
    )
    lines.append("}")
    return "\n".join(lines)


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


def _convert(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or case.lanes
    expected_type = case.expected_type_tag or case.type_tag
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  using ToVec = tsl::simd<{target}, tsl::generic<{target_lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type a0;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) a0[i] = in0[i];",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f"  typename ToVec::register_type result = "
        f"tsl::{case.call_name}<Vec, ToVec, {case.index_value}>(a0);",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", result, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _repr_cast(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    expected_type = case.expected_type_tag or case.type_tag
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  using ToVec = tsl::simd<{target}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type a0;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) a0[i] = in0[i];",
        f"  static const {target} expected[{case.lanes}] = {{{expected}}};",
        f"  typename ToVec::register_type result = tsl::{case.call_name}<Vec, ToVec>(a0);",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)


def _extension_extract(case: ValueTestCasePlan) -> str:
    out_lanes = len(case.expected)
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{case.source_extension}>;",
        f"  using ToVec = tsl::simd<{case.base_spelling}, tsl::{case.target_extension}>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename tsl::array_for<Vec>::type hin;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) hin[i] = in0[i];",
        f"  auto result = tsl::{case.call_name}<Vec, ToVec, {case.index_value}>("
        f"tsl::{case.from_array_name}<Vec>(hin));",
        f"  typename tsl::array_for<ToVec>::type hout = "
        f"tsl::{case.to_array_name}<ToVec>(result);",
        f"  static const {case.base_spelling} expected[{out_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", hout, expected, {out_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _extension_insert(case: ValueTestCasePlan) -> str:
    out_lanes = len(case.expected)
    orig_lits = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    data_lits = cpp_literal_list(case.vector_inputs[1], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using DataVec = tsl::simd<{case.base_spelling}, tsl::{case.source_extension}>;",
        f"  using ResultVec = tsl::simd<{case.base_spelling}, tsl::{case.target_extension}>;",
        f"  static const {case.base_spelling} orig0[{out_lanes}] = {{{orig_lits}}};",
        f"  static const {case.base_spelling} data0[{case.lanes}] = {{{data_lits}}};",
        "  typename tsl::array_for<ResultVec>::type horig;",
        "  typename tsl::array_for<DataVec>::type hdata;",
        f"  for (std::size_t i = 0; i < {out_lanes}; ++i) horig[i] = orig0[i];",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) hdata[i] = data0[i];",
        f"  auto result = tsl::{case.call_name}<DataVec, ResultVec, {case.index_value}>("
        f"tsl::{case.from_array_name}<ResultVec>(horig), "
        f"tsl::{case.from_array_name}<DataVec>(hdata));",
        f"  typename tsl::array_for<ResultVec>::type hout = "
        f"tsl::{case.to_array_name}<ResultVec>(result);",
        f"  static const {case.base_spelling} expected[{out_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", hout, expected, {out_lanes});',
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


def _mask_logic(case: ValueTestCasePlan) -> str:
    expected_int = int(case.expected[0])
    bits = ", ".join("1" if (expected_int >> i) & 1 else "0" for i in range(case.lanes))
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    arg_names = []
    for position, mask in enumerate(case.mask_inputs):
        lines.append(f"  typename Vec::mask_type m{position} = {mask}ull;")
        arg_names.append(f"m{position}")
    lines.append(
        f"  typename Vec::mask_type result = "
        f"tsl::{case.call_name}<Vec>({', '.join(arg_names)});"
    )
    lines.append(f"  static const int expected[{case.lanes}] = {{{bits}}};")
    lines.append(f'  return tsl::test::check_mask("{case.case_name}", result, expected, {case.lanes});')
    lines.append("}")
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


def _load(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    axis = _axis_suffix(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} data[{case.lanes}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{case.buffer_offset + case.lanes}] = {{0}};",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
        f"buf[{case.buffer_offset} + i] = data[i];",
        f"  typename Vec::register_type result = "
        f"tsl::{case.call_name}<Vec{axis}>(buf + {case.buffer_offset});",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)


def _store(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    axis = _axis_suffix(case)
    buflen = case.buffer_length or len(case.expected)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v[i] = in0[i];",
        f"  {case.base_spelling} buf[{buflen}] = {{0}};",
        f"  tsl::{case.call_name}<Vec{axis}>(buf + {case.buffer_offset}, v);",
        f"  static const {case.base_spelling} expected[{buflen}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", buf, expected, {buflen});',
        "}",
    ]
    return "\n".join(lines)


def _differential(case: ValueTestCasePlan) -> str:
    lines = [
        f"int {case.function_name}() {{",
        f"  using Hw = tsl::simd<{case.base_spelling}, tsl::{case.hardware_extension}>;",
        f"  using Ref = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    hw_args = []
    ref_args = []
    for position, values in enumerate(case.vector_inputs):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(f"  static const {case.base_spelling} in{position}[{case.lanes}] = {{{literals}}};")
        lines.append(f"  typename tsl::array_for<Hw>::type hin{position};")
        lines.append(f"  typename Ref::register_type r{position};")
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
            f"{{ hin{position}[i] = in{position}[i]; r{position}[i] = in{position}[i]; }}"
        )
        hw_args.append(f"tsl::{case.from_array_name}<Hw>(hin{position})")
        ref_args.append(f"r{position}")
    hw_call = f"tsl::{case.call_name}<Hw>({', '.join(hw_args)})"
    ref_call = f"tsl::{case.call_name}<Ref>({', '.join(ref_args)})"
    if case.result_kind == "m":
        lines.append(f"  auto hw = tsl::{case.to_integral_name}<Hw>({hw_call});")
        lines.append(f"  typename Ref::mask_type ref = {ref_call};")
        lines.append(f'  return tsl::test::check_mask_match("{case.function_name}", hw, ref, {case.lanes});')
    else:
        lines.append(f"  typename tsl::array_for<Hw>::type hout = tsl::{case.to_array_name}<Hw>({hw_call});")
        lines.append(f"  typename Ref::register_type ref = {ref_call};")
        lines.append(
            f'  return tsl::test::check_match<{case.base_spelling}>('
            f'"{case.function_name}", hout, ref, {case.lanes});'
        )
    lines.append("}")
    return "\n".join(lines)


def _append_vector_inputs(
    lines: list[str],
    case: ValueTestCasePlan,
    register_type: str,
    prefix: str,
) -> list[str]:
    names: list[str] = []
    for position, values in enumerate(case.vector_inputs):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(f"  static const {case.base_spelling} in{position}[{case.lanes}] = {{{literals}}};")
        lines.append(f"  {register_type} {prefix}{position};")
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
            f"{prefix}{position}[i] = in{position}[i];"
        )
        names.append(f"{prefix}{position}")
    return names


def _axis_suffix(case: ValueTestCasePlan) -> str:
    return "".join(f", {value}" for value in case.axis_args)


__all__ = ["render_cpp_values_runner"]
