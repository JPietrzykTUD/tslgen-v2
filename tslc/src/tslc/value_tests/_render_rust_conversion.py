"""Render Rust conversion and extension value-test cases."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.value_tests._render_rust_helpers import rust_extension_tag
from tslc.value_tests.literals import rust_literal_list
from tslc.value_tests.model import ValueTestCasePlan


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
    if case.source_extension is not None:
        return _fixed_extension_repr_cast(case)
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or len(case.expected)
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
            f"        let result = {rust_raw_identifier(case.call_name)}::<Vec, ToVec>(a0);",
            f"        for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _fixed_extension_repr_cast(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or len(case.expected)
    expected_type = case.expected_type_tag or case.type_tag
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, expected_type)
    from_array = _helper_name(case, "from_array_name")
    to_array = _helper_name(case, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(case.source_extension)}>;",
            f"        type ToVec = Simd<{target}, {rust_extension_tag(case.target_extension)}>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut h0: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{case.lanes} {{ h0[i] = in0[i]; }}",
            f"        let expected: [{target}; {target_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<Vec, ToVec>({from_array}::<Vec>(h0));",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _load_convert(case: ValueTestCasePlan) -> str:
    target = case.target_base_spelling or case.base_spelling
    target_lanes = case.target_lanes or len(case.expected)
    expected_type = case.expected_type_tag or case.type_tag
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, expected_type)
    if case.source_extension is not None and case.target_extension is not None:
        return _fixed_extension_load_convert(case, target, target_lanes, expected, literals)
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
            f"        type ToVec = Simd<{target}, Generic<{target_lanes}>>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            f"        let mut buf: [{case.base_spelling}; {case.lanes}] = "
            f"[Default::default(); {case.lanes}];",
            f"        for i in 0..{case.lanes} {{ buf[i] = in0[i]; }}",
            f"        let expected: [{target}; {target_lanes}] = [{expected}];",
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            "::<Vec, ToVec>(buf.as_mut_ptr()) };",
            f"        for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _fixed_extension_load_convert(
    case: ValueTestCasePlan,
    target: str,
    target_lanes: int,
    expected: str,
    literals: str,
) -> str:
    to_array = _helper_name(case, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(case.source_extension)}>;",
            f"        type ToVec = Simd<{target}, {rust_extension_tag(case.target_extension)}>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            f"        let mut buf: [{case.base_spelling}; {case.lanes}] = "
            f"[Default::default(); {case.lanes}];",
            f"        for i in 0..{case.lanes} {{ buf[i] = in0[i]; }}",
            f"        let expected: [{target}; {target_lanes}] = [{expected}];",
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            "::<Vec, ToVec>(buf.as_mut_ptr()) };",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _extension_extract(case: ValueTestCasePlan) -> str:
    out_lanes = len(case.expected)
    literals = rust_literal_list(case.vector_inputs[0], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    from_array = _helper_name(case, "from_array_name")
    to_array = _helper_name(case, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(case.source_extension)}>;",
            f"        type ToVec = Simd<{case.base_spelling}, {rust_extension_tag(case.target_extension)}>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut h0: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{case.lanes} {{ h0[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {out_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<Vec, ToVec, {case.index_value}>({from_array}::<Vec>(h0));",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _extension_insert(case: ValueTestCasePlan) -> str:
    out_lanes = len(case.expected)
    orig = rust_literal_list(case.vector_inputs[0], case.type_tag)
    data = rust_literal_list(case.vector_inputs[1], case.type_tag)
    expected = rust_literal_list(case.expected, case.type_tag)
    from_array = _helper_name(case, "from_array_name")
    to_array = _helper_name(case, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type DataVec = Simd<{case.base_spelling}, {rust_extension_tag(case.source_extension)}>;",
            f"        type ResultVec = Simd<{case.base_spelling}, {rust_extension_tag(case.target_extension)}>;",
            f"        let orig0: [{case.base_spelling}; {out_lanes}] = [{orig}];",
            f"        let data0: [{case.base_spelling}; {case.lanes}] = [{data}];",
            "        let mut orig: <ResultVec as SimdVector>::Array = Default::default();",
            "        let mut data: <DataVec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{out_lanes} {{ orig[i] = orig0[i]; }}",
            f"        for i in 0..{case.lanes} {{ data[i] = data0[i]; }}",
            f"        let expected: [{case.base_spelling}; {out_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<DataVec, ResultVec, {case.index_value}>("
            f"{from_array}::<ResultVec>(orig), {from_array}::<DataVec>(data));",
            f"        let out = {to_array}::<ResultVec>(result);",
            f"        for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _helper_name(case: ValueTestCasePlan, field_name: str) -> str:
    name = getattr(case, field_name)
    if not name:
        raise ValueError(
            f"Rust value-test case {case.function_name!r} is missing {field_name}"
        )
    return rust_raw_identifier(name)


__all__ = (
    "_convert",
    "_extension_extract",
    "_extension_insert",
    "_fixed_extension_repr_cast",
    "_load_convert",
    "_repr_cast",
)
