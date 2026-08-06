from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import tslc.pipeline as pipeline_module
from tslc.api import generate_project
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    BackendExtensionMetadata,
    Catalog,
    Extension,
    ExtensionMetadata,
    ParamTypeRule,
    Primitive,
    TestComparison as CaseComparison,
    TestFailureReason as FailureReason,
    TestArg as TslTestArg,
    TestCase as TslTestCase,
)
from tslc.compiler_assets import RenderAssets
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.lower.lowerer import LoweredSpecialization
from tslc.lower.target_vectors import TargetVector
from tslc.backend.emitted_names import finalize_emitted_names
from tslc.target_text import LoweredBody
from tslc.backend.emitted_profile import EmittedProfile
from tslc.render.project import render_project
from tslc.value_tests.coverage import (
    ValueTestCaseDrop,
    parity_gaps,
    parity_inventory,
)
from tslc.value_tests.literals import cpp_literal
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    discover_harness_primitives,
)
from tslc.value_tests.model import (
    DEFAULT_VALUE_TEST_CASE_CAPABILITIES,
    DEFAULT_VALUE_TEST_CASE_KINDS,
    ValueTestBackendSupport,
    ValueTestCasePlan as _ValueTestCasePlan,
    ValueTestCoverageEntry,
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestFact,
    ValueTestFailure,
    ValueTestIndex,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestProfileCaseExclusion,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
    ValueTestRepresentation,
    ValueTestScalable,
    ValueTestTarget,
)
from tslc.value_tests.param_layouts import scalar_type_tag_from_expr
from tslc.value_tests.renderer_capability import ValueTestRendererCapability
from tslc.value_tests._render_cpp_dispatch import CPP_VALUE_TEST_RENDERER
from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT, render_cpp_values_runner
from tslc.value_tests.render_rust import (
    RUST_VALUE_TEST_RENDERER,
    RUST_VALUE_TEST_SUPPORT,
    render_rust_values_file,
)

_VALUE_TEST_SUPPORTS = (CPP_VALUE_TEST_SUPPORT, RUST_VALUE_TEST_SUPPORT)


def ValueTestCasePlan(*identity: object, **fields: Any) -> _ValueTestCasePlan:
    """Concise fixture adapter; production builders use the typed components directly."""

    names = (
        "kind",
        "function_name",
        "case_name",
        "call_name",
        "type_tag",
        "base_spelling",
        "lanes",
    )
    values = dict(zip(names, identity, strict=False))
    values.update(fields)
    core = {name: values.pop(name) for name in names}

    source_extension = values.pop("source_extension", None)
    runtime_lanes = values.pop("runtime_lanes_template", None)
    target_values = {
        "type_tag": values.pop("expected_type_tag", None),
        "base_spelling": values.pop("target_base_spelling", None),
        "lanes": values.pop("target_lanes", None),
    }
    index_values = {
        "value": values.pop("index_value", None),
        "type_tag": values.pop("index_type_tag", None),
        "base_spelling": values.pop("index_base_spelling", None),
        "lanes": values.pop("index_lanes", None),
        "style": values.pop("index_style", None),
    }
    memory_values = {
        "buffer_offset": values.pop("buffer_offset", 0),
        "buffer_length": values.pop("buffer_length", None),
        "source_offset": values.pop("source_offset", 0),
        "alignment": values.pop("alignment", None),
        "storage": values.pop("storage", None),
    }
    hardware_extension = values.pop("hardware_extension", None)
    from_array = values.pop("from_array_name", None)
    to_array = values.pop("to_array_name", None)
    to_integral = values.pop("to_integral_name", None)
    to_mask = values.pop("to_mask_name", None)

    plan = _ValueTestCasePlan(
        **core,
        inputs=ValueTestInputs(
            vectors=values.pop("vector_inputs", ()),
            masks=values.pop("mask_inputs", ()),
            scalar=values.pop("scalar_input", None),
            scalars=values.pop("scalar_inputs", ()),
        ),
        expectation=ValueTestExpectation(
            values=values.pop("expected", ()),
            text=values.pop("text_expected", None),
            comparison=values.pop("comparison", CaseComparison.VALUE),
            scalable_layout=values.pop("scalable_expected_layout", "tiled"),
        ),
        invocation=ValueTestInvocation(
            result_kind=values.pop("result_kind", None),
            param_kinds=values.pop("param_kinds", ()),
            axis_args=values.pop("axis_args", ()),
            immediate=values.pop("immediate_value", None),
            generic_defaults=values.pop("generic_defaults", ()),
        ),
        target=ValueTestTarget(**target_values) if any(value is not None for value in target_values.values()) else None,
        index=ValueTestIndex(**index_values) if any(value is not None for value in index_values.values()) else None,
        memory=ValueTestMemory(**memory_values) if any(memory_values.values()) else None,
        representation=(
            ValueTestRepresentation(
                source_extension=source_extension,
                target_extension=values.pop("target_extension", None),
                from_array_name=from_array,
                to_array_name=to_array,
            )
            if source_extension is not None and runtime_lanes is None
            else None
        ),
        scalable=(
            ValueTestScalable(
                source_extension=source_extension,
                runtime_lanes_template=runtime_lanes,
                mask_from_bits_template=values.pop("mask_from_bits_template", None),
                mask_check_template=values.pop("mask_check_template", None),
                mask_bits=values.pop("mask_bits", ()),
                expected_mask_bits=values.pop("expected_mask_bits", None),
                load_name=values.pop("load_name", None),
                store_name=values.pop("store_name", None),
            )
            if source_extension is not None and runtime_lanes is not None
            else None
        ),
        differential=(
            ValueTestDifferential(
                hardware_extension=hardware_extension,
                from_array_name=from_array or "",
                to_array_name=to_array,
                to_integral_name=to_integral,
                to_mask_name=to_mask,
                mask_from_bits_template=values.pop("mask_from_bits_template", None),
                nonzero_argument_index=values.pop(
                    "nonzero_argument_index", None
                ),
                fuzz_seed=values.pop("fuzz_seed", None),
                fuzz_iterations=values.pop("fuzz_iterations", 0),
            )
            if hardware_extension is not None
            else None
        ),
        failure=values.pop("failure", None),
        header_group=values.pop("header_group", None),
        required_compiler_features=values.pop("required_compiler_features", ()),
    )
    assert not values, f"unhandled fixture fields: {sorted(values)}"
    return plan


def test_emitted_profile_requires_name_finalization_context() -> None:
    with pytest.raises(TypeError, match="immediate_split_names"):
        EmittedProfile(  # type: ignore[call-arg]
            profile=MachineProfile("unit", "generic", frozenset(), {}),
            specializations_by_backend={},
        )


def test_emitted_profile_freezes_backend_mappings() -> None:
    source_cpp: dict[str, tuple[LoweredSpecialization, ...]] = {}
    profile = EmittedProfile(
        profile=MachineProfile("unit", "generic", frozenset(), {}),
        specializations_by_backend={"cpp": source_cpp, "rust": {}},
        immediate_split_names=frozenset(),
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
        Primitive("mask_from_bits", "m:=im", ("bits",), (), ()),
        Primitive("load", "v:=cptr", ("ptr",), (), ()),
        Primitive("store", "void:=(ptr,v)", ("ptr", "data"), (), ()),
    )

    harness = discover_harness_primitives(catalog)

    assert harness.from_array == "lane_in"
    assert harness.to_array == "lane_out"
    assert harness.to_integral == "mask_bits"
    assert harness.to_mask == "mask_from_bits"
    assert harness.load == "load"
    assert harness.store == "store"
    assert harness.diagnostics == ()


def test_runtime_failure_cases_plan_and_render_for_both_backends(
    render_assets: RenderAssets,
) -> None:
    primitive = Primitive(
        "div",
        "v:=(v,v)",
        ("dividend", "divisor"),
        (),
        (),
        tests=(
            TslTestCase(
                name="active_zero",
                type_tag="si32",
                tags=("failure",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("8", "-9", "10", "-12")),
                    TslTestArg("vector", values=("2", "0", "-2", "4")),
                ),
                expected=(),
                role="runtime_failure",
                failure=FailureReason.INTEGER_ZERO_DIVISOR,
            ),
        ),
    )
    cpp_spec = _spec("div", "div", param_kinds=("v", "v"))
    rust_spec = replace(
        cpp_spec,
        backend_id="rust",
        base_type_spelling="i32",
        register_spelling="[i32; 4]",
    )
    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        _VALUE_TEST_SUPPORTS,
    ).plan(
        _inputs(
            _profile(
                cpp={"div": (cpp_spec,)},
                rust={"div": (rust_spec,)},
            )
        )
    )

    assert plan.diagnostics == ()
    assert [case.kind for case in plan.profiles_for("cpp")[0].cases] == [
        "runtime_failure"
    ]
    assert [case.kind for case in plan.profiles_for("rust")[0].cases] == [
        "runtime_failure"
    ]
    cpp_source = render_cpp_values_runner(
        plan.profiles_for("cpp")[0], render_assets
    )
    rust_source = render_rust_values_file(plan.profiles_for("rust"), render_assets)
    assert "catch (const std::domain_error& error)" in cpp_source
    assert '"TSL_ARITH_INTEGER_ZERO_DIVISOR"' in cpp_source
    assert "std::panic::catch_unwind" in rust_source
    assert 'Some("TSL_ARITH_INTEGER_ZERO_DIVISOR")' in rust_source


def test_scalable_runtime_failure_materializes_vector_and_mask_inputs(
    render_assets: RenderAssets,
) -> None:
    primitive = Primitive(
        "div",
        "v:=(m,v,v)",
        ("mask", "dividend", "divisor"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="active_zero",
                type_tag="si32",
                tags=("failure",),
                lanes=4,
                inputs=(
                    TslTestArg("mask", mask_bits="10"),
                    TslTestArg("vector", values=("8", "-9", "10", "-12")),
                    TslTestArg("vector", values=("2", "0", "-2", "4")),
                ),
                expected=(),
                role="runtime_failure",
                failure=FailureReason.INTEGER_ZERO_DIVISOR,
            ),
        ),
    )
    spec = _spec(
        "div_maskz",
        "div",
        param_kinds=("m", "v", "v"),
        mask_policy="zero",
        extension_name="sve",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    catalog = Catalog(
        primitives=(primitive, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )

    plan = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", "sve", {"div_maskz": (spec,)}
            ),
        )
    )

    assert not plan.diagnostics
    assert [case.kind for case in plan.profiles[0].cases] == [
        "runtime_failure",
        "scalable_runtime_failure",
    ]
    scalable = plan.profiles[0].cases[1]
    assert scalable.scalable is not None
    assert scalable.scalable.mask_bits == (10,)
    source = render_cpp_values_runner(plan.profiles[0], render_assets)
    assert "using Vec = tsl::simd<std::int32_t, tsl::sve>;" in source
    assert "tsl::load<Vec, false>(in0.data())" in source
    assert "make_mask<tsl::simd<std::int32_t, tsl::sve>>(10ull, 4, lanes)" in source
    assert "tsl::div_maskz<Vec>(m0, v0, v1)" in source
    assert "catch (const std::domain_error& error)" in source


