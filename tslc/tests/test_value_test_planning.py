from __future__ import annotations

from pathlib import Path

import pytest

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    Catalog,
    ParamTypeRule,
    Primitive,
    TestArg as TslTestArg,
    TestCase as TslTestCase,
)
from tslc.compiler_assets import RenderAssets
from tslc.lower.lowerer import LoweredSpecialization
from tslc.render.emitted_names import finalize_emitted_names
from tslc.render.model import LoweredBody
from tslc.render.project import ProfileRender, render_project
from tslc.value_tests.coverage import parity_gaps, parity_inventory
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    discover_harness_primitives,
)
from tslc.value_tests.model import (
    DEFAULT_VALUE_TEST_CASE_CAPABILITIES,
    DEFAULT_VALUE_TEST_CASE_KINDS,
    ValueTestCasePlan,
    ValueTestCoverageEntry,
    ValueTestProfilePlan,
)
from tslc.value_tests.renderer_capability import ValueTestRendererCapability
from tslc.value_tests._render_cpp_dispatch import CPP_VALUE_TEST_RENDERER
from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT, render_cpp_values_runner
from tslc.value_tests.render_rust import (
    RUST_VALUE_TEST_RENDERER,
    RUST_VALUE_TEST_SUPPORT,
    render_rust_values_file,
)

_VALUE_TEST_SUPPORTS = (CPP_VALUE_TEST_SUPPORT, RUST_VALUE_TEST_SUPPORT)


def test_profile_render_freezes_backend_mappings() -> None:
    source_cpp: dict[str, tuple[LoweredSpecialization, ...]] = {}
    profile = ProfileRender(
        profile=MachineProfile("unit", "generic", frozenset(), {}),
        specializations_by_backend={"cpp": source_cpp, "rust": {}},
    )

    source_cpp["late"] = ()

    assert "late" not in profile.specializations("cpp")
    with pytest.raises(TypeError):
        profile.specializations("cpp")["late"] = ()  # type: ignore[index]


def test_harness_discovery_uses_signatures_not_names() -> None:
    catalog = _catalog(
        Primitive("lane_in", "v:=s[]", ("data",), (), ()),
        Primitive("lane_out", "s[]:=v", ("data",), (), ()),
        Primitive("mask_bits", "im:=m", ("mask",), (), ()),
        Primitive("load", "v:=cptr", ("ptr",), (), ()),
        Primitive("store", "void:=(ptr,v)", ("ptr", "data"), (), ()),
    )

    harness = discover_harness_primitives(catalog)

    assert harness.from_array == "lane_in"
    assert harness.to_array == "lane_out"
    assert harness.to_integral == "mask_bits"
    assert harness.load == "load"
    assert harness.store == "store"
    assert harness.diagnostics == ()


def test_emitted_name_split_preserves_source_primitive_identity() -> None:
    runtime = _spec("shift", "shift", param_kinds=("v", "v"))
    immediate = _spec(
        "shift",
        "shift",
        param_kinds=("v", "sImm"),
        immediate=("amount", "std::uint32_t"),
    )

    finalized = finalize_emitted_names({"shift": (runtime, immediate)}, frozenset({"shift"}))

    assert finalized["shift_imm"][0].primitive_name == "shift_imm"
    assert finalized["shift_imm"][0].source_primitive_name == "shift"


def test_planner_uses_source_identity_for_emitted_mask_name() -> None:
    primitive = Primitive(
        "sum",
        "v:=(m,v,v)",
        ("mask", "a", "b"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="masked",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                inputs=(
                    TslTestArg("mask", mask_bits="5"),
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("vector", values=("10", "20", "30", "40")),
                ),
                expected=("11", "0", "33", "0"),
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec(
        "sum_maskz",
        "sum",
        param_kinds=("m", "v", "v"),
        mask_policy="zero",
    )
    profile = _profile(cpp={"sum_maskz": (spec,)})

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    cpp_profiles = plan.profiles_for("cpp")
    assert cpp_profiles[0].cases[0].call_name == "sum_maskz"
    assert cpp_profiles[0].cases[0].kind == "masked"


def test_planner_emits_fixed_masked_mask_result_cases() -> None:
    primitive = Primitive(
        "equal",
        "m:=(m,v,v)",
        ("mask", "left", "right"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="masked_equal",
                type_tag="si32",
                tags=("mask", "basic"),
                lanes=4,
                inputs=(
                    TslTestArg("mask", mask_bits="5"),
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("vector", values=("1", "0", "3", "0")),
                ),
                expected=("-1", "0", "-1", "0"),
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec(
        "equal_maskz",
        "equal",
        result_kind="m",
        param_kinds=("m", "v", "v"),
        mask_policy="zero",
    )
    profile = _profile(cpp={"equal_maskz": (spec,)}, rust={"equal_maskz": (spec,)})

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    cpp_case = plan.profiles_for("cpp")[0].cases[0]
    rust_case = plan.profiles_for("rust")[0].cases[0]
    assert cpp_case.kind == "mask_result"
    assert rust_case.kind == "mask_result"
    assert cpp_case.call_name == "equal_maskz"
    assert cpp_case.param_kinds == ("m", "v", "v")
    assert cpp_case.mask_inputs == ("5",)
    assert cpp_case.vector_inputs == (("1", "2", "3", "4"), ("1", "0", "3", "0"))
    assert cpp_case.expected == ("5",)
    assert {entry.status for entry in plan.coverage} == {"emitted"}


def test_simple_shape_patterns_are_not_ordered_by_first_overload() -> None:
    primitive = Primitive(
        "store",
        "void:=(ptr,v)",
        ("ptr", "data"),
        (),
        (),
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                inputs=(TslTestArg("vector", values=("1", "2", "3", "4")),),
                expected=("1", "2", "3", "4"),
                attrs={"aligned": "false"},
            ),
        ),
    )
    scalar_overload = _spec(
        "store",
        "store",
        result_kind="void",
        param_kinds=("ptr", "s"),
        axis=(("aligned", "false"),),
    )
    vector_overload = _spec(
        "store",
        "store",
        result_kind="void",
        param_kinds=("ptr", "v"),
        axis=(("aligned", "false"),),
    )
    profile = _profile(cpp={"store": (scalar_overload, vector_overload)})

    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        (CPP_VALUE_TEST_SUPPORT,),
    ).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", "unit", profile.specializations("cpp")
            ),
        )
    )

    assert plan.diagnostics == ()
    cases = plan.profiles_for("cpp")[0].cases
    assert [(case.kind, case.case_name, case.axis_args) for case in cases] == [
        ("store", "basic", ("false",))
    ]


