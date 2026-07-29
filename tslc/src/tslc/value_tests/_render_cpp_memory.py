"""Render memory-oriented C++ value-test cases."""

from __future__ import annotations

from tslc.value_tests.lane_math import runtime_tile_index as _runtime_tile_index
from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan, ValueTestMemory
from tslc.value_tests.render_cpp_helpers import (
    append_runtime_vector_input as _append_runtime_vector_input,
    axis_suffix as _axis_suffix,
    cast_literal_list as _cast_literal_list,
    cpp_string_literal as _cpp_string_literal,
    scalable_header as _scalable_header,
    scalable_mask_from_bits as _scalable_mask_from_bits,
    uint_literal as _uint_literal,
)


def _memory(case: ValueTestCasePlan) -> ValueTestMemory:
    return case.memory if case.memory is not None else ValueTestMemory()


def _buffer_length(case: ValueTestCasePlan) -> int:
    """The plan registry makes MEMORY_LENGTH mandatory for callers of this."""

    memory = case.memory
    assert memory is not None and memory.buffer_length is not None
    return memory.buffer_length


def _scalar_pointer_load(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal(case.expectation.values[0], case.type_tag)
    axis = _axis_suffix(case)
    buflen = _buffer_length(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{buflen}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{buflen}] = {{0}};",
        f"  for (std::size_t i = 0; i < {buflen}; ++i) buf[i] = in0[i];",
        f"  {case.base_spelling} result = tsl::{case.call_name}<Vec{axis}>(buf + {memory.buffer_offset});",
        f"  {case.base_spelling} expected = {expected};",
        f'  return tsl::test::check_scalar<{case.base_spelling}>("{case.case_name}", result, expected);',
        "}",
    ]
    return "\n".join(lines)