def test_runtime_failure_cases_report_wasm_profile_capability_exclusions() -> None:
    primitive = Primitive(
        "div",
        "v:=(v,v)",
        ("dividend", "divisor"),
        (),
        (),
        tests=(
            TslTestCase(
                name="active_zero",
                type_tag="si32",
                tags=("failure",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("8", "-9", "10", "-12")),
                    TslTestArg("vector", values=("2", "0", "-2", "4")),
                ),
                expected=(),
                role="runtime_failure",
                failure=FailureReason.INTEGER_ZERO_DIVISOR,
            ),
        ),
    )
    cpp_spec = _spec("div", "div", param_kinds=("v", "v"))
    rust_spec = replace(
        cpp_spec,
        backend_id="rust",
        base_type_spelling="i32",
        register_spelling="[i32; 4]",
    )

    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        _VALUE_TEST_SUPPORTS,
    ).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", "wasm32-simd128", {"div": (cpp_spec,)}, "wasm32"
            ),
            ValueTestBackendProfileInput(
                "rust", "wasm32-simd128", {"div": (rust_spec,)}, "wasm32"
            ),
        )
    )

    assert all(not profile.cases for profile in plan.profiles)
    exclusions = {
        entry.backend_id: entry
        for entry in plan.coverage
        if entry.case_name == "active_zero"
    }
    assert exclusions["cpp"].status == "backend_unsupported"
    assert "exception unwinding" in exclusions["cpp"].reason
    assert exclusions["rust"].status == "backend_unsupported"
    assert "aborting panics" in exclusions["rust"].reason


def test_cpp_differential_uses_extension_mask_materialization_template() -> None:
    case = ValueTestCasePlan(
        "differential",
        "test_diff_sve128_div_mask",
        "div_mask",
        "div_mask",
        "si32",
        "int32_t",
        4,
        param_kinds=("m", "v", "v"),
        result_kind="v",
        vector_inputs=(("8", "9", "10", "12"), ("2", "3", "5", "4")),
        mask_inputs=("10",),
        hardware_extension="sve128",
        from_array_name="from_array",
        to_array_name="to_array",
        to_mask_name="to_mask",
        mask_from_bits_template=(
            "::tsl::test::mask_from_bits<{vec}>("
            "{mask_bits}, {authored_lanes}, {lanes})"
        ),
    )

    source = CPP_VALUE_TEST_RENDERER.render_case(case)

    assert "::tsl::test::mask_from_bits<Hw>(10ull, 4, 4)" in source
    assert "static_cast<typename Hw::imask_type>" not in source
    assert "static_cast<typename Ref::imask_type>(10ull)" in source


def test_differential_renderers_support_runtime_lane_scalar_kinds() -> None:
    extract = ValueTestCasePlan(
        "differential",
        "test_diff_avx2_extract_value_at",
        "extract_value_at_si32",
        "extract_value_at",
        "si32",
        "i32",
        8,
        vector_inputs=(("1", "2", "3", "4", "5", "6", "7", "8"),),
        scalar_inputs=("7",),
        result_kind="s",
        param_kinds=("v", "usize"),
        hardware_extension="avx2",
        from_array_name="from_array",
        to_array_name="to_array",
    )
    insert = ValueTestCasePlan(
        "differential",
        "test_diff_avx2_insert_value_at",
        "insert_value_at_si32",
        "insert_value_at",
        "si32",
        "i32",
        8,
        vector_inputs=(("1", "2", "3", "4", "5", "6", "7", "8"),),
        scalar_inputs=("7", "9"),
        result_kind="v",
        param_kinds=("v", "usize", "s"),
        hardware_extension="avx2",
        from_array_name="from_array",
        to_array_name="to_array",
    )
    set_mask = ValueTestCasePlan(
        "differential",
        "test_diff_avx512_set_mask_lane",
        "set_mask_lane_ui32",
        "set_mask_lane",
        "ui32",
        "u32",
        16,
        mask_inputs=("5",),
        scalar_inputs=("15", "1"),
        result_kind="m",
        param_kinds=("m", "usize", "usize"),
        hardware_extension="avx512",
        from_array_name="from_array",
        to_array_name="to_array",
        to_integral_name="to_integral",
        to_mask_name="to_mask",
    )

    cpp_extract = CPP_VALUE_TEST_RENDERER.render_case(extract)
    rust_extract = RUST_VALUE_TEST_RENDERER.render_case(extract)
    assert "extract_value_at<Hw>(tsl::from_array<Hw>(hin0), static_cast<std::size_t>(7))" in cpp_extract
    assert "check_scalar<i32>" in cpp_extract
    assert "extract_value_at::<Hw>(from_array::<Hw>(&hin0), 7usize)" in rust_extract
    assert "hw.lane_eq(reference)" in rust_extract

    cpp_insert = CPP_VALUE_TEST_RENDERER.render_case(insert)
    rust_insert = RUST_VALUE_TEST_RENDERER.render_case(insert)
    assert "static_cast<std::size_t>(7), 9" in cpp_insert
    assert "7usize, 9" in rust_insert

    cpp_mask = CPP_VALUE_TEST_RENDERER.render_case(set_mask)
    rust_mask = RUST_VALUE_TEST_RENDERER.render_case(set_mask)
    assert "static_cast<std::size_t>(1)" in cpp_mask
    assert "to_integral<Hw>(tsl::set_mask_lane<Hw>" in cpp_mask
    assert "1usize" in rust_mask
    assert "to_integral::<Hw>(set_mask_lane::<Hw>" in rust_mask


def test_masked_immediate_cases_plan_and_render_for_both_backends(
    render_assets: RenderAssets,
) -> None:
    primitive = Primitive(
        "mod_imm",
        "v:=(m,v,sImm)",
        ("mask", "dividend", "divisor"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="masked_immediate",
                type_tag="si32",
                tags=("masked",),
                lanes=4,
                inputs=(
                    TslTestArg("mask", mask_bits="5"),
                    TslTestArg("vector", values=("10", "-9", "8", "-7")),
                    TslTestArg("scalar", scalar="3"),
                ),
                expected=("1", "0", "2", "0"),
            ),
        ),
    )
    cpp_spec = _spec(
        "mod_imm",
        "mod_imm",
        param_kinds=("m", "v", "sImm"),
        immediate=("divisor", "std::int32_t"),
        mask_policy="zero",
    )
    rust_spec = replace(
        cpp_spec,
        backend_id="rust",
        base_type_spelling="i32",
        register_spelling="[i32; 4]",
        immediate=("divisor", "i32"),
    )
    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        _VALUE_TEST_SUPPORTS,
    ).plan(
        _inputs(
            _profile(
                cpp={"mod_imm": (cpp_spec,)},
                rust={"mod_imm": (rust_spec,)},
            )
        )
    )

    assert plan.diagnostics == ()
    assert [case.kind for case in plan.profiles_for("cpp")[0].cases] == [
        "immediate"
    ]
    assert [case.kind for case in plan.profiles_for("rust")[0].cases] == [
        "immediate"
    ]
    cpp_source = render_cpp_values_runner(
        plan.profiles_for("cpp")[0], render_assets
    )
    rust_source = render_rust_values_file(plan.profiles_for("rust"), render_assets)
    assert "typename Vec::mask_type m0 = 5ull;" in cpp_source
    assert "tsl::mod_imm<Vec, 3>(m0, a0)" in cpp_source
    assert "let m0: <Vec as SimdVector>::MaskType = 5u64;" in rust_source
    assert "mod_imm::<Vec, 3>(m0, a0)" in rust_source


def test_arithmetic_failure_masked_and_immediate_corpus_cases_have_typed_coverage(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["div", "mod", "mod_imm"],
        profiles=["avx2"],
        backends=["cpp", "rust"],
        test_harness=True,
        value_test_warnings=True,
    )
    assert result.rendered is not None
    plan = result.rendered.value_tests
    blocking = [
        entry
        for entry in plan.coverage
        if entry.primitive_name in {"div", "mod", "mod_imm"}
        and entry.status in {"authored_unplanned", "backend_unsupported"}
    ]
    assert not blocking

    for backend in ("cpp", "rust"):
        cases = [case for profile in plan.profiles_for(backend) for case in profile.cases]
        failure_cases = [
            case
            for case in cases
            if case.kind == "runtime_failure"
            and (case.call_name.startswith("div") or case.call_name.startswith("mod"))
        ]
        assert len(failure_cases) == 6
        assert all(case.failure is not None for case in failure_cases)
        assert all(case.differential is None for case in failure_cases)
        compile_failure_cases = [
            case
            for case in cases
            if case.kind == "compile_failure" and case.call_name.startswith("mod_imm")
        ]
        assert len(compile_failure_cases) == 4
        assert {
            (case.call_name, case.invocation.immediate, case.inputs.masks)
            for case in compile_failure_cases
        } >= {
            ("mod_imm", "0", ()),
            ("mod_imm", "256", ()),
            ("mod_imm_mask", "0", ("0",)),
            ("mod_imm_maskz", "0", ("0",)),
        }
        assert all(
            case.failure
            == ValueTestFailure(FailureReason.INTEGER_ZERO_DIVISOR, phase="compile")
            for case in compile_failure_cases
        )

        masked_differentials = [
            case
            for case in cases
            if case.kind == "differential"
            and case.inputs.masks
            and (case.call_name.startswith("div") or case.call_name.startswith("mod"))
        ]
        assert masked_differentials
        assert all(
            case.differential is not None
            and case.differential.to_mask_name == "to_mask"
            for case in masked_differentials
        )
        assert any(
            case.call_name in {"mod_imm_mask", "mod_imm_maskz"}
            and case.invocation.immediate is not None
            for case in masked_differentials
        )
        differential_names = {
            case.case_name for case in cases if case.kind == "differential"
        }
        assert differential_names >= {
            "mod_si32_edge_overflow",
            "mod_si32_edge_signs",
        }
        if backend == "cpp":
            assert "div_si32_edge_overflow_signs" in differential_names
        else:
            assert any(
                case.kind == "generic_golden"
                and case.case_name == "div_si32_edge_overflow_signs"
                for case in cases
            )

    emitted = result.emitted_profiles[0]
    for backend in ("cpp", "rust"):
        specializations = tuple(
            spec
            for name in ("mod_imm", "mod_imm_mask", "mod_imm_maskz")
            for spec in emitted.specializations(backend)[name]
        )
        assert all(
            len(spec.arithmetic_preconditions) == 1
            for spec in specializations
            if spec.type_tag.startswith(("si", "ui"))
        )
        assert all(
            spec.arithmetic_preconditions == ()
            for spec in specializations
            if spec.type_tag.startswith("f")
        )

    assert result.rendered is not None
    for backend in result.rendered.verify.backends:
        assert len(backend.profiles[0].compile_failures) == 4
        assert all(
            failure.marker == "TSL_ARITH_INTEGER_IMMEDIATE_ZERO"
            for failure in backend.profiles[0].compile_failures
        )

    artifacts = {
        artifact.logical_path: artifact.content for artifact in result.artifacts.artifacts
    }
    cpp_negative_paths = sorted(
        path
        for path in artifacts
        if path.startswith("cpp/tests/tsl_compile_failure_")
    )
    rust_negative_paths = sorted(
        path
        for path in artifacts
        if path.startswith("rust/examples/tsl_compile_failure_")
    )
    assert len(cpp_negative_paths) == 4
    assert len(rust_negative_paths) == 4
    rust_negative_manifests = sorted(
        path
        for path in artifacts
        if path.startswith("rust/verify/tsl_compile_failure_")
        and path.endswith("/Cargo.toml")
    )
    assert len(rust_negative_manifests) == 4
    assert all(
        path.removeprefix("cpp/tests/").removesuffix(".cpp")
        not in artifacts["cpp/tests/values_avx2.cpp"]
        for path in cpp_negative_paths
    )
    assert all(
        path.removeprefix("rust/examples/").removesuffix(".rs")
        not in artifacts["rust/tests/values.rs"]
        for path in rust_negative_paths
    )
    assert "static_assert(static_cast<std::uint8_t>(divisor)" in artifacts[
        "cpp/include/tsl_avx2.hpp"
    ]
    assert "const { assert!((divisor as u8) != 0" in artifacts[
        "rust/src/tsl_avx2.rs"
    ]
    assert "EXCLUDE_FROM_ALL" in artifacts["cpp/CMakeLists.txt"]
    rust_manifest = artifacts["rust/Cargo.toml"]
    assert "tsl_compile_failures" not in rust_manifest
    assert "required-features" not in rust_manifest
    assert 'runtime-dispatch = ["std"]' in rust_manifest
    assert all(
        'tsl = { package = "tsl", path = "../.." }' in artifacts[path]
        for path in rust_negative_manifests
    )


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