def test_lane_list_value_tests_are_planned_and_rendered(
    render_assets: RenderAssets,
) -> None:
    primitive = Primitive(
        "set",
        "v:=(lanes<s>)",
        ("values",),
        (),
        (),
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                inputs=(TslTestArg("vector", values=("1", "2", "3", "4")),),
                expected=("4", "3", "2", "1"),
            ),
        ),
    )
    catalog = _catalog(primitive)
    spec = _spec("set", "set", param_kinds=("lanes<s>",))
    profile = _profile(cpp={"set": (spec,)}, rust={"set": (spec,)})

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    assert [case.kind for case in plan.profiles_for("cpp")[0].cases] == ["lane_list"]
    assert [case.kind for case in plan.profiles_for("rust")[0].cases] == ["lane_list"]
    cpp_source = render_cpp_values_runner(plan.profiles_for("cpp")[0], render_assets)
    rust_source = render_rust_values_file(plan.profiles_for("rust"), render_assets)
    assert "typename tsl::array_for<Vec>::type values;" in cpp_source
    assert "tsl::set<Vec>(values)" in cpp_source
    assert "let mut values: <Vec as SimdVector>::Array = Default::default();" in rust_source
    assert "set::<Vec>(&values)" in rust_source


def test_pointer_layout_planning_consumes_param_types() -> None:
    primitive = Primitive(
        "store_mask_repr",
        "void:=(ptr,m)",
        ("ptr", "mask"),
        (),
        (),
        attributes={"aligned": "true", "packed": "false"},
        param_type_rules=(
            ParamTypeRule(
                parameter_name="ptr",
                attribute_name="packed",
                attribute_value="false",
                type_expr="type<generation>(base::in) *",
            ),
        ),
        tests=(
            TslTestCase(
                name="store_mask_repr_si32_packed_false_layout",
                type_tag="si32",
                tags=("layout",),
                lanes=4,
                inputs=(TslTestArg("mask", mask_bits="5"),),
                expected=("1", "0", "1", "0"),
                attrs={"aligned": "true", "packed": "false"},
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec(
        "store_mask_repr",
        "store_mask_repr",
        param_kinds=("ptr", "m"),
        result_kind="void",
        axis=(("aligned", "true"), ("packed", "false")),
    )
    profile = _profile(cpp={"store_mask_repr": (spec,)})

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    cases = plan.profiles_for("cpp")[0].cases
    assert len(cases) == 1
    assert cases[0].kind == "mask_store"
    assert cases[0].expected_type_tag == "si32"
    assert cases[0].target_base_spelling == "std::int32_t"


def test_planner_warns_for_each_unsupported_authored_case() -> None:
    primitive = Primitive(
        "neg",
        "v:=v",
        ("value",),
        (),
        (),
        tests=(
            TslTestCase(
                name="good",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                inputs=(TslTestArg("vector", values=("1", "2", "3", "4")),),
                expected=("-1", "-2", "-3", "-4"),
            ),
            TslTestCase(
                name="bad",
                type_tag="si32",
                tags=("bad",),
                lanes=4,
                inputs=(TslTestArg("vector", values=("1", "2", "3", "4")),),
                expected=("-1", "-2", "-3"),
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec("neg", "neg", param_kinds=("v",))
    profile = _profile(cpp={"neg": (spec,)})

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    assert [case.case_name for case in plan.profiles_for("cpp")[0].cases] == ["good"]
    warnings = [
        diagnostic
        for diagnostic in plan.diagnostics
        if diagnostic.code == "TSL-VALUE-TEST-UNSUPPORTED-CASE"
    ]
    assert len(warnings) == 1
    assert "bad" in warnings[0].message


def test_render_project_surfaces_value_test_warnings_when_requested(
    render_assets: RenderAssets,
) -> None:
    primitive = Primitive(
        "neg",
        "v:=v",
        ("value",),
        (),
        (),
        tests=(
            TslTestCase(
                name="bad",
                type_tag="si32",
                tags=("bad",),
                lanes=4,
                inputs=(TslTestArg("vector", values=("1", "2", "3", "4")),),
                expected=("-1", "-2", "-3"),
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec("neg", "neg", param_kinds=("v",))
    profile = _profile(cpp={"neg": (spec,)})

    rendered = render_project(
        (profile,),
        backends=("cpp",),
        catalog=catalog,
        value_test_warnings=True,
        assets=render_assets,
    )

    assert [diagnostic.code for diagnostic in rendered.diagnostics] == [
        "TSL-VALUE-TEST-UNSUPPORTED-CASE"
    ]
    suppressed = render_project(
        (profile,),
        backends=("cpp",),
        catalog=catalog,
        value_test_warnings=False,
        assets=render_assets,
    )
    assert suppressed.diagnostics == ()


def test_renderers_consume_prebuilt_plans_without_catalog(
    render_assets: RenderAssets,
) -> None:
    cpp_case = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_add",
        case_name="basic",
        call_name="plus",
        type_tag="si32",
        base_spelling="std::int32_t",
        lanes=2,
        vector_inputs=(("1", "2"), ("3", "4")),
        expected=("4", "6"),
        result_kind="v",
        param_kinds=("v", "v"),
    )
    cpp_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_case,)), render_assets
    )
    assert "tsl::plus<Vec>(v0, v1)" in cpp_source

    cpp_scalable_case = ValueTestCasePlan(
        kind="scalable_golden",
        function_name="test_scalable_plus",
        case_name="basic",
        call_name="plus",
        type_tag="si32",
        base_spelling="std::int32_t",
        lanes=2,
        vector_inputs=(("1", "2"), ("3", "4")),
        expected=("4", "6"),
        result_kind="v",
        param_kinds=("v", "v"),
        source_extension="sve",
        load_name="load",
        store_name="store",
        runtime_lanes_expr="svcntb() / sizeof(std::int32_t)",
    )
    cpp_scalable_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_scalable_case,)),
        render_assets,
    )
    assert "using Vec = tsl::simd<std::int32_t, tsl::sve>;" in cpp_scalable_source
    assert "const std::size_t lanes = static_cast<std::size_t>(" in cpp_scalable_source
    assert "tsl::load<Vec, false>(in0.data())" in cpp_scalable_source
    assert "tsl::plus<Vec>(v0, v1)" in cpp_scalable_source
    assert "tsl::store<Vec, false>(actual.data(), result)" in cpp_scalable_source

    rust_case = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_mod",
        case_name="keyword",
        call_name="mod",
        type_tag="si32",
        base_spelling="i32",
        lanes=2,
        vector_inputs=(("5", "7"), ("2", "3")),
        expected=("1", "1"),
        result_kind="v",
        param_kinds=("v", "v"),
    )
    rust_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_case,)),),
        render_assets,
    )
    assert "r#mod::<Vec>(a0, a1)" in rust_source

    rust_masked_case = ValueTestCasePlan(
        kind="masked",
        function_name="test_add_mask",
        case_name="masked",
        call_name="add_maskz",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"), ("10", "20", "30", "40")),
        expected=("11", "0", "33", "0"),
        param_kinds=("m", "v", "v"),
        mask_inputs=("5",),
    )
    rust_masked_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_masked_case,)),),
        render_assets,
    )
    assert "let m0: <Vec as SimdVector>::MaskType = 5u64;" in rust_masked_source
    assert "add_maskz::<Vec>(m0, v0, v1)" in rust_masked_source
    assert "expected: [i32; 4] = [11, 0, 33, 0]" in rust_masked_source

    rust_mask_to_vector_case = ValueTestCasePlan(
        kind="mask_to_vector",
        function_name="test_to_vector",
        case_name="to_vector",
        call_name="to_vector",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        expected=("-1", "0", "-1", "0"),
        mask_inputs=("5",),
    )
    rust_mask_to_vector_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_mask_to_vector_case,)),),
        render_assets,
    )
    assert "let mask: <Vec as SimdVector>::MaskType = 5u64;" in rust_mask_to_vector_source
    assert "to_vector::<Vec>(mask)" in rust_mask_to_vector_source

    rust_mask_result_case = ValueTestCasePlan(
        kind="mask_result",
        function_name="test_equal",
        case_name="equal",
        call_name="equal",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"), ("1", "0", "3", "0")),
        expected=("5",),
        param_kinds=("v", "v"),
    )
    rust_mask_result_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_mask_result_case,)),),
        render_assets,
    )
    assert "equal::<Vec>(v0, v1)" in rust_mask_result_source
    assert 'assert_eq!(mask_bit(result as u64, 2), true, "equal lane 2");' in rust_mask_result_source

    rust_mask_logic_case = ValueTestCasePlan(
        kind="mask_logic",
        function_name="test_mask_and",
        case_name="mask_and",
        call_name="mask_binary_and",
        type_tag="ui32",
        base_spelling="u32",
        lanes=4,
        expected=("8",),
        mask_inputs=("10", "12"),
        param_kinds=("m", "m"),
    )
    rust_mask_logic_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_mask_logic_case,)),),
        render_assets,
    )
    assert "mask_binary_and::<Vec>(m0, m1)" in rust_mask_logic_source
    assert (
        'assert_eq!(mask_bit(result as u64, 3), true, "mask_and lane 3");'
        in rust_mask_logic_source
    )

    rust_broadcast_case = ValueTestCasePlan(
        kind="broadcast",
        function_name="test_set1",
        case_name="set1",
        call_name="set1",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        expected=("7", "7", "7", "7"),
        scalar_input="7",
    )
    rust_broadcast_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_broadcast_case,)),),
        render_assets,
    )
    assert "let value: i32 = 7;" in rust_broadcast_source
    assert "set1::<Vec>(value)" in rust_broadcast_source

    rust_immediate_case = ValueTestCasePlan(
        kind="immediate",
        function_name="test_shift_left_imm",
        case_name="shift_left_imm",
        call_name="shift_left_imm",
        type_tag="ui32",
        base_spelling="u32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"),),
        expected=("2", "4", "6", "8"),
        immediate_value="1",
    )
    rust_immediate_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_immediate_case,)),),
        render_assets,
    )
    assert "shift_left_imm::<Vec, 1>(a0)" in rust_immediate_source
    assert "let expected: [u32; 4] = [2, 4, 6, 8];" in rust_immediate_source

    rust_mask_store_case = ValueTestCasePlan(
        kind="mask_store",
        function_name="test_store_mask_repr",
        case_name="store_mask_repr",
        call_name="store_mask_repr",
        type_tag="ui32",
        base_spelling="u32",
        lanes=4,
        expected=("0", "4294967295", "0", "4294967295"),
        expected_type_tag="ui32",
        mask_inputs=("10",),
        axis_args=("false", "false"),
        target_base_spelling="u32",
        buffer_length=4,
    )
    rust_mask_store_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_mask_store_case,)),),
        render_assets,
    )
    assert not any(line.rstrip() != line for line in rust_mask_store_source.splitlines())
    assert "let mut buf: [u32; 4] = [Default::default(); 4];" in rust_mask_store_source
    assert "store_mask_repr::<Vec, false, false>(" in rust_mask_store_source
    assert (
        "buf.as_mut_ptr().add(0) as *mut <Vec as SimdVector>::BaseType"
        in rust_mask_store_source
    )
    assert "for i in 0..4 { assert!(buf[i].lane_eq(expected[i])," in rust_mask_store_source

    rust_reduction_case = ValueTestCasePlan(
        kind="reduction",
        function_name="test_hadd",
        case_name="hadd",
        call_name="hadd",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"),),
        expected=("10",),
    )
    rust_reduction_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_reduction_case,)),),
        render_assets,
    )
    assert "hadd::<Vec>(v0)" in rust_reduction_source
    assert "let expected: i32 = 10;" in rust_reduction_source
    assert "result.lane_eq(expected)" in rust_reduction_source

    rust_scalar_vector_case = ValueTestCasePlan(
        kind="scalar_vector",
        function_name="test_sequence",
        case_name="sequence",
        call_name="sequence",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        expected=("3", "4", "5", "6"),
        param_kinds=("s",),
        scalar_inputs=("3",),
    )
    rust_scalar_vector_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_scalar_vector_case,)),),
        render_assets,
    )
    assert "let s0: i32 = 3;" in rust_scalar_vector_source
    assert "sequence::<Vec>(s0)" in rust_scalar_vector_source

    rust_scalar_case = ValueTestCasePlan(
        kind="scalar_result",
        function_name="test_extract_value",
        case_name="extract_value",
        call_name="extract_value",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"),),
        expected=("3",),
        result_kind="s",
        param_kinds=("v",),
        index_value="2",
    )
    rust_scalar_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_scalar_case,)),),
        render_assets,
    )
    assert "extract_value::<Vec, 2>(v0)" in rust_scalar_source
    assert "let expected: i32 = 3;" in rust_scalar_source
    assert "result.lane_eq(expected)" in rust_scalar_source

    rust_compile_case = ValueTestCasePlan(
        kind="compile_only",
        function_name="test_set_undef_compiles",
        case_name="compile",
        call_name="set_undef",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        result_kind="v",
        param_kinds=(),
    )
    rust_compile_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_compile_case,)),),
        render_assets,
    )
    assert "let result = set_undef::<Vec>();" in rust_compile_source
    assert "let _ = result;" in rust_compile_source


