"""Render Rust memory-oriented value-test cases."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.value_tests._render_rust_helpers import axis_args, rust_string_literal
from tslc.value_tests.literals import rust_literal, rust_literal_list
from tslc.value_tests.model import ValueTestCasePlan


def _load(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    axis = axis_args(case)
    buflen = case.buffer_offset + case.lanes
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            f"        let mut buf: [{case.base_spelling}; {buflen}] = "
            f"[Default::default(); {buflen}];",
            f"        for i in 0..{case.lanes} {{ buf[{case.buffer_offset} + i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];",
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec{axis}>(buf.as_ptr().add({case.buffer_offset})) }};",
            f"        for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _store(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    axis = axis_args(case)
    buflen = case.buffer_length or len(case.expected)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut v0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{case.lanes} {{ v0[i] = in0[i]; }}",
            f"        let mut buf: [{case.base_spelling}; {buflen}] = "
            f"[Default::default(); {buflen}];",
            f"        unsafe {{ {rust_raw_identifier(case.call_name)}::<Vec{axis}, _>(",
            f"            buf.as_mut_ptr().add({case.buffer_offset}),",
            "            v0,",
            "        ); }",
            f"        let expected: [{case.base_spelling}; {buflen}] = [{expected}];",
            f"        for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], buf[i]); }",
            "    }",
        ]
    )


def _scalar_pointer_load(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal(case.expected[0], case.type_tag)
    axis = axis_args(case)
    buflen = case.buffer_length or len(case.vector_inputs[0])
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {buflen}] = [{literals}];",
            f"        let mut buf: [{case.base_spelling}; {buflen}] = "
            f"[Default::default(); {buflen}];",
            f"        for i in 0..{buflen} {{ buf[i] = in0[i]; }}",
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec{axis}>(buf.as_ptr().add({case.buffer_offset})) }};",
            f"        let expected: {case.base_spelling} = {expected};",
            f"        assert!(result.lane_eq(expected), "
            f'"{case.case_name}: expected {{:?}}, got {{:?}}", expected, result);',
            "    }",
        ]
    )


def _mask_pointer_load(case: ValueTestCasePlan) -> str:
    input_type = case.expected_type_tag or case.type_tag
    storage_type = case.target_base_spelling or case.base_spelling
    literals = rust_literal_list(case.vector_inputs[0], input_type)
    expected = int(case.expected[0])
    axis = axis_args(case)
    buflen = case.buffer_length or len(case.vector_inputs[0])
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
        f"        let in0: [{storage_type}; {buflen}] = [{literals}];",
        f"        let mut buf: [{storage_type}; {buflen}] = [Default::default(); {buflen}];",
        f"        for i in 0..{buflen} {{ buf[i] = in0[i]; }}",
        f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}::<Vec{axis}>(",
        f"            buf.as_ptr().add({case.buffer_offset}) as *const <Vec as SimdVector>::BaseType",
        "        ) };",
    ]
    for lane in range(case.lanes):
        bit = "true" if (expected >> lane) & 1 else "false"
        lines.append(
            f"        assert_eq!(mask_bit(result as u64, {lane}), {bit}, "
            f'"{case.case_name} lane {lane}");'
        )
    lines.append("    }")
    return "\n".join(lines)


def _masked_pointer_load(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    axis = axis_args(case)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let mask: <Vec as SimdVector>::MaskType = {case.mask_inputs[0]}u64;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            f"        let mut buf: [{case.base_spelling}; {case.lanes}] = "
            f"[Default::default(); {case.lanes}];",
            f"        for i in 0..{case.lanes} {{ buf[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];",
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec{axis}>(mask, buf.as_ptr()) }};",
            f"        for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _masked_pointer_store(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    axis = axis_args(case)
    buflen = case.buffer_length or len(case.expected)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let mask: <Vec as SimdVector>::MaskType = {case.mask_inputs[0]}u64;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut v0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{case.lanes} {{ v0[i] = in0[i]; }}",
            f"        let mut buf: [{case.base_spelling}; {buflen}] = "
            f"[Default::default(); {buflen}];",
            f"        unsafe {{ {rust_raw_identifier(case.call_name)}::<Vec{axis}>(",
            "            mask,",
            f"            buf.as_mut_ptr().add({case.buffer_offset}),",
            "            v0,",
            "        ); }",
            f"        let expected: [{case.base_spelling}; {buflen}] = [{expected}];",
            f"        for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], buf[i]); }",
            "    }",
        ]
    )


def _memory_copy(case: ValueTestCasePlan) -> str:
    src = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    src_len = len(case.vector_inputs[0])
    dst_len = case.buffer_length or len(case.expected)
    count = rust_literal(case.scalar_inputs[0] if case.scalar_inputs else str(src_len), case.type_tag)
    zero = rust_literal("0", case.type_tag)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let src_in: [{case.base_spelling}; {src_len}] = [{src}];",
            f"        let mut src: [{case.base_spelling}; {src_len + case.source_offset}] = "
            f"[Default::default(); {src_len + case.source_offset}];",
            f"        let mut dst: [{case.base_spelling}; {dst_len}] = "
            f"[Default::default(); {dst_len}];",
            f"        for i in 0..{src_len} {{ src[{case.source_offset} + i] = src_in[i]; }}",
            f"        unsafe {{ {rust_raw_identifier(case.call_name)}::<Vec>(",
            f"            dst.as_mut_ptr().add({case.buffer_offset}),",
            f"            src.as_ptr().add({case.source_offset}),",
            f"            {count},",
            f"            {zero},",
            "        ); }",
            f"        let expected: [{case.base_spelling}; {dst_len}] = [{expected}];",
            f"        for i in 0..{dst_len} {{ assert!(dst[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], dst[i]); }",
            "    }",
        ]
    )


def _pointer_lifetime(case: ValueTestCasePlan) -> str:
    args = ", ".join(f"{value}usize" for value in case.scalar_inputs)
    alignment = case.scalar_inputs[1] if len(case.scalar_inputs) > 1 else None
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        let ptr = {rust_raw_identifier(case.call_name)}({args});",
        f'        assert!(!ptr.is_null(), "{case.case_name}: null pointer");',
    ]
    if alignment is not None:
        lines.append(
            f"        assert_eq!((ptr as usize) % {alignment}usize, 0, "
            f'"{case.case_name}: pointer alignment");'
        )
    lines.append("        unsafe { mem_free(ptr); }")
    lines.append("    }")
    return "\n".join(lines)


def _pointer_free(case: ValueTestCasePlan) -> str:
    count = case.scalar_inputs[0] if case.scalar_inputs else "1"
    if case.target_base_spelling is None:
        alloc = f"mem_alloc({count}usize)"
    else:
        alloc = f"mem_alloc_aligned({case.target_base_spelling}usize, {count}usize)"
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        let ptr = unsafe {{ {alloc} }};",
            f'        assert!(!ptr.is_null(), "{case.case_name}: setup allocation failed");',
            f"        unsafe {{ {rust_raw_identifier(case.call_name)}(ptr); }}",
            "    }",
        ]
    )


def _indexed_load(case: ValueTestCasePlan) -> str:
    data = rust_literal_list(case.vector_inputs[0], case.type_tag)
    index_type = case.index_type_tag or case.type_tag
    index_base = case.index_base_spelling or case.base_spelling
    indices = rust_literal_list(case.vector_inputs[1], index_type)
    expected = rust_literal_list(case.expected, case.type_tag)
    lanes = case.target_lanes or len(case.expected)
    index_lanes = case.index_lanes or lanes
    scale = case.immediate_value or "1"
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{lanes}>>;",
        f"        type Indices = Simd<{index_base}, Generic<{index_lanes}>>;",
        f"        let data_in: [{case.base_spelling}; {len(case.vector_inputs[0])}] = [{data}];",
        f"        let idx_in: [{index_base}; {index_lanes}] = [{indices}];",
        f"        let mut data: [{case.base_spelling}; {len(case.vector_inputs[0])}] = "
        f"[Default::default(); {len(case.vector_inputs[0])}];",
        f"        for i in 0..{len(case.vector_inputs[0])} {{ data[i] = data_in[i]; }}",
        "        let mut idx: <Indices as SimdVector>::RegisterType = Default::default();",
        f"        for i in 0..{index_lanes} {{ idx[i] = idx_in[i]; }}",
    ]
    if case.mask_inputs:
        source = rust_literal_list(case.vector_inputs[2], case.type_tag)
        lines.append(f"        let mask: <Vec as SimdVector>::MaskType = {case.mask_inputs[0]}u64;")
        lines.append(f"        let source_in: [{case.base_spelling}; {lanes}] = [{source}];")
        lines.append("        let mut source: <Vec as SimdVector>::RegisterType = Default::default();")
        lines.append(f"        for i in 0..{lanes} {{ source[i] = source_in[i]; }}")
        lines.append(
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec, Indices, {scale}, {index_lanes}>(mask, data.as_ptr(), idx, source) }};"
        )
    else:
        lines.append(
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec, Indices, {scale}, {index_lanes}>(data.as_ptr(), idx) }};"
        )
    lines.extend(
        [
            f"        let expected: [{case.base_spelling}; {lanes}] = [{expected}];",
            f"        for i in 0..{lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )
    return "\n".join(lines)


def _indexed_store(case: ValueTestCasePlan) -> str:
    values = rust_literal_list(case.vector_inputs[0], case.type_tag)
    index_type = case.index_type_tag or case.type_tag
    index_base = case.index_base_spelling or case.base_spelling
    indices = rust_literal_list(case.vector_inputs[1], index_type)
    expected = rust_literal_list(case.expected, case.type_tag)
    lanes = case.lanes
    index_lanes = case.index_lanes or lanes
    scale = case.immediate_value or "1"
    buflen = case.buffer_length or len(case.expected)
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{lanes}>>;",
        f"        type Indices = Simd<{index_base}, Generic<{index_lanes}>>;",
        f"        let value_in: [{case.base_spelling}; {lanes}] = [{values}];",
        f"        let idx_in: [{index_base}; {index_lanes}] = [{indices}];",
        f"        let mut data: [{case.base_spelling}; {buflen}] = [Default::default(); {buflen}];",
        "        let mut values: <Vec as SimdVector>::RegisterType = Default::default();",
        "        let mut idx: <Indices as SimdVector>::RegisterType = Default::default();",
        f"        for i in 0..{lanes} {{ values[i] = value_in[i]; }}",
        f"        for i in 0..{index_lanes} {{ idx[i] = idx_in[i]; }}",
    ]
    if case.mask_inputs:
        lines.append(f"        let mask: <Vec as SimdVector>::MaskType = {case.mask_inputs[0]}u64;")
        lines.append(
            f"        unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec, Indices, {scale}, {index_lanes}>(mask, data.as_mut_ptr(), idx, values); }}"
        )
    else:
        lines.append(
            f"        unsafe {{ {rust_raw_identifier(case.call_name)}"
            f"::<Vec, Indices, {scale}, {index_lanes}>(data.as_mut_ptr(), idx, values); }}"
        )
    lines.extend(
        [
            f"        let expected: [{case.base_spelling}; {buflen}] = [{expected}];",
            f"        for i in 0..{buflen} {{ assert!(data[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], data[i]); }",
            "    }",
        ]
    )
    return "\n".join(lines)


def _stream(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    modifier = rust_literal(case.scalar_inputs[0] if case.scalar_inputs else "0", case.type_tag)
    expected = rust_string_literal(case.text_expected or "")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut v0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{case.lanes} {{ v0[i] = in0[i]; }}",
            "        let mut out = String::new();",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(",
            f"            &mut out, v0, {modifier},",
            "        );",
            f"        assert_eq!(result.as_str(), {expected}, \"{case.case_name}\");",
            "    }",
        ]
    )


__all__ = (
    "_indexed_load",
    "_indexed_store",
    "_load",
    "_mask_pointer_load",
    "_masked_pointer_load",
    "_masked_pointer_store",
    "_memory_copy",
    "_pointer_free",
    "_pointer_lifetime",
    "_scalar_pointer_load",
    "_store",
    "_stream",
)
