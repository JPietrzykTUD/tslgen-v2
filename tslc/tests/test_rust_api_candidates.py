"""Rust facade candidate normalization and exclusion tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rust_api_test_support import _plan, _spec
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_model import RustFacadeCoverageStatus
from tslc.backend.rust_api_planner import (
    RustFacadePlanningError,
    plan_rust_facade,
)
from tslc.backend.rust_static_selection import (
    RustStaticFallbackModule,
    RustStaticProfileSelection,
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
    RustTargetRequirement,
)
from tslc.catalog.conversion import (
    ConversionKind,
    LaneCountRelation,
    NumericConversionMode,
    PrimitiveConversionContract,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.lower.lowerer import LoweredTypeParam
from tslc.lower.target_vectors import TargetVector


def test_missing_generic_baseline_is_a_typed_exclusion() -> None:
    spec = _spec("hardware_only")
    emitted = EmittedProfile(
        MachineProfile("hardware", "x86", frozenset(), {}),
        {"rust": {"hardware_only": (replace(spec, extension_name="avx2"),)}},
        immediate_split_names=frozenset(),
    )

    plan = plan_rust_facade(
        (emitted,),
        RustStaticSelectionPlan(
            (
                RustStaticProfileSelection(
                    "hardware",
                    RustTargetRequirement("x86_64", ()),
                    (),
                    (),
                ),
            ),
            (),
            RustStaticFallbackModule((), ()),
        ),
    )

    assert plan.comprehensive_methods == ()
    assert plan.coverage[0].status is RustFacadeCoverageStatus.EXCLUDED
    assert plan.coverage[0].reason == "missing generic baseline"


def test_target_vector_admission_is_explicit_and_lane_preserving() -> None:
    conversion = PrimitiveConversionContract(
        ConversionKind.NUMERIC,
        LaneCountRelation.PRESERVE_LANE_COUNT,
        NumericConversionMode.SCALAR_AS,
    )
    result_vector = replace(
        _spec("convert_lanes", conversion=conversion),
        type_params=(
            LoweredTypeParam(
                "ToVec",
                base_type_binding="f64",
                base_type_binding_spelling="f64",
            ),
        ),
        result_vector_param="ToVec",
    )
    mappings = (
        RustStaticVectorMapping(
            "si32",
            "i32",
            4,
            128,
            "Simd<i32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
        RustStaticVectorMapping(
            "f64",
            "f64",
            4,
            256,
            "Simd<f64, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
    )

    method = plan_rust_facade(
        (),
        _plan(result_vector, fallback_mappings=mappings),
    ).comprehensive_methods[0]

    assert method.type_parameters[0].source_name == "ToVec"
    assert method.type_parameters[0].public_name == "U"
    assert method.type_parameters[0].type_tags == ("f64",)

    concrete_target = replace(
        _spec("reinterpret_target"),
        target=TargetVector("Vector", "Register", "generic", "f64", "f64"),
    )
    exclusion = plan_rust_facade(
        (),
        _plan(concrete_target, fallback_mappings=mappings),
    ).coverage[0]
    assert exclusion.status is RustFacadeCoverageStatus.EXCLUDED
    assert exclusion.reason == "concrete target-vector shape is lower-level only"


def test_unresolved_conversion_target_binding_is_rejected() -> None:
    conversion = PrimitiveConversionContract(
        ConversionKind.NUMERIC,
        LaneCountRelation.PRESERVE_LANE_COUNT,
        NumericConversionMode.SCALAR_AS,
    )
    specialization = replace(
        _spec(
            "unresolved_convert",
            result_kind="v",
            param_names=("data",),
            param_kinds=("v",),
            operation=PrimitiveOperation.CONVERT,
            roles=((OperandRole.PRIMARY, 0, "v"),),
            conversion=conversion,
        ),
        type_params=(LoweredTypeParam("ToVec"),),
        result_vector_param="ToVec",
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(specialization))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-TARGET-BINDING-MISMATCH"
    }


def test_unknown_overload_is_rejected_before_rendering() -> None:
    spec = _spec(
        "future_overload",
        overload=ResolvedPrimitiveOverload("future_axis", "future_value", True),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(spec))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-UNKNOWN-OVERLOAD"
    }


def test_role_signature_mismatch_is_rejected_before_rendering() -> None:
    spec = _spec(
        "mismatched_role",
        roles=(
            (OperandRole.PRIMARY, 0, "m"),
            (OperandRole.SECONDARY, 1, "s"),
        ),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(spec))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-ROLE-MISMATCH"
    }
