from __future__ import annotations

from pathlib import Path

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Primitive, TestArg as TslTestArg, TestCase as TslTestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.render.emitted_names import finalize_emitted_names
from tslc.render.model import LoweredBody
from tslc.render.project import ProfileRender
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    discover_harness_primitives,
)
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProfilePlan
from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT, render_cpp_values_runner
from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT, render_rust_values_file

_VALUE_TEST_SUPPORTS = (CPP_VALUE_TEST_SUPPORT, RUST_VALUE_TEST_SUPPORT)


def test_harness_discovery_uses_signatures_not_names() -> None:
    catalog = _catalog(
        Primitive("lane_in", "v:=s[]", ("data",), (), ()),
        Primitive("lane_out", "s[]:=v", ("data",), (), ()),
        Primitive("mask_bits", "im:=m", ("mask",), (), ()),
    )

    harness = discover_harness_primitives(catalog)

    assert harness.from_array == "lane_in"
    assert harness.to_array == "lane_out"
    assert harness.to_integral == "mask_bits"
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
    catalog = _catalog(primitive)
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


def test_lane_list_value_tests_are_planned_and_rendered() -> None:
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
    cpp_source = render_cpp_values_runner(plan.profiles_for("cpp")[0])
    rust_source = render_rust_values_file(plan.profiles_for("rust"))
    assert "typename tsl::array_for<Vec>::type values;" in cpp_source
    assert "tsl::set<Vec>(values)" in cpp_source
    assert "let mut values: <Vec as SimdVector>::Array = Default::default();" in rust_source
    assert "set::<Vec>(values)" in rust_source


def test_renderers_consume_prebuilt_plans_without_catalog() -> None:
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
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_case,))
    )
    assert "tsl::plus<Vec>(v0, v1)" in cpp_source

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
        (ValueTestProfilePlan("rust", "unit-profile", (rust_case,)),)
    )
    assert "r#mod::<Vec>(a0, a1)" in rust_source


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
    planner = Path("tslc/src/tslc/value_tests/planner.py").read_text(encoding="utf-8")
    patterns = Path("tslc/src/tslc/value_tests/patterns.py").read_text(encoding="utf-8")
    case_plans = Path("tslc/src/tslc/value_tests/case_plans.py").read_text(encoding="utf-8")
    render_cpp = Path("tslc/src/tslc/value_tests/render_cpp.py").read_text(encoding="utf-8")

    assert len(planner.splitlines()) < 250
    assert "def discover_harness_primitives" not in planner
    assert "class _GenericGoldenPattern" not in planner
    assert "backend_ids" not in patterns
    assert '"cpp"' not in patterns
    assert '"rust"' not in patterns
    assert "def simple_case" not in case_plans
    assert 'extension_name == "scalar"' not in case_plans
    assert "_rust_literal" not in render_cpp
    assert 'backend_id == "rust"' not in render_cpp


def _catalog(*primitives: Primitive) -> Catalog:
    return Catalog(
        primitives=primitives,
        type_groups={},
        extensions={},
        type_spellings={},
        translations={},
    )


def _profile(
    *,
    cpp: dict[str, tuple[LoweredSpecialization, ...]] | None = None,
    rust: dict[str, tuple[LoweredSpecialization, ...]] | None = None,
) -> ProfileRender:
    return ProfileRender(
        profile=MachineProfile("unit", "generic", frozenset(), {}),
        cpp=cpp or {},
        rust=rust or {},
    )


def _inputs(profile: ProfileRender) -> tuple[ValueTestBackendProfileInput, ...]:
    return (
        ValueTestBackendProfileInput("cpp", profile.profile.name, profile.cpp),
        ValueTestBackendProfileInput("rust", profile.profile.name, profile.rust),
    )


def _spec(
    primitive_name: str,
    source_primitive_name: str,
    *,
    param_kinds: tuple[str, ...],
    result_kind: str = "v",
    immediate: tuple[str, str] | None = None,
    mask_policy: str | None = None,
) -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="cpp",
        primitive_name=primitive_name,
        source_primitive_name=source_primitive_name,
        extension_name="generic",
        type_tag="si32",
        base_type_spelling="std::int32_t",
        result_kind=result_kind,
        param_names=tuple(f"p{i}" for i in range(len(param_kinds))),
        param_kinds=param_kinds,
        body=LoweredBody.from_text("", backend_id="cpp"),
        uses_sized_vector=True,
        lane_parameter="4",
        immediate=immediate,
        mask_policy=mask_policy,
    )
