"""Render Rust value-test plans."""

from __future__ import annotations

from collections.abc import Callable

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.render._common import slug
from tslc.value_tests._render_rust_conversion import (
    _convert,
    _extension_extract,
    _extension_insert,
    _load_convert,
    _repr_cast,
)
from tslc.value_tests._render_rust_helpers import (
    append_call_args,
    axis_args,
    scalar_expected,
    scalar_result_type,
)
from tslc.value_tests._render_rust_memory import (
    _indexed_load,
    _indexed_store,
    _load,
    _mask_pointer_load,
    _masked_pointer_load,
    _masked_pointer_store,
    _memory_copy,
    _pointer_free,
    _pointer_lifetime,
    _scalar_pointer_load,
    _store,
    _stream,
)
from tslc.value_tests.literals import rust_literal, rust_literal_list, token_truthy
from tslc.value_tests.model import (
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestProfilePlan,
)

RustCaseRenderer = Callable[[ValueTestCasePlan], str]


def render_rust_values_file(profiles: tuple[ValueTestProfilePlan, ...]) -> str:
    sections: list[str] = ['#![cfg(feature = "value_tests")]', ""]
    for profile in profiles:
        if not profile.cases:
            continue
        profile_slug = slug(profile.profile_name)
        body = "\n\n".join(_render_case(case) for case in profile.cases)
        sections.append(
            f'#[cfg(feature = "{profile_slug}")]\n'
            f"mod {profile_slug}_values {{\n"
            "    #![allow(non_snake_case)]\n"
            "    use tsl_generated::tsl_core::*;\n"
            f"    use tsl_generated::tsl_{profile_slug}::*;\n"
            "    use tsl_generated::tsl_test_core::*;\n\n"
            f"{body}\n"
            "}"
        )
    return "\n\n".join(sections) + "\n"


def _render_case(case: ValueTestCasePlan) -> str:
    try:
        renderer = RUST_CASE_RENDERERS[case.kind]
    except KeyError as exc:
        raise ValueError(f"unsupported Rust value-test case kind {case.kind!r}") from exc
    return renderer(case)


def _generic_golden(case: ValueTestCasePlan) -> str:
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    arg_names = []
    for position, values in enumerate(case.vector_inputs):
        literals = rust_literal_list(values, case.type_tag)
        lines.append(f"        let in{position}: [{case.base_spelling}; {case.lanes}] = [{literals}];")
        lines.append(
            f"        let mut a{position}: <Vec as SimdVector>::RegisterType = "
            "Default::default();"
        )
        lines.append(f"        for i in 0..{case.lanes} {{ a{position}[i] = in{position}[i]; }}")
        arg_names.append(f"a{position}")
    call = f"{rust_raw_identifier(case.call_name)}::<Vec>({', '.join(arg_names)})"
    if case.result_kind == "m":
        bits = ", ".join("true" if token_truthy(v) else "false" for v in case.expected)
        lines.append(f"        let expected: [bool; {case.lanes}] = [{bits}];")
        lines.append(f"        let result = {call};")
        lines.append(
            f"        for i in 0..{case.lanes} {{ assert_eq!(mask_bit(result as u64, i), "
            f'expected[i], "{case.case_name} lane {{}}", i); }}'
        )
    else:
        expected = rust_literal_list(case.expected, case.type_tag)
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
    for position, values in enumerate(case.vector_inputs):
        literals = rust_literal_list(values, case.type_tag)
        lines.append(f"        let in{position}: [{case.base_spelling}; {case.lanes}] = [{literals}];")
        lines.append(
            f"        let mut a{position}: <Vec as SimdVector>::RegisterType = "
            "Default::default();"
        )
        lines.append(f"        for i in 0..{case.lanes} {{ a{position}[i] = in{position}[i]; }}")
        arg_names.append(f"a{position}")
    template_args = ["Vec"]
    if case.immediate_value is not None:
        template_args.append(case.immediate_value)
    template_args.extend(case.generic_defaults)
    expected = rust_literal_list(case.expected, case.type_tag)
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
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    input_lanes = len(case.vector_inputs[0])
    expected_lanes = len(case.expected)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{input_lanes}>>;",
            f"        let in0: [{case.base_spelling}; {input_lanes}] = [{literals}];",
            f"        let mut {local_name}: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{input_lanes} {{ {local_name}[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {expected_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>({local_name});",
            _lane_assert(case, expected_lanes, "result"),
            "    }",
        ]
    )


