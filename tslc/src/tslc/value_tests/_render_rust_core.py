"""Core Rust value-test case renderers."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.value_tests._render_rust_helpers import (
    append_call_args,
    axis_args,
    scalar_expected,
    scalar_result_type,
)
from tslc.value_tests.literals import rust_literal, rust_literal_list, token_truthy
from tslc.value_tests.model import ValueTestCasePlan


def _generic_golden(case: ValueTestCasePlan) -> str:
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    arg_names = []
    for position, values in enumerate(case.inputs.vectors):
        literals = rust_literal_list(values, case.type_tag)
        lines.append(f"        let in{position}: [{case.base_spelling}; {case.lanes}] = [{literals}];")
        lines.append(
            f"        let mut a{position}: <Vec as SimdVector>::RegisterType = "
            "Default::default();"
        )
        lines.append(f"        for i in 0..{case.lanes} {{ a{position}[i] = in{position}[i]; }}")
        arg_names.append(f"a{position}")
    template_args = ["Vec", *case.invocation.generic_defaults]
    template_args.extend("_" for _ in range(case.invocation.inferred_type_args))
    call = (
        f"{rust_raw_identifier(case.call_name)}"
        f"::<{', '.join(template_args)}>({', '.join(arg_names)})"
    )
    if case.invocation.result_kind == "m":
        bits = ", ".join("true" if token_truthy(v) else "false" for v in case.expectation.values)
        lines.append(f"        let expected: [bool; {case.lanes}] = [{bits}];")
        lines.append(f"        let result = {call};")
        lines.append(
            f"        for i in 0..{case.lanes} {{ assert_eq!(mask_bit(result as u64, i), "
            f'expected[i], "{case.case_name} lane {{}}", i); }}'
        )
    else:
        expected = rust_literal_list(case.expectation.values, case.type_tag)
        lines.append(f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];")
        lines.append(f"        let result = {call};")
        lines.append(_lane_assert(case, case.lanes, "result"))
    lines.append("    }")
    return "\n".join(lines)


def _immediate(case: ValueTestCasePlan) -> str:
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    arg_names = []
    for position, values in enumerate(case.inputs.vectors):
        literals = rust_literal_list(values, case.type_tag)
        lines.append(f"        let in{position}: [{case.base_spelling}; {case.lanes}] = [{literals}];")
        lines.append(
            f"        let mut a{position}: <Vec as SimdVector>::RegisterType = "
            "Default::default();"
        )
        lines.append(f"        for i in 0..{case.lanes} {{ a{position}[i] = in{position}[i]; }}")
        arg_names.append(f"a{position}")
    template_args = ["Vec"]
    if case.invocation.immediate is not None:
        template_args.append(case.invocation.immediate)
    template_args.extend(case.invocation.generic_defaults)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    lines.append(f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];")
    lines.append(
        f"        let result = {rust_raw_identifier(case.call_name)}"
        f"::<{', '.join(template_args)}>({', '.join(arg_names)});"
    )
    lines.append(_lane_assert(case, case.lanes, "result"))
    lines.append("    }")
    return "\n".join(lines)


def _lane_list(case: ValueTestCasePlan) -> str:
    return _array_to_vector_like(case, "values")


def _array_to_vector(case: ValueTestCasePlan) -> str:
    return _array_to_vector_like(case, "values")


def _array_to_vector_like(case: ValueTestCasePlan, local_name: str) -> str:
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    input_lanes = len(case.inputs.vectors[0])
    expected_lanes = len(case.expectation.values)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{input_lanes}>>;",
            f"        let in0: [{case.base_spelling}; {input_lanes}] = [{literals}];",
            f"        let mut {local_name}: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{input_lanes} {{ {local_name}[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {expected_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(&{local_name});",
            _lane_assert(case, expected_lanes, "result"),
            "    }",
        ]
    )


def _vector_to_array(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    input_lanes = len(case.inputs.vectors[0])
    expected_lanes = len(case.expectation.values)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{input_lanes}>>;",
            f"        let in0: [{case.base_spelling}; {input_lanes}] = [{literals}];",
            "        let mut v0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{input_lanes} {{ v0[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {expected_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(v0);",
            _lane_assert(case, expected_lanes, "result"),
            "    }",
        ]
    )


def _mask_to_vector(case: ValueTestCasePlan) -> str:
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let mask: <Vec as SimdVector>::MaskType = {case.inputs.masks[0]}u64;",
            f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(mask);",
            _lane_assert(case, case.lanes, "result"),
            "    }",
        ]
    )


def _masked(case: ValueTestCasePlan) -> str:
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    args = append_call_args(lines, case)
    lines.append(f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];")
    lines.append(
        f"        let result = {rust_raw_identifier(case.call_name)}"
        f"::<Vec>({', '.join(args)});"
    )
    lines.append(_lane_assert(case, case.lanes, "result"))
    lines.append("    }")
    return "\n".join(lines)


def _mask_result(case: ValueTestCasePlan) -> str:
    expected = int(case.expectation.values[0])
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    args = append_call_args(lines, case)
    lines.append(
        f"        let result = {rust_raw_identifier(case.call_name)}"
        f"::<Vec>({', '.join(args)});"
    )
    for lane in range(case.lanes):
        bit = "true" if (expected >> lane) & 1 else "false"
        lines.append(
            f"        assert_eq!(mask_bit(result as u64, {lane}), {bit}, "
            f'"{case.case_name} lane {lane}");'
        )
    lines.append("    }")
    return "\n".join(lines)


def _mask_logic(case: ValueTestCasePlan) -> str:
    expected = int(case.expectation.values[0])
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    arg_names = []
    for position, mask in enumerate(case.inputs.masks):
        lines.append(
            f"        let m{position}: <Vec as SimdVector>::MaskType = {mask}u64;"
        )
        arg_names.append(f"m{position}")
    lines.append(
        f"        let result = {rust_raw_identifier(case.call_name)}"
        f"::<Vec>({', '.join(arg_names)});"
    )
    for lane in range(case.lanes):
        bit = "true" if (expected >> lane) & 1 else "false"
        lines.append(
            f"        assert_eq!(mask_bit(result as u64, {lane}), {bit}, "
            f'"{case.case_name} lane {lane}");'
        )
    lines.append("    }")
    return "\n".join(lines)


def _broadcast(case: ValueTestCasePlan) -> str:
    value = rust_literal(case.inputs.scalar or "0", case.type_tag)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let value: {case.base_spelling} = {value};",
            f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(value);",
            _lane_assert(case, case.lanes, "result"),
            "    }",
        ]
    )


def _mask_store(case: ValueTestCasePlan) -> str:
    packed = case.invocation.result_kind == "packed"
    target = case.target
    memory = case.memory
    storage_type = (
        "<Vec as SimdVector>::ImaskType"
        if packed
        else (target.base_spelling if target is not None else None)
        or case.base_spelling
    )
    expected_type = (
        "ui64"
        if packed
        else (target.type_tag if target is not None else None) or case.type_tag
    )
    expected = rust_literal_list(case.expectation.values, expected_type)
    axis = axis_args(case)
    buflen = (
        memory.buffer_length if memory is not None else None
    ) or len(case.expectation.values)
    buffer_offset = memory.buffer_offset if memory is not None else 0
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
        f"        let mask: <Vec as SimdVector>::MaskType = {case.inputs.masks[0]}u64;",
        f"        let mut buf: [{storage_type}; {buflen}] = [Default::default(); {buflen}];",
        f"        let expected: [{storage_type}; {buflen}] = [{expected}];",
        f"        unsafe {{ {rust_raw_identifier(case.call_name)}::<Vec{axis}>(",
        f"            buf.as_mut_ptr().add({buffer_offset}) as *mut <Vec as SimdVector>::BaseType,",
        "            mask,",
        "        ); }",
        f"        for i in 0..{buflen} {{ assert!(buf[i].lane_eq(expected[i]), ",
        f'            "{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", ',
        "            i, expected[i], buf[i]); }",
        "    }",
    ]
    return "\n".join(lines)


def _scalar_result(case: ValueTestCasePlan) -> str:
    result_type = scalar_result_type(case)
    expected = scalar_expected(case, result_type)
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    args = append_call_args(lines, case)
    template_args = ["Vec"]
    if case.index is not None and case.index.value is not None:
        template_args.append(case.index.value)
    template_args.extend(case.invocation.generic_defaults)
    lines.append(
        f"        let result = {rust_raw_identifier(case.call_name)}"
        f"::<{', '.join(template_args)}>({', '.join(args)});"
    )
    lines.append(f"        let expected: {result_type} = {expected};")
    lines.append(
        f"        assert!(result.lane_eq(expected), "
        f'"{case.case_name}: expected {{:?}}, got {{:?}}", expected, result);'
    )
    lines.append("    }")
    return "\n".join(lines)


def _scalar_vector(case: ValueTestCasePlan) -> str:
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    args = append_call_args(lines, case)
    template_args = ["Vec", *case.invocation.generic_defaults]
    template_args.extend("_" for _ in range(case.invocation.inferred_type_args))
    lines.append(f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];")
    lines.append(
        f"        let result = {rust_raw_identifier(case.call_name)}"
        f"::<{', '.join(template_args)}>({', '.join(args)});"
    )
    lines.append(_lane_assert(case, case.lanes, "result"))
    lines.append("    }")
    return "\n".join(lines)


def _reduction(case: ValueTestCasePlan) -> str:
    values = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal(case.expectation.values[0], case.type_tag)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{values}];",
            "        let mut v0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{case.lanes} {{ v0[i] = in0[i]; }}",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(v0);",
            f"        let expected: {case.base_spelling} = {expected};",
            f"        assert!(result.lane_eq(expected), "
            f'"{case.case_name}: expected {{:?}}, got {{:?}}", expected, result);',
            "    }",
        ]
    )


def _compile_only(case: ValueTestCasePlan) -> str:
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    args = append_call_args(lines, case)
    call = f"{rust_raw_identifier(case.call_name)}::<Vec>({', '.join(args)})"
    if case.invocation.result_kind == "void":
        lines.append(f"        {call};")
    else:
        lines.append(f"        let result = {call};")
        lines.append("        let _ = result;")
    lines.append("    }")
    return "\n".join(lines)


def _lane_assert(case: ValueTestCasePlan, lanes: int, result_name: str) -> str:
    return (
        f"        for i in 0..{lanes} {{ assert!({result_name}[i].lane_eq(expected[i]), "
        f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
        f"i, expected[i], {result_name}[i]); }}"
    )


__all__ = [
    "_array_to_vector",
    "_broadcast",
    "_compile_only",
    "_generic_golden",
    "_immediate",
    "_lane_list",
    "_mask_logic",
    "_mask_result",
    "_mask_store",
    "_mask_to_vector",
    "_masked",
    "_reduction",
    "_scalar_result",
    "_scalar_vector",
    "_vector_to_array",
]