def test_planner_selects_authored_tests_by_source_signature() -> None:
    immediate_primitive = Primitive(
        "shift",
        "v:=(v,sImm)",
        ("data", "amount"),
        (),
        (),
        tests=(
            TslTestCase(
                name="immediate",
                type_tag="si32",
                tags=("immediate",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("scalar", scalar="1"),
                ),
                expected=("2", "4", "6", "8"),
            ),
        ),
    )
    runtime_primitive = Primitive(
        "shift",
        "v:=(v,s)",
        ("data", "amount"),
        (),
        (),
        tests=(
            TslTestCase(
                name="runtime",
                type_tag="si32",
                tags=("runtime",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("scalar", scalar="1"),
                ),
                expected=("2", "4", "6", "8"),
            ),
        ),
    )
    immediate = _spec(
        "shift_imm",
        "shift",
        param_kinds=("v", "sImm"),
        immediate=("amount", "std::uint32_t"),
    )
    runtime = _spec("shift", "shift", param_kinds=("v", "s"))
    profile = _profile(
        cpp={"shift": (runtime,), "shift_imm": (immediate,)},
    )

    plan = ValueTestPlanner(
        _catalog(immediate_primitive, runtime_primitive, *_harness_primitives()),
        (CPP_VALUE_TEST_SUPPORT,),
    ).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", "unit", profile.specializations("cpp")
            ),
        )
    )

    assert plan.diagnostics == ()
    assert [
        (case.call_name, case.case_name)
        for case in plan.profiles_for("cpp")[0].cases
    ] == [("shift", "runtime"), ("shift_imm", "immediate")]


def test_status_pointer_case_checks_runtime_contract_for_both_backends() -> None:
    primitive = Primitive(
        "random_step",
        "usize:=(ptr)",
        ("out",),
        (),
        (),
        tests=(
            TslTestCase(
                name="random_step_ui64_contract",
                type_tag="ui64",
                tags=("contract",),
                inputs=(TslTestArg("scalar", scalar="0"),),
                expected=(),
                expected_rule="status_pointer",
            ),
        ),
    )
    cpp_spec = replace(
        _spec(
            "random_step",
            "random_step",
            param_kinds=("ptr",),
            result_kind="usize",
        ),
        type_tag="ui64",
        base_type_spelling="std::uint64_t",
    )
    rust_spec = replace(
        cpp_spec,
        backend_id="rust",
        base_type_spelling="u64",
        register_spelling="u64",
    )
    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        _VALUE_TEST_SUPPORTS,
    ).plan(
        _inputs(
            _profile(
                cpp={"random_step": (cpp_spec,)},
                rust={"random_step": (rust_spec,)},
            )
        )
    )

    assert plan.diagnostics == ()
    assert {entry.status for entry in plan.coverage} == {"emitted"}
    cpp_case = plan.profiles_for("cpp")[0].cases[0]
    rust_case = plan.profiles_for("rust")[0].cases[0]
    assert cpp_case.kind == rust_case.kind == "status_pointer"
    cpp_source = CPP_VALUE_TEST_RENDERER.render_case(cpp_case)
    rust_source = RUST_VALUE_TEST_RENDERER.render_case(rust_case)
    assert "const std::size_t status = tsl::random_step(&value);" in cpp_source
    assert "status == 0 && value != before" in cpp_source
    assert "let status = unsafe { random_step(&mut value) };" in rust_source
    assert "if status == 0" in rust_source


def test_target_imask_case_uses_source_and_target_mask_layouts() -> None:
    primitive = Primitive(
        "insert_imask",
        "im:=(imt,im,usize)",
        ("orig", "data", "position"),
        (),
        (),
        tests=(
            TslTestCase(
                name="replace",
                type_tag="si32",
                tags=("extension",),
                extension="sse",
                to_extension="avx2",
                inputs=(
                    TslTestArg("mask", mask_bits="255"),
                    TslTestArg("mask", mask_bits="0"),
                    TslTestArg("scalar", scalar="2"),
                ),
                expected=("195",),
            ),
        ),
    )
    extensions = {
        name: Extension(
            name,
            name,
            "x86",
            {},
            {},
            backend_supported={"cpp": True, "rust": True},
            vector_bits=bits,
        )
        for name, bits in (("sse", 128), ("avx2", 256))
    }
    catalog = Catalog(
        primitives=(primitive, *_harness_primitives()),
        type_groups={},
        extensions=extensions,
        type_spellings={},
        translations={},
    )
    target = TargetVector(
        "target-vector",
        "target-register",
        "avx2",
        "si32",
        "std::int32_t",
    )
    cpp_spec = replace(
        _spec(
            "insert_imask",
            "insert_imask",
            param_kinds=("imt", "im", "usize"),
            result_kind="im",
            extension_name="sse",
            uses_sized_vector=False,
            lane_parameter=None,
        ),
        target=target,
    )
    rust_spec = replace(
        cpp_spec,
        backend_id="rust",
        base_type_spelling="i32",
        target=replace(target, base_spelling="i32"),
    )

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(
        _inputs(
            _profile(
                cpp={"insert_imask": (cpp_spec,)},
                rust={"insert_imask": (rust_spec,)},
            )
        )
    )

    assert plan.diagnostics == ()
    assert {entry.status for entry in plan.coverage} == {"emitted"}
    cpp_case = plan.profiles_for("cpp")[0].cases[0]
    rust_case = plan.profiles_for("rust")[0].cases[0]
    assert cpp_case.kind == rust_case.kind == "target_imask"
    assert cpp_case.lanes == 4
    assert cpp_case.target is not None and cpp_case.target.lanes == 8
    cpp_source = CPP_VALUE_TEST_RENDERER.render_case(cpp_case)
    rust_source = RUST_VALUE_TEST_RENDERER.render_case(rust_case)
    assert "typename ToVec::imask_type a0" in cpp_source
    assert "typename Vec::imask_type a1" in cpp_source
    assert "tsl::insert_imask<Vec, ToVec>(a0, a1, a2)" in cpp_source
    assert "<ToVec as SimdVector>::ImaskType" in rust_source
    assert "insert_imask::<Vec, ToVec>(a0, a1, a2)" in rust_source


def test_different_arity_leading_mask_form_gets_portable_emitted_name() -> None:
    plain = _spec("hadd", "hadd", param_kinds=("v",))
    masked = _spec("hadd", "hadd", param_kinds=("m", "v"))

    finalized = finalize_emitted_names(
        {"hadd": (plain, masked)}, immediate_split_names=frozenset()
    )

    assert finalized["hadd"] == (plain,)
    assert finalized["hadd_mask"][0].primitive_name == "hadd_mask"
    assert finalized["hadd_mask"][0].source_primitive_name == "hadd"


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