def _mask_pointer_load(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    target = case.target
    expected_int = int(case.expectation.values[0])
    bits = ", ".join("1" if (expected_int >> i) & 1 else "0" for i in range(case.lanes))
    if target is not None and target.type_tag is not None and target.base_spelling is not None:
        input_type = target.type_tag
        storage_type = target.base_spelling
    else:
        input_type = case.type_tag
        storage_type = case.base_spelling
    literals = cpp_literal_list(case.inputs.vectors[0], input_type)
    axis = _axis_suffix(case)
    buflen = _buffer_length(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {storage_type} in0[{buflen}] = {{{literals}}};",
        f"  {storage_type} buf[{buflen}] = {{0}};",
        f"  for (std::size_t i = 0; i < {buflen}; ++i) buf[i] = in0[i];",
        f"  typename Vec::mask_type result = tsl::{case.call_name}<Vec{axis}>("
        f"reinterpret_cast<typename Vec::base_type const *>(buf + {memory.buffer_offset}));",
        f"  static const int expected[{case.lanes}] = {{{bits}}};",
        f'  return tsl::test::check_mask("{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _mask_store(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    target = case.target
    assert memory.storage is not None
    if memory.storage == "packed":
        buffer_type = "typename Vec::imask_type"
        expected = _cast_literal_list(case.expectation.values, "typename Vec::imask_type")
    else:
        assert target is not None
        assert target.base_spelling is not None and target.type_tag is not None
        buffer_type = target.base_spelling
        expected = cpp_literal_list(case.expectation.values, target.type_tag)
    axis = _axis_suffix(case)
    buflen = _buffer_length(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {_uint_literal(case.inputs.masks[0])};",
        f"  {buffer_type} buf[{buflen}] = {{0}};",
        f"  static const {buffer_type} expected[{buflen}] = {{{expected}}};",
        f"  return tsl::test::check_lanes<{buffer_type}>("
        f'"{case.case_name}", buf, expected, {buflen});',
        "}",
    ]
    call = (
        f"  tsl::{case.call_name}<Vec{axis}>("
        f"reinterpret_cast<typename Vec::base_type *>(buf + {memory.buffer_offset}), mask);"
    )
    lines.insert(5, call)
    return "\n".join(lines)

def _masked_pointer_load(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    axis = _axis_suffix(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {_uint_literal(case.inputs.masks[0])};",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{memory.buffer_offset + case.lanes}] = {{0}};",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
        f"buf[{memory.buffer_offset} + i] = in0[i];",
    ]
    call_args = f"mask, buf + {memory.buffer_offset}"
    if len(case.inputs.vectors) == 2:
        pass_through = cpp_literal_list(case.inputs.vectors[1], case.type_tag)
        lines.extend(
            [
                f"  static const {case.base_spelling} in1[{case.lanes}] = {{{pass_through}}};",
                "  typename Vec::register_type v1;",
                f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v1[i] = in1[i];",
            ]
        )
        call_args += ", v1"
    lines.extend(
        [
            f"  typename Vec::register_type result = "
            f"tsl::{case.call_name}<Vec{axis}>({call_args});",
            f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", result, expected, {case.lanes});',
            "}",
        ]
    )
    return "\n".join(lines)

def _masked_pointer_store(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    axis = _axis_suffix(case)
    buflen = _buffer_length(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  typename Vec::mask_type mask = {_uint_literal(case.inputs.masks[0])};",
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
    memory = _memory(case)
    src = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    src_len = len(case.inputs.vectors[0])
    dst_len = _buffer_length(case)
    count = case.inputs.scalars[0]
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} src_in[{src_len}] = {{{src}}};",
        f"  {case.base_spelling} src[{src_len + memory.source_offset}] = {{0}};",
        f"  {case.base_spelling} dst[{dst_len}] = {{0}};",
        f"  for (std::size_t i = 0; i < {src_len}; ++i) src[{memory.source_offset} + i] = src_in[i];",
        f"  tsl::{case.call_name}<Vec>(dst + {memory.buffer_offset}, src + {memory.source_offset}, "
        f"static_cast<{case.base_spelling}>({count}), static_cast<{case.base_spelling}>(0));",
        f"  static const {case.base_spelling} expected[{dst_len}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", dst, expected, {dst_len});',
        "}",
    ]
    return "\n".join(lines)

def _pointer_lifetime(case: ValueTestCasePlan) -> str:
    args = ", ".join(f"static_cast<std::size_t>({value})" for value in case.inputs.scalars)
    alignment = case.inputs.scalars[1] if len(case.inputs.scalars) > 1 else None
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
    memory = _memory(case)
    count = case.inputs.scalars[0]
    alignment = memory.alignment
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
    index = case.index
    target = case.target
    assert target is not None and target.lanes is not None
    assert index is not None and index.lanes is not None and index.style is not None
    assert case.invocation.immediate is not None
    data = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    index_type = index.type_tag if index.type_tag is not None else case.type_tag
    index_base = (
        index.base_spelling if index.base_spelling is not None else case.base_spelling
    )
    indices = cpp_literal_list(case.inputs.vectors[1], index_type)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lanes = target.lanes
    index_lanes = index.lanes
    scale = case.invocation.immediate
    pointer_indices = index.style == "pointer"
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{lanes}>>;",
        f"  using Indices = tsl::simd<{index_base}, tsl::generic<{index_lanes}>>;",
        f"  static const {case.base_spelling} data_in[{len(case.inputs.vectors[0])}] = {{{data}}};",
        f"  static const {index_base} idx_in[{index_lanes}] = {{{indices}}};",
        f"  {case.base_spelling} data[{len(case.inputs.vectors[0])}] = {{0}};",
        f"  for (std::size_t i = 0; i < {len(case.inputs.vectors[0])}; ++i) data[i] = data_in[i];",
    ]
    if not pointer_indices:
        lines.extend(
            [
                "  typename Indices::register_type idx;",
                f"  for (std::size_t i = 0; i < {index_lanes}; ++i) idx[i] = idx_in[i];",
            ]
        )
    if case.inputs.masks:
        source = cpp_literal_list(case.inputs.vectors[2], case.type_tag)
        lines.append(f"  typename Vec::mask_type mask = {_uint_literal(case.inputs.masks[0])};")
        lines.append(f"  static const {case.base_spelling} source_in[{lanes}] = {{{source}}};")
        lines.append("  typename Vec::register_type source;")
        lines.append(f"  for (std::size_t i = 0; i < {lanes}; ++i) source[i] = source_in[i];")
        lines.append(
            f"  typename Vec::register_type result = "
            f"tsl::{case.call_name}<Vec, Indices, {scale}>(mask, data, idx, source);"
        )
    elif pointer_indices:
        lines.append(
            f"  typename Vec::register_type result = "
            f"tsl::{case.call_name}<Vec, Indices, {scale}>(data, idx_in);"
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
    index = case.index
    assert index is not None and index.lanes is not None
    assert case.invocation.immediate is not None
    values = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    index_type = index.type_tag if index.type_tag is not None else case.type_tag
    index_base = (
        index.base_spelling if index.base_spelling is not None else case.base_spelling
    )
    indices = cpp_literal_list(case.inputs.vectors[1], index_type)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lanes = case.lanes
    index_lanes = index.lanes
    scale = case.invocation.immediate
    buflen = _buffer_length(case)
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
    if case.inputs.masks:
        lines.append(f"  typename Vec::mask_type mask = {_uint_literal(case.inputs.masks[0])};")
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
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    modifier = case.inputs.scalars[0]
    assert case.expectation.text is not None
    expected = _cpp_string_literal(case.expectation.text)
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
    memory = _memory(case)
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    axis = _axis_suffix(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} data[{case.lanes}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{memory.buffer_offset + case.lanes}] = {{0}};",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
        f"buf[{memory.buffer_offset} + i] = data[i];",
        f"  typename Vec::register_type result = "
        f"tsl::{case.call_name}<Vec{axis}>(buf + {memory.buffer_offset});",
        f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", result, expected, {case.lanes});',
        "}",
    ]
    return "\n".join(lines)

def _store(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    axis = _axis_suffix(case)
    buflen = _buffer_length(case)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) v[i] = in0[i];",
        f"  {case.base_spelling} buf[{buflen}] = {{0}};",
        f"  tsl::{case.call_name}<Vec{axis}>(buf + {memory.buffer_offset}, v);",
        f"  static const {case.base_spelling} expected[{buflen}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", buf, expected, {buflen});',
        "}",
    ]
    return "\n".join(lines)