def test_value_test_case_plan_validates_kind_requirements() -> None:
    zero_arg = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_zero",
        case_name="zero",
        call_name="set_zero",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        expected=("0", "0", "0", "0"),
        result_kind="v",
        param_kinds=(),
    )
    assert zero_arg.vector_inputs == ()

    with pytest.raises(ValueError, match="unsupported value-test case kind"):
        ValueTestCasePlan(
            kind="surprise",
            function_name="test_bad",
            case_name="bad",
            call_name="bad",
            type_tag="si32",
            base_spelling="i32",
            lanes=4,
        )

    with pytest.raises(ValueError, match="requires expected to contain 4 lane values"):
        ValueTestCasePlan(
            kind="load",
            function_name="test_load_bad",
            case_name="load_bad",
            call_name="load",
            type_tag="si32",
            base_spelling="i32",
            lanes=4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2"),
        )

    with pytest.raises(ValueError, match="requires runtime_lanes_expr"):
        ValueTestCasePlan(
            kind="scalable_mask_result",
            function_name="test_scalable_bad",
            case_name="scalable_bad",
            call_name="equal",
            type_tag="si32",
            base_spelling="i32",
            lanes=4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "0", "1", "0"),
            result_kind="m",
            param_kinds=("v",),
            source_extension="sve",
            load_name="load",
            mask_check_expr="true",
        )

    with pytest.raises(ValueError, match="requires to_array_name for value results"):
        ValueTestCasePlan(
            kind="differential",
            function_name="test_diff_bad_value",
            case_name="diff_bad_value",
            call_name="add",
            type_tag="si32",
            base_spelling="i32",
            lanes=4,
            vector_inputs=(("1", "2", "3", "4"),),
            result_kind="v",
            param_kinds=("v",),
            hardware_extension="avx2",
            from_array_name="from_array",
        )

    with pytest.raises(ValueError, match="requires to_integral_name for mask results"):
        ValueTestCasePlan(
            kind="differential_fuzz",
            function_name="test_diff_bad_mask",
            case_name="diff_bad_mask",
            call_name="equal",
            type_tag="si32",
            base_spelling="i32",
            lanes=4,
            result_kind="m",
            param_kinds=("v",),
            hardware_extension="avx2",
            from_array_name="from_array",
            to_array_name="to_array",
            fuzz_seed=1,
            fuzz_iterations=8,
        )