def test_masked_indexed_permute_plans_and_renders_for_both_backends() -> None:
    zero_overload = Primitive(
        "permute_lanes",
        "v:=(m,v,vidx)",
        ("mask", "data", "indexes"),
        ("mask",),
        (),
        attributes={"mask": "pass_through"},
    )
    pass_through = Primitive(
        "permute_lanes",
        "v:=(m,v,v,vidx)",
        ("mask", "src", "data", "indexes"),
        ("mask",),
        (),
        attributes={"mask": "pass_through"},
        tests=(
            TslTestCase(
                name="masked_indexed",
                type_tag="si32",
                tags=("masked",),
                lanes=4,
                index_type="ui32",
                inputs=(
                    TslTestArg("mask", mask_bits="5"),
                    TslTestArg("vector", values=("100", "200", "300", "400")),
                    TslTestArg("vector", values=("10", "20", "30", "40")),
                    TslTestArg("vector", values=("3", "2", "1", "0")),
                ),
                expected=("40", "200", "20", "400"),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(zero_overload, pass_through, *_harness_primitives()),
        type_groups={},
        extensions={},
        type_spellings={
            "cpp": {"u32": "std::uint32_t"},
            "rust": {"u32": "u32"},
        },
        translations={},
    )
    cpp_spec = _spec(
        "permute_lanes_mask",
        "permute_lanes",
        param_kinds=("m", "v", "v", "vidx"),
        mask_policy="pass_through",
    )
    rust_spec = replace(
        cpp_spec,
        backend_id="rust",
        base_type_spelling="i32",
        register_spelling="[i32; 4]",
    )
    profile = _profile(
        cpp={"permute_lanes_mask": (cpp_spec,)},
        rust={"permute_lanes_mask": (rust_spec,)},
    )

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    assert plan.diagnostics == ()
    cpp_case = plan.profiles_for("cpp")[0].cases[0]
    rust_case = plan.profiles_for("rust")[0].cases[0]
    assert cpp_case.kind == rust_case.kind == "masked"
    assert cpp_case.index is not None and cpp_case.index.type_tag == "ui32"
    cpp_source = CPP_VALUE_TEST_RENDERER.render_case(cpp_case)
    rust_source = RUST_VALUE_TEST_RENDERER.render_case(rust_case)
    assert "using Indices = tsl::simd<std::uint32_t, tsl::generic<4>>;" in cpp_source
    assert "permute_lanes_mask<Vec, Indices>(m0, v0, v1, v2)" in cpp_source
    assert "type Indices = Simd<u32, Generic<4>>;" in rust_source
    assert "permute_lanes_mask::<Vec, Indices>(m0, v0, v1, v2)" in rust_source


def test_planner_preserves_trailing_masks_for_indexed_memory_cases(
    render_assets: RenderAssets,
) -> None:
    gather = Primitive(
        "gather",
        "v:=(m,cptr,vidx,v,sImm)",
        ("mask", "base_ptr", "index", "source", "scale"),
        ("mask",),
        (),
        attributes={"mask": "pass_through"},
        tests=(
            TslTestCase(
                name="masked_gather",
                type_tag="si32",
                tags=("masked",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("10", "20", "30", "40")),
                    TslTestArg("vector", values=("0", "1", "2", "3")),
                    TslTestArg("vector", values=("100", "101", "102", "103")),
                    # This is the catalog shape produced by the authored indexed-memory
                    # tests, whose mask literal follows the vector-shaped operands.
                    TslTestArg("scalar", scalar="10"),
                ),
                expected=("100", "20", "102", "40"),
                scale=4,
            ),
        ),
    )
    scatter = Primitive(
        "scatter",
        "void:=(m,ptr,vidx,v,sImm)",
        ("mask", "base_ptr", "index", "data", "scale"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="masked_scatter",
                type_tag="si32",
                tags=("masked",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("10", "20", "30", "40")),
                    TslTestArg("vector", values=("0", "1", "2", "3")),
                    TslTestArg("scalar", scalar="10"),
                ),
                expected=("0", "20", "0", "40"),
                scale=4,
            ),
        ),
    )
    gather_spec = _spec(
        "gather_mask",
        "gather",
        param_kinds=("m", "cptr", "vidx", "v", "sImm"),
        immediate=("scale", "std::size_t"),
        mask_policy="pass_through",
    )
    scatter_spec = _spec(
        "scatter_mask",
        "scatter",
        result_kind="void",
        param_kinds=("m", "ptr", "vidx", "v", "sImm"),
        immediate=("scale", "std::size_t"),
        mask_policy="zero",
    )
    profile = _profile(
        cpp={"gather_mask": (gather_spec,), "scatter_mask": (scatter_spec,)}
    )

    plan = ValueTestPlanner(
        _catalog(gather, scatter, *_harness_primitives()),
        (CPP_VALUE_TEST_SUPPORT,),
    ).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", profile.profile.name, profile.specializations("cpp")
            ),
        )
    )

    assert plan.diagnostics == ()
    cases = plan.profiles_for("cpp")[0].cases
    assert [(case.call_name, case.inputs.masks) for case in cases] == [
        ("gather_mask", ("10",)),
        ("scatter_mask", ("10",)),
    ]
    source = render_cpp_values_runner(plan.profiles_for("cpp")[0], render_assets)
    assert "gather_mask<Vec, Indices, 4>(mask, data, idx, source)" in source
    assert "scatter_mask<Vec, Indices, 4>(mask, data, idx, values)" in source


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
    assert cpp_case.invocation.param_kinds == ("m", "v", "v")
    assert cpp_case.inputs.masks == ("5",)
    assert cpp_case.inputs.vectors == (("1", "2", "3", "4"), ("1", "0", "3", "0"))
    assert cpp_case.expectation.values == ("5",)
    assert {entry.status for entry in plan.coverage} == {"emitted"}


def test_runtime_lane_and_mask_mutation_shapes_reuse_typed_case_kinds() -> None:
    extract = Primitive(
        "extract_value_at",
        "s:=(v,usize)",
        ("data", "index"),
        (),
        (),
        tests=(
            TslTestCase(
                name="extract_last",
                type_tag="si32",
                tags=("last",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("scalar", scalar="3"),
                ),
                expected=("4",),
            ),
        ),
    )
    insert = Primitive(
        "insert_value_at",
        "v:=(v,usize,s)",
        ("data", "index", "value"),
        (),
        (),
        tests=(
            TslTestCase(
                name="insert_last",
                type_tag="si32",
                tags=("last",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("scalar", scalar="3"),
                    TslTestArg("scalar", scalar="9"),
                ),
                expected=("1", "2", "3", "9"),
            ),
        ),
    )
    set_mask = Primitive(
        "set_mask_lane",
        "m:=(m,usize,usize)",
        ("mask", "index", "value"),
        (),
        (),
        tests=(
            TslTestCase(
                name="set_mask_last",
                type_tag="si32",
                tags=("last",),
                lanes=4,
                inputs=(
                    TslTestArg("mask", mask_bits="5"),
                    TslTestArg("scalar", scalar="3"),
                    TslTestArg("scalar", scalar="1"),
                ),
                expected=("13",),
            ),
        ),
    )
    specs = {
        "extract_value_at": (
            _spec(
                "extract_value_at",
                "extract_value_at",
                result_kind="s",
                param_kinds=("v", "usize"),
            ),
        ),
        "insert_value_at": (
            _spec(
                "insert_value_at",
                "insert_value_at",
                param_kinds=("v", "usize", "s"),
            ),
        ),
        "set_mask_lane": (
            _spec(
                "set_mask_lane",
                "set_mask_lane",
                result_kind="m",
                param_kinds=("m", "usize", "usize"),
            ),
        ),
    }
    plan = ValueTestPlanner(
        _catalog(extract, insert, set_mask, *_harness_primitives()),
        (CPP_VALUE_TEST_SUPPORT,),
    ).plan((ValueTestBackendProfileInput("cpp", "unit", specs),))

    assert plan.diagnostics == ()
    cases = plan.profiles_for("cpp")[0].cases
    assert [(case.call_name, case.kind) for case in cases] == [
        ("extract_value_at", "scalar_result"),
        ("insert_value_at", "scalar_vector"),
        ("set_mask_lane", "mask_result"),
    ]
    assert {entry.status for entry in plan.coverage} == {"emitted"}


def test_runtime_mask_mutation_rejects_integral_mask_value_operand() -> None:
    primitive = Primitive(
        "set_mask_lane",
        "m:=(m,usize,im)",
        ("mask", "index", "value"),
        (),
        (),
        tests=(
            TslTestCase(
                name="set_mask_last",
                type_tag="si32",
                tags=("last",),
                lanes=4,
                inputs=(
                    TslTestArg("mask", mask_bits="5"),
                    TslTestArg("scalar", scalar="3"),
                    TslTestArg("mask", mask_bits="1"),
                ),
                expected=("13",),
            ),
        ),
    )
    spec = _spec(
        "set_mask_lane",
        "set_mask_lane",
        result_kind="m",
        param_kinds=("m", "usize", "im"),
    )
    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        (CPP_VALUE_TEST_SUPPORT,),
    ).plan(
        (
            ValueTestBackendProfileInput(
                "cpp",
                "unit",
                {"set_mask_lane": (spec,)},
            ),
        )
    )

    assert plan.profiles_for("cpp")[0].cases == ()
    assert len(plan.coverage) == 1
    assert plan.coverage[0].status == "authored_unplanned"
    assert plan.coverage[0].reason == "no value-test pattern accepted the authored case shape"


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
    assert [
        (case.kind, case.case_name, case.invocation.axis_args) for case in cases
    ] == [
        ("store", "basic", ("false",))
    ]


def test_overload_inference_placeholders_are_backend_capability_driven() -> None:
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
        "store", "store", result_kind="void", param_kinds=("ptr", "s")
    )
    vector_overload = _spec(
        "store", "store", result_kind="void", param_kinds=("ptr", "v")
    )
    support = ValueTestBackendSupport(
        backend_id="future",
        case_kinds=CPP_VALUE_TEST_SUPPORT.case_kinds,
        overload_inference_placeholders=2,
    )

    plan = ValueTestPlanner(
        _catalog(primitive, *_harness_primitives()),
        (support,),
    ).plan(
        (
            ValueTestBackendProfileInput(
                "future", "unit", {"store": (scalar_overload, vector_overload)}
            ),
        )
    )

    assert plan.profiles_for("future")[0].cases[0].invocation.inferred_type_args == 2


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
                type_expr="type(base::in) *",
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
    assert cases[0].target is not None
    assert cases[0].target.type_tag == "si32"
    assert cases[0].target.base_spelling == "std::int32_t"
    # The buffer layout is a typed memory fact; the invocation keeps the
    # primitive's honest result kind.
    assert cases[0].invocation.result_kind == "void"
    assert cases[0].memory is not None
    assert cases[0].memory.storage == "unpacked"


