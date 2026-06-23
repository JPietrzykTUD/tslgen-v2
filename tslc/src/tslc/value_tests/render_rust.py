"""Render Rust value-test plans."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.render._common import slug
from tslc.value_tests.literals import rust_literal_list, token_truthy
from tslc.value_tests.model import (
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestProfilePlan,
)

RUST_VALUE_TEST_SUPPORT = ValueTestBackendSupport(
    backend_id="rust",
    case_kinds=frozenset({"convert", "generic_golden", "lane_list", "repr_cast"}),
)


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
    if case.kind == "generic_golden":
        return _generic_golden(case)
    if case.kind == "lane_list":
        return _lane_list(case)
    if case.kind == "convert":
        return _convert(case)
    if case.kind == "repr_cast":
        return _repr_cast(case)
    raise ValueError(f"unsupported Rust value-test case kind {case.kind!r}")


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
        lines.append(
            f"        for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }"
        )
    lines.append("    }")
    return "\n".join(lines)


def _lane_list(case: ValueTestCasePlan) -> str:
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut values: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{case.lanes} {{ values[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {case.lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec>(values);",
            f"        for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _convert(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or case.lanes
    expected_type = case.expected_type_tag or case.type_tag
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, expected_type)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        type ToVec = Simd<{target}, Generic<{target_lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut a0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{case.lanes} {{ a0[i] = in0[i]; }}",
            f"        let expected: [{target}; {target_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<Vec, ToVec, {case.index_value}>(a0);",
            f"        for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _repr_cast(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    expected_type = case.expected_type_tag or case.type_tag
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, expected_type)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        type ToVec = Simd<{target}, Generic<{case.lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut a0: <Vec as SimdVector>::RegisterType = Default::default();",
            f"        for i in 0..{case.lanes} {{ a0[i] = in0[i]; }}",
            f"        let expected: [{target}; {case.lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec, ToVec>(a0);",
            f"        for i in 0..{case.lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


__all__ = ["RUST_VALUE_TEST_SUPPORT", "render_rust_values_file"]
