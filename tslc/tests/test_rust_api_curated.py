"""Curated Rust facade method, conversion, and operator tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rust_api_test_support import (
    _arithmetic_spec,
    _fallback_extension,
    _plan,
    _spec,
)
from tslc.backend.rust_api_model import RustFacadeReceiverKind
from tslc.backend.rust_api_planner import (
    RustFacadePlanningError,
    plan_rust_facade,
)
from tslc.backend.rust_static_selection import RustStaticVectorMapping
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
from tslc.catalog.semantics import (
    OperandBinding,
    OperandRole,
    PrimitiveOperation,
    PrimitiveSemanticContract,
)
from tslc.lower.lowerer import LoweredSpecialization, LoweredTypeParam
from tslc.lower.target_vectors import TargetVector
from tslc.render.rust_facade import (
    _bit_conversion_impls,
    _canonical_operator_impl,
    _conversion_pair_impls,
    _curated_method_impl,
    _operator_impls,
)


def test_sparse_numeric_conversion_pairs_do_not_expand_cartesian_products() -> None:
    conversion = PrimitiveConversionContract(
        ConversionKind.NUMERIC,
        LaneCountRelation.PRESERVE_LANE_COUNT,
        NumericConversionMode.SCALAR_AS,
    )
    spellings = {
        "si32": "i32",
        "ui32": "u32",
        "f32": "f32",
        "f64": "f64",
    }

    def conversion_spec(
        source_type_tag: str,
        target_type_tag: str,
        emitted_name: str,
    ) -> LoweredSpecialization:
        source_spelling = spellings[source_type_tag]
        target_spelling = spellings[target_type_tag]
        return replace(
            _spec(
                "sparse_convert",
                result_kind="v",
                param_names=("data",),
                param_kinds=("v",),
                operation=PrimitiveOperation.CONVERT,
                roles=((OperandRole.PRIMARY, 0, "v"),),
                conversion=conversion,
                emitted_name=emitted_name,
            ),
            type_tag=source_type_tag,
            base_type_spelling=source_spelling,
            register_spelling=f"array_type<{source_spelling}, LANES>",
            type_params=(
                LoweredTypeParam(
                    "ToVec",
                    base_type_binding=target_type_tag,
                    base_type_binding_spelling=target_spelling,
                ),
            ),
            result_vector_param="ToVec",
        )

    specs = (
        conversion_spec("si32", "f32", "convert_i32_to_f32"),
        conversion_spec("ui32", "f64", "convert_u32_to_f64"),
    )
    mappings = tuple(
        RustStaticVectorMapping(
            type_tag,
            spelling,
            lanes,
            lanes * (64 if type_tag == "f64" else 32),
            f"Simd<{spelling}, Generic<{lanes}>>",
            "u64",
            uses_sized_vector=True,
        )
        for type_tag, spelling in spellings.items()
        for lanes in (4, 8)
    )

    plan = plan_rust_facade(
        (),
        _plan(*specs, fallback_mappings=mappings),
    )
    permuted = plan_rust_facade(
        (),
        _plan(*reversed(specs), fallback_mappings=tuple(reversed(mappings))),
    )
    method = next(
        item
        for item in plan.comprehensive_methods
        if item.source_primitive_name == "sparse_convert"
    )
    cast = next(item for item in plan.curated_methods if item.public_name == "cast")
    exact_pairs = {
        (pair.source_type_tag, pair.target_type_tag): (
            pair.shape_keys,
            tuple(delegate.primitive_name for delegate in pair.delegates),
        )
        for pair in method.conversion_pairs
    }

    assert exact_pairs == {
        ("si32", "f32"): (
            (("si32", 4), ("si32", 8)),
            ("convert_i32_to_f32",),
        ),
        ("ui32", "f64"): (
            (("ui32", 4), ("ui32", 8)),
            ("convert_u32_to_f64",),
        ),
    }
    assert cast.conversion_pairs == method.conversion_pairs
    rendered = _conversion_pair_impls(plan)
    assert rendered.count("impl private::ConvertTo<") == 4
    assert "impl private::ConvertTo<f32, 4> for i32" in rendered
    assert "impl private::ConvertTo<f64, 8> for u32" in rendered
    assert "impl private::ConvertTo<f64, 4> for i32" not in rendered
    assert "impl private::ConvertTo<f32, 8> for u32" not in rendered
    assert permuted == plan
    assert _conversion_pair_impls(permuted) == rendered


def test_ambiguous_delegate_for_one_exact_conversion_pair_is_rejected() -> None:
    conversion = PrimitiveConversionContract(
        ConversionKind.NUMERIC,
        LaneCountRelation.PRESERVE_LANE_COUNT,
        NumericConversionMode.SCALAR_AS,
    )
    base = replace(
        _spec(
            "ambiguous_convert",
            result_kind="v",
            param_names=("data",),
            param_kinds=("v",),
            operation=PrimitiveOperation.CONVERT,
            roles=((OperandRole.PRIMARY, 0, "v"),),
            conversion=conversion,
            emitted_name="first_convert",
        ),
        type_params=(
            LoweredTypeParam(
                "ToVec",
                base_type_binding="f32",
                base_type_binding_spelling="f32",
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
            "f32",
            "f32",
            4,
            128,
            "Simd<f32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade(
            (),
            _plan(
                base,
                replace(base, primitive_name="second_convert"),
                fallback_mappings=mappings,
            ),
        )

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-DELEGATE-MISMATCH"
    }


def test_scalar_conversion_target_mapping_uses_the_target_element_width() -> None:
    scalar_extension = _fallback_extension("portable_scalar", sized=False)
    conversion = PrimitiveConversionContract(
        ConversionKind.NUMERIC,
        LaneCountRelation.PRESERVE_LANE_COUNT,
        NumericConversionMode.SCALAR_AS,
    )
    specialization = replace(
        _spec(
            "scalar_convert",
            result_kind="v",
            param_names=("data",),
            param_kinds=("v",),
            operation=PrimitiveOperation.CONVERT,
            roles=((OperandRole.PRIMARY, 0, "v"),),
            conversion=conversion,
        ),
        extension_name=scalar_extension.name,
        uses_sized_vector=False,
        lane_parameter=None,
        register_is_base=True,
        register_spelling="i32",
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
        RustStaticVectorMapping("si32", "i32", 1, 32, "i32", "u64"),
        RustStaticVectorMapping("f64", "f64", 1, 64, "f64", "u64"),
    )

    plan = plan_rust_facade(
        (),
        _plan(
            specialization,
            fallback_extensions=(scalar_extension,),
            fallback_mappings=mappings,
        ),
    )

    assert plan.comprehensive_methods[0].conversion_pairs[0].shape_keys == (
        ("si32", 1),
    )


def test_bit_conversion_directions_retain_their_exact_delegates() -> None:
    conversion = PrimitiveConversionContract(
        ConversionKind.BIT_PATTERN,
        LaneCountRelation.PRESERVE_REGISTER_WIDTH,
    )
    to_bits = replace(
        _spec(
            "reinterpret_sparse",
            result_kind="v",
            param_names=("data",),
            param_kinds=("v",),
            operation=PrimitiveOperation.REINTERPRET,
            roles=((OperandRole.PRIMARY, 0, "v"),),
            conversion=conversion,
            emitted_name="float_to_bits",
        ),
        type_tag="f32",
        base_type_spelling="f32",
        register_spelling="array_type<f32, LANES>",
        target=TargetVector("Vector", "Register", "generic", "ui32", "u32"),
    )
    from_bits = replace(
        to_bits,
        primitive_name="bits_to_float",
        type_tag="ui32",
        base_type_spelling="u32",
        register_spelling="array_type<u32, LANES>",
        target=TargetVector("Vector", "Register", "generic", "f32", "f32"),
    )
    mappings = (
        RustStaticVectorMapping(
            "f32",
            "f32",
            4,
            128,
            "Simd<f32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
        RustStaticVectorMapping(
            "ui32",
            "u32",
            4,
            128,
            "Simd<u32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
    )

    plan = plan_rust_facade(
        (),
        _plan(to_bits, from_bits, fallback_mappings=mappings),
    )
    planned = plan.bit_conversions[0]

    assert tuple(
        delegate.primitive_name for delegate in planned.to_bits.delegates
    ) == ("float_to_bits",)
    assert tuple(
        delegate.primitive_name for delegate in planned.from_bits.delegates
    ) == ("bits_to_float",)
    rendered = _bit_conversion_impls(plan)
    assert "float_to_bits::<" in rendered
    assert "bits_to_float::<" in rendered


def test_ambiguous_exact_bit_conversion_delegate_is_diagnosed() -> None:
    conversion = PrimitiveConversionContract(
        ConversionKind.BIT_PATTERN,
        LaneCountRelation.PRESERVE_REGISTER_WIDTH,
    )
    to_bits = replace(
        _spec(
            "ambiguous_reinterpret",
            result_kind="v",
            param_names=("data",),
            param_kinds=("v",),
            operation=PrimitiveOperation.REINTERPRET,
            roles=((OperandRole.PRIMARY, 0, "v"),),
            conversion=conversion,
            emitted_name="first_to_bits",
        ),
        type_tag="f32",
        base_type_spelling="f32",
        target=TargetVector("Vector", "Register", "generic", "ui32", "u32"),
    )
    second_to_bits = replace(to_bits, primitive_name="second_to_bits")
    from_bits = replace(
        to_bits,
        primitive_name="from_bits",
        type_tag="ui32",
        base_type_spelling="u32",
        target=TargetVector("Vector", "Register", "generic", "f32", "f32"),
    )
    mappings = (
        RustStaticVectorMapping(
            "f32",
            "f32",
            4,
            128,
            "Simd<f32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
        RustStaticVectorMapping(
            "ui32",
            "u32",
            4,
            128,
            "Simd<u32, Generic<4>>",
            "u64",
            uses_sized_vector=True,
        ),
    )

    with pytest.raises(RustFacadePlanningError) as error:
        plan_rust_facade(
            (),
            _plan(
                to_bits,
                second_to_bits,
                from_bits,
                fallback_mappings=mappings,
            ),
        )

    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "TSL-BACKEND-RUST-FACADE-DELEGATE-MISMATCH"
    }


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


def test_mask_operators_are_emitted_only_from_planned_trait_arms() -> None:
    binary = _spec(
        "future_mask_and",
        result_kind="m",
        param_names=("left", "right"),
        param_kinds=("m", "m"),
        operation=PrimitiveOperation.MASK_AND,
        roles=(
            (OperandRole.PRIMARY, 0, "m"),
            (OperandRole.SECONDARY, 1, "m"),
        ),
    )
    unary = _spec(
        "future_mask_not",
        result_kind="m",
        param_names=("value",),
        param_kinds=("m",),
        operation=PrimitiveOperation.MASK_NOT,
        roles=((OperandRole.PRIMARY, 0, "m"),),
    )

    plan = plan_rust_facade((), _plan(binary, unary))
    rendered = _operator_impls(plan)

    assert all(
        implementation.receiver_kind is RustFacadeReceiverKind.MASK
        for trait in plan.trait_implementations
        for implementation in trait.implementations
    )
    assert "impl core::ops::BitAnd<Mask<i32, 4>> for Mask<i32, 4>" in rendered
    assert "impl core::ops::Not for Mask<i32, 4>" in rendered


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
    rendered = _curated_method_impl(
        method,
        method.implementation_arms[0],
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
    rendered = _curated_method_impl(
        method,
        method.implementation_arms[0],
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
    implementation = trait.implementations[0]
    rendered = _canonical_operator_impl(
        implementation,
        implementation.canonical_arms[0],
    )

    assert trait.trait_path == trait_path
    assert trait.invocation.public_argument_index_by_source_index == (1, 0)
    assert "(rhs.value, self.value)" in rendered


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
