"""Typed, render-independent planning for the ordinary Rust facade."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_model import (
    RustFacadeCoreDelegate,
    RustFacadeCoverageStatus,
    RustFacadeConstParameterSource,
    RustFacadeInvocation,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeRepresentation,
    RustFacadeReceiverKind,
    RustFacadeShape,
    RustFacadeTargetSelection,
    RustFacadeTraitRhsKind,
)
from tslc.backend.rust_api_planner import (
    RUST_FACADE_CORE_OPERATION_REQUIREMENTS,
    RustFacadePlanningError,
    plan_rust_facade,
    validate_rust_facade,
)
from tslc.backend.rust_static_selection import (
    RustStaticFallbackModule,
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
    RustTargetRequirement,
    plan_rust_static_selection,
)
from tslc.catalog.arithmetic import (
    ArithmeticContract,
    ArithmeticGuarantee,
    ArithmeticOperandBinding,
    ArithmeticOperandRole,
    ArithmeticOperation,
)
from tslc.catalog.conversion import (
    ConversionKind,
    LaneCountRelation,
    NumericConversionMode,
    PrimitiveConversionContract,
)
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import ImplementationSafety
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import (
    OperandBinding,
    OperandRole,
    PrimitiveOperation,
    PrimitiveSemanticContract,
)
from tslc.diagnostics import has_errors
from tslc.lower.lowerer import LoweredSpecialization, LoweredTypeParam
from tslc.lower.primitive_semantics import LoweredPrimitiveSemantics
from tslc.lower.target_vectors import TargetVector
from tslc.render.rust_facade import (
    _canonical_operator_impl,
    _curated_method_impl,
    _facade_impl,
)
from tslc.render.rust_facade_comprehensive import render_comprehensive_facade
from tslc.render.rust_facade_common import (
    representations_can_coexist,
    selection_cfg,
)
from tslc.target_text import LoweredBody


def _operation(
    kind: PrimitiveOperation,
    roles: tuple[tuple[OperandRole, int, str], ...],
    names: tuple[str, ...],
) -> PrimitiveSemanticContract:
    return PrimitiveSemanticContract(
        kind,
        tuple(
            OperandBinding(role, names[index], index, parameter_kind)
            for role, index, parameter_kind in roles
        ),
    )


def _spec(
    name: str,
    *,
    result_kind: str = "v",
    param_names: tuple[str, ...] = ("data", "value"),
    param_kinds: tuple[str, ...] = ("v", "s"),
    operation: PrimitiveOperation = PrimitiveOperation.BIT_AND_NOT,
    roles: tuple[tuple[OperandRole, int, str], ...] = (
        (OperandRole.PRIMARY, 0, "v"),
        (OperandRole.SECONDARY, 1, "s"),
    ),
    overload: ResolvedPrimitiveOverload | None = None,
    immediate: tuple[str, str] | None = None,
    mask_policy: str | None = None,
    safety: ImplementationSafety = ImplementationSafety(),
    arithmetic: ArithmeticContract | None = None,
    conversion: PrimitiveConversionContract | None = None,
    emitted_name: str | None = None,
) -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="rust",
        primitive_name=emitted_name or name,
        source_primitive_name=name,
        extension_name="generic",
        type_tag="si32",
        base_type_spelling="i32",
        register_spelling="array_type<i32, LANES>",
        result_kind=result_kind,
        param_names=param_names,
        param_kinds=param_kinds,
        body=LoweredBody.from_text(""),
        primitive_semantics=LoweredPrimitiveSemantics(
            overload=overload,
            arithmetic=arithmetic,
            operation=_operation(operation, roles, param_names),
            conversion=conversion,
        ),
        uses_sized_vector=True,
        lane_parameter="LANES",
        immediate=immediate,
        mask_policy=mask_policy,
        safety=safety,
    )


def _arithmetic_spec(
    name: str = "sum",
    *,
    operation: ArithmeticOperation = ArithmeticOperation.ADDITION,
    reordered: bool = False,
) -> LoweredSpecialization:
    names = ("right", "left") if reordered else ("left", "right")
    rhs_role = (
        ArithmeticOperandRole.DIVISOR
        if operation in {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
        else ArithmeticOperandRole.SECONDARY
    )
    primary_index = 1 if reordered else 0
    rhs_index = 0 if reordered else 1
    guarantees = {
        ArithmeticOperation.ADDITION: frozenset(
            {ArithmeticGuarantee.INTEGER_WRAPPING}
        ),
        ArithmeticOperation.SUBTRACTION: frozenset(
            {ArithmeticGuarantee.INTEGER_WRAPPING}
        ),
        ArithmeticOperation.DIVISION: frozenset(
            {
                ArithmeticGuarantee.INTEGER_QUOTIENT_TOWARD_ZERO,
                ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
                ArithmeticGuarantee.SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN,
                ArithmeticGuarantee.FLOATING_DIVISION_IEEE754_VALUES,
            }
        ),
    }[operation]
    arithmetic = ArithmeticContract(
        frozenset({operation}),
        (
            ArithmeticOperandBinding(
                ArithmeticOperandRole.PRIMARY,
                "left",
                primary_index,
                primary_index,
                "v",
            ),
            ArithmeticOperandBinding(
                rhs_role,
                "right",
                rhs_index,
                rhs_index,
                "v",
            ),
        ),
        guarantees,
    )
    return _spec(
        name,
        param_names=names,
        param_kinds=("v", "v"),
        roles=(),
        arithmetic=arithmetic,
    )


def _plan(
    *specs: LoweredSpecialization,
    profiles: tuple[EmittedProfile, ...] = (),
) -> RustStaticSelectionPlan:
    by_name: dict[str, list[LoweredSpecialization]] = {}
    for spec in specs:
        by_name.setdefault(spec.primitive_name, []).append(spec)
    return RustStaticSelectionPlan(
        profiles=(),
        fallback_mappings=(
            RustStaticVectorMapping(
                "si32", "i32", 4, 128, "Simd<i32, Generic<4>>", "u64"
            ),
        ),
        fallback_module=RustStaticFallbackModule(
            tuple(
                (name, tuple(group)) for name, group in sorted(by_name.items())
            ),
            (),
        ),
    )


def test_generic_fallback_excludes_exact_profile_arms_without_width_holes() -> None:
    avx2 = RustTargetRequirement("x86_64", ("avx2",))
    avx512 = RustTargetRequirement("x86_64", ("avx2", "avx512f"))
    fallback = RustFacadeRepresentation(
        None,
        None,
        (),
        RustStaticVectorMapping(
            "si32", "i32", 4, 128, "Simd<i32, Generic<4>>", "u64"
        ),
        (RustFacadeTargetSelection(avx2, (avx512,)),),
    )
    avx2_representation = RustFacadeRepresentation(
        "avx2",
        avx2,
        (avx512,),
        RustStaticVectorMapping(
            "si32",
            "i32",
            4,
            128,
            "Simd<i32, Sse>",
            "u8",
            "sse",
            "Sse",
        ),
    )
    avx512_representation = RustFacadeRepresentation(
        "avx512",
        avx512,
        (),
        RustStaticVectorMapping(
            "si32",
            "i32",
            16,
            512,
            "Simd<i32, Avx512>",
            "u16",
            "avx512",
            "Avx512",
        ),
    )

    rendered = selection_cfg(fallback)

    assert 'target_feature = "avx2"' in rendered
    assert 'target_feature = "avx512f"' in rendered
    assert rendered.startswith("not(any(all(")
    assert not representations_can_coexist(fallback, avx2_representation)
    assert representations_can_coexist(fallback, avx512_representation)


@pytest.mark.parametrize(
    ("spec", "expected"),
    (
        (
            _spec(
                "shift_left",
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "uniform", True
                ),
            ),
            "shift_left",
        ),
        (
            _spec(
                "shift_left",
                param_names=("data", "shift"),
                param_kinds=("v", "sImm"),
                roles=(
                    (OperandRole.PRIMARY, 0, "v"),
                    (OperandRole.COUNT, 1, "sImm"),
                ),
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "uniform", False
                ),
                immediate=("shift", "u32"),
            ),
            "shift_left_imm",
        ),
        (
            _spec(
                "shift_left",
                param_names=("data", "shift"),
                param_kinds=("v", "v"),
                roles=(
                    (OperandRole.PRIMARY, 0, "v"),
                    (OperandRole.COUNT, 1, "v"),
                ),
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "per_lane", False
                ),
            ),
            "shift_left_each",
        ),
        (
            _spec(
                "mul_imm",
                param_names=("mask", "data", "factor"),
                param_kinds=("m", "v", "sImm"),
                roles=(
                    (OperandRole.CONTROL_MASK, 0, "m"),
                    (OperandRole.PRIMARY, 1, "v"),
                    (OperandRole.COUNT, 2, "sImm"),
                ),
                immediate=("factor", "i32"),
                mask_policy="pass_through",
            ),
            "mul_imm_masked",
        ),
        (
            _spec(
                "shift_left",
                param_names=("mask", "data", "shift"),
                param_kinds=("m", "v", "sImm"),
                roles=(
                    (OperandRole.CONTROL_MASK, 0, "m"),
                    (OperandRole.PRIMARY, 1, "v"),
                    (OperandRole.COUNT, 2, "sImm"),
                ),
                overload=ResolvedPrimitiveOverload(
                    "count_distribution", "uniform", False
                ),
                immediate=("shift", "u32"),
                mask_policy="zero",
            ),
            "shift_left_imm_masked_zero",
        ),
    ),
)
def test_public_name_components_are_composed_once(
    spec: LoweredSpecialization,
    expected: str,
) -> None:
    plan = plan_rust_facade((), _plan(spec))

    assert [method.public_name for method in plan.comprehensive_methods] == [expected]


def test_receiver_is_finalized_before_explicit_arguments() -> None:
    spec = _spec(
        "masked_op",
        param_names=("mask", "data", "factor"),
        param_kinds=("m", "v", "sImm"),
        roles=(
            (OperandRole.CONTROL_MASK, 0, "m"),
            (OperandRole.PRIMARY, 1, "v"),
            (OperandRole.COUNT, 2, "sImm"),
        ),
        immediate=("factor", "i32"),
        mask_policy="pass_through",
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.VECTOR
    assert tuple(parameter.placement for parameter in method.parameters) == (
        RustFacadeParameterPlacement.ARGUMENT,
        RustFacadeParameterPlacement.RECEIVER,
        RustFacadeParameterPlacement.CONST_GENERIC,
    )
    assert method.parameters[0].role is OperandRole.CONTROL_MASK
    assert method.parameters[2].public_name == "FACTOR"


def test_mask_primary_becomes_a_mask_receiver() -> None:
    spec = _spec(
        "mask_not",
        result_kind="m",
        param_names=("mask",),
        param_kinds=("m",),
        operation=PrimitiveOperation.MASK_NOT,
        roles=((OperandRole.PRIMARY, 0, "m"),),
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.MASK
    assert method.parameters[0].placement is RustFacadeParameterPlacement.RECEIVER


def test_attribute_and_generic_const_parameters_are_finalized() -> None:
    spec = replace(
        _spec("configured"),
        axis=(("aligned", "true"),),
        generic_params=(("PreserveSign", "bool", "true"),),
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert tuple(item.public_name for item in method.const_parameters) == (
        "ALIGNED",
        "PRESERVE_SIGN",
    )
    assert method.const_parameters[1].source_default == "true"


def test_immediate_is_a_finalized_const_parameter() -> None:
    spec = _spec(
        "configured_immediate",
        param_names=("data", "shift"),
        param_kinds=("v", "sImm"),
        roles=(
            (OperandRole.PRIMARY, 0, "v"),
            (OperandRole.COUNT, 1, "sImm"),
        ),
        immediate=("shift", "u32"),
    )

    method = plan_rust_facade((), _plan(spec)).comprehensive_methods[0]

    assert tuple(
        (item.public_name, item.type_spelling, item.source)
        for item in method.const_parameters
    ) == (("SHIFT", "u32", RustFacadeConstParameterSource.IMMEDIATE),)


def test_no_receiver_projects_as_a_free_function() -> None:
    method = plan_rust_facade(
        (),
        _plan(
            _spec(
                "broadcast_source",
                param_names=("value",),
                param_kinds=("s",),
                operation=PrimitiveOperation.VECTOR_SPLAT,
                roles=((OperandRole.VALUE, 0, "s"),),
            )
        ),
    ).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.FREE
    assert method.parameters[0].placement is RustFacadeParameterPlacement.ARGUMENT
    assert method.shape_keys == (("si32", 4),)


def test_vector_value_role_is_a_coherent_receiver() -> None:
    method = plan_rust_facade(
        (),
        _plan(
            _spec(
                "write_value",
                result_kind="void",
                param_names=("mask", "destination", "value"),
                param_kinds=("m", "ptr", "v"),
                operation=PrimitiveOperation.STORE,
                roles=(
                    (OperandRole.CONTROL_MASK, 0, "m"),
                    (OperandRole.MEMORY_DESTINATION, 1, "ptr"),
                    (OperandRole.VALUE, 2, "v"),
                ),
                mask_policy="pass_through",
            )
        ),
    ).comprehensive_methods[0]

    assert method.receiver_kind is RustFacadeReceiverKind.VECTOR
    assert method.parameters[2].placement is RustFacadeParameterPlacement.RECEIVER


def test_curated_unmasked_memory_shapes_are_not_duplicated() -> None:
    vector_store = _spec(
        "source_store",
        result_kind="void",
        param_names=("destination", "value"),
        param_kinds=("ptr", "v"),
        operation=PrimitiveOperation.STORE,
        roles=(
            (OperandRole.MEMORY_DESTINATION, 0, "ptr"),
            (OperandRole.VALUE, 1, "v"),
        ),
        overload=ResolvedPrimitiveOverload("payload_extent", "vector", True),
    )
    scalar_store = replace(
        vector_store,
        param_names=("destination", "value"),
        param_kinds=("ptr", "s"),
        primitive_semantics=replace(
            vector_store.primitive_semantics,
            overload=ResolvedPrimitiveOverload(
                "payload_extent", "scalar", False
            ),
            operation=_operation(
                PrimitiveOperation.STORE,
                (
                    (OperandRole.MEMORY_DESTINATION, 0, "ptr"),
                    (OperandRole.VALUE, 1, "s"),
                ),
                ("destination", "value"),
            ),
        ),
    )

    plan = plan_rust_facade((), _plan(vector_store, scalar_store))

    assert len(plan.comprehensive_methods) == 1
    assert plan.comprehensive_methods[0].receiver_kind is RustFacadeReceiverKind.FREE
    assert any(
        entry.reason
        == "unmasked vector store is exposed by the curated memory boundary"
        for entry in plan.coverage
    )


def test_attribute_combinations_remain_delegate_owned() -> None:
    base = _spec("configured_axis")
    false_spec = replace(base, axis=(("aligned", "false"),))
    true_spec = replace(base, axis=(("aligned", "true"),))

    method = plan_rust_facade(
        (), _plan(false_spec, true_spec)
    ).comprehensive_methods[0]

    assert method.delegates[0].vectors[0].attribute_combinations == (
        (("aligned", "false"),),
        (("aligned", "true"),),
    )


def test_caller_safety_is_preserved_and_mismatches_are_rejected() -> None:
    unsafe_spec = _spec(
        "unsafe_op",
        safety=ImplementationSafety(caller_unsafe=True),
    )
    method = plan_rust_facade((), _plan(unsafe_spec)).comprehensive_methods[0]
    assert method.caller_unsafe

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade(
            (),
            _plan(unsafe_spec, replace(unsafe_spec, safety=ImplementationSafety())),
        )
    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-SAFETY-MISMATCH"
    }


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
            (),
            _plan().fallback_mappings,
            RustStaticFallbackModule((), ()),
        ),
    )

    assert plan.comprehensive_methods == ()
    assert plan.coverage[0].status is RustFacadeCoverageStatus.EXCLUDED
    assert plan.coverage[0].reason == "missing generic baseline"


def test_public_name_collision_is_rejected_before_rendering() -> None:
    immediate = _spec(
        "collision",
        param_names=("data", "factor"),
        param_kinds=("v", "sImm"),
        roles=(
            (OperandRole.PRIMARY, 0, "v"),
            (OperandRole.COUNT, 1, "sImm"),
        ),
        immediate=("factor", "i32"),
    )
    already_named = _spec("collision_imm")

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(immediate, already_named))

    assert "TSL-BACKEND-RUST-FACADE-NAME-COLLISION" in {
        diagnostic.code for diagnostic in error.value.diagnostics
    }


def test_curated_name_is_reserved_before_comprehensive_methods() -> None:
    comparison = _spec(
        "comparison_source",
        result_kind="m",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        operation=PrimitiveOperation.COMPARE_EQUAL,
        roles=(
            (OperandRole.PRIMARY, 0, "v"),
            (OperandRole.SECONDARY, 1, "v"),
        ),
    )
    comprehensive = _spec("simd_eq")

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(comparison, comprehensive))

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-NAME-COLLISION"
    }


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

    method = plan_rust_facade((), _plan(result_vector)).comprehensive_methods[0]

    assert method.type_parameters[0].source_name == "ToVec"
    assert method.type_parameters[0].public_name == "U"
    assert method.type_parameters[0].type_tags == ("f64",)

    concrete_target = replace(
        _spec("reinterpret_target"),
        target=TargetVector("Vector", "Register", "avx2", "f64", "f64"),
    )
    exclusion = plan_rust_facade((), _plan(concrete_target)).coverage[0]
    assert exclusion.status is RustFacadeCoverageStatus.EXCLUDED
    assert exclusion.reason == "concrete target-vector shape is lower-level only"


def test_semantic_rename_keeps_curated_trait_and_operation_value() -> None:
    original = plan_rust_facade((), _plan(_arithmetic_spec("first_name")))
    renamed = plan_rust_facade((), _plan(_arithmetic_spec("renamed_sum")))

    assert original.trait_implementations[0].trait_path == "core::ops::Add"
    assert renamed.trait_implementations[0].trait_path == "core::ops::Add"
    assert original.operation_values[0].public_name == "Add"
    assert renamed.operation_values[0].public_name == "Add"
    assert original.comprehensive_methods[0].public_name == "first_name"
    assert renamed.comprehensive_methods[0].public_name == "renamed_sum"


def test_immediate_arithmetic_remains_a_named_method() -> None:
    vector = _arithmetic_spec("add_imm")
    assert vector.primitive_semantics.arithmetic is not None
    arithmetic = replace(
        vector.primitive_semantics.arithmetic,
        operand_bindings=(
            vector.primitive_semantics.arithmetic.operand_bindings[0],
            replace(
                vector.primitive_semantics.arithmetic.operand_bindings[1],
                parameter_kind="sImm",
            ),
        ),
    )
    immediate = replace(
        vector,
        param_names=("left", "right"),
        param_kinds=("v", "sImm"),
        immediate=("right", "i32"),
        primitive_semantics=replace(
            vector.primitive_semantics,
            arithmetic=arithmetic,
        ),
    )

    plan = plan_rust_facade((), _plan(immediate))

    assert plan.comprehensive_methods[0].public_name == "add_imm"
    assert plan.trait_implementations == ()


def test_neg_trait_excludes_unsigned_element_types() -> None:
    arithmetic = ArithmeticContract(
        frozenset({ArithmeticOperation.NEGATION}),
        (
            ArithmeticOperandBinding(
                ArithmeticOperandRole.PRIMARY, "data", 0, 0, "v"
            ),
        ),
        frozenset(
            {
                ArithmeticGuarantee.INTEGER_WRAPPING,
                ArithmeticGuarantee.FLOATING_SIGN_BIT_TOGGLE,
            }
        ),
    )
    specs = tuple(
        replace(
            _spec(
                "neg",
                param_names=("data",),
                param_kinds=("v",),
                roles=(),
                arithmetic=arithmetic,
            ),
            type_tag=tag,
        )
        for tag in ("si32", "ui32", "f32")
    )

    trait = plan_rust_facade((), _plan(*specs)).trait_implementations[0]

    assert trait.trait_path == "core::ops::Neg"
    assert trait.type_tags == ("f32", "si32")


def test_additive_unaliased_primitive_gets_only_a_comprehensive_method() -> None:
    plan = plan_rust_facade((), _plan(_spec("future_primitive")))

    assert plan.comprehensive_methods[0].public_name == "future_primitive"
    assert plan.trait_implementations == ()
    assert plan.curated_methods == ()


def test_selection_curated_method_uses_the_control_mask_receiver() -> None:
    spec = _spec(
        "arbitrary_selection_name",
        param_names=("mask", "true_values", "false_values"),
        param_kinds=("m", "v", "v"),
        operation=PrimitiveOperation.SELECT,
        roles=(
            (OperandRole.CONTROL_MASK, 0, "m"),
            (OperandRole.PRIMARY, 1, "v"),
            (OperandRole.PASS_THROUGH, 2, "v"),
        ),
    )

    plan = plan_rust_facade((), _plan(spec))

    assert plan.comprehensive_methods[0].receiver_kind is RustFacadeReceiverKind.VECTOR
    assert plan.comprehensive_methods[0].public_name == "arbitrary_selection_name_masked"
    assert plan.curated_methods[0].public_name == "select"
    assert plan.curated_methods[0].receiver_kind is RustFacadeReceiverKind.MASK


def test_reordered_selection_preserves_the_authored_lower_call_order() -> None:
    spec = _spec(
        "reordered_selection",
        param_names=("false_values", "mask", "true_values"),
        param_kinds=("v", "m", "v"),
        operation=PrimitiveOperation.SELECT,
        roles=(
            (OperandRole.PASS_THROUGH, 0, "v"),
            (OperandRole.CONTROL_MASK, 1, "m"),
            (OperandRole.PRIMARY, 2, "v"),
        ),
    )

    plan = plan_rust_facade((), _plan(spec))
    method = plan.curated_methods[0]
    shape = plan.shapes[0]
    rendered = _curated_method_impl(
        method,
        shape,
        shape.representations[0],
        method.delegates[0],
    )

    assert method.invocation.public_argument_index_by_source_index == (2, 0, 1)
    assert "pub fn select(self, true_values:" in rendered
    assert "(false_values.value, self.value, true_values.value)" in rendered


def test_reordered_comparison_preserves_the_authored_lower_call_order() -> None:
    spec = _spec(
        "reordered_less",
        result_kind="m",
        param_names=("right", "left"),
        param_kinds=("v", "v"),
        operation=PrimitiveOperation.COMPARE_LESS,
        roles=(
            (OperandRole.SECONDARY, 0, "v"),
            (OperandRole.PRIMARY, 1, "v"),
        ),
    )

    plan = plan_rust_facade((), _plan(spec))
    method = plan.curated_methods[0]
    shape = plan.shapes[0]
    rendered = _curated_method_impl(
        method,
        shape,
        shape.representations[0],
        method.delegates[0],
    )

    assert method.public_name == "simd_lt"
    assert method.invocation.public_argument_index_by_source_index == (1, 0)
    assert "(other.value, self.value)" in rendered


@pytest.mark.parametrize(
    ("operation", "trait_path"),
    (
        (ArithmeticOperation.SUBTRACTION, "core::ops::Sub"),
        (ArithmeticOperation.DIVISION, "core::ops::Div"),
    ),
)
def test_reordered_noncommutative_operator_preserves_the_lower_call_order(
    operation: ArithmeticOperation,
    trait_path: str,
) -> None:
    spec = _arithmetic_spec(
        f"reordered_{operation.value}",
        operation=operation,
        reordered=True,
    )

    plan = plan_rust_facade((), _plan(spec))
    trait = plan.trait_implementations[0]
    shape = plan.shapes[0]
    rendered = _canonical_operator_impl(
        trait,
        shape,
        shape.representations[0],
        trait.delegates[0],
        f"Simd<{shape.base_spelling}, {shape.lanes}>",
    )

    assert trait.trait_path == trait_path
    assert trait.invocation.public_argument_index_by_source_index == (1, 0)
    assert "(rhs.value, self.value)" in rendered


def test_core_store_and_lane_insertion_render_from_finalized_invocations() -> None:
    representation = RustFacadeRepresentation(
        None,
        None,
        (),
        RustStaticVectorMapping(
            "si32", "i32", 4, 128, "Simd<i32, Generic<4>>", "u64"
        ),
    )
    shape = RustFacadeShape("si32", "i32", 4, 128, (representation,))
    delegates = tuple(
        RustFacadeCoreDelegate(
            role=requirement.role,
            type_tag="si32",
            lanes=4,
            profile_name=None,
            source_primitive_name=f"test_{requirement.role}",
            invocation=RustFacadeInvocation(
                (
                    (1, 0)
                    if requirement.role == "store"
                    else (2, 0, 1)
                    if requirement.role == "insert_lane"
                    else tuple(range(len(requirement.parameter_kinds)))
                )
            ),
        )
        for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
    )
    plan = RustFacadePlan(
        shapes=(shape,),
        operation_bindings=(),
        core_delegates=delegates,
        comprehensive_methods=(),
        curated_methods=(),
        bit_conversions=(),
        trait_implementations=(),
        native_aliases=(),
        operation_values=(),
        coverage=(),
    )

    rendered = _facade_impl(plan, shape, representation)

    assert "test_store::<" in rendered
    assert ">(value, destination)" in rendered
    assert "test_insert_lane::<" in rendered
    assert ">(lane, value, index)" in rendered


@pytest.mark.parametrize(
    "indices",
    (
        (0, 0),
        (1,),
        (0, 2),
    ),
)
def test_invocation_requires_an_exact_argument_permutation(
    indices: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError, match="exact permutation"):
        RustFacadeInvocation(indices)


@pytest.mark.parametrize(
    ("bindings", "diagnostic_code"),
    (
        (
            (OperandBinding(OperandRole.PRIMARY, "left", 0, "v"),),
            "TSL-BACKEND-RUST-FACADE-INVOCATION-MISMATCH",
        ),
        (
            (
                OperandBinding(OperandRole.PRIMARY, "left", 0, "v"),
                OperandBinding(OperandRole.SECONDARY, "right", 0, "v"),
            ),
            "TSL-BACKEND-RUST-FACADE-INVOCATION-MISMATCH",
        ),
        (
            (
                OperandBinding(OperandRole.PRIMARY, "left", 2, "v"),
                OperandBinding(OperandRole.SECONDARY, "right", 1, "v"),
            ),
            "TSL-BACKEND-RUST-FACADE-ROLE-MISMATCH",
        ),
    ),
)
def test_invalid_curated_invocation_roles_are_rejected_during_planning(
    bindings: tuple[OperandBinding, ...],
    diagnostic_code: str,
) -> None:
    spec = _spec(
        "invalid_comparison_roles",
        result_kind="m",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        operation=PrimitiveOperation.COMPARE_LESS,
        roles=(),
    )
    spec = replace(
        spec,
        primitive_semantics=replace(
            spec.primitive_semantics,
            operation=PrimitiveSemanticContract(
                PrimitiveOperation.COMPARE_LESS,
                bindings,
            ),
        ),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(spec))

    assert {item.code for item in error.value.diagnostics} == {diagnostic_code}


def test_incomplete_core_invocation_is_rejected_before_rendering() -> None:
    spec = _spec(
        "incomplete_store",
        result_kind="void",
        param_names=("value", "destination"),
        param_kinds=("v", "ptr"),
        operation=PrimitiveOperation.STORE,
        roles=((OperandRole.VALUE, 0, "v"),),
        overload=ResolvedPrimitiveOverload("payload_extent", "vector", True),
        safety=ImplementationSafety(caller_unsafe=True),
    )
    spec = replace(spec, axis=(("aligned", "false"),))

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade((), _plan(spec))

    assert {item.code for item in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-INVOCATION-MISMATCH"
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


def test_reduced_inventory_validation_does_not_require_facade_core_closure() -> None:
    spec = _spec("isolated_semantic_primitive")
    static = _plan(spec)

    assert validate_rust_facade((), static) == ()


def test_current_lowered_families_plan_without_reopening_the_catalog(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "add",
            "div",
            "equal",
            "nequal",
            "less_than",
            "less_than_or_equal",
            "greater_than",
            "greater_than_or_equal",
            "select",
            "convert_lanes",
            "reinterpret",
            "shift_left_wrapping",
            "shift_right_wrapping",
        ],
        profiles=["scalar", "sse2", "avx", "avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)
    artifacts = {
        artifact.logical_path: artifact.content
        for artifact in result.artifacts.artifacts
    }

    assert validate_rust_facade(result.emitted_profiles, static) == ()
    plan = plan_rust_facade(result.emitted_profiles, static)

    assert any(
        trait.trait_path == "core::ops::Add"
        and trait.operation is ArithmeticOperation.ADDITION
        and trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
        for trait in plan.trait_implementations
    )
    assert any(method.public_name == "simd_eq" for method in plan.curated_methods)
    assert {
        method.public_name
        for method in plan.curated_methods
        if method.receiver_kind is RustFacadeReceiverKind.VECTOR
    } >= {
        "simd_eq",
        "simd_ne",
        "simd_lt",
        "simd_le",
        "simd_gt",
        "simd_ge",
        "cast",
    }
    cast = next(
        method for method in plan.curated_methods if method.public_name == "cast"
    )
    assert set(cast.target_type_tags) == {
        "f32",
        "f64",
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    }
    assert ("si32", 4) in cast.shape_keys
    assert {
        (conversion.float_type_tag, conversion.bits_type_tag)
        for conversion in plan.bit_conversions
    } == {("f32", "ui32"), ("f64", "ui64")}
    assert any(
        method.public_name == "select"
        and method.receiver_kind is RustFacadeReceiverKind.MASK
        for method in plan.curated_methods
    )
    assert any(
        method.public_name == "shift_left_wrapping_each"
        for method in plan.comprehensive_methods
    )
    assert any(
        shape.type_tag == "si32"
        and shape.lanes == 8
        and {item.profile_name for item in shape.representations}
        == {None, "avx2"}
        for shape in plan.shapes
    )
    si32_native = next(alias for alias in plan.native_aliases if alias.type_tag == "si32")
    assert next(
        selection.lanes
        for selection in si32_native.selections
        if selection.profile_name == "avx"
    ) == 4
    expected_native_profiles = {None} | {
        profile.profile_name for profile in static.profiles
    }
    assert all(
        {selection.profile_name for selection in alias.selections}
        == expected_native_profiles
        for alias in plan.native_aliases
    )
    assert {
        trait.rhs_kind
        for trait in plan.trait_implementations
        if trait.trait_path in {"core::ops::Shl", "core::ops::Shr"}
    } == {
        RustFacadeTraitRhsKind.SAME_TYPE,
        RustFacadeTraitRhsKind.SCALAR,
    }
    assert any(
        trait.trait_path == "core::ops::Div"
        and ("si32", 4) in trait.shape_keys
        for trait in plan.trait_implementations
    )
    assert {
        delegate.role
        for delegate in plan.core_delegates
        if delegate.type_tag == "si32"
        and delegate.lanes == 8
        and delegate.profile_name == "avx2"
    } >= {
        "vector_splat",
        "vector_from_array",
        "vector_to_array",
        "load",
        "store",
        "mask_from_integral",
        "mask_to_integral",
    }
    facade = artifacts["rust/src/tsl_facade.rs"]
    library = artifacts["rust/src/lib.rs"]
    assert "pub fn add(self, right: Simd<i32, 4>)" in facade
    assert "pub fn add_masked(" in facade
    assert "pub fn add_masked_zero(" in facade
    assert "pub fn convert_lanes<U>(self)" in facade
    assert "pub unsafe fn store<T, const N: usize, const ALIGNED: bool>" in facade
    assert "load_masked, load_masked_zero" in library


def test_scalar_only_native_aliases_use_the_scalar_lane(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)

    plan = plan_rust_facade(result.emitted_profiles, static)

    assert {alias.type_tag for alias in plan.native_aliases} == {
        "f32",
        "f64",
        "si8",
        "si16",
        "si32",
        "si64",
        "ui8",
        "ui16",
        "ui32",
        "ui64",
    }
    assert all(
        tuple(
            (selection.profile_name, selection.lanes)
            for selection in alias.selections
        )
        == ((None, 1),)
        for alias in plan.native_aliases
    )


def test_facade_owner_equivalence_and_wrapper_audit(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "shift_left_wrapping", "store"],
        profiles=["scalar", "sse2", "avx2"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    static = plan_rust_static_selection(result.emitted_profiles)
    plan = plan_rust_facade(result.emitted_profiles, static)
    rendered = render_comprehensive_facade(plan)
    lowered_sources = {
        spec.source_primitive_name
        for profile in result.emitted_profiles
        for specs in profile.specializations("rust").values()
        for spec in specs
    } | {
        spec.source_primitive_name
        for _name, specs in static.fallback_module.primitive_specializations
        for spec in specs
    }
    lowered_names = {
        spec.primitive_name
        for profile in result.emitted_profiles
        for specs in profile.specializations("rust").values()
        for spec in specs
    } | {
        spec.primitive_name
        for _name, specs in static.fallback_module.primitive_specializations
        for spec in specs
    }

    assert plan.comprehensive_methods
    for method in plan.comprehensive_methods:
        assert method.source_primitive_name in lowered_sources
        assert all(delegate.primitive_name in lowered_names for delegate in method.delegates)
        assert f"fn {method.public_name}" in rendered.public_items

    delegate_lines = tuple(
        line
        for line in rendered.private_impls.splitlines()
        if "crate::tsl_" in line and "::<" in line
    )
    assert rendered.private_impls.count("fn call") == len(delegate_lines)
    assert rendered.public_items.count("pub fn ") + rendered.public_items.count(
        "pub unsafe fn "
    ) == rendered.public_items.count("::call")
    for forbidden in (
        "\n        for ",
        "\n        while ",
        "core::arch",
        "std::arch",
        "rem_euclid",
    ):
        assert forbidden not in rendered.private_impls
        assert forbidden not in rendered.public_items
