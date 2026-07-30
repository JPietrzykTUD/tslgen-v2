"""Render conversion and extension C++ value-test cases."""

from __future__ import annotations

from tslc.catalog.model import TestComparison
from tslc.value_tests.lane_math import runtime_tile_index
from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests.render_cpp_helpers import (
    append_runtime_vector_input,
    render_extension_test_template,
    scalable_header,
)


def _convert(case: ValueTestCasePlan) -> str:
    target_plan = case.target
    index = case.index
    assert target_plan is not None and index is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        f"  using ToVec = tsl::simd<{target}, tsl::generic<{target_lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename Vec::register_type a0;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) a0[i] = in0[i];",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f"  typename ToVec::register_type result = "
        f"tsl::{case.call_name}<Vec, ToVec, {index.value}>(a0);",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", result, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


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
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, expected_type)
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


def _scalable_repr_cast(case: ValueTestCasePlan) -> str:
    target = case.target
    scalable = case.scalable
    assert target is not None and scalable is not None
    assert target.base_spelling is not None and target.type_tag is not None
    assert scalable.store_name is not None
    lines = scalable_header(case)
    lines.append(
        f"  using ToVec = tsl::simd<{target.base_spelling}, "
        f"tsl::{scalable.source_extension}>;"
    )
    source = append_runtime_vector_input(lines, case, 0)
    expected = cpp_literal_list(case.expectation.values, target.type_tag)
    check = (
        "check_lanes_bitwise"
        if case.expectation.comparison is TestComparison.BITWISE
        else "check_lanes"
    )
    lines.extend(
        [
            f"  static const {target.base_spelling} authored_expected[{case.lanes}] = "
            f"{{{expected}}};",
            f"  std::vector<{target.base_spelling}> expected(lanes);",
            f"  std::vector<{target.base_spelling}> actual(lanes);",
            f"  for (std::size_t i = 0; i < lanes; ++i) expected[i] = "
            f"authored_expected[{runtime_tile_index('i', case.lanes)}];",
            f"  typename ToVec::register_type result = "
            f"tsl::{case.call_name}<Vec, ToVec>({source});",
            f"  tsl::{scalable.store_name}<ToVec, false>(actual.data(), result);",
            f"  return tsl::test::{check}<{target.base_spelling}>("
            f"\"{case.case_name}\", actual.data(), expected.data(), lanes);",
            "}",
        ]
    )
    return "\n".join(lines)


def _lane_convert(case: ValueTestCasePlan) -> str:
    target_plan = case.target
    assert target_plan is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes == case.lanes
    target = target_plan.base_spelling
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, target_plan.type_tag)
    representation = case.representation
    source_extension = (
        f"tsl::{representation.source_extension}"
        if representation is not None
        else f"tsl::generic<{case.lanes}>"
    )
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, {source_extension}>;",
        f"  using ToVec = tsl::simd<{target}, tsl::generic<{case.lanes}>>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
    ]
    if representation is None:
        lines.extend(
            [
                "  typename Vec::register_type source{};",
                f"  for (std::size_t i = 0; i < {case.lanes}; ++i) source[i] = in0[i];",
            ]
        )
    else:
        assert representation.from_array_name is not None
        lines.extend(
            [
                "  typename tsl::array_for<Vec>::type source_array{};",
                f"  for (std::size_t i = 0; i < {case.lanes}; ++i) source_array[i] = in0[i];",
                f"  auto source = tsl::{representation.from_array_name}<Vec>(source_array);",
            ]
        )
    lines.extend(
        [
            f"  auto result = tsl::{case.call_name}<Vec, ToVec>(source);",
            f"  static const {target} expected[{case.lanes}] = {{{expected}}};",
            f'  return tsl::test::check_lanes<{target}>('
            f'"{case.case_name}", result, expected, {case.lanes});',
            "}",
        ]
    )
    return "\n".join(lines)


