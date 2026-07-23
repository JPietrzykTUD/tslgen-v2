"""Render Rust conversion and extension value-test cases."""

from __future__ import annotations

from tslc.catalog.model import TestComparison
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.value_tests._render_rust_helpers import rust_extension_tag
from tslc.value_tests.literals import rust_literal, rust_literal_list
from tslc.value_tests.model import ValueTestCasePlan


def _convert(case: ValueTestCasePlan) -> str:
    target_plan = case.target
    index = case.index
    assert target_plan is not None and index is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, expected_type)
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
            f"::<Vec, ToVec, {index.value}>(a0);",
            f"        for i in 0..{target_lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], result[i]); }",
            "    }",
        ]
    )


def _repr_cast(case: ValueTestCasePlan) -> str:
    if case.representation is not None:
        return _fixed_extension_repr_cast(case)
    target_plan = case.target
    assert target_plan is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, expected_type)
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


def _target_imask(case: ValueTestCasePlan) -> str:
    target = case.target
    representation = case.representation
    assert target is not None and representation is not None
    assert target.base_spelling is not None
    assert representation.target_extension is not None
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(representation.source_extension)}>;",
        f"        type ToVec = Simd<{target.base_spelling}, {rust_extension_tag(representation.target_extension)}>;",
    ]
    args: list[str] = []
    mask_index = 0
    scalar_index = 0
    for position, kind in enumerate(case.invocation.param_kinds):
        if kind in {"im", "imt"}:
            owner = "ToVec" if kind == "imt" else "Vec"
            value = rust_literal(case.inputs.masks[mask_index], "ui64")
            lines.append(
                f"        let a{position}: <{owner} as SimdVector>::ImaskType = "
                f"({value}) as <{owner} as SimdVector>::ImaskType;"
            )
            mask_index += 1
        else:
            assert kind == "usize"
            value = case.inputs.scalars[scalar_index]
            lines.append(f"        let a{position}: usize = ({value}) as usize;")
            scalar_index += 1
        args.append(f"a{position}")
    expected = rust_literal(case.expectation.values[0], "ui64")
    lines.extend(
        [
            f"        let result: <ToVec as SimdVector>::ImaskType = "
            f"{rust_raw_identifier(case.call_name)}::<Vec, ToVec>({', '.join(args)});",
            "        let expected: <ToVec as SimdVector>::ImaskType = "
            f"({expected}) as <ToVec as SimdVector>::ImaskType;",
            f'        assert_eq!(result, expected, "{case.case_name}: expected {{:?}}, got {{:?}}", expected, result);',
            "    }",
        ]
    )
    return "\n".join(lines)


