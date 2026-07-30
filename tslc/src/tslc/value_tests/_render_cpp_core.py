"""Render core C++ value-test cases."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests.render_cpp_helpers import (
    append_call_args as _append_call_args,
    append_runtime_vector_input as _append_runtime_vector_input,
    scalable_header as _scalable_header,
    scalable_mask_from_bits as _scalable_mask_from_bits,
    scalar_expected as _scalar_expected,
    scalar_result_type as _scalar_result_type,
)

# The golden and masked case shapes (fixed `generic<N>` and scalable SVE alike) are rendered
# by the shared lane-model renderers in `lane_model`; the renderers below cover the remaining
# fixed-lane case shapes.


def _mask_to_vector(case: ValueTestCasePlan) -> str:
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {case.inputs.masks[0]}ull;",
        f"  typename Vec::register_type result = tsl::{case.call_name}<Vec>(mask);",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _immediate(case: ValueTestCasePlan) -> str:
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    for position, values in enumerate(case.inputs.vectors):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(f"  static const {case.base_spelling} in{position}[{case.lanes}] = {{{literals}}};")
        lines.append(
            f"  typename Vec::register_type a{position};"
        )
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) a{position}[i] = in{position}[i];"
        )
    arg_names: list[str] = []
    vector_index = 0
    mask_index = 0
    param_kinds = case.invocation.param_kinds or (
        ("v",) * len(case.inputs.vectors) + ("sImm",)
    )
    for kind in param_kinds:
        if kind == "v":
            arg_names.append(f"a{vector_index}")
            vector_index += 1
        elif kind == "m":
            lines.append(
                f"  typename Vec::mask_type m{mask_index} = "
                f"{case.inputs.masks[mask_index]}ull;"
            )
            arg_names.append(f"m{mask_index}")
            mask_index += 1
        elif kind != "sImm":
            raise ValueError(f"unsupported immediate argument kind {kind!r}")
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    targs = ["Vec"]
    if case.invocation.immediate is not None:
        targs.append(case.invocation.immediate)
    targs.extend(case.invocation.generic_defaults)
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
    if case.invocation.result_kind == "void":
        lines.append(f"  {call};")
    else:
        lines.append(f"  auto result = {call};")
        lines.append("  (void)result;")
    lines.append("  return 0;")
    lines.append("}")
    return "\n".join(lines)


def _runtime_failure(case: ValueTestCasePlan) -> str:
    assert case.failure is not None
    marker = case.failure.marker
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _append_call_args(lines, case)
    call = f"tsl::{case.call_name}<Vec>({', '.join(args)})"
    lines.extend(
        [
            "  try {",
            f"    (void){call};",
            "  } catch (const std::domain_error& error) {",
            f'    return std::string(error.what()) == "{marker}" ? 0 : 1;',
            "  } catch (...) {",
            "    return 1;",
            "  }",
            "  return 1;",
            "}",
        ]
    )
    return "\n".join(lines)


def _scalable_runtime_failure(case: ValueTestCasePlan) -> str:
    assert case.failure is not None
    lines = _scalable_header(case)
    args: list[str] = []
    vector_index = 0
    mask_index = 0
    for kind in case.invocation.param_kinds:
        if kind == "v":
            args.append(_append_runtime_vector_input(lines, case, vector_index))
            vector_index += 1
        elif kind == "m":
            lines.append(
                f"  typename Vec::mask_type m{mask_index} = "
                f"{_scalable_mask_from_bits(case, mask_index)};"
            )
            args.append(f"m{mask_index}")
            mask_index += 1
        else:
            raise ValueError(
                f"scalable runtime-failure test does not support argument kind {kind!r}"
            )
    call = f"tsl::{case.call_name}<Vec>({', '.join(args)})"
    lines.extend(
        [
            "  try {",
            f"    (void){call};",
            "  } catch (const std::domain_error& error) {",
            f'    return std::string(error.what()) == "{case.failure.marker}" ? 0 : 1;',
            "  } catch (...) {",
            "    return 1;",
            "  }",
            "  return 1;",
            "}",
        ]
    )
    return "\n".join(lines)


def _status_pointer(case: ValueTestCasePlan) -> str:
    value = cpp_literal(case.inputs.scalars[0], case.type_tag)
    return "\n".join(
        [
            f"int {case.function_name}() {{",
            f"  {case.base_spelling} value = {value};",
            f"  const {case.base_spelling} before = value;",
            f"  const std::size_t status = tsl::{case.call_name}(&value);",
            "  if (status > 1) return 1;",
            "  if (status == 0 && value != before) return 1;",
            "  return 0;",
            "}",
        ]
    )

def _array_to_vector(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
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
    assert case.inputs.scalar is not None
    value = cpp_literal(case.inputs.scalar, case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
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
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _append_call_args(lines, case)
    template_args = ["Vec"]
    if case.index is not None and case.index.value is not None:
        template_args.append(case.index.value)
    template_args.extend(case.invocation.generic_defaults)
    lines.append(
        f"  typename Vec::register_type result = "
        f"tsl::{case.call_name}<{', '.join(template_args)}>({', '.join(args)});"
    )
    lines.append(f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};")
    lines.append(
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});'
    )
    lines.append("}")
    return "\n".join(lines)

def _vector_to_array(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
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
    if case.index is not None and case.index.value is not None:
        template_args.append(case.index.value)
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


def _scalable_mask_count(case: ValueTestCasePlan) -> str:
    scalable = case.scalable
    assert scalable is not None
    lines = _scalable_header(case)
    lines.extend(
        [
            "  typename Vec::mask_type mask = "
            f"{_scalable_mask_from_bits(case, 0)};",
            f"  auto result = tsl::{case.call_name}<Vec>(mask);",
            f"  constexpr std::uint64_t authored_mask = "
            f"{scalable.mask_bits[0]}ull;",
            "  std::size_t expected = 0;",
            "  for (std::size_t i = 0; i < lanes; ++i) {",
            f"    expected += static_cast<std::size_t>("
            f"(authored_mask >> (i % {case.lanes})) & 1ull);",
            "  }",
            f'  return tsl::test::check_scalar<std::size_t>("'
            f'{case.case_name}", result, expected);',
            "}",
        ]
    )
    return "\n".join(lines)


def _lane_list(case: ValueTestCasePlan) -> str:
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
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
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal(case.expectation.values[0], case.type_tag)
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
    "_runtime_failure",
    "_scalable_runtime_failure",
    "_array_to_vector",
    "_broadcast",
    "_scalar_vector",
    "_vector_to_array",
    "_scalar_result",
    "_scalable_mask_count",
    "_lane_list",
    "_reduction",
    "_status_pointer",
)