def test_scalable_tiling_is_gated_on_corpus_cross_lane_fact() -> None:
    # Every scalable tiling kind replicates the authored fixed-length pattern across the runtime
    # lane count with `i % authored_lanes`; that identity holds only for lane-local ops. The gate
    # trusts the corpus-declared `cross_lane` fact: the elementwise default (False) is tiling-safe,
    # a cross-lane op (True) is refused, and an unresolved primitive is refused conservatively.
    from tslc.value_tests._case_scalable_common import tiling_is_safe

    catalog = _catalog(
        Primitive("add", "v:=(v,v)", ("a", "b"), (), ()),
        Primitive("hadd", "v:=(v,v)", ("a", "b"), (), (), cross_lane=True),
    )
    elementwise = _spec("add", "add", param_kinds=("v", "v"))
    cross_lane = _spec("hadd", "hadd", param_kinds=("v", "v"))
    unknown = _spec("ghost", "ghost", param_kinds=("v", "v"))

    assert tiling_is_safe((elementwise,), catalog) is True
    assert tiling_is_safe((cross_lane,), catalog) is False
    assert tiling_is_safe((unknown,), catalog) is False


def test_rust_renderer_consumes_memory_and_conversion_plans_without_catalog(
    render_assets: RenderAssets,
) -> None:
    cases = (
        ValueTestCasePlan(
            "array_to_vector",
            "test_from_array",
            "from_array",
            "from_array",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
        ),
        ValueTestCasePlan(
            "vector_to_array",
            "test_to_array",
            "to_array",
            "to_array",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
        ),
        ValueTestCasePlan(
            "load",
            "test_load",
            "load",
            "load",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
            axis_args=("true",),
        ),
        ValueTestCasePlan(
            "store",
            "test_store",
            "store",
            "store",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
            axis_args=("false",),
            buffer_length=4,
        ),
        ValueTestCasePlan(
            "scalar_pointer_load",
            "test_load_scalar",
            "load_scalar",
            "load_scalar",
            "f32",
            "f32",
            4,
            vector_inputs=(("0", "5", "9"),),
            expected=("5",),
            axis_args=("false",),
            buffer_offset=1,
            buffer_length=3,
        ),
        ValueTestCasePlan(
            "mask_pointer_load",
            "test_load_mask_repr",
            "load_mask_repr",
            "load_mask_repr",
            "ui32",
            "u32",
            4,
            vector_inputs=(("0", "4294967295", "0", "4294967295"),),
            expected=("10",),
            expected_type_tag="ui32",
            target_base_spelling="u32",
            axis_args=("false", "false"),
            buffer_length=4,
        ),
        ValueTestCasePlan(
            "masked_pointer_load",
            "test_expand_load",
            "expand_load",
            "expand_load",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
            mask_inputs=("15",),
            axis_args=("true",),
        ),
        ValueTestCasePlan(
            "masked_pointer_store",
            "test_compress_store",
            "compress_store",
            "compress_store",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
            mask_inputs=("15",),
            axis_args=("true",),
            buffer_length=4,
        ),
        ValueTestCasePlan(
            "memory_copy",
            "test_memory_cp",
            "memory_cp",
            "memory_cp",
            "ui8",
            "u8",
            16,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "0", "0"),
            scalar_inputs=("2",),
            buffer_length=4,
        ),
        ValueTestCasePlan(
            "pointer_lifetime",
            "test_allocate",
            "allocate",
            "allocate",
            "ptr",
            "*mut core::ffi::c_void",
            4,
            scalar_inputs=("64",),
        ),
        ValueTestCasePlan(
            "pointer_free",
            "test_deallocate",
            "deallocate",
            "deallocate",
            "ptr",
            "*mut core::ffi::c_void",
            4,
            scalar_inputs=("64",),
        ),
        ValueTestCasePlan(
            "indexed_load",
            "test_gather",
            "gather",
            "gather",
            "ui32",
            "u32",
            4,
            vector_inputs=(("10", "20", "30", "40"), ("0", "1", "2", "3")),
            expected=("10", "20", "30", "40"),
            immediate_value="4",
            target_lanes=4,
        ),
        ValueTestCasePlan(
            "indexed_store",
            "test_scatter",
            "scatter",
            "scatter",
            "ui32",
            "u32",
            4,
            vector_inputs=(("10", "20", "30", "40"), ("0", "1", "2", "3")),
            expected=("10", "20", "30", "40"),
            immediate_value="4",
            buffer_length=4,
        ),
        ValueTestCasePlan(
            "stream",
            "test_to_ostream",
            "to_ostream",
            "to_ostream",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("4|3|2|1|\n",),
            scalar_inputs=("0",),
            text_expected="4|3|2|1|\n",
        ),
        ValueTestCasePlan(
            "load_convert",
            "test_load_convert",
            "load_convert",
            "load_convert_up",
            "si16",
            "i16",
            16,
            vector_inputs=(("1", "2", "3", "4"),),
            expected=("1", "2", "3", "4"),
            expected_type_tag="si32",
            target_base_spelling="i32",
            target_lanes=4,
            source_extension="avx2",
            target_extension="avx2",
            to_array_name="to_array",
        ),
        ValueTestCasePlan(
            "extension_extract",
            "test_extract",
            "extract",
            "extract",
            "si32",
            "i32",
            8,
            vector_inputs=(("1", "2", "3", "4", "5", "6", "7", "8"),),
            expected=("5", "6", "7", "8"),
            index_value="1",
            source_extension="avx2",
            target_extension="sse",
            from_array_name="from_array",
            to_array_name="to_array",
        ),
        ValueTestCasePlan(
            "extension_insert",
            "test_insert",
            "insert",
            "insert",
            "si32",
            "i32",
            4,
            vector_inputs=(("100", "200", "300", "400", "500", "600", "700", "800"), ("1", "2", "3", "4")),
            expected=("100", "200", "300", "400", "1", "2", "3", "4"),
            index_value="1",
            source_extension="sse",
            target_extension="avx2",
            from_array_name="from_array",
            to_array_name="to_array",
        ),
    )

    source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", cases),), render_assets
    )

    assert "from_array::<Vec>(&values)" in source
    assert "to_array::<Vec>(v0)" in source
    assert "load::<Vec, true>(buf.as_ptr().add(0))" in source
    assert "store::<Vec, false, _>(" in source
    assert "load_scalar::<Vec, false>(buf.as_ptr().add(1))" in source
    assert "load_mask_repr::<Vec, false, false>(" in source
    assert "expand_load::<Vec, true>(mask, buf.as_ptr())" in source
    assert "compress_store::<Vec, true>(" in source
    assert "memory_cp::<Vec>(" in source
    assert "let ptr = allocate(64usize);" in source
    assert "unsafe { deallocate(ptr); }" in source
    assert "gather::<Vec, Indices, 4, 4>(data.as_ptr(), idx)" in source
    assert "scatter::<Vec, Indices, 4, 4>(data.as_mut_ptr(), idx, values);" in source
    assert 'assert_eq!(result.as_str(), "4|3|2|1|\\n", "to_ostream");' in source
    assert "type Vec = Simd<i16, Avx2>;" in source
    assert "load_convert_up::<Vec, ToVec>(buf.as_ptr())" in source
    assert "type Vec = Simd<i32, Avx2>;" in source
    assert "extract::<Vec, ToVec, 1>(from_array::<Vec>(&h0))" in source
    assert "type DataVec = Simd<i32, Sse>;" in source
    assert "insert::<DataVec, ResultVec, 1>(from_array::<ResultVec>(&orig), from_array::<DataVec>(&data))" in source