def test_packed_mask_store_plan_keeps_honest_result_kind(
    render_assets: RenderAssets,
) -> None:
    primitive = Primitive(
        "store_mask_repr",
        "void:=(ptr,m)",
        ("ptr", "mask"),
        (),
        (),
        attributes={"packed": "true"},
        tests=(
            TslTestCase(
                name="store_mask_repr_packed",
                type_tag="si32",
                tags=("layout",),
                lanes=4,
                inputs=(TslTestArg("mask", mask_bits="5"),),
                expected=("5",),
                attrs={"packed": "true"},
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec(
        "store_mask_repr",
        "store_mask_repr",
        param_kinds=("ptr", "m"),
        result_kind="void",
        axis=(("packed", "true"),),
    )
    profile = _profile(
        cpp={"store_mask_repr": (spec,)}, rust={"store_mask_repr": (spec,)}
    )

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    for backend in ("cpp", "rust"):
        case = plan.profiles_for(backend)[0].cases[0]
        assert case.kind == "mask_store"
        assert case.invocation.result_kind == "void"
        assert case.memory is not None
        assert case.memory.storage == "packed"
        assert case.memory.buffer_length == 1
    cpp_source = render_cpp_values_runner(plan.profiles_for("cpp")[0], render_assets)
    rust_source = render_rust_values_file(
        (plan.profiles_for("rust")[0],), render_assets
    )
    assert "typename Vec::imask_type buf[1]" in cpp_source
    assert "<Vec as SimdVector>::ImaskType; 1]" in rust_source


def test_pointer_layout_scalar_resolver_uses_param_type_expression_parser() -> None:
    assert scalar_type_tag_from_expr("type(base::in) *", "si32") == "si32"
    assert (
        scalar_type_tag_from_expr(
            "type(base::unsigned_of(type(base::in))) const*",
            "si32",
        )
        == "ui32"
    )


def test_pointer_layout_warning_names_unsupported_param_types_expression() -> None:
    primitive = Primitive(
        "store_mask_repr",
        "void:=(ptr,m)",
        ("ptr", "mask"),
        (),
        (),
        attributes={"packed": "false"},
        param_type_rules=(
            ParamTypeRule(
                parameter_name="ptr",
                attribute_name="packed",
                attribute_value="false",
                type_expr="type(vector::imask) *",
            ),
        ),
        tests=(
            TslTestCase(
                name="store_mask_repr_layout",
                type_tag="si32",
                tags=("layout",),
                lanes=4,
                inputs=(TslTestArg("mask", mask_bits="5"),),
                expected=("1", "0", "1", "0"),
                attrs={"packed": "false"},
            ),
        ),
    )
    catalog = _catalog(primitive, *_harness_primitives())
    spec = _spec(
        "store_mask_repr",
        "store_mask_repr",
        param_kinds=("ptr", "m"),
        result_kind="void",
        axis=(("packed", "false"),),
    )
    profile = _profile(cpp={"store_mask_repr": (spec,)})

    plan = ValueTestPlanner(catalog, _VALUE_TEST_SUPPORTS).plan(_inputs(profile))

    assert plan.profiles_for("cpp")[0].cases == ()
    warning = next(
        diagnostic
        for diagnostic in plan.diagnostics
        if diagnostic.code == "TSL-VALUE-TEST-UNSUPPORTED-CASE"
    )
    assert "unsupported param_types layout expression" in warning.message
    assert "type(vector::imask) *" in warning.message


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
            TslTestCase(
                name="bad_unselected_type",
                type_tag="ui64",
                tags=("bad",),
                lanes=2,
                inputs=(TslTestArg("vector", values=("1", "2")),),
                expected=("-1",),
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
    assert "bad_unselected_type" not in warnings[0].message


def test_render_project_consumes_prebuilt_value_test_plan(
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

    plan = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", profile.profile.name, profile.specializations("cpp")
            ),
        )
    )
    rendered = render_project((profile,), ("cpp",), plan, assets=render_assets)

    assert [diagnostic.code for diagnostic in plan.diagnostics] == [
        "TSL-VALUE-TEST-UNSUPPORTED-CASE"
    ]
    assert rendered.value_tests is plan


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

    cpp_bitwise_case = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_neg_bits",
        case_name="float-bits",
        call_name="neg",
        type_tag="f32",
        base_spelling="float",
        lanes=2,
        vector_inputs=(("NAN", "-NAN"),),
        expected=("-NAN", "NAN"),
        comparison=CaseComparison.BITWISE,
        result_kind="v",
        param_kinds=("v",),
    )
    cpp_bitwise_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_bitwise_case,)),
        render_assets,
    )
    assert "check_lanes_bitwise<float>" in cpp_bitwise_source
    assert "{-NAN, NAN}" in cpp_bitwise_source

    cpp_permute_case = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_permute_lanes",
        case_name="indexed",
        call_name="permute_lanes",
        type_tag="si32",
        base_spelling="std::int32_t",
        lanes=2,
        vector_inputs=(("10", "20"), ("1", "0")),
        expected=("20", "10"),
        result_kind="v",
        param_kinds=("v", "vidx"),
        index_type_tag="ui32",
        index_base_spelling="std::uint32_t",
        index_lanes=2,
    )
    cpp_permute_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_permute_case,)),
        render_assets,
    )
    assert "using Indices = tsl::simd<std::uint32_t, tsl::generic<2>>;" in cpp_permute_source
    assert "tsl::permute_lanes<Vec, Indices>(v0, v1)" in cpp_permute_source

    guarded_cpp_case = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_clang_add",
        case_name="clang-basic",
        call_name="plus",
        type_tag="si32",
        base_spelling="std::int32_t",
        lanes=2,
        vector_inputs=(("1", "2"), ("3", "4")),
        expected=("4", "6"),
        result_kind="v",
        param_kinds=("v", "v"),
        header_group="clang",
        required_compiler_features=("ext_vector_type_boolean",),
    )
    guarded_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (guarded_cpp_case,)),
        render_assets,
    )
    assert guarded_source.count("#if defined(TSL_ENABLE_CLANG)") == 2
    assert guarded_source.count("#if defined(__has_feature)") == 2
    assert guarded_source.count("#  if __has_feature(ext_vector_type_boolean)") == 2

    cpp_indexed_case = ValueTestCasePlan(
        kind="indexed_load",
        function_name="test_gather_narrow_partial",
        case_name="partial",
        call_name="gather_narrow_partial",
        type_tag="ui16",
        base_spelling="std::uint16_t",
        lanes=4,
        vector_inputs=(("100", "101", "102", "103", "104"), ("0", "4")),
        expected=("100", "104", "0", "0"),
        immediate_value="2",
        target_lanes=4,
        index_type_tag="ui64",
        index_base_spelling="std::uint64_t",
        index_lanes=2,
        index_style="register",
    )
    cpp_indexed_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_indexed_case,)),
        render_assets,
    )
    assert "using Vec = tsl::simd<std::uint16_t, tsl::generic<4>>;" in cpp_indexed_source
    assert (
        "using Indices = tsl::simd<std::uint64_t, tsl::generic<2>>;"
        in cpp_indexed_source
    )
    assert "static const std::uint64_t idx_in[2] = {0ULL, 4ULL};" in cpp_indexed_source
    assert (
        "tsl::gather_narrow_partial<Vec, Indices, 2>(data, idx);"
        in cpp_indexed_source
    )

    cpp_pointer_indexed_case = ValueTestCasePlan(
        kind="indexed_load",
        function_name="test_gather_narrow",
        case_name="basic",
        call_name="gather_narrow",
        type_tag="ui16",
        base_spelling="std::uint16_t",
        lanes=8,
        vector_inputs=(
            ("100", "101", "102", "103", "104", "105", "106", "107"),
            ("3", "0", "2", "1", "7", "6", "5", "4"),
        ),
        expected=("103", "100", "102", "101", "107", "106", "105", "104"),
        result_kind="v",
        param_kinds=("cptr", "cptr", "sImm"),
        immediate_value="2",
        target_lanes=8,
        index_type_tag="ui64",
        index_base_spelling="std::uint64_t",
        index_lanes=8,
        index_style="pointer",
    )
    cpp_pointer_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (cpp_pointer_indexed_case,)),
        render_assets,
    )
    assert "typename Indices::register_type idx" not in cpp_pointer_source
    assert (
        "tsl::gather_narrow<Vec, Indices, 2>(data, idx_in);"
        in cpp_pointer_source
    )

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
        runtime_lanes_template="svcntb() / sizeof({base_type})",
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

    rust_bitwise_case = replace(
        cpp_bitwise_case,
        base_spelling="f32",
    )
    rust_bitwise_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_bitwise_case,)),),
        render_assets,
    )
    assert ".lane_bitwise_eq(expected[i])" in rust_bitwise_source
    assert "[-f32::NAN, f32::NAN]" in rust_bitwise_source

    rust_permute_case = ValueTestCasePlan(
        kind="generic_golden",
        function_name="test_permute_lanes",
        case_name="indexed",
        call_name="permute_lanes",
        type_tag="si32",
        base_spelling="i32",
        lanes=2,
        vector_inputs=(("10", "20"), ("1", "0")),
        expected=("20", "10"),
        result_kind="v",
        param_kinds=("v", "vidx"),
        index_type_tag="ui32",
        index_base_spelling="u32",
        index_lanes=2,
    )
    rust_permute_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_permute_case,)),),
        render_assets,
    )
    assert "type Indices = Simd<u32, Generic<2>>;" in rust_permute_source
    assert "permute_lanes::<Vec, Indices>(v0, v1)" in rust_permute_source

    rust_pointer_source = render_rust_values_file(
        (
            ValueTestProfilePlan(
                "rust",
                "unit-profile",
                (
                    ValueTestCasePlan(
                        kind="indexed_load",
                        function_name="test_gather_narrow",
                        case_name="basic",
                        call_name="gather_narrow",
                        type_tag="ui16",
                        base_spelling="u16",
                        lanes=8,
                        vector_inputs=(
                            ("100", "101", "102", "103", "104", "105", "106", "107"),
                            ("3", "0", "2", "1", "7", "6", "5", "4"),
                        ),
                        expected=("103", "100", "102", "101", "107", "106", "105", "104"),
                        result_kind="v",
                        param_kinds=("cptr", "cptr", "sImm"),
                        immediate_value="2",
                        target_lanes=8,
                        index_type_tag="ui64",
                        index_base_spelling="u64",
                        index_lanes=8,
                        index_style="pointer",
                    ),
                ),
            ),
        ),
        render_assets,
    )
    assert "let mut idx: <Indices as SimdVector>::RegisterType" not in rust_pointer_source
    assert (
        "gather_narrow::<Vec, Indices, 2, 8>(data.as_ptr(), idx_in.as_ptr())"
        in rust_pointer_source
    )

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
        storage="unpacked",
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

    rust_indexed_vector_case = ValueTestCasePlan(
        kind="scalar_vector",
        function_name="test_insert_value",
        case_name="insert_value",
        call_name="insert_value",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"),),
        scalar_inputs=("9",),
        expected=("1", "2", "9", "4"),
        param_kinds=("v", "s"),
        index_value="2",
    )
    rust_indexed_vector_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_indexed_vector_case,)),),
        render_assets,
    )
    assert "insert_value::<Vec, 2>(v0, s0)" in rust_indexed_vector_source

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

    rust_diff_case = ValueTestCasePlan(
        kind="differential",
        function_name="test_diff_wasm128_add_si32_basic",
        case_name="add_si32_basic",
        call_name="add",
        type_tag="si32",
        base_spelling="i32",
        lanes=4,
        vector_inputs=(("1", "2", "3", "4"), ("4", "3", "2", "1")),
        result_kind="v",
        param_kinds=("v", "v"),
        hardware_extension="wasm128",
        from_array_name="from_array",
        to_array_name="to_array",
    )
    rust_diff_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (rust_diff_case,)),),
        render_assets,
    )
    assert "type Hw = Simd<i32, Wasm128>;" in rust_diff_source
    assert "type Ref = Simd<i32, Generic<4>>;" in rust_diff_source
    assert "from_array::<Hw>(&hin0)" in rust_diff_source
    assert "let hw = to_array::<Hw>(add::<Hw>(" in rust_diff_source
    assert "let reference = add::<Ref>(r0, r1);" in rust_diff_source
    assert "hw[i].lane_eq(reference[i])" in rust_diff_source