def _vector_to_array(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    input_lanes = len(case.vector_inputs[0])
    expected_lanes = len(case.expected)
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
    expected = rust_literal_list(case.expected, case.type_tag)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let mask: <Vec as SimdVector>::MaskType = {case.mask_inputs[0]}u64;",
            f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(mask);",
            _lane_assert(case, case.lanes, "result"),
            "    }",
        ]
    )


def _masked(case: ValueTestCasePlan) -> str:
    expected = rust_literal_list(case.expected, case.type_tag)
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
    expected = int(case.expected[0])
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


def _broadcast(case: ValueTestCasePlan) -> str:
    value = rust_literal(case.scalar_input or "0", case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
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
    packed = case.result_kind == "packed"
    storage_type = (
        "<Vec as SimdVector>::ImaskType"
        if packed
        else case.target_base_spelling or case.base_spelling
    )
    expected_type = "ui64" if packed else case.expected_type_tag or case.type_tag
    expected = rust_literal_list(case.expected, expected_type)
    axis = axis_args(case)
    buflen = case.buffer_length or len(case.expected)
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
        f"        let mask: <Vec as SimdVector>::MaskType = {case.mask_inputs[0]}u64;",
        f"        let mut buf: [{storage_type}; {buflen}] = [Default::default(); {buflen}];",
        f"        let expected: [{storage_type}; {buflen}] = [{expected}];",
        f"        unsafe {{ {rust_raw_identifier(case.call_name)}::<Vec{axis}>(",
        f"            buf.as_mut_ptr().add({case.buffer_offset}) as *mut <Vec as SimdVector>::BaseType,",
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
    if case.index_value is not None:
        template_args.append(case.index_value)
    template_args.extend(case.generic_defaults)
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
    expected = rust_literal_list(case.expected, case.type_tag)
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


def _reduction(case: ValueTestCasePlan) -> str:
    values = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal(case.expected[0], case.type_tag)
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
    if case.result_kind == "void":
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


RUST_CASE_RENDERERS: dict[str, RustCaseRenderer] = {
    "array_to_vector": _array_to_vector,
    "broadcast": _broadcast,
    "compile_only": _compile_only,
    "convert": _convert,
    "extension_extract": _extension_extract,
    "extension_insert": _extension_insert,
    "generic_golden": _generic_golden,
    "immediate": _immediate,
    "indexed_load": _indexed_load,
    "indexed_store": _indexed_store,
    "lane_list": _lane_list,
    "load": _load,
    "load_convert": _load_convert,
    "mask_pointer_load": _mask_pointer_load,
    "mask_result": _mask_result,
    "mask_store": _mask_store,
    "mask_to_vector": _mask_to_vector,
    "masked": _masked,
    "masked_pointer_load": _masked_pointer_load,
    "masked_pointer_store": _masked_pointer_store,
    "memory_copy": _memory_copy,
    "pointer_free": _pointer_free,
    "pointer_lifetime": _pointer_lifetime,
    "reduction": _reduction,
    "repr_cast": _repr_cast,
    "scalar_pointer_load": _scalar_pointer_load,
    "scalar_result": _scalar_result,
    "scalar_vector": _scalar_vector,
    "store": _store,
    "stream": _stream,
    "vector_to_array": _vector_to_array,
}

RUST_VALUE_TEST_SUPPORT = ValueTestBackendSupport(
    backend_id="rust",
    case_kinds=frozenset(RUST_CASE_RENDERERS),
)


__all__ = ["RUST_CASE_RENDERERS", "RUST_VALUE_TEST_SUPPORT", "render_rust_values_file"]