def test_render_tests_project_stays_an_assembler() -> None:
    source = Path("tslc/src/tslc/render/tests_project.py").read_text(encoding="utf-8")

    assert "Catalog" not in source
    assert "LoweredSpecialization" not in source
    assert "_is_" not in source
    for primitive_name in (
        "from_array",
        "to_array",
        "to_integral",
        "convert_down",
        "extract",
        "insert",
    ):
        assert primitive_name not in source


def test_value_test_modules_keep_owned_boundaries() -> None:
    value_tests = Path("tslc/src/tslc/value_tests")
    cpp_values_template = Path(
        "tslc/src/tslc/backend/assets/cpp_value_tests.cpp.tmpl"
    ).read_text(encoding="utf-8")
    rust_values_template = Path(
        "tslc/src/tslc/backend/assets/rust_value_tests.rs.tmpl"
    ).read_text(encoding="utf-8")
    rust_profile_template = Path(
        "tslc/src/tslc/backend/assets/rust_value_tests_profile.rs.tmpl"
    ).read_text(encoding="utf-8")
    planner = Path("tslc/src/tslc/value_tests/planner.py").read_text(encoding="utf-8")
    render_cpp_entry = Path("tslc/src/tslc/value_tests/render_cpp.py").read_text(
        encoding="utf-8"
    )
    patterns = "\n".join(
        (value_tests / name).read_text(encoding="utf-8")
        for name in (
            "patterns.py",
            "_pattern_base.py",
            "_pattern_core.py",
            "_pattern_masks.py",
            "_pattern_memory.py",
            "_pattern_conversion.py",
        )
    )
    case_plans = "\n".join(
        (value_tests / name).read_text(encoding="utf-8")
        for name in (
            "case_plans.py",
            "_case_common.py",
            "_case_core.py",
            "_case_scalable.py",
            "_case_scalable_common.py",
            "_case_scalable_masks.py",
            "_case_memory.py",
            "_case_conversion.py",
        )
    )
    render_cpp = "\n".join(
        (value_tests / name).read_text(encoding="utf-8")
        for name in (
            "render_cpp.py",
            "lane_model.py",
            "_render_cpp_core.py",
            "_render_cpp_memory.py",
            "_render_cpp_conversion.py",
            "_render_cpp_dispatch.py",
        )
    )
    render_rust = "\n".join(
        (value_tests / name).read_text(encoding="utf-8")
        for name in (
            "render_rust.py",
            "_render_rust_core.py",
            "_render_rust_conversion.py",
            "_render_rust_helpers.py",
            "_render_rust_memory.py",
        )
    )
    pipeline = Path("tslc/src/tslc/pipeline.py").read_text(encoding="utf-8")

    assert len(planner.splitlines()) < 250
    for path in (
        "case_plans.py",
        "_case_common.py",
        "_case_core.py",
        "_case_scalable.py",
        "_case_scalable_common.py",
        "_case_scalable_masks.py",
        "_case_memory.py",
        "_case_conversion.py",
        "patterns.py",
        "_pattern_base.py",
        "_pattern_core.py",
        "_pattern_masks.py",
        "_pattern_memory.py",
        "_pattern_conversion.py",
        "render_cpp.py",
        "lane_model.py",
        "_render_cpp_core.py",
        "_render_cpp_memory.py",
        "_render_cpp_conversion.py",
        "_render_cpp_dispatch.py",
        "render_rust.py",
        "_render_rust_core.py",
        "_render_rust_conversion.py",
        "_render_rust_helpers.py",
        "_render_rust_memory.py",
        "support_headers.py",
    ):
        assert len((value_tests / path).read_text(encoding="utf-8").splitlines()) < 500
    assert "def discover_harness_primitives" not in planner
    assert "class _GenericGoldenPattern" not in planner
    assert "backend_ids" not in patterns
    assert '"cpp"' not in patterns
    assert '"rust"' not in patterns
    assert "def simple_case" not in case_plans
    assert 'extension_name == "scalar"' not in case_plans
    assert "_rust_literal" not in render_cpp
    assert 'backend_id == "rust"' not in render_cpp
    assert "assets.fill" in render_cpp_entry
    assert "cpp_value_tests.cpp.tmpl" in render_cpp_entry
    assert "std::fprintf" not in render_cpp_entry
    assert "std::fprintf" in cpp_values_template
    assert "assets.fill" in render_rust
    assert "rust_value_tests.rs.tmpl" in render_rust
    assert "rust_value_tests_profile.rs.tmpl" in render_rust
    assert "#![cfg(feature = \"value_tests\")]" not in render_rust
    assert "#![cfg(feature = \"value_tests\")]" in rust_values_template
    assert "tsl_generated::tsl_core" not in render_rust
    assert "tsl_generated::tsl_core" in rust_profile_template
    assert "Catalog" not in render_rust
    assert "Primitive" not in render_rust
    assert "value_test_warnings=self.request.value_test_warnings" in pipeline
    assert "value_test_warnings=self.request.test_harness" not in pipeline