def test_extension_result_renderers_use_distinct_fixed_extensions(
    render_assets: RenderAssets,
) -> None:
    concat = ValueTestCasePlan(
        "extension_result",
        "test_concat",
        "concat",
        "concat",
        "si32",
        "std::int32_t",
        4,
        vector_inputs=(("1", "2", "3", "4"), ("5", "6", "7", "8")),
        expected=("1", "2", "3", "4", "5", "6", "7", "8"),
        result_kind="v",
        param_kinds=("v", "v"),
        expected_type_tag="si32",
        target_base_spelling="std::int32_t",
        target_lanes=8,
        source_extension="sse",
        target_extension="avx2",
        from_array_name="from_array",
        to_array_name="to_array",
    )
    cpp_source = render_cpp_values_runner(
        ValueTestProfilePlan("cpp", "unit-profile", (concat,)), render_assets
    )
    assert "using Vec = tsl::simd<std::int32_t, tsl::sse>;" in cpp_source
    assert "using ToVec = tsl::simd<std::int32_t, tsl::avx2>;" in cpp_source
    assert "tsl::concat<Vec, ToVec>(" in cpp_source
    assert '"concat", hout, expected, 8' in cpp_source

    undefined_upper = replace(
        concat,
        function_name="test_resize_up_undef",
        case_name="resize_up_undef",
        call_name="resize_up_undef",
        base_spelling="i32",
        inputs=ValueTestInputs(vectors=(("1", "2", "3", "4"),)),
        expectation=ValueTestExpectation(values=("1", "2", "3", "4")),
        invocation=ValueTestInvocation(result_kind="v", param_kinds=("v",)),
        target=ValueTestTarget(type_tag="si32", base_spelling="i32", lanes=8),
    )
    rust_source = render_rust_values_file(
        (ValueTestProfilePlan("rust", "unit-profile", (undefined_upper,)),),
        render_assets,
    )
    assert "type Vec = Simd<i32, Sse>;" in rust_source
    assert "type ToVec = Simd<i32, Avx2>;" in rust_source
    assert "resize_up_undef::<Vec, ToVec>(" in rust_source
    assert "for i in 0..4" in rust_source


def test_value_test_case_plan_validates_kind_requirements() -> None:
    assert all(
        isinstance(fact, ValueTestFact)
        for capability in DEFAULT_VALUE_TEST_CASE_CAPABILITIES
        for fact in capability.requirements.required_facts
    )
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
    assert zero_arg.inputs.vectors == ()

    aligned_free = ValueTestCasePlan(
        kind="pointer_free",
        function_name="test_aligned_free",
        case_name="aligned_free",
        call_name="deallocate",
        type_tag="ptr",
        base_spelling="void*",
        lanes=1,
        scalar_inputs=("64",),
        alignment=32,
    )
    assert aligned_free.memory is not None
    assert aligned_free.memory.alignment == 32
    assert aligned_free.target is None

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

    with pytest.raises(ValueError, match="requires scalable_"):
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
            mask_check_template="true",
            expected_mask_bits=5,
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

    with pytest.raises(ValueError, match="requires memory_length"):
        ValueTestCasePlan(
            kind="mask_pointer_load",
            function_name="test_load_mask_bad",
            case_name="load_mask_bad",
            call_name="load_mask",
            type_tag="ui32",
            base_spelling="u32",
            lanes=4,
            vector_inputs=(("0", "1", "0", "1"),),
            expected=("10",),
        )

    with pytest.raises(ValueError, match="requires memory_length"):
        ValueTestCasePlan(
            kind="indexed_store",
            function_name="test_scatter_bad",
            case_name="scatter_bad",
            call_name="scatter",
            type_tag="ui32",
            base_spelling="u32",
            lanes=4,
            vector_inputs=(("1", "2"), ("0", "1")),
            expected=("1", "2"),
            immediate_value="4",
            index_lanes=2,
            index_style="register",
        )

    with pytest.raises(ValueError, match="requires index_style"):
        ValueTestCasePlan(
            kind="indexed_load",
            function_name="test_gather_bad",
            case_name="gather_bad",
            call_name="gather",
            type_tag="ui32",
            base_spelling="u32",
            lanes=4,
            vector_inputs=(("1", "2"), ("0", "1")),
            expected=("1", "2"),
            immediate_value="4",
            target_lanes=2,
            index_lanes=2,
        )

    with pytest.raises(ValueError, match="requires memory_storage"):
        ValueTestCasePlan(
            kind="mask_store",
            function_name="test_mask_store_bad",
            case_name="mask_store_bad",
            call_name="store_mask",
            type_tag="ui32",
            base_spelling="u32",
            lanes=4,
            mask_inputs=("5",),
            expected=("0", "1", "0", "1"),
            buffer_length=4,
        )


