"""Render conversion and extension C++ value-test cases."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan

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

def _differential_fuzz(case: ValueTestCasePlan) -> str:
    """A runtime PRNG loop comparing `prim<Hw>` to the generic reference `prim<Ref>` over many
    random inputs. On the first disagreement it prints the failing lane (via check_match) plus the
    reproducing iteration, seed, and the per-lane inputs, then fails."""

    arity = len(case.param_kinds)
    lanes = case.lanes
    base = case.base_spelling
    lines = [
        f"int {case.function_name}() {{",
        f"  using Hw = tsl::simd<{base}, tsl::{case.hardware_extension}>;",
        f"  using Ref = tsl::simd<{base}, tsl::generic<{lanes}>>;",
        f"  std::uint64_t rng = {case.fuzz_seed}ULL;",
        f"  for (std::size_t iter = 0; iter < {case.fuzz_iterations}; ++iter) {{",
    ]
    for position in range(arity):
        lines.append(f"    typename tsl::array_for<Hw>::type hin{position};")
        lines.append(f"    typename Ref::register_type r{position};")
    lines.append(f"    for (std::size_t i = 0; i < {lanes}; ++i) {{")
    for position in range(arity):
        lines.append(
            f"      const {base} v{position} = tsl::test::fuzz_next<{base}>(rng); "
            f"hin{position}[i] = v{position}; r{position}[i] = v{position};"
        )
    lines.append("    }")
    hw_args = ", ".join(f"tsl::{case.from_array_name}<Hw>(hin{p})" for p in range(arity))
    ref_args = ", ".join(f"r{p}" for p in range(arity))
    hw_call = f"tsl::{case.call_name}<Hw>({hw_args})"
    ref_call = f"tsl::{case.call_name}<Ref>({ref_args})"
    if case.result_kind == "m":
        lines.append(f"    auto hw = tsl::{case.to_integral_name}<Hw>({hw_call});")
        lines.append(f"    typename Ref::mask_type ref = {ref_call};")
        check = f'tsl::test::check_mask_match("{case.function_name}", hw, ref, {lanes})'
    else:
        lines.append(f"    typename tsl::array_for<Hw>::type hw = tsl::{case.to_array_name}<Hw>({hw_call});")
        lines.append(f"    typename Ref::register_type ref = {ref_call};")
        check = f'tsl::test::check_match<{base}>("{case.function_name}", hw, ref, {lanes})'
    lines.append(f"    if ({check} != 0) {{")
    lines.append(
        f'      std::fprintf(stderr, "  reproduce: fuzz iter %zu, seed {case.fuzz_seed}\\n", iter);'
    )
    lines.append(f"      for (std::size_t i = 0; i < {lanes}; ++i) {{")
    lines.append('        std::fprintf(stderr, "    lane %zu:", i);')
    for position in range(arity):
        lines.append(f'        std::fprintf(stderr, " arg{position}=");')
        lines.append(f"        tsl::test::print_lane<{base}>(hin{position}[i]);")
    lines.append('        std::fprintf(stderr, "\\n");')
    lines.append("      }")
    lines.append("      return 1;")
    lines.append("    }")
    lines.append("  }")
    lines.append("  return 0;")
    lines.append("}")
    return "\n".join(lines)

__all__ = (
    "_convert",
    "_repr_cast",
    "_fixed_extension_repr_cast",
    "_extension_extract",
    "_extension_insert",
    "_load_convert",
    "_fixed_extension_load_convert",
    "_differential",
    "_differential_fuzz",
)