def test_cpp_value_test_support_matches_renderer_dispatch() -> None:
    assert CPP_VALUE_TEST_SUPPORT.case_kinds == CPP_VALUE_TEST_RENDERER.case_kinds
    assert CPP_VALUE_TEST_RENDERER.backend_support() == CPP_VALUE_TEST_SUPPORT
    with pytest.raises(TypeError):
        CPP_VALUE_TEST_RENDERER.case_renderers["new_case"] = (  # type: ignore[index]
            lambda case: ""
        )


def test_rust_value_test_support_matches_renderer_dispatch() -> None:
    assert RUST_VALUE_TEST_SUPPORT.case_kinds == RUST_VALUE_TEST_RENDERER.case_kinds
    assert RUST_VALUE_TEST_RENDERER.backend_support() == RUST_VALUE_TEST_SUPPORT
    with pytest.raises(TypeError):
        RUST_VALUE_TEST_RENDERER.case_renderers["new_case"] = (  # type: ignore[index]
            lambda case: ""
        )


def test_value_test_case_requirements_cover_renderer_dispatch() -> None:
    assert frozenset(ValueTestCasePlan.CASE_REQUIREMENTS) == DEFAULT_VALUE_TEST_CASE_KINDS
    assert {
        capability.kind for capability in DEFAULT_VALUE_TEST_CASE_CAPABILITIES
    } == DEFAULT_VALUE_TEST_CASE_KINDS
    assert CPP_VALUE_TEST_SUPPORT.case_kinds <= DEFAULT_VALUE_TEST_CASE_KINDS
    assert RUST_VALUE_TEST_SUPPORT.case_kinds <= DEFAULT_VALUE_TEST_CASE_KINDS


