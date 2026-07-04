"""Render memory-oriented C++ value-test cases."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests.render_cpp_helpers import (
    axis_suffix as _axis_suffix,
    cast_literal_list as _cast_literal_list,
    cpp_string_literal as _cpp_string_literal,
    scalable_header as _scalable_header,
    uint_literal as _uint_literal,
)

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
        f"reinterpret_cast<typename Vec::base_type const *>(buf + {case.buffer_offset}));",
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

def _indexed_load(case: ValueTestCasePlan) -> str:
    data = cpp_literal_list(case.vector_inputs[0], case.type_tag)
    index_type = case.index_type_tag or case.type_tag
    index_base = case.index_base_spelling or case.base_spelling
    indices = cpp_literal_list(case.vector_inputs[1], index_type)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lanes = case.target_lanes or len(case.expected)
    index_lanes = case.index_lanes or lanes
    scale = case.immediate_value or "1"
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  using Indices = tsl::simd<{index_base}, tsl::generic<{index_lanes}>>;",
        f"  static const {case.base_spelling} data_in[{len(case.vector_inputs[0])}] = {{{data}}};",
        f"  static const {index_base} idx_in[{index_lanes}] = {{{indices}}};",
        f"  {case.base_spelling} data[{len(case.vector_inputs[0])}] = {{0}};",
        f"  for (std::size_t i = 0; i < {len(case.vector_inputs[0])}; ++i) data[i] = data_in[i];",
        "  typename Indices::register_type idx;",
        f"  for (std::size_t i = 0; i < {index_lanes}; ++i) idx[i] = idx_in[i];",
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
    index_type = case.index_type_tag or case.type_tag
    index_base = case.index_base_spelling or case.base_spelling
    indices = cpp_literal_list(case.vector_inputs[1], index_type)
    expected = cpp_literal_list(case.expected, case.type_tag)
    lanes = case.lanes
    index_lanes = case.index_lanes or lanes
    scale = case.immediate_value or "1"
    buflen = case.buffer_length or len(case.expected)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  using Indices = tsl::simd<{index_base}, tsl::generic<{index_lanes}>>;",
        f"  static const {case.base_spelling} value_in[{lanes}] = {{{values}}};",
        f"  static const {index_base} idx_in[{index_lanes}] = {{{indices}}};",
        f"  {case.base_spelling} data[{buflen}] = {{0}};",
        "  typename Vec::register_type values;",
        "  typename Indices::register_type idx;",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) values[i] = value_in[i];",
        f"  for (std::size_t i = 0; i < {index_lanes}; ++i) idx[i] = idx_in[i];",
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

def _scalable_mask_store(case: ValueTestCasePlan) -> str:
    if (
        case.source_extension is None
        or case.runtime_lanes_expr is None
        or not case.mask_from_bits_exprs
        or case.target_base_spelling is None
        or case.expected_type_tag is None
    ):
        raise ValueError(
            "scalable mask-store C++ value test requires extension, lanes, "
            "mask input, and storage layout"
        )
    storage_type = case.target_base_spelling
    expected = cpp_literal_list(case.expected, case.expected_type_tag)
    authored_len = len(case.expected)
    axis = _axis_suffix(case)
    lines = _scalable_header(case)
    lines.extend(
        [
            f"  typename Vec::mask_type mask = {case.mask_from_bits_exprs[0]};",
            f"  static const {storage_type} authored_expected[{authored_len}] = {{{expected}}};",
            f"  std::vector<{storage_type}> actual({case.buffer_offset} + lanes);",
            f"  std::vector<{storage_type}> expected({case.buffer_offset} + lanes);",
            f"  for (std::size_t i = 0; i < {case.buffer_offset}; ++i) "
            "expected[i] = authored_expected[i];",
            f"  for (std::size_t i = 0; i < lanes; ++i) expected[{case.buffer_offset} + i] = "
            f"authored_expected[{case.buffer_offset} + (i % {case.lanes})];",
            f"  tsl::{case.call_name}<Vec{axis}>("
            "reinterpret_cast<typename Vec::base_type *>(actual.data() + "
            f"{case.buffer_offset}), mask);",
            f'  return tsl::test::check_lanes<{storage_type}>('
            f'"{case.case_name}", actual.data(), expected.data(), expected.size());',
            "}",
        ]
    )
    return "\n".join(lines)

__all__ = (
    "_scalar_pointer_load",
    "_mask_pointer_load",
    "_mask_store",
    "_scalable_mask_store",
    "_masked_pointer_load",
    "_masked_pointer_store",
    "_memory_copy",
    "_pointer_lifetime",
    "_pointer_free",
    "_indexed_load",
    "_indexed_store",
    "_stream",
    "_load",
    "_store",
)