def _fixed_extension_repr_cast(case: ValueTestCasePlan) -> str:
    target_plan = case.target
    representation = case.representation
    assert target_plan is not None and representation is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, expected_type)
    from_array = _required_name(representation.from_array_name, "from_array_name")
    to_array = _required_name(representation.to_array_name, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(representation.source_extension)}>;",
            f"        type ToVec = Simd<{target}, {rust_extension_tag(representation.target_extension)}>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut h0: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{case.lanes} {{ h0[i] = in0[i]; }}",
            f"        let expected: [{target}; {target_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<Vec, ToVec>({from_array}::<Vec>(&h0));",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _load_convert(case: ValueTestCasePlan) -> str:
    target_plan = case.target
    assert target_plan is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, expected_type)
    if case.representation is not None:
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
            "::<Vec, ToVec>(buf.as_ptr()) };",
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
    representation = case.representation
    assert representation is not None
    to_array = _required_name(representation.to_array_name, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(representation.source_extension)}>;",
            f"        type ToVec = Simd<{target}, {rust_extension_tag(representation.target_extension)}>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            f"        let mut buf: [{case.base_spelling}; {case.lanes}] = "
            f"[Default::default(); {case.lanes}];",
            f"        for i in 0..{case.lanes} {{ buf[i] = in0[i]; }}",
            f"        let expected: [{target}; {target_lanes}] = [{expected}];",
            f"        let result = unsafe {{ {rust_raw_identifier(case.call_name)}"
            "::<Vec, ToVec>(buf.as_ptr()) };",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        for i in 0..{target_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _extension_extract(case: ValueTestCasePlan) -> str:
    representation = case.representation
    index = case.index
    assert representation is not None and index is not None
    out_lanes = len(case.expectation.values)
    literals = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    from_array = _required_name(representation.from_array_name, "from_array_name")
    to_array = _required_name(representation.to_array_name, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(representation.source_extension)}>;",
            f"        type ToVec = Simd<{case.base_spelling}, {rust_extension_tag(representation.target_extension)}>;",
            f"        let in0: [{case.base_spelling}; {case.lanes}] = [{literals}];",
            "        let mut h0: <Vec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{case.lanes} {{ h0[i] = in0[i]; }}",
            f"        let expected: [{case.base_spelling}; {out_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<Vec, ToVec, {index.value}>({from_array}::<Vec>(&h0));",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _extension_insert(case: ValueTestCasePlan) -> str:
    representation = case.representation
    index = case.index
    assert representation is not None and index is not None
    out_lanes = len(case.expectation.values)
    orig = rust_literal_list(case.inputs.vectors[0], case.type_tag)
    data = rust_literal_list(case.inputs.vectors[1], case.type_tag)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    from_array = _required_name(representation.from_array_name, "from_array_name")
    to_array = _required_name(representation.to_array_name, "to_array_name")
    return "\n".join(
        [
            "    #[test]",
            f"    fn {case.function_name}() {{",
            f"        type DataVec = Simd<{case.base_spelling}, {rust_extension_tag(representation.source_extension)}>;",
            f"        type ResultVec = Simd<{case.base_spelling}, {rust_extension_tag(representation.target_extension)}>;",
            f"        let orig0: [{case.base_spelling}; {out_lanes}] = [{orig}];",
            f"        let data0: [{case.base_spelling}; {case.lanes}] = [{data}];",
            "        let mut orig: <ResultVec as SimdVector>::Array = Default::default();",
            "        let mut data: <DataVec as SimdVector>::Array = Default::default();",
            f"        for i in 0..{out_lanes} {{ orig[i] = orig0[i]; }}",
            f"        for i in 0..{case.lanes} {{ data[i] = data0[i]; }}",
            f"        let expected: [{case.base_spelling}; {out_lanes}] = [{expected}];",
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<DataVec, ResultVec, {index.value}>("
            f"{from_array}::<ResultVec>(&orig), {from_array}::<DataVec>(&data));",
            f"        let out = {to_array}::<ResultVec>(result);",
            f"        for i in 0..{out_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )


def _extension_result(case: ValueTestCasePlan) -> str:
    target = case.target
    representation = case.representation
    assert target is not None and representation is not None
    assert target.lanes is not None
    from_array = _required_name(representation.from_array_name, "from_array_name")
    to_array = _required_name(representation.to_array_name, "to_array_name")
    expected_lanes = len(case.expectation.values)
    expected = rust_literal_list(case.expectation.values, case.type_tag)
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Vec = Simd<{case.base_spelling}, {rust_extension_tag(representation.source_extension)}>;",
        f"        type ToVec = Simd<{case.base_spelling}, {rust_extension_tag(representation.target_extension)}>;",
    ]
    args: list[str] = []
    for position, values in enumerate(case.inputs.vectors):
        literals = rust_literal_list(values, case.type_tag)
        lines.extend(
            [
                f"        let in{position}: [{case.base_spelling}; {case.lanes}] = [{literals}];",
                f"        let mut h{position}: <Vec as SimdVector>::Array = Default::default();",
                f"        for i in 0..{case.lanes} {{ h{position}[i] = in{position}[i]; }}",
            ]
        )
        args.append(f"{from_array}::<Vec>(&h{position})")
    lines.extend(
        [
            f"        let result = {rust_raw_identifier(case.call_name)}"
            f"::<Vec, ToVec>({', '.join(args)});",
            f"        let out = {to_array}::<ToVec>(result);",
            f"        let expected: [{case.base_spelling}; {expected_lanes}] = [{expected}];",
            f"        for i in 0..{expected_lanes} {{ assert!(out[i].lane_eq(expected[i]), "
            f'"{case.case_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, expected[i], out[i]); }",
            "    }",
        ]
    )
    return "\n".join(lines)


def _differential(case: ValueTestCasePlan) -> str:
    differential = case.differential
    assert differential is not None
    from_array = differential.from_array_name
    to_array = _required_name(differential.to_array_name, "to_array_name")
    lines = [
        "    #[test]",
        f"    fn {case.function_name}() {{",
        f"        type Hw = Simd<{case.base_spelling}, {rust_extension_tag(differential.hardware_extension)}>;",
        f"        type Ref = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    for position, values in enumerate(case.inputs.vectors):
        literals = rust_literal_list(values, case.type_tag)
        lines.append(
            f"        let in{position}: [{case.base_spelling}; {case.lanes}] = [{literals}];"
        )
        lines.append(
            f"        let mut hin{position}: <Hw as SimdVector>::Array = Default::default();"
        )
        lines.append(
            f"        let mut r{position}: <Ref as SimdVector>::RegisterType = Default::default();"
        )
        lines.append(
            f"        for i in 0..{case.lanes} {{ "
            f"hin{position}[i] = in{position}[i]; "
            f"r{position}[i] = in{position}[i]; }}"
        )
    for position, mask in enumerate(case.inputs.masks):
        to_mask = _required_name(differential.to_mask_name, "to_mask_name")
        lines.append(
            f"        let hm{position} = {to_mask}::<Hw>("
            f"{mask}u64 as <Hw as SimdVector>::ImaskType);"
        )
        lines.append(
            f"        let rm{position} = {to_mask}::<Ref>("
            f"{mask}u64 as <Ref as SimdVector>::ImaskType);"
        )
    hw_args: list[str] = []
    ref_args: list[str] = []
    vector_index = 0
    mask_index = 0
    for kind in case.invocation.param_kinds:
        if kind == "v":
            hw_args.append(f"{from_array}::<Hw>(&hin{vector_index})")
            ref_args.append(f"r{vector_index}")
            vector_index += 1
        elif kind == "m":
            hw_args.append(f"hm{mask_index}")
            ref_args.append(f"rm{mask_index}")
            mask_index += 1
        elif kind != "sImm":
            raise ValueError(f"unsupported differential argument kind {kind!r}")
    hw_template_args = ["Hw", *case.invocation.generic_defaults]
    ref_template_args = ["Ref", *case.invocation.generic_defaults]
    if case.invocation.immediate is not None:
        hw_template_args.insert(1, case.invocation.immediate)
        ref_template_args.insert(1, case.invocation.immediate)
    hw_template_args.extend("_" for _ in range(case.invocation.inferred_type_args))
    ref_template_args.extend("_" for _ in range(case.invocation.inferred_type_args))
    hw_call = (
        f"{rust_raw_identifier(case.call_name)}"
        f"::<{', '.join(hw_template_args)}>({', '.join(hw_args)})"
    )
    ref_call = (
        f"{rust_raw_identifier(case.call_name)}"
        f"::<{', '.join(ref_template_args)}>({', '.join(ref_args)})"
    )
    if case.invocation.result_kind == "m":
        to_integral = _required_name(
            differential.to_integral_name,
            "to_integral_name",
        )
        lines.append(f"        let hw = {to_integral}::<Hw>({hw_call});")
        lines.append(f"        let reference: <Ref as SimdVector>::MaskType = {ref_call};")
        lines.append(
            f"        for i in 0..{case.lanes} {{ assert_eq!("
            "mask_bit(hw as u64, i), mask_bit(reference as u64, i), "
            f'"{case.function_name} lane {{}}", i); }}'
        )
    else:
        lines.append(f"        let hw = {to_array}::<Hw>({hw_call});")
        lines.append(f"        let reference = {ref_call};")
        comparison = (
            "lane_bitwise_eq"
            if case.expectation.comparison is TestComparison.BITWISE
            else "lane_eq"
        )
        lines.append(
            f"        for i in 0..{case.lanes} {{ assert!(hw[i].{comparison}(reference[i]), "
            f'"{case.function_name} lane {{}}: expected {{:?}}, got {{:?}}", '
            "i, reference[i], hw[i]); }"
        )
    lines.append("    }")
    return "\n".join(lines)


def _required_name(name: str | None, field_name: str) -> str:
    if not name:
        raise ValueError(f"Rust value-test case is missing {field_name}")
    return rust_raw_identifier(name)


__all__ = (
    "_convert",
    "_differential",
    "_extension_extract",
    "_extension_insert",
    "_fixed_extension_repr_cast",
    "_load_convert",
    "_repr_cast",
    "_target_imask",
)