def test_value_test_renderer_rejects_unregistered_case_kind() -> None:
    with pytest.raises(ValueError, match="unregistered case kind"):
        ValueTestRendererCapability(
            backend_id="unit",
            case_renderers={"not_registered": lambda case: ""},
        )


def test_parity_inventory_groups_backend_case_statuses() -> None:
    entries = (
        ValueTestCoverageEntry("cpp", "unit", "add", "basic", "emitted"),
        ValueTestCoverageEntry("rust", "unit", "add", "basic", "emitted"),
        ValueTestCoverageEntry("cpp", "unit", "store", "basic", "emitted"),
        ValueTestCoverageEntry(
            "cpp", "unit", "mask", "basic", "emitted"
        ),
        ValueTestCoverageEntry(
            "rust",
            "unit",
            "mask",
            "basic",
            "backend_unsupported",
            "renderer missing case kind",
            "masked",
        ),
    )

    inventory = parity_inventory(entries, ("cpp", "rust"))
    by_case = {(entry.primitive_name, entry.case_name): entry for entry in inventory}

    assert by_case[("add", "basic")].status_for("cpp") == "emitted"
    assert by_case[("add", "basic")].status_for("rust") == "emitted"
    assert by_case[("store", "basic")].status_for("rust") is None
    assert by_case[("mask", "basic")].backend_statuses[1].case_kind == "masked"
    assert [
        (entry.primitive_name, entry.case_name)
        for entry in parity_gaps(entries, ("cpp", "rust"))
    ] == [("mask", "basic"), ("store", "basic")]