def test_differential_cases_require_profile_scoped_round_trip_helpers() -> None:
    primitive = Primitive(
        "add",
        "v:=(v,v)",
        ("left", "right"),
        (),
        (),
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("vector", values=("4", "3", "2", "1")),
                ),
                expected=("5", "5", "5", "5"),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(primitive, *_harness_primitives()),
        type_groups={},
        extensions={
            "sse": Extension(
                "sse",
                "sse",
                "x86",
                {},
                {},
                backend_supported={"cpp": True},
                vector_bits=128,
                default_test_target=True,
            )
        },
        type_spellings={},
        translations={},
    )
    add = _spec(
        "add",
        "add",
        param_kinds=("v", "v"),
        extension_name="sse",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    lane_in = _spec(
        "lane_in",
        "lane_in",
        param_kinds=("s[]",),
        extension_name="sse",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    lane_out = _spec(
        "lane_out",
        "lane_out",
        param_kinds=("v",),
        result_kind="s[]",
        extension_name="sse",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    planner = ValueTestPlanner(
        catalog,
        (CPP_VALUE_TEST_SUPPORT,),
        fuzz=True,
    )

    missing_helpers = planner.plan(
        (ValueTestBackendProfileInput("cpp", "sse", {"add": (add,)}),)
    )
    complete_helpers = planner.plan(
        (
            ValueTestBackendProfileInput(
                "cpp",
                "sse",
                {
                    "add": (add,),
                    "lane_in": (lane_in,),
                    "lane_out": (lane_out,),
                },
            ),
        )
    )

    assert {case.kind for case in missing_helpers.profiles[0].cases} == {
        "generic_golden"
    }
    assert {case.kind for case in complete_helpers.profiles[0].cases} == {
        "differential",
        "differential_fuzz",
        "generic_golden",
    }
    # The suppressed synthetic fuzz case gets an explicit coverage entry whose
    # reason names the missing harness closure, not the renderer.
    fuzz_drop = next(
        entry for entry in missing_helpers.coverage if entry.case_name == "add:fuzz"
    )
    assert fuzz_drop.status == "backend_unsupported"
    assert fuzz_drop.case_kind == "differential_fuzz"
    assert "differential harness primitive(s) 'lane_in', 'lane_out'" in fuzz_drop.reason
    assert "extension 'sse'" in fuzz_drop.reason
    assert "renderer" not in fuzz_drop.reason
    assert all(
        entry.case_name != "add:fuzz" for entry in complete_helpers.coverage
    )


def test_fuzz_without_backend_fuzz_renderer_reports_explicit_coverage() -> None:
    primitive = Primitive(
        "add",
        "v:=(v,v)",
        ("left", "right"),
        (),
        (),
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("vector", values=("4", "3", "2", "1")),
                ),
                expected=("5", "5", "5", "5"),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(primitive, *_harness_primitives()),
        type_groups={},
        extensions={
            "sse": Extension(
                "sse",
                "sse",
                "x86",
                {},
                {},
                backend_supported={"rust": True},
                vector_bits=128,
                default_test_target=True,
            )
        },
        type_spellings={},
        translations={},
    )
    add = _spec(
        "add",
        "add",
        param_kinds=("v", "v"),
        extension_name="sse",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    lane_in = _spec(
        "lane_in",
        "lane_in",
        param_kinds=("s[]",),
        extension_name="sse",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    lane_out = _spec(
        "lane_out",
        "lane_out",
        param_kinds=("v",),
        result_kind="s[]",
        extension_name="sse",
        uses_sized_vector=False,
        lane_parameter=None,
    )
    planner = ValueTestPlanner(catalog, (RUST_VALUE_TEST_SUPPORT,), fuzz=True)

    plan = planner.plan(
        (
            ValueTestBackendProfileInput(
                "rust",
                "sse",
                {"add": (add,), "lane_in": (lane_in,), "lane_out": (lane_out,)},
            ),
        )
    )

    assert all(
        case.kind != "differential_fuzz" for case in plan.profiles[0].cases
    )
    entry = next(item for item in plan.coverage if item.case_name == "add:fuzz")
    assert entry.status == "backend_unsupported"
    assert entry.case_kind == "differential_fuzz"
    assert entry.reason == (
        "synthetic fuzz case kind 'differential_fuzz' is not supported by "
        "the rust value-test renderer"
    )
    assert any(
        diagnostic.code == "TSL-VALUE-TEST-UNSUPPORTED-CASE"
        and "add:fuzz" in diagnostic.message
        for diagnostic in plan.diagnostics
    )


def test_wasm_rust_value_tests_render_native_differential_cases(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["wasm32-simd128"],
        type_tags=("f32",),
        backends=("rust",),
        test_harness=True,
    )

    assert not [diagnostic for diagnostic in result.diagnostics if diagnostic.severity == "error"]
    values_source = next(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path == "rust/tests/values.rs"
    )

    assert "fn test_diff_wasm128_add_f32_basic()" in values_source
    assert "type Hw = Simd<f32, Wasm128>;" in values_source
    assert "type Ref = Simd<f32, Generic<4>>;" in values_source
    assert "from_array::<Hw>(&hin0)" in values_source
    assert "let hw = to_array::<Hw>(add::<Hw>(" in values_source
    assert "let reference = add::<Ref>(r0, r1);" in values_source


def test_opt_in_clang_overlays_get_guarded_differential_targets(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["avx2"],
        type_tags=("si32",),
        backends=("cpp",),
        test_harness=True,
    )

    assert result.rendered is not None
    cases = tuple(
        case
        for profile in result.rendered.value_tests.profiles_for("cpp")
        for case in profile.cases
    )
    assert any(
        case.differential is not None
        and case.differential.hardware_extension == "avx2"
        for case in cases
    )
    clang_cases = tuple(
        case
        for case in cases
        if case.differential is not None
        and case.differential.hardware_extension.startswith("clang_v")
    )
    assert clang_cases
    assert all(case.header_group == "clang" for case in clang_cases)
    bool_cases = tuple(
        case
        for case in clang_cases
        if case.differential is not None
        and case.differential.hardware_extension.endswith("_bool")
    )
    comparison_cases = tuple(case for case in clang_cases if case not in bool_cases)
    assert bool_cases
    assert all(
        case.required_compiler_features == ("ext_vector_type_boolean",)
        for case in bool_cases
    )
    assert all(not case.required_compiler_features for case in comparison_cases)

    values_source = next(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path == "cpp/tests/values_avx2.cpp"
    )
    assert "#if defined(TSL_ENABLE_CLANG)" in values_source
    assert "#  if __has_feature(ext_vector_type_boolean)" in values_source
    assert "using Hw = tsl::simd<int32_t, tsl::clang_v256>;" in values_source


def test_incompatible_value_test_header_groups_are_diagnosed() -> None:
    first = Extension(
        "first",
        "first",
        "unit",
        {},
        {},
        backend_supported={"cpp": True},
        metadata=ExtensionMetadata(
            backend={
                "cpp": BackendExtensionMetadata(header_group="first_group")
            }
        ),
        source=SourceSpan(Path("extensions.tsl"), 10, 1, 10, 6),
    )
    second = Extension(
        "second",
        "second",
        "unit",
        {},
        {},
        backend_supported={"cpp": True},
        metadata=ExtensionMetadata(
            backend={
                "cpp": BackendExtensionMetadata(header_group="second_group")
            }
        ),
        source=SourceSpan(Path("extensions.tsl"), 20, 1, 20, 7),
    )
    catalog = Catalog(
        primitives=(),
        type_groups={},
        extensions={"first": first, "second": second},
        type_spellings={},
        translations={},
    )
    planner = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,))
    case = ValueTestCasePlan(
        "compile_only",
        "test_conflicting_headers",
        "conflicting_headers",
        "unit",
        "si32",
        "std::int32_t",
        4,
        result_kind="v",
        source_extension="first",
        target_extension="second",
    )
    diagnostics: list[Diagnostic] = []

    planned = planner._with_header_group(case, "cpp", diagnostics)

    assert isinstance(planned, ValueTestCaseDrop)
    assert planned.cause == "header_group_conflict"
    assert "incompatible generated header groups" in planned.reason("cpp")
    assert "first_group" in planned.reason("cpp")
    assert diagnostics == [
        Diagnostic(
            severity="error",
            code="TSL-VALUE-TEST-INCOMPATIBLE-HEADER-GROUPS",
            message=(
                "cpp value-test case 'test_conflicting_headers' spans incompatible "
                "header groups ['first_group', 'second_group'] through extensions "
                "['first', 'second']"
            ),
            span=first.source,
        )
    ]


def test_value_test_planning_error_prevents_project_rendering(
    data_root: Path,
    machine_profiles_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planning_error = Diagnostic(
        severity="error",
        code="TSL-VALUE-TEST-UNIT-ERROR",
        message="unit planning failure",
    )
    monkeypatch.setattr(
        pipeline_module._GenerationSession,
        "_plan_value_tests",
        lambda self, profiles: ValueTestProjectPlan(  # noqa: ARG005
            profiles=(), diagnostics=(planning_error,)
        ),
    )

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar"],
        type_tags=("si32",),
        backends=("rust",),
    )

    assert result.rendered is None
    assert result.artifacts.artifacts == ()
    assert planning_error in result.diagnostics


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


def _scalable_test_extension() -> Extension:
    return Extension(
        "sve",
        "sve",
        "arm",
        {},
        {},
        backend_supported={"cpp": True},
        vector_bits_kind="scalable",
        default_test_target=True,
        test_runtime_lanes={"cpp": "svcntb() / sizeof({base_type})"},
        test_mask_from_bits={
            "cpp": "make_mask<{vec}>({mask_bits}, {authored_lanes}, {lanes})"
        },
        test_mask_check={
            "cpp": "check_mask_bits<{vec}>({case_name}, {mask}, {expected_bits}, "
            "{authored_lanes}, {lanes})"
        },
    )


def test_scalable_immediate_cases_plan_and_render_runtime_lanes(
    render_assets: RenderAssets,
) -> None:
    unmasked = Primitive(
        "mul_imm",
        "v:=(v,sImm)",
        ("data", "factor"),
        (),
        (),
        tests=(
            TslTestCase(
                name="mul_imm_sve",
                type_tag="si32",
                tags=("sve",),
                lanes=4,
                extension="sve",
                inputs=(
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("scalar", scalar="3"),
                ),
                expected=("3", "6", "9", "12"),
            ),
        ),
    )
    masked = Primitive(
        "mul_imm",
        "v:=(m,v,sImm)",
        ("mask", "data", "factor"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="mul_imm_maskz_sve",
                type_tag="si32",
                tags=("sve",),
                lanes=4,
                extension="sve",
                inputs=(
                    TslTestArg("mask", mask_bits="10"),
                    TslTestArg("vector", values=("1", "2", "3", "4")),
                    TslTestArg("scalar", scalar="3"),
                ),
                expected=("0", "6", "0", "12"),
            ),
        ),
    )
    specs = {
        "mul_imm": (
            _spec(
                "mul_imm",
                "mul_imm",
                param_kinds=("v", "sImm"),
                immediate=("factor", "std::uint32_t"),
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
        "mul_imm_maskz": (
            _spec(
                "mul_imm_maskz",
                "mul_imm",
                param_kinds=("m", "v", "sImm"),
                immediate=("factor", "std::uint32_t"),
                mask_policy="zero",
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
    }
    catalog = Catalog(
        primitives=(unmasked, masked, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )

    plan = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(
        (ValueTestBackendProfileInput("cpp", "sve", specs),)
    )

    assert not plan.diagnostics
    scalable = tuple(
        case for case in plan.profiles[0].cases if case.scalable is not None
    )
    assert [case.kind for case in scalable] == [
        "scalable_immediate",
        "scalable_masked_immediate",
    ]
    assert all(case.invocation.immediate == "3" for case in scalable)
    assert scalable[1].scalable is not None
    assert scalable[1].scalable.mask_bits == (10,)

    source = render_cpp_values_runner(plan.profiles[0], render_assets)
    assert "tsl::load<Vec, false>(in0.data())" in source
    assert "tsl::mul_imm<Vec, 3>(v0)" in source
    assert "tsl::mul_imm_maskz<Vec, 3>(" in source
    assert "make_mask<tsl::simd<std::int32_t, tsl::sve>>(10ull, 4, lanes)" in source
    assert "authored_expected[i % 4]" in source

def test_scalable_indexed_lane_uses_one_runtime_lane() -> None:
    insert_value = Primitive(
        "insert_value",
        "v:=(v,s)",
        ("data", "value"),
        (),
        (),
        tests=(
            TslTestCase(
                name="insert_lane_3",
                type_tag="si32",
                tags=("sve",),
                lanes=4,
                extension="sve",
                index=3,
                inputs=(
                    TslTestArg("vector", values=("1", "-2", "3", "-4")),
                    TslTestArg("scalar", scalar="-99"),
                ),
                expected=("1", "-2", "3", "-99"),
            ),
        ),
    )
    spec = replace(
        _spec(
            "insert_value",
            "insert_value",
            param_kinds=("v", "s"),
            extension_name="sve",
            uses_sized_vector=False,
            lane_parameter=None,
        ),
        generic_params=(("Index", "std::size_t", "0"),),
    )
    catalog = Catalog(
        primitives=(insert_value, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )

    plan = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(
        (
            ValueTestBackendProfileInput(
                "cpp", "sve", {"insert_value": (spec,)}
            ),
        )
    )

    assert not plan.diagnostics
    case = next(
        case for case in plan.profiles[0].cases if case.scalable is not None
    )
    assert case.kind == "scalable_scalar_vector"
    assert case.index == ValueTestIndex(value="3")
    assert case.invocation.generic_defaults == ()
    assert case.expectation.scalable_layout == "indexed_lane"

    source = CPP_VALUE_TEST_RENDERER.render_case(case)
    assert "tsl::insert_value<Vec, 3>(v0, s0)" in source
    assert "expected[i] = authored0[i % 4];" in source
    assert "if (3 < lanes) expected[3] = authored_expected[3];" in source
    assert "authored_expected[i % 4]" not in source


def test_scalable_plan_facts_stay_backend_neutral_for_sve_case() -> None:
    # Planned scalable facts carry raw extension templates, integer mask bits, and the
    # unquoted authored case name. The C++ renderer alone spells `tsl::simd<...>`,
    # appends `ull` suffixes, and quotes names, so no planned scalable fact may contain
    # backend text or filled placeholders.
    add = Primitive(
        "add",
        "v:=(v,v)",
        ("left", "right"),
        (),
        (),
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=2,
                inputs=(
                    TslTestArg("vector", values=("1", "2")),
                    TslTestArg("vector", values=("3", "4")),
                ),
                expected=("4", "6"),
            ),
        ),
    )
    mask_and = Primitive(
        "mask_and",
        "m:=(m,m)",
        ("left", "right"),
        (),
        (),
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=2,
                inputs=(
                    TslTestArg("mask", mask_bits="3"),
                    TslTestArg("mask", mask_bits="1"),
                ),
                expected=("1",),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(add, mask_and, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )
    specs = {
        "add": (
            _spec(
                "add",
                "add",
                param_kinds=("v", "v"),
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
        "mask_and": (
            _spec(
                "mask_and",
                "mask_and",
                param_kinds=("m", "m"),
                result_kind="m",
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
    }
    planner = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,))
    plan = planner.plan((ValueTestBackendProfileInput("cpp", "sve", specs),))

    scalable_cases = [
        case
        for profile in plan.profiles
        for case in profile.cases
        if case.scalable is not None
    ]
    assert {case.kind for case in scalable_cases} == {
        "scalable_golden",
        "scalable_mask_logic",
    }
    for case in scalable_cases:
        scalable = case.scalable
        assert scalable is not None
        facts = (
            scalable.source_extension,
            scalable.runtime_lanes_template,
            scalable.mask_from_bits_template or "",
            scalable.mask_check_template or "",
            scalable.load_name or "",
            scalable.store_name or "",
            case.case_name,
        )
        assert not any("tsl::" in fact for fact in facts)
        assert not any("ull" in fact for fact in facts)
        assert '"' not in case.case_name
    logic = next(case for case in scalable_cases if case.kind == "scalable_mask_logic")
    assert logic.scalable is not None
    assert logic.scalable.mask_bits == (3, 1)
    assert logic.scalable.expected_mask_bits == 1
    assert logic.scalable.mask_from_bits_template is not None
    assert "{vec}" in logic.scalable.mask_from_bits_template
    assert logic.scalable.mask_check_template is not None
    assert "{expected_bits}" in logic.scalable.mask_check_template


def test_scalable_mask_count_uses_runtime_tiled_oracle(
    render_assets: RenderAssets,
) -> None:
    count = Primitive(
        "mask_count",
        "usize:=m",
        ("mask",),
        (),
        (),
        tests=(
            TslTestCase(
                name="mask_count_si32_sve_basic",
                type_tag="si32",
                tags=("basic",),
                lanes=4,
                extension="sve",
                expected_rule="popcnt",
                inputs=(TslTestArg("mask", mask_bits="10"),),
                expected=("2",),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(count, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )
    specs = {
        "mask_count": (
            _spec(
                "mask_count",
                "mask_count",
                param_kinds=("m",),
                result_kind="usize",
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
    }
    plan = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(
        (ValueTestBackendProfileInput("cpp", "sve", specs),)
    )

    assert not plan.diagnostics
    assert plan.coverage[0].status == "emitted"
    assert plan.coverage[0].case_kind == "scalable_mask_count"
    case = plan.profiles[0].cases[0]
    assert case.kind == "scalable_mask_count"
    assert case.scalable is not None
    assert case.scalable.mask_bits == (10,)

    source = render_cpp_values_runner(plan.profiles[0], render_assets)
    assert "using Vec = tsl::simd<std::int32_t, tsl::sve>;" in source
    assert "make_mask<tsl::simd<std::int32_t, tsl::sve>>(10ull, 4, lanes)" in source
    assert "auto result = tsl::mask_count<Vec>(mask);" in source
    assert "(authored_mask >> (i % 4)) & 1ull" in source
    assert "check_scalar<std::size_t>" in source


def test_scalable_mask_count_rejects_mismatched_authored_oracle() -> None:
    count = Primitive(
        "mask_count",
        "usize:=m",
        ("mask",),
        (),
        (),
        tests=(
            TslTestCase(
                name="bad_count",
                type_tag="si32",
                tags=("bad",),
                lanes=4,
                extension="sve",
                expected_rule="popcnt",
                inputs=(TslTestArg("mask", mask_bits="10"),),
                expected=("3",),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(count, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )
    specs = {
        "mask_count": (
            _spec(
                "mask_count",
                "mask_count",
                param_kinds=("m",),
                result_kind="usize",
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
    }

    plan = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(
        (ValueTestBackendProfileInput("cpp", "sve", specs),)
    )

    assert plan.profiles[0].cases == ()
    assert plan.coverage[0].status == "authored_unplanned"
    assert "matching authored-lane count" in plan.coverage[0].reason


def test_scalable_only_case_reports_backend_unsupported_without_scalable_kinds() -> None:
    # A case only plannable as a scalable kind (the mask operand is authored as a scalar
    # token, which the fixed masked-mask-result shape rejects) must surface as
    # `backend_unsupported` through the planner's central drop machinery when the backend
    # lacks scalable kinds — not as `authored_unplanned`.
    masked_cmp = Primitive(
        "cmpeq_mask",
        "m:=(m,v,v)",
        ("mask", "left", "right"),
        ("mask",),
        (),
        attributes={"mask": "zero"},
        tests=(
            TslTestCase(
                name="basic",
                type_tag="si32",
                tags=("basic",),
                lanes=2,
                inputs=(
                    TslTestArg("scalar", scalar="1"),
                    TslTestArg("vector", values=("1", "2")),
                    TslTestArg("vector", values=("1", "3")),
                ),
                expected=("1", "0"),
            ),
        ),
    )
    catalog = Catalog(
        primitives=(masked_cmp, *_harness_primitives()),
        type_groups={},
        extensions={"sve": _scalable_test_extension()},
        type_spellings={},
        translations={},
    )
    specs = {
        "cmpeq_mask": (
            _spec(
                "cmpeq_mask",
                "cmpeq_mask",
                param_kinds=("m", "v", "v"),
                result_kind="m",
                mask_policy="zero",
                extension_name="sve",
                uses_sized_vector=False,
                lane_parameter=None,
            ),
        ),
    }
    profile_inputs = (ValueTestBackendProfileInput("cpp", "sve", specs),)

    full = ValueTestPlanner(catalog, (CPP_VALUE_TEST_SUPPORT,)).plan(profile_inputs)
    full_entry = next(
        entry for entry in full.coverage if entry.primitive_name == "cmpeq_mask"
    )
    assert full_entry.status == "emitted"
    assert full_entry.case_kind == "scalable_masked_mask_result"

    without_scalable = ValueTestBackendSupport(
        backend_id="cpp",
        case_kinds=frozenset(
            kind
            for kind in CPP_VALUE_TEST_SUPPORT.case_kinds
            if not kind.startswith("scalable_")
        ),
    )
    restricted = ValueTestPlanner(catalog, (without_scalable,)).plan(profile_inputs)
    entry = next(
        entry for entry in restricted.coverage if entry.primitive_name == "cmpeq_mask"
    )
    assert entry.status == "backend_unsupported"
    assert entry.case_kind == "scalable_masked_mask_result"
    assert "not supported by the cpp value-test renderer" in entry.reason


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
            "masked_pointer_load",
            "test_load_mask",
            "load_mask",
            "load_mask",
            "ui32",
            "u32",
            4,
            vector_inputs=(("1", "2", "3", "4"), ("10", "20", "30", "40")),
            expected=("1", "20", "3", "40"),
            mask_inputs=("5",),
            axis_args=("false",),
            buffer_offset=1,
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
            index_lanes=4,
            index_style="register",
        ),
        ValueTestCasePlan(
            "indexed_load",
            "test_gather_narrow_partial",
            "gather_narrow_partial",
            "gather_narrow_partial",
            "ui16",
            "u16",
            4,
            vector_inputs=(("100", "101", "102", "103", "104"), ("0", "4")),
            expected=("100", "104", "0", "0"),
            immediate_value="2",
            target_lanes=4,
            index_type_tag="ui64",
            index_base_spelling="u64",
            index_lanes=2,
            index_style="register",
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
            index_lanes=4,
            index_style="register",
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
    assert "let mut buf: [u32; 5] = [Default::default(); 5];" in source
    assert "for i in 0..4 { buf[1 + i] = in0[i]; }" in source
    assert "let mut v1: <Vec as SimdVector>::RegisterType = Default::default();" in source
    assert "load_mask::<Vec, false>(mask, buf.as_ptr().add(1), v1)" in source
    assert "compress_store::<Vec, true>(" in source
    assert "memory_cp::<Vec>(" in source
    assert "let ptr = allocate(64usize);" in source
    assert "unsafe { deallocate(ptr); }" in source
    assert "gather::<Vec, Indices, 4, 4>(data.as_ptr(), idx)" in source
    assert "type Indices = Simd<u64, Generic<2>>;" in source
    assert "gather_narrow_partial::<Vec, Indices, 2, 2>(data.as_ptr(), idx)" in source
    assert "let expected: [u16; 4] = [100, 104, 0, 0];" in source
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
    renderer_projections = {
        "vector_inputs",
        "mask_inputs",
        "scalar_input",
        "scalar_inputs",
        "expected",
        "text_expected",
        "result_kind",
        "param_kinds",
        "axis_args",
        "immediate_value",
        "generic_defaults",
        "expected_type_tag",
        "target_base_spelling",
        "target_lanes",
        "index_value",
        "index_type_tag",
        "index_base_spelling",
        "index_lanes",
        "index_style",
        "buffer_offset",
        "buffer_length",
        "source_offset",
        "alignment",
        "storage",
        "source_extension",
        "target_extension",
        "from_array_name",
        "to_array_name",
        "to_integral_name",
        "hardware_extension",
        "runtime_lanes_template",
        "mask_from_bits_template",
        "mask_check_template",
        "mask_bits",
        "expected_mask_bits",
        "load_name",
        "store_name",
        "fuzz_seed",
        "fuzz_iterations",
    }
    rendered_tree = ast.parse(
        (render_cpp + render_rust).replace("from __future__ import annotations", "")
    )
    assert renderer_projections.isdisjoint(
        node.attr
        for node in ast.walk(rendered_tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "case"
    )
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
    assert "#![cfg(tsl_value_tests)]" in rust_values_template
    assert "tsl::tsl_core" not in render_rust
    assert "tsl::tsl_core" in rust_profile_template
    assert "Catalog" not in render_rust
    assert "Primitive" not in render_rust
def test_cpp_value_test_support_matches_renderer_dispatch() -> None:
    assert CPP_VALUE_TEST_SUPPORT.case_kinds == CPP_VALUE_TEST_RENDERER.case_kinds
    assert CPP_VALUE_TEST_RENDERER.backend_support() == CPP_VALUE_TEST_SUPPORT
    with pytest.raises(TypeError):
        CPP_VALUE_TEST_RENDERER.case_renderers["new_case"] = (  # type: ignore[index]
            lambda case: ""
        )


def test_cpp_integer_literals_are_valid_at_64_bit_boundaries() -> None:
    assert cpp_literal("-9223372036854775808", "si64") == (
        "(-9223372036854775807LL - 1LL)"
    )
    assert cpp_literal("18446744073709551615", "ui64") == (
        "18446744073709551615ULL"
    )


def test_rust_value_test_support_matches_renderer_dispatch() -> None:
    assert RUST_VALUE_TEST_SUPPORT.case_kinds == RUST_VALUE_TEST_RENDERER.case_kinds
    assert RUST_VALUE_TEST_RENDERER.backend_support() == RUST_VALUE_TEST_SUPPORT
    with pytest.raises(TypeError):
        RUST_VALUE_TEST_RENDERER.case_renderers["new_case"] = (  # type: ignore[index]
            lambda case: ""
        )


def test_value_test_case_requirements_cover_renderer_dispatch() -> None:
    assert frozenset(_ValueTestCasePlan.CASE_REQUIREMENTS) == DEFAULT_VALUE_TEST_CASE_KINDS
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


def test_value_test_renderer_rejects_exclusion_for_undeclared_case_kind() -> None:
    with pytest.raises(ValueError, match="excludes undeclared case kind"):
        ValueTestRendererCapability(
            backend_id="unit",
            case_renderers={"generic_golden": lambda case: ""},
            profile_case_exclusions=(
                ValueTestProfileCaseExclusion(
                    "wasm32", "runtime_failure", "unobservable failure"
                ),
            ),
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
        Primitive("mask_from_bits", "m:=im", ("bits",), (), ()),
        Primitive("load", "v:=cptr", ("ptr",), (), ()),
        Primitive("store", "void:=(ptr,v)", ("ptr", "data"), (), ()),
    )


def _profile(
    *,
    cpp: dict[str, tuple[LoweredSpecialization, ...]] | None = None,
    rust: dict[str, tuple[LoweredSpecialization, ...]] | None = None,
) -> EmittedProfile:
    return EmittedProfile(
        profile=MachineProfile("unit", "generic", frozenset(), {}),
        specializations_by_backend={"cpp": cpp or {}, "rust": rust or {}},
        immediate_split_names=frozenset(),
    )


def _inputs(profile: EmittedProfile) -> tuple[ValueTestBackendProfileInput, ...]:
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
    extension_name: str = "generic",
    uses_sized_vector: bool = True,
    lane_parameter: str | None = "4",
) -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="cpp",
        primitive_name=primitive_name,
        source_primitive_name=source_primitive_name,
        extension_name=extension_name,
        type_tag="si32",
        base_type_spelling="std::int32_t",
        register_spelling="std::int32_t[4]",
        result_kind=result_kind,
        param_names=tuple(f"p{i}" for i in range(len(param_kinds))),
        param_kinds=param_kinds,
        body=LoweredBody.from_text(""),
        uses_sized_vector=uses_sized_vector,
        lane_parameter=lane_parameter,
        axis=axis,
        immediate=immediate,
        mask_policy=mask_policy,
    )