def _scalable_masked_pointer_load(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    scalable = case.scalable
    if scalable is None or not scalable.mask_bits or not scalable.value_harness_ready:
        raise ValueError(
            "scalable masked-load C++ value test requires extension, mask input, "
            "and load/store harness primitives"
        )
    authored_memory = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    authored_expected = cpp_literal_list(case.expectation.values, case.type_tag)
    axis = _axis_suffix(case)
    lines = _scalable_header(case)
    lines.extend(
        [
            f"  static const {case.base_spelling} authored_memory[{case.lanes}] = "
            f"{{{authored_memory}}};",
            f"  std::vector<{case.base_spelling}> memory({memory.buffer_offset} + lanes);",
            f"  for (std::size_t i = 0; i < lanes; ++i) "
            f"memory[{memory.buffer_offset} + i] = "
            f"authored_memory[{_runtime_tile_index('i', case.lanes)}];",
            f"  typename Vec::mask_type mask = {_scalable_mask_from_bits(case, 0)};",
        ]
    )
    call_args = f"mask, memory.data() + {memory.buffer_offset}"
    if len(case.inputs.vectors) == 2:
        pass_through = _append_runtime_vector_input(lines, case, 1)
        call_args += f", {pass_through}"
    lines.extend(
        [
            f"  typename Vec::register_type result = "
            f"tsl::{case.call_name}<Vec{axis}>({call_args});",
            f"  std::vector<{case.base_spelling}> actual(lanes);",
            f"  tsl::{scalable.store_name}<Vec, false>(actual.data(), result);",
            f"  static const {case.base_spelling} authored_expected[{case.lanes}] = "
            f"{{{authored_expected}}};",
            f"  std::vector<{case.base_spelling}> expected(lanes);",
            f"  for (std::size_t i = 0; i < lanes; ++i) expected[i] = "
            f"authored_expected[{_runtime_tile_index('i', case.lanes)}];",
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", actual.data(), expected.data(), lanes);',
            "}",
        ]
    )
    return "\n".join(lines)


def _scalable_masked_pointer_store(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    scalable = case.scalable
    if scalable is None or not scalable.mask_bits or not scalable.value_harness_ready:
        raise ValueError(
            "scalable masked-store C++ value test requires extension, mask input, "
            "and load/store harness primitives"
        )
    authored_expected = cpp_literal_list(case.expectation.values, case.type_tag)
    axis = _axis_suffix(case)
    lines = _scalable_header(case)
    value = _append_runtime_vector_input(lines, case, 0)
    lines.extend(
        [
            f"  typename Vec::mask_type mask = {_scalable_mask_from_bits(case, 0)};",
            f"  std::vector<{case.base_spelling}> actual({memory.buffer_offset} + lanes);",
            f"  static const {case.base_spelling} authored_expected[{case.lanes}] = "
            f"{{{authored_expected}}};",
            f"  std::vector<{case.base_spelling}> expected({memory.buffer_offset} + lanes);",
            f"  for (std::size_t i = 0; i < lanes; ++i) "
            f"expected[{memory.buffer_offset} + i] = "
            f"authored_expected[{_runtime_tile_index('i', case.lanes)}];",
            f"  tsl::{case.call_name}<Vec{axis}>("
            f"mask, actual.data() + {memory.buffer_offset}, {value});",
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", actual.data(), expected.data(), expected.size());',
            "}",
        ]
    )
    return "\n".join(lines)


def _scalable_mask_store(case: ValueTestCasePlan) -> str:
    memory = _memory(case)
    scalable = case.scalable
    target = case.target
    if scalable is None or not scalable.mask_bits or target is None:
        raise ValueError(
            "scalable mask-store C++ value test requires extension, lanes, "
            "mask input, and storage layout"
        )
    storage_type = target.base_spelling
    expected_type = target.type_tag
    assert storage_type is not None and expected_type is not None
    expected = cpp_literal_list(case.expectation.values, expected_type)
    authored_len = len(case.expectation.values)
    axis = _axis_suffix(case)
    lines = _scalable_header(case)
    lines.extend(
        [
            f"  typename Vec::mask_type mask = {_scalable_mask_from_bits(case, 0)};",
            f"  static const {storage_type} authored_expected[{authored_len}] = {{{expected}}};",
            f"  std::vector<{storage_type}> actual({memory.buffer_offset} + lanes);",
            f"  std::vector<{storage_type}> expected({memory.buffer_offset} + lanes);",
            f"  for (std::size_t i = 0; i < {memory.buffer_offset}; ++i) "
            "expected[i] = authored_expected[i];",
            f"  for (std::size_t i = 0; i < lanes; ++i) expected[{memory.buffer_offset} + i] = "
            f"authored_expected[{memory.buffer_offset} + ({_runtime_tile_index('i', case.lanes)})];",
            f"  tsl::{case.call_name}<Vec{axis}>("
            "reinterpret_cast<typename Vec::base_type *>(actual.data() + "
            f"{memory.buffer_offset}), mask);",
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
    "_scalable_masked_pointer_load",
    "_scalable_masked_pointer_store",
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