def _catalog(*primitives: Primitive) -> Catalog:
    return Catalog(
        primitives=primitives,
        type_groups={},
        extensions={},
        type_spellings={},
        translations={},
    )


def _harness_primitives() -> tuple[Primitive, ...]:
    return (
        Primitive("lane_in", "v:=s[]", ("data",), (), ()),
        Primitive("lane_out", "s[]:=v", ("data",), (), ()),
        Primitive("mask_bits", "im:=m", ("mask",), (), ()),
        Primitive("load", "v:=cptr", ("ptr",), (), ()),
        Primitive("store", "void:=(ptr,v)", ("ptr", "data"), (), ()),
    )


def _profile(
    *,
    cpp: dict[str, tuple[LoweredSpecialization, ...]] | None = None,
    rust: dict[str, tuple[LoweredSpecialization, ...]] | None = None,
) -> ProfileRender:
    return ProfileRender(
        profile=MachineProfile("unit", "generic", frozenset(), {}),
        specializations_by_backend={"cpp": cpp or {}, "rust": rust or {}},
    )


def _inputs(profile: ProfileRender) -> tuple[ValueTestBackendProfileInput, ...]:
    return (
        ValueTestBackendProfileInput(
            "cpp", profile.profile.name, profile.specializations("cpp")
        ),
        ValueTestBackendProfileInput(
            "rust", profile.profile.name, profile.specializations("rust")
        ),
    )


def _spec(
    primitive_name: str,
    source_primitive_name: str,
    *,
    param_kinds: tuple[str, ...],
    result_kind: str = "v",
    immediate: tuple[str, str] | None = None,
    mask_policy: str | None = None,
    axis: tuple[tuple[str, str], ...] = (),
) -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="cpp",
        primitive_name=primitive_name,
        source_primitive_name=source_primitive_name,
        extension_name="generic",
        type_tag="si32",
        base_type_spelling="std::int32_t",
        register_spelling="std::int32_t[4]",
        result_kind=result_kind,
        param_names=tuple(f"p{i}" for i in range(len(param_kinds))),
        param_kinds=param_kinds,
        body=LoweredBody.from_text("", backend_id="cpp"),
        uses_sized_vector=True,
        lane_parameter="4",
        axis=axis,
        immediate=immediate,
        mask_policy=mask_policy,
    )