def _target_imask(case: ValueTestCasePlan) -> str:
    target = case.target
    representation = case.representation
    assert target is not None and representation is not None
    assert target.base_spelling is not None
    assert representation.target_extension is not None
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{representation.source_extension}>;",
        f"  using ToVec = tsl::simd<{target.base_spelling}, tsl::{representation.target_extension}>;",
        "  using Result = typename ToVec::imask_type;",
    ]
    args: list[str] = []
    mask_index = 0
    scalar_index = 0
    for position, kind in enumerate(case.invocation.param_kinds):
        if kind in {"im", "imt"}:
            owner = "ToVec" if kind == "imt" else "Vec"
            value = cpp_literal(case.inputs.masks[mask_index], "ui64")
            lines.append(
                f"  typename {owner}::imask_type a{position} = "
                f"static_cast<typename {owner}::imask_type>({value});"
            )
            mask_index += 1
        else:
            assert kind == "usize"
            value = case.inputs.scalars[scalar_index]
            lines.append(
                f"  std::size_t a{position} = static_cast<std::size_t>({value});"
            )
            scalar_index += 1
        args.append(f"a{position}")
    expected = cpp_literal(case.expectation.values[0], "ui64")
    lines.extend(
        [
            f"  Result result = tsl::{case.call_name}<Vec, ToVec>({', '.join(args)});",
            f"  Result expected = static_cast<Result>({expected});",
            f'  return tsl::test::check_scalar<Result>("{case.case_name}", result, expected);',
            "}",
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
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{representation.source_extension}>;",
        f"  using ToVec = tsl::simd<{target}, tsl::{representation.target_extension}>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename tsl::array_for<Vec>::type hin;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) hin[i] = in0[i];",
        f"  auto result = tsl::{case.call_name}<Vec, ToVec>("
        f"tsl::{representation.from_array_name}<Vec>(hin));",
        f"  typename tsl::array_for<ToVec>::type hout = "
        f"tsl::{representation.to_array_name}<ToVec>(result);",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", hout, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _extension_extract(case: ValueTestCasePlan) -> str:
    representation = case.representation
    index = case.index
    assert representation is not None and index is not None
    out_lanes = len(case.expectation.values)
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{representation.source_extension}>;",
        f"  using ToVec = tsl::simd<{case.base_spelling}, tsl::{representation.target_extension}>;",
        f"  static const {case.base_spelling} in0[{case.lanes}] = {{{literals}}};",
        "  typename tsl::array_for<Vec>::type hin;",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) hin[i] = in0[i];",
        f"  auto result = tsl::{case.call_name}<Vec, ToVec, {index.value}>("
        f"tsl::{representation.from_array_name}<Vec>(hin));",
        f"  typename tsl::array_for<ToVec>::type hout = "
        f"tsl::{representation.to_array_name}<ToVec>(result);",
        f"  static const {case.base_spelling} expected[{out_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", hout, expected, {out_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _extension_insert(case: ValueTestCasePlan) -> str:
    representation = case.representation
    index = case.index
    assert representation is not None and index is not None
    out_lanes = len(case.expectation.values)
    orig_lits = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    data_lits = cpp_literal_list(case.inputs.vectors[1], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using DataVec = tsl::simd<{case.base_spelling}, tsl::{representation.source_extension}>;",
        f"  using ResultVec = tsl::simd<{case.base_spelling}, tsl::{representation.target_extension}>;",
        f"  static const {case.base_spelling} orig0[{out_lanes}] = {{{orig_lits}}};",
        f"  static const {case.base_spelling} data0[{case.lanes}] = {{{data_lits}}};",
        "  typename tsl::array_for<ResultVec>::type horig;",
        "  typename tsl::array_for<DataVec>::type hdata;",
        f"  for (std::size_t i = 0; i < {out_lanes}; ++i) horig[i] = orig0[i];",
        f"  for (std::size_t i = 0; i < {case.lanes}; ++i) hdata[i] = data0[i];",
        f"  auto result = tsl::{case.call_name}<DataVec, ResultVec, {index.value}>("
        f"tsl::{representation.from_array_name}<ResultVec>(horig), "
        f"tsl::{representation.from_array_name}<DataVec>(hdata));",
        f"  typename tsl::array_for<ResultVec>::type hout = "
        f"tsl::{representation.to_array_name}<ResultVec>(result);",
        f"  static const {case.base_spelling} expected[{out_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{case.base_spelling}>('
        f'"{case.case_name}", hout, expected, {out_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _extension_result(case: ValueTestCasePlan) -> str:
    target = case.target
    representation = case.representation
    assert target is not None and representation is not None
    assert target.lanes is not None
    expected_lanes = len(case.expectation.values)
    expected = cpp_literal_list(case.expectation.values, case.type_tag)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{representation.source_extension}>;",
        f"  using ToVec = tsl::simd<{case.base_spelling}, tsl::{representation.target_extension}>;",
    ]
    args: list[str] = []
    for position, values in enumerate(case.inputs.vectors):
        literals = cpp_literal_list(values, case.type_tag)
        lines.extend(
            [
                f"  static const {case.base_spelling} in{position}[{case.lanes}] = {{{literals}}};",
                f"  typename tsl::array_for<Vec>::type h{position};",
                f"  for (std::size_t i = 0; i < {case.lanes}; ++i) h{position}[i] = in{position}[i];",
            ]
        )
        args.append(f"tsl::{representation.from_array_name}<Vec>(h{position})")
    lines.extend(
        [
            f"  auto result = tsl::{case.call_name}<Vec, ToVec>({', '.join(args)});",
            f"  typename tsl::array_for<ToVec>::type hout = "
            f"tsl::{representation.to_array_name}<ToVec>(result);",
            f"  static const {case.base_spelling} expected[{expected_lanes}] = {{{expected}}};",
            f'  return tsl::test::check_lanes<{case.base_spelling}>('
            f'"{case.case_name}", hout, expected, {expected_lanes});',
            "}",
        ]
    )
    return "\n".join(lines)


def _load_convert(case: ValueTestCasePlan) -> str:
    if case.representation is not None:
        return _fixed_extension_load_convert(case)
    target_plan = case.target
    assert target_plan is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, expected_type)
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
    target_plan = case.target
    representation = case.representation
    assert target_plan is not None and representation is not None
    assert target_plan.base_spelling is not None and target_plan.type_tag is not None
    assert target_plan.lanes is not None
    target = target_plan.base_spelling
    target_lanes = target_plan.lanes
    expected_type = target_plan.type_tag
    buffer_len = len(case.inputs.vectors[0])
    literals = cpp_literal_list(case.inputs.vectors[0], case.type_tag)
    expected = cpp_literal_list(case.expectation.values, expected_type)
    lines = [
        f"int {case.function_name}() {{",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::{representation.source_extension}>;",
        f"  using ToVec = tsl::simd<{target}, tsl::{representation.target_extension}>;",
        f"  static const {case.base_spelling} in0[{buffer_len}] = {{{literals}}};",
        f"  {case.base_spelling} buf[{buffer_len}] = {{0}};",
        f"  for (std::size_t i = 0; i < {buffer_len}; ++i) buf[i] = in0[i];",
        f"  auto result = tsl::{case.call_name}<Vec, ToVec>(buf);",
        f"  typename tsl::array_for<ToVec>::type hout = "
        f"tsl::{representation.to_array_name}<ToVec>(result);",
        f"  static const {target} expected[{target_lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{target}>('
        f'"{case.case_name}", hout, expected, {target_lanes});',
        "}",
    ]
    return "\n".join(lines)


def _differential(case: ValueTestCasePlan) -> str:
    differential = case.differential
    assert differential is not None
    lines = [
        f"int {case.function_name}() {{",
        f"  using Hw = tsl::simd<{case.base_spelling}, tsl::{differential.hardware_extension}>;",
        f"  using Ref = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    for position, values in enumerate(case.inputs.vectors):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(f"  static const {case.base_spelling} in{position}[{case.lanes}] = {{{literals}}};")
        lines.append(f"  typename tsl::array_for<Hw>::type hin{position};")
        lines.append(f"  typename Ref::register_type r{position};")
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
            f"{{ hin{position}[i] = in{position}[i]; r{position}[i] = in{position}[i]; }}"
        )
    mask_kinds = tuple(
        kind for kind in case.invocation.param_kinds if kind in {"m", "im"}
    )
    for position, (kind, mask) in enumerate(
        zip(mask_kinds, case.inputs.masks, strict=True)
    ):
        if kind != "m":
            continue
        if differential.to_mask_name is None:
            raise ValueError("masked differential case requires to_mask_name")
        hardware_mask = _differential_hardware_mask(case, f"{mask}ull")
        lines.append(
            f"  typename Hw::mask_type hm{position} = {hardware_mask};"
        )
        lines.append(
            f"  typename Ref::mask_type rm{position} = "
            f"tsl::{differential.to_mask_name}<Ref>("
            f"static_cast<typename Ref::imask_type>({mask}ull));"
        )
    hw_args = []
    ref_args = []
    vector_index = 0
    mask_index = 0
    scalar_index = 0
    for kind in case.invocation.param_kinds:
        if kind == "v":
            hw_args.append(
                f"tsl::{differential.from_array_name}<Hw>(hin{vector_index})"
            )
            ref_args.append(f"r{vector_index}")
            vector_index += 1
        elif kind == "m":
            hw_args.append(f"hm{mask_index}")
            ref_args.append(f"rm{mask_index}")
            mask_index += 1
        elif kind == "im":
            mask = case.inputs.masks[mask_index]
            hw_args.append(
                "static_cast<typename Hw::imask_type>("
                f"{mask}ull)"
            )
            ref_args.append(
                "static_cast<typename Ref::imask_type>("
                f"{mask}ull)"
            )
            mask_index += 1
        elif kind == "s":
            value = cpp_literal(case.inputs.scalars[scalar_index], case.type_tag)
            hw_args.append(value)
            ref_args.append(value)
            scalar_index += 1
        elif kind == "usize":
            value = case.inputs.scalars[scalar_index]
            hw_args.append(f"static_cast<std::size_t>({value})")
            ref_args.append(f"static_cast<std::size_t>({value})")
            scalar_index += 1
        elif kind != "sImm":
            raise ValueError(f"unsupported differential argument kind {kind!r}")
    template_args_hw = ["Hw"]
    template_args_ref = ["Ref"]
    if case.invocation.immediate is not None:
        template_args_hw.append(case.invocation.immediate)
        template_args_ref.append(case.invocation.immediate)
    template_args_hw.extend(case.invocation.generic_defaults)
    template_args_ref.extend(case.invocation.generic_defaults)
    hw_call = (
        f"tsl::{case.call_name}<{', '.join(template_args_hw)}>({', '.join(hw_args)})"
    )
    ref_call = (
        f"tsl::{case.call_name}<{', '.join(template_args_ref)}>({', '.join(ref_args)})"
    )
    if case.invocation.result_kind == "m":
        lines.append(f"  auto hw = tsl::{differential.to_integral_name}<Hw>({hw_call});")
        lines.append(f"  typename Ref::mask_type ref = {ref_call};")
        lines.append(
            f'  return tsl::test::check_mask_match_for<Hw>("{case.function_name}", '
            f"hw, ref, {case.lanes});"
        )
    elif case.invocation.result_kind == "s":
        lines.append(f"  {case.base_spelling} hw = {hw_call};")
        lines.append(f"  {case.base_spelling} ref = {ref_call};")
        lines.append(
            f'  return tsl::test::check_scalar<{case.base_spelling}>('
            f'"{case.function_name}", hw, ref);'
        )
    else:
        lines.append(f"  typename tsl::array_for<Hw>::type hout = tsl::{differential.to_array_name}<Hw>({hw_call});")
        lines.append(f"  typename Ref::register_type ref = {ref_call};")
        check = (
            "check_match_bitwise"
            if case.expectation.comparison is TestComparison.BITWISE
            else "check_match"
        )
        lines.append(
            f"  return tsl::test::{check}<{case.base_spelling}>("
            f'"{case.function_name}", hout, ref, {case.lanes});'
        )
    lines.append("}")
    return "\n".join(lines)


def _differential_hardware_mask(case: ValueTestCasePlan, mask_bits: str) -> str:
    """Materialize authored lane bits through the extension's mask test adapter."""

    differential = case.differential
    assert differential is not None and differential.to_mask_name is not None
    template = differential.mask_from_bits_template
    if template is None:
        return (
            f"tsl::{differential.to_mask_name}<Hw>("
            f"static_cast<typename Hw::imask_type>({mask_bits}))"
        )
    return render_extension_test_template(
        template,
        vec="Hw",
        mask_bits=mask_bits,
        authored_lanes=str(case.lanes),
        lanes=str(case.lanes),
        base_type=case.base_spelling,
        base=case.base_spelling,
    )


def _differential_fuzz(case: ValueTestCasePlan) -> str:
    """A runtime PRNG loop comparing `prim<Hw>` to the generic reference `prim<Ref>` over many
    random inputs. On the first disagreement it prints the failing lane (via check_match) plus the
    reproducing iteration, seed, and the per-lane inputs, then fails."""

    differential = case.differential
    assert differential is not None
    param_kinds = case.invocation.param_kinds
    vector_positions = [
        position for position, kind in enumerate(param_kinds) if kind == "v"
    ]
    vector_index_by_position = {
        position: vector_index
        for vector_index, position in enumerate(vector_positions)
    }
    mask_positions = [
        position for position, kind in enumerate(param_kinds) if kind == "m"
    ]
    if len(mask_positions) > 1:
        raise ValueError("differential fuzz supports at most one mask argument")
    if any(kind not in {"m", "v"} for kind in param_kinds):
        raise ValueError("differential fuzz supports only mask and vector arguments")
    if mask_positions and differential.to_mask_name is None:
        raise ValueError("masked differential fuzz requires to_mask_name")
    lanes = case.lanes
    base = case.base_spelling
    lines = [
        f"int {case.function_name}() {{",
        f"  using Hw = tsl::simd<{base}, tsl::{differential.hardware_extension}>;",
        f"  using Ref = tsl::simd<{base}, tsl::generic<{lanes}>>;",
        f"  std::uint64_t rng = {differential.fuzz_seed}ULL;",
        f"  for (std::size_t iter = 0; iter < {differential.fuzz_iterations}; ++iter) {{",
    ]
    if mask_positions:
        to_mask_name = differential.to_mask_name
        lines.extend(
            [
                "    const std::uint64_t mask_bits = "
                "tsl::test::fuzz_next<std::uint64_t>(rng);",
                "    typename Hw::mask_type hm = "
                f"{_differential_hardware_mask(case, 'mask_bits')};",
                "    typename Ref::mask_type rm = "
                f"tsl::{to_mask_name}<Ref>("
                "static_cast<typename Ref::imask_type>(mask_bits));",
            ]
        )
    for vector_index in range(len(vector_positions)):
        lines.append(f"    typename tsl::array_for<Hw>::type hin{vector_index};")
        lines.append(f"    typename Ref::register_type r{vector_index};")
    lines.append(f"    for (std::size_t i = 0; i < {lanes}; ++i) {{")
    for position in vector_positions:
        vector_index = vector_index_by_position[position]
        qualifier = (
            "" if position == differential.nonzero_argument_index else "const "
        )
        lines.append(
            f"      {qualifier}{base} v{vector_index} = "
            f"tsl::test::fuzz_next<{base}>(rng);"
        )
        if position == differential.nonzero_argument_index:
            if mask_positions:
                lines.append(
                    f"      if (((mask_bits >> i) & 1ULL) == 0) v{vector_index} = "
                    f"static_cast<{base}>(0);"
                )
                lines.append(
                    f"      else if (v{vector_index} == static_cast<{base}>(0)) "
                    f"v{vector_index} = static_cast<{base}>(1);"
                )
            else:
                lines.append(
                    f"      if (v{vector_index} == static_cast<{base}>(0)) "
                    f"v{vector_index} = static_cast<{base}>(1);"
                )
        lines.append(
            f"      hin{vector_index}[i] = v{vector_index}; "
            f"r{vector_index}[i] = v{vector_index};"
        )
    lines.append("    }")
    hw_args: list[str] = []
    ref_args: list[str] = []
    for position, kind in enumerate(param_kinds):
        if kind == "m":
            hw_args.append("hm")
            ref_args.append("rm")
        else:
            vector_index = vector_index_by_position[position]
            hw_args.append(
                f"tsl::{differential.from_array_name}<Hw>(hin{vector_index})"
            )
            ref_args.append(f"r{vector_index}")
    hw_call = f"tsl::{case.call_name}<Hw>({', '.join(hw_args)})"
    ref_call = f"tsl::{case.call_name}<Ref>({', '.join(ref_args)})"
    if case.invocation.result_kind == "m":
        lines.append(f"    auto hw = tsl::{differential.to_integral_name}<Hw>({hw_call});")
        lines.append(f"    typename Ref::mask_type ref = {ref_call};")
        check = f'tsl::test::check_mask_match_for<Hw>("{case.function_name}", hw, ref, {lanes})'
    else:
        lines.append(f"    typename tsl::array_for<Hw>::type hw = tsl::{differential.to_array_name}<Hw>({hw_call});")
        lines.append(f"    typename Ref::register_type ref = {ref_call};")
        check = f'tsl::test::check_match<{base}>("{case.function_name}", hw, ref, {lanes})'
    lines.append(f"    if ({check} != 0) {{")
    lines.append(
        f'      std::fprintf(stderr, "  reproduce: fuzz iter %zu, seed {differential.fuzz_seed}\\n", iter);'
    )
    if mask_positions:
        lines.append(
            '      std::fprintf(stderr, "    mask_bits=%llu\\n", '
            "static_cast<unsigned long long>(mask_bits));"
        )
    lines.append(f"      for (std::size_t i = 0; i < {lanes}; ++i) {{")
    lines.append('        std::fprintf(stderr, "    lane %zu:", i);')
    for position in vector_positions:
        vector_index = vector_index_by_position[position]
        lines.append(f'        std::fprintf(stderr, " arg{position}=");')
        lines.append(
            f"        tsl::test::print_lane<{base}>(hin{vector_index}[i]);"
        )
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
    "_lane_convert",
    "_target_imask",
    "_fixed_extension_repr_cast",
    "_extension_extract",
    "_extension_insert",
    "_load_convert",
    "_fixed_extension_load_convert",
    "_differential",
    "_differential_fuzz",
)
