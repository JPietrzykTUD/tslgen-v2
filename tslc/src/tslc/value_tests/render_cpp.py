"""Render C++ value-test plans."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal, cpp_literal_list, token_truthy
from tslc.value_tests.model import (
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestProfilePlan,
)
from tslc.value_tests.render_cpp_helpers import (
    append_call_args as _append_call_args,
    append_vector_inputs as _append_vector_inputs,
    axis_suffix as _axis_suffix,
    cast_literal_list as _cast_literal_list,
    cpp_string_literal as _cpp_string_literal,
    scalar_expected as _scalar_expected,
    scalar_result_type as _scalar_result_type,
    uint_literal as _uint_literal,
)

CPP_VALUE_TEST_SUPPORT = ValueTestBackendSupport(
    backend_id="cpp",
    case_kinds=frozenset(
        {
            "array_to_vector",
            "broadcast",
            "compile_only",
            "convert",
            "differential",
            "extension_extract",
            "extension_insert",
            "generic_golden",
            "immediate",
            "indexed_load",
            "indexed_store",
            "lane_list",
            "load",
            "load_convert",
            "mask_logic",
            "mask_pointer_load",
            "mask_result",
            "mask_store",
            "mask_to_vector",
            "masked",
            "masked_pointer_load",
            "masked_pointer_store",
            "memory_copy",
            "pointer_free",
            "pointer_lifetime",
            "reduction",
            "repr_cast",
            "scalar_pointer_load",
            "scalar_result",
            "scalar_vector",
            "store",
            "stream",
            "vector_to_array",
        }
    ),
    supports_differential=True,
)


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
        "#include <cstdlib>\n"
        "#include <string>\n\n"
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
    if case.kind == "compile_only":
        return _compile_only(case)
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
    if case.kind == "array_to_vector":
        return _array_to_vector(case)
    if case.kind == "broadcast":
        return _broadcast(case)
    if case.kind == "scalar_vector":
        return _scalar_vector(case)
    if case.kind == "lane_list":
        return _lane_list(case)
    if case.kind == "immediate":
        return _immediate(case)
    if case.kind == "mask_to_vector":
        return _mask_to_vector(case)
    if case.kind == "mask_result":
        return _mask_result(case)
    if case.kind == "scalar_result":
        return _scalar_result(case)
    if case.kind == "scalar_pointer_load":
        return _scalar_pointer_load(case)
    if case.kind == "mask_pointer_load":
        return _mask_pointer_load(case)
    if case.kind == "mask_store":
        return _mask_store(case)
    if case.kind == "masked_pointer_load":
        return _masked_pointer_load(case)
    if case.kind == "masked_pointer_store":
        return _masked_pointer_store(case)
    if case.kind == "memory_copy":
        return _memory_copy(case)
    if case.kind == "pointer_lifetime":
        return _pointer_lifetime(case)
    if case.kind == "pointer_free":
        return _pointer_free(case)
    if case.kind == "load_convert":
        return _load_convert(case)
    if case.kind == "indexed_load":
        return _indexed_load(case)
    if case.kind == "indexed_store":
        return _indexed_store(case)
    if case.kind == "stream":
        return _stream(case)
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
    if case.source_extension is not None:
        return _fixed_extension_repr_cast(case)
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
        f"  typename ToVec::register_type result = tsl::{case.call_name}<Vec, ToVec>(a0);",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", result, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _fixed_extension_repr_cast(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or case.lanes
    expected_type = case.expected_type_tag or case.type_tag
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{case.source_extension}>;",
        f"  using ToVec = tsl::simd<{target}, tsl::{case.target_extension}>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename tsl::array_for<Vec>::type hin;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) hin[i] = in0[i];",
        f"  auto result = tsl::{case.call_name}<Vec, ToVec>("
        f"tsl::{case.from_array_name}<Vec>(hin));",
        f"  typename tsl::array_for<ToVec>::type hout = "
        f"tsl::{case.to_array_name}<ToVec>(result);",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", hout, expected, {target_lanes});',
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


def _mask_result(case: ValueTestCasePlan) -> str:
    expected_int = int(case.expected[0])
    bits = ", ".join("1" if (expected_int >> i) & 1 else "0" for i in range(case.lanes))
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _append_call_args(lines, case)
    lines.append(
        f"  typename Vec::mask_type result = tsl::{case.call_name}<Vec>({', '.join(args)});"
    )
    lines.append(f"  static const int expected[{case.lanes}] = {{{bits}}};")
    lines.append(f'  return tsl::test::check_mask("{case.case_name}", result, expected, {case.lanes});')
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


def _scalar_pointer_load(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal(case.expected[0], case.type_tag)
    axis = _axis_suffix(case)
    buflen = case.buffer_length or len(case.vector_inputs[0])
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{buflen}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{buflen}] = {{0}};",
        f"  for (std::size_t i = 0; i < {buflen}; ++i) buf[i] = in0[i];",
        f"  {case.base_spelling} result = tsl::{case.call_name}<Vec{axis}>(buf + {case.buffer_offset});",
        f"  {case.base_spelling} expected = {expected};",
        f'  return tsl::test::check_scalar<{case.base_spelling}>("{case.case_name}", result, expected);',
        "}",
    ]
    return "\n".join(lines)


def _mask_pointer_load(case: ValueTestCasePlan) -> str:
    expected_int = int(case.expected[0])
    bits = ", ".join("1" if (expected_int >> i) & 1 else "0" for i in range(case.lanes))
    input_type = case.expected_type_tag or case.type_tag
    storage_type = case.target_base_spelling or case.base_spelling
    literals = cpp_literal_list(case.vector_inputs[0], input_type)
    axis = _axis_suffix(case)
    buflen = case.buffer_length or len(case.vector_inputs[0])
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {storage_type} in0[{buflen}] = {{{literals}}};",
        f"  {storage_type} buf[{buflen}] = {{0}};",
        f"  for (std::size_t i = 0; i < {buflen}; ++i) buf[i] = in0[i];",
        f"  typename Vec::mask_type result = tsl::{case.call_name}<Vec{axis}>("
        f"reinterpret_cast<typename Vec::base_type *>(buf + {case.buffer_offset}));",
        f"  static const int expected[{case.lanes}] = {{{bits}}};",
        f'  return tsl::test::check_mask("{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)


def _mask_store(case: ValueTestCasePlan) -> str:
    packed = case.result_kind == "packed"
    unpacked_type = case.target_base_spelling or case.base_spelling
    unpacked_tag = case.expected_type_tag or case.type_tag
    buffer_type = "typename Vec::imask_type" if packed else unpacked_type
    expected = (
        _cast_literal_list(case.expected, "typename Vec::imask_type")
        if packed
        else cpp_literal_list(case.expected, unpacked_tag)
    )
    axis = _axis_suffix(case)
    buflen = case.buffer_length or len(case.expected)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {_uint_literal(case.mask_inputs[0])};",
        f"  {buffer_type} buf[{buflen}] = {{0}};",
        f"  static const {buffer_type} expected[{buflen}] = {{{expected}}};",
        f"  return tsl::test::check_lanes<{buffer_type}>("
        f'"{case.case_name}", buf, expected, {buflen});',
        "}",
    ]
    call = (
        f"  tsl::{case.call_name}<Vec{axis}>("
        f"reinterpret_cast<typename Vec::base_type *>(buf + {case.buffer_offset}), mask);"
    )
    lines.insert(5, call)
    return "\n".join(lines)


def _masked_pointer_load(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    axis = _axis_suffix(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {_uint_literal(case.mask_inputs[0])};",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{case.lanes}] = {{0}};",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) buf[i] = in0[i];",
        f"  typename Vec::register_type result = tsl::{case.call_name}<Vec{axis}>(mask, buf);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)


def _masked_pointer_store(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    axis = _axis_suffix(case)
    buflen = case.buffer_length or len(case.expected)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {_uint_literal(case.mask_inputs[0])};",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v[i] = in0[i];",
        f"  {case.base_spelling} buf[{buflen}] = {{0}};",
        f"  tsl::{case.call_name}<Vec{axis}>(mask, buf, v);",
        f"  static const {case.base_spelling} expected[{buflen}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", buf, expected, {buflen});',
        "}",
    ]
    return "\n".join(lines)


def _memory_copy(case: ValueTestCasePlan) -> str:
    src = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    src_len = len(case.vector_inputs[0])
    dst_len = case.buffer_length or len(case.expected)
    count = case.scalar_inputs[0] if case.scalar_inputs else str(src_len)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} src_in[{src_len}] = {{{src}}};",
        f"  {case.base_spelling} src[{src_len + case.source_offset}] = {{0}};",
        f"  {case.base_spelling} dst[{dst_len}] = {{0}};",
        f"  for (std::size_t i = 0; i < {src_len}; ++i) src[{case.source_offset} + i] = src_in[i];",
        f"  tsl::{case.call_name}<Vec>(dst + {case.buffer_offset}, src + {case.source_offset}, "
        f"static_cast<{case.base_spelling}>({count}), static_cast<{case.base_spelling}>(0));",
        f"  static const {case.base_spelling} expected[{dst_len}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", dst, expected, {dst_len});',
        "}",
    ]
    return "\n".join(lines)


def _pointer_lifetime(case: ValueTestCasePlan) -> str:
    args = ", ".join(f"static_cast<std::size_t>({value})" for value in case.scalar_inputs)
    alignment = case.scalar_inputs[1] if len(case.scalar_inputs) > 1 else None
    lines = [
        f"int {case.function_name}() {{",
        f"  void* ptr = tsl::{case.call_name}({args});",
        "  int failures = 0;",
        f'  if (ptr == nullptr) {{ std::fprintf(stderr, "FAIL {case.case_name}: null pointer\\n"); ++failures; }}',
    ]
    if alignment is not None:
        lines.append(
            f"  if (ptr != nullptr && (reinterpret_cast<std::uintptr_t>(ptr) % "
            f"static_cast<std::size_t>({alignment})) != 0) {{ ++failures; }}"
        )
    lines.append("  std::free(ptr);")
    lines.append("  return failures;")
    lines.append("}")
    return "\n".join(lines)


def _pointer_free(case: ValueTestCasePlan) -> str:
    count = case.scalar_inputs[0] if case.scalar_inputs else "1"
    alignment = case.target_base_spelling
    alloc = (
        f"std::aligned_alloc(static_cast<std::size_t>({alignment}), static_cast<std::size_t>({count}))"
        if alignment is not None
        else f"std::malloc(static_cast<std::size_t>({count}))"
    )
    lines = [
        f"int {case.function_name}() {{",
        f"  void* ptr = {alloc};",
        f'  if (ptr == nullptr) {{ std::fprintf(stderr, "FAIL {case.case_name}: setup allocation failed\\n"); return 1; }}',
        f"  tsl::{case.call_name}(ptr);",
        "  return 0;",
        "}",
    ]
    return "\n".join(lines)


def _load_convert(case: ValueTestCasePlan) -> str:
    if case.source_extension is not None:
        return _fixed_extension_load_convert(case)
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or len(case.expected)
    expected_type = case.expected_type_tag or case.type_tag
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  using ToVec = tsl::simd<{target}, tsl::generic<{target_lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{case.lanes}] = {{0}};",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) buf[i] = in0[i];",
        f"  typename ToVec::register_type result = tsl::{case.call_name}<Vec, ToVec>(buf);",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", result, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _fixed_extension_load_convert(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or len(case.expected)
    expected_type = case.expected_type_tag or case.type_tag
    buffer_len = len(case.vector_inputs[0])
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    expected = cpp_literal_list(case.expected, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{case.source_extension}>;",
        f"  using ToVec = tsl::simd<{target}, tsl::{case.target_extension}>;",
        f"  static const {case.base_spelling} in0[{buffer_len}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{buffer_len}] = {{0}};",
        f"  for (std::size_t i = 0; i < {buffer_len}; ++i) buf[i] = in0[i];",
        f"  auto result = tsl::{case.call_name}<Vec, ToVec>(buf);",
        f"  typename tsl::array_for<ToVec>::type hout = "
        f"tsl::{case.to_array_name}<ToVec>(result);",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", hout, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _indexed_load(case: ValueTestCasePlan) -> str:
    data = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    indices = cpp_literal_list(case.vector_inputs[1], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lanes = case.target_lanes or len(case.expected)
    scale = case.immediate_value or "1"
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  using Indices = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  static const {case.base_spelling} data_in[{len(case.vector_inputs[0])}] = {{{data}}};",
        f"  static const {case.base_spelling} idx_in[{lanes}] = {{{indices}}};",
        f"  {case.base_spelling} data[{len(case.vector_inputs[0])}] = {{0}};",
        f"  for (std::size_t i = 0; i < {len(case.vector_inputs[0])}; ++i) data[i] = data_in[i];",
        "  typename Indices::register_type idx;",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) idx[i] = idx_in[i];",
    ]
    if case.mask_inputs:
        source = cpp_literal_list(case.vector_inputs[2], case.type_tag)
        lines.append(f"  typename Vec::mask_type mask = {_uint_literal(case.mask_inputs[0])};")
        lines.append(f"  static const {case.base_spelling} source_in[{lanes}] = {{{source}}};")
        lines.append("  typename Vec::register_type source;")
        lines.append(f"  for (std::size_t i = 0; i < {lanes}; ++i) source[i] = source_in[i];")
        lines.append(
            f"  typename Vec::register_type result = "
            f"tsl::{case.call_name}<Vec, Indices, {scale}>(mask, data, idx, source);"
        )
    else:
        lines.append(
            f"  typename Vec::register_type result = "
            f"tsl::{case.call_name}<Vec, Indices, {scale}>(data, idx);"
        )
    lines.extend(
        [
            f"  static const {case.base_spelling} expected[{lanes}] = {{{expected}}};",
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", result, expected, {lanes});',
            "}",
        ]
    )
    return "\n".join(lines)


def _indexed_store(case: ValueTestCasePlan) -> str:
    values = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    indices = cpp_literal_list(case.vector_inputs[1], case.type_tag)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lanes = case.lanes
    scale = case.immediate_value or "1"
    buflen = case.buffer_length or len(case.expected)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  using Indices = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  static const {case.base_spelling} value_in[{lanes}] = {{{values}}};",
        f"  static const {case.base_spelling} idx_in[{lanes}] = {{{indices}}};",
        f"  {case.base_spelling} data[{buflen}] = {{0}};",
        "  typename Vec::register_type values;",
        "  typename Indices::register_type idx;",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) {{ values[i] = value_in[i]; idx[i] = idx_in[i]; }}",
    ]
    if case.mask_inputs:
        lines.append(f"  typename Vec::mask_type mask = {_uint_literal(case.mask_inputs[0])};")
        lines.append(f"  tsl::{case.call_name}<Vec, Indices, {scale}>(mask, data, idx, values);")
    else:
        lines.append(f"  tsl::{case.call_name}<Vec, Indices, {scale}>(data, idx, values);")
    lines.extend(
        [
            f"  static const {case.base_spelling} expected[{buflen}] = {{{expected}}};",
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", data, expected, {buflen});',
            "}",
        ]
    )
    return "\n".join(lines)


def _stream(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    modifier = case.scalar_inputs[0] if case.scalar_inputs else "0"
    expected = _cpp_string_literal(case.text_expected or "")
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v[i] = in0[i];",
        "  std::string out;",
        f"  std::string result = tsl::{case.call_name}<Vec>(out, v, static_cast<{case.base_spelling}>({modifier}));",
        f"  if (result == {expected}) return 0;",
        f'  std::fprintf(stderr, "FAIL {case.case_name}: stream output mismatch\\n");',
        "  return 1;",
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


__all__ = ["CPP_VALUE_TEST_SUPPORT", "render_cpp_values_runner"]
