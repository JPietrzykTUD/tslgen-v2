"""Cross-record invariants for a finalized ordinary Rust facade plan."""

from __future__ import annotations

from tslc.backend.rust_api_arms import (
    RustCuratedMethodKind,
    RustFacadeBitConversionDirection,
    RustFacadeConversionImplementationArm,
)
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustCuratedTraitImplementation,
    RustFacadeBitConversion,
    RustFacadeConversionPair,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeReceiverKind,
    RustFacadeShape,
    RustFacadeTraitRhsKind,
    rust_facade_representations_can_coexist,
)
from tslc.catalog.semantics import PrimitiveOperation

_ShapeKey = tuple[str, int]
_ShapeIndex = dict[_ShapeKey, RustFacadeShape]
_ConversionRepresentationKey = tuple[
    str,
    int,
    str | None,
    str,
    str | None,
]


def validate_rust_facade_plan(plan: RustFacadePlan) -> None:
    """Validate relationships that span the plan's finalized record families."""

    shapes_by_key = _validate_surface_identity(plan)
    shape_key_set = set(shapes_by_key)
    _validate_comprehensive_methods(
        plan.comprehensive_methods,
        plan.shapes,
        shapes_by_key,
    )
    _validate_curated_methods(plan.curated_methods, shapes_by_key)
    _validate_bit_conversions(plan.bit_conversions, shapes_by_key)
    _validate_trait_implementations(plan.trait_implementations, shapes_by_key)
    _validate_core_and_equality(plan, shape_key_set)
    _validate_conversion_pairs(plan, shape_key_set)
    _validate_remaining_inventories(plan, shape_key_set)


def _validate_surface_identity(plan: RustFacadePlan) -> _ShapeIndex:
    method_keys = tuple(
        (item.receiver_kind, item.public_name)
        for item in plan.comprehensive_methods
    ) + tuple(
        (item.receiver_kind, item.public_name) for item in plan.curated_methods
    )
    if len(set(method_keys)) != len(method_keys):
        raise ValueError("Rust facade method names must be unique per receiver")
    shape_keys = tuple((item.type_tag, item.lanes) for item in plan.shapes)
    if len(set(shape_keys)) != len(shape_keys):
        raise ValueError("Rust facade logical shapes must be unique")
    return {(shape.type_tag, shape.lanes): shape for shape in plan.shapes}


def _validate_comprehensive_methods(
    methods: tuple[RustComprehensiveMethod, ...],
    shapes: tuple[RustFacadeShape, ...],
    shapes_by_key: _ShapeIndex,
) -> None:
    for method in methods:
        expected_public_shapes = (
            ()
            if method.receiver_kind is RustFacadeReceiverKind.FREE
            else tuple(
                shape
                for shape in shapes
                if (shape.type_tag, shape.lanes) in method.shape_keys
            )
        )
        if method.public_shapes != expected_public_shapes:
            raise ValueError(
                "Final Rust comprehensive methods require exact public shapes"
            )
        if not method.implementation_arms:
            raise ValueError(
                "Final Rust comprehensive methods require implementation arms"
            )
        if len(set(method.implementation_arms)) != len(method.implementation_arms):
            raise ValueError("Rust comprehensive implementation arms must be unique")
        if {
            (arm.source_shape.type_tag, arm.source_shape.lanes)
            for arm in method.implementation_arms
        } != set(method.shape_keys):
            raise ValueError(
                "Rust comprehensive implementation arms must cover every shape"
            )
        if method.type_parameters:
            expected_conversion_arms = frozenset(
                key
                for pair in method.conversion_pairs
                for key in _expected_conversion_representation_keys(
                    pair,
                    shapes_by_key,
                )
            )
            actual_conversion_arms = frozenset(
                (
                    arm.source_shape.type_tag,
                    arm.source_shape.lanes,
                    arm.source_representation.profile_name,
                    arm.target_shape.type_tag,
                    arm.target_representation.profile_name,
                )
                for arm in method.implementation_arms
                if arm.target_shape is not None
                and arm.target_representation is not None
            )
            if actual_conversion_arms != expected_conversion_arms:
                raise ValueError(
                    "Rust comprehensive conversion arms must cover every "
                    "compatible representation pair"
                )
        else:
            expected_representations = {
                (
                    shape.type_tag,
                    shape.lanes,
                    representation.profile_name,
                )
                for shape_key in method.shape_keys
                for shape in (shapes_by_key[shape_key],)
                for representation in shape.representations
            }
            actual_representations = {
                (
                    arm.source_shape.type_tag,
                    arm.source_shape.lanes,
                    arm.source_representation.profile_name,
                )
                for arm in method.implementation_arms
            }
            if actual_representations != expected_representations:
                raise ValueError(
                    "Rust comprehensive implementation arms must cover "
                    "every representation"
                )
        runtime_parameter_count = sum(
            parameter.placement is not RustFacadeParameterPlacement.CONST_GENERIC
            for parameter in method.parameters
        )
        if any(
            len(arm.call.arguments) != runtime_parameter_count
            for arm in method.implementation_arms
        ):
            raise ValueError(
                "Rust comprehensive lower-call arguments must match the "
                "runtime signature"
            )


def _validate_curated_methods(
    methods: tuple[RustCuratedMethod, ...],
    shapes_by_key: _ShapeIndex,
) -> None:
    for method in methods:
        if method.kind is None:
            raise ValueError("Final Rust curated methods require a typed item kind")
        is_numeric = method.kind is RustCuratedMethodKind.NUMERIC_CAST
        if is_numeric != bool(method.conversion_implementation_arms):
            raise ValueError(
                "Rust numeric curated methods require conversion arms only"
            )
        if is_numeric and method.implementation_arms:
            raise ValueError(
                "Rust numeric curated methods cannot have ordinary method arms"
            )
        if not is_numeric and not method.implementation_arms:
            raise ValueError("Final Rust curated methods require implementation arms")
        active_arms = (
            method.conversion_implementation_arms
            if is_numeric
            else method.implementation_arms
        )
        if len(set(active_arms)) != len(active_arms):
            raise ValueError("Rust curated implementation arms must be unique")
        active_shape_keys = (
            {
                (arm.source_shape.type_tag, arm.source_shape.lanes)
                for arm in method.conversion_implementation_arms
            }
            if is_numeric
            else {
                (arm.shape.type_tag, arm.shape.lanes)
                for arm in method.implementation_arms
            }
        )
        if active_shape_keys != set(method.shape_keys):
            raise ValueError(
                "Rust curated implementation arms must cover every shape"
            )
        if is_numeric:
            expected_arms = frozenset(
                key
                for pair in method.conversion_pairs
                for key in _expected_conversion_representation_keys(
                    pair,
                    shapes_by_key,
                )
            )
            actual_arms = frozenset(
                _conversion_arm_representation_key(arm)
                for arm in method.conversion_implementation_arms
            )
            if actual_arms != expected_arms:
                raise ValueError(
                    "Rust curated conversion arms must cover every "
                    "compatible representation pair"
                )
        else:
            expected_representations = {
                (
                    shape.type_tag,
                    shape.lanes,
                    representation.profile_name,
                )
                for shape_key in method.shape_keys
                for shape in (shapes_by_key[shape_key],)
                for representation in shape.representations
            }
            actual_representations = {
                (
                    arm.shape.type_tag,
                    arm.shape.lanes,
                    arm.representation.profile_name,
                )
                for arm in method.implementation_arms
            }
            if actual_representations != expected_representations:
                raise ValueError(
                    "Rust curated implementation arms must cover every "
                    "representation"
                )
        if any(
            len(arm.call.arguments)
            != len(method.invocation.public_argument_index_by_source_index)
            for arm in active_arms
        ):
            raise ValueError(
                "Rust curated lower-call arguments must match its invocation"
            )


def _validate_bit_conversions(
    conversions: tuple[RustFacadeBitConversion, ...],
    shapes_by_key: _ShapeIndex,
) -> None:
    for conversion in conversions:
        if not conversion.implementation_arms:
            raise ValueError("Final Rust bit conversions require implementation arms")
        if len(set(conversion.implementation_arms)) != len(
            conversion.implementation_arms
        ):
            raise ValueError(
                "Rust bit-conversion implementation arms must be unique"
            )
        if any(
            len(arm.conversion.call.arguments)
            != len(conversion.invocation.public_argument_index_by_source_index)
            for arm in conversion.implementation_arms
        ):
            raise ValueError(
                "Rust bit-conversion lower-call arguments must match its invocation"
            )
        expected_arms = {
            (
                RustFacadeBitConversionDirection.TO_BITS,
                key,
            )
            for key in _expected_conversion_representation_keys(
                conversion.to_bits,
                shapes_by_key,
            )
        } | {
            (
                RustFacadeBitConversionDirection.FROM_BITS,
                key,
            )
            for key in _expected_conversion_representation_keys(
                conversion.from_bits,
                shapes_by_key,
            )
        }
        actual_arms = {
            (
                arm.direction,
                _conversion_arm_representation_key(arm.conversion),
            )
            for arm in conversion.implementation_arms
        }
        if actual_arms != expected_arms:
            raise ValueError(
                "Rust bit-conversion arms must cover every compatible "
                "representation pair in both directions"
            )


def _validate_trait_implementations(
    traits: tuple[RustCuratedTraitImplementation, ...],
    shapes_by_key: _ShapeIndex,
) -> None:
    for trait in traits:
        is_generic_mask = trait.receiver_kind is RustFacadeReceiverKind.MASK
        if is_generic_mask != (trait.generic_mask_implementation is not None):
            raise ValueError(
                "Final Rust mask traits require one generic implementation"
            )
        if is_generic_mask and trait.implementations:
            raise ValueError(
                "Final Rust mask traits cannot have concrete implementations"
            )
        if (
            is_generic_mask
            and trait.generic_mask_implementation is not None
            and (
                trait.generic_mask_implementation.trait_path != trait.trait_path
                or trait.generic_mask_implementation.method_name != trait.method_name
                or trait.generic_mask_implementation.operation != trait.operation
                or (trait.generic_mask_implementation.rhs_type is None)
                != (trait.rhs_kind is None)
            )
        ):
            raise ValueError(
                "Rust generic mask implementation must match its trait"
            )
        if not is_generic_mask and not trait.implementations:
            raise ValueError(
                "Final Rust vector traits require operator implementations"
            )
        if len(set(trait.implementations)) != len(trait.implementations):
            raise ValueError("Rust operator implementations must be unique")
        if not is_generic_mask and {
            (implementation.shape.type_tag, implementation.shape.lanes)
            for implementation in trait.implementations
        } != set(trait.shape_keys):
            raise ValueError(
                "Rust operator implementations must cover every trait shape"
            )
        expected_operator_keys = {
            (
                shape.type_tag,
                shape.lanes,
                rhs_type,
            )
            for shape_key in trait.shape_keys
            for shape in (shapes_by_key[shape_key],)
            for rhs_type in (
                trait.rhs_type_spellings
                if trait.rhs_kind is RustFacadeTraitRhsKind.SCALAR
                else (
                    (
                        "Simd"
                        if trait.receiver_kind is RustFacadeReceiverKind.VECTOR
                        else "Mask"
                    )
                    + f"<{shape.base_spelling}, {shape.lanes}>",
                )
                if trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
                else (None,)
            )
        }
        actual_operator_keys = {
            (
                implementation.shape.type_tag,
                implementation.shape.lanes,
                implementation.rhs_type,
            )
            for implementation in trait.implementations
        }
        if not is_generic_mask and actual_operator_keys != expected_operator_keys:
            raise ValueError(
                "Rust operator implementations must cover every finalized "
                "shape and RHS spelling"
            )
        if any(
            len(arm.call.arguments)
            != len(trait.invocation.public_argument_index_by_source_index)
            for implementation in trait.implementations
            for arm in implementation.canonical_arms
        ):
            raise ValueError(
                "Rust operator lower-call arguments must match its invocation"
            )


def _validate_core_and_equality(
    plan: RustFacadePlan,
    shape_key_set: set[_ShapeKey],
) -> None:
    core_arm_keys = tuple(
        (
            arm.shape.type_tag,
            arm.shape.lanes,
            arm.representation.profile_name,
        )
        for arm in plan.core_implementation_arms
    )
    if len(set(core_arm_keys)) != len(core_arm_keys):
        raise ValueError("Rust facade core implementation arms must be unique")
    equality_keys = tuple(
        (implementation.shape.type_tag, implementation.shape.lanes)
        for implementation in plan.equality_implementations
    )
    if len(set(equality_keys)) != len(equality_keys):
        raise ValueError("Rust facade equality implementations must be unique")
    if any(key not in shape_key_set for key in equality_keys):
        raise ValueError(
            "Rust facade equality implementations require admitted shapes"
        )
    expected_equality = {
        (shape_key, method.public_name)
        for method in plan.curated_methods
        if method.operation is PrimitiveOperation.COMPARE_EQUAL
        for shape_key in method.shape_keys
    }
    actual_equality = {
        (
            (implementation.shape.type_tag, implementation.shape.lanes),
            implementation.method_name,
        )
        for implementation in plan.equality_implementations
    }
    if actual_equality != expected_equality:
        raise ValueError(
            "Rust facade equality implementations must cover every "
            "planned equality shape"
        )


def _validate_conversion_pairs(
    plan: RustFacadePlan,
    shape_key_set: set[_ShapeKey],
) -> None:
    method_pair_keys = tuple(
        tuple(
            (pair.source_type_tag, pair.target_type_tag)
            for pair in method.conversion_pairs
        )
        for method in plan.comprehensive_methods
    ) + tuple(
        tuple(
            (pair.source_type_tag, pair.target_type_tag)
            for pair in method.conversion_pairs
        )
        for method in plan.curated_methods
    )
    for pair_keys in method_pair_keys:
        if len(set(pair_keys)) != len(pair_keys):
            raise ValueError(
                "Rust facade conversion pairs must be unique per method"
            )
    conversion_pairs = tuple(
        pair
        for method in plan.comprehensive_methods
        for pair in method.conversion_pairs
    ) + tuple(
        pair
        for method in plan.curated_methods
        for pair in method.conversion_pairs
    ) + tuple(
        pair
        for conversion in plan.bit_conversions
        for pair in (conversion.to_bits, conversion.from_bits)
    )
    if any(not pair.shape_keys for pair in conversion_pairs):
        raise ValueError(
            "Final Rust facade conversion pairs require admitted logical shapes"
        )
    if any(
        source_key not in shape_key_set
        or (pair.target_type_tag, source_key[1]) not in shape_key_set
        for pair in conversion_pairs
        for source_key in pair.shape_keys
    ):
        raise ValueError(
            "Rust facade conversion pairs must reference admitted source and target shapes"
        )


def _validate_remaining_inventories(
    plan: RustFacadePlan,
    shape_key_set: set[_ShapeKey],
) -> None:
    operation_keys = tuple(
        (
            item.operation,
            item.source_primitive_name,
            item.result_kind,
            item.parameter_kinds,
            item.operand_roles,
            item.axis_names,
            item.memory_access,
            item.memory_addressing,
            item.memory_alignment_axis_name,
            item.memory_alignment_modes,
            item.mask_policy,
            item.overload,
        )
        for item in plan.operation_bindings
    )
    if len(set(operation_keys)) != len(operation_keys):
        raise ValueError("Rust facade operation bindings must be unique")
    core_delegate_keys = tuple(
        (item.role, item.type_tag, item.lanes, item.profile_name)
        for item in plan.core_delegates
    )
    if len(set(core_delegate_keys)) != len(core_delegate_keys):
        raise ValueError("Rust facade core delegates must be unique")
    if any(
        (alias.type_tag, selection.lanes) not in shape_key_set
        for alias in plan.native_aliases
        for selection in alias.selections
    ):
        raise ValueError("Rust native aliases must select an admitted logical shape")
    native_type_tags = tuple(item.type_tag for item in plan.native_aliases)
    if len(set(native_type_tags)) != len(native_type_tags):
        raise ValueError("Rust native aliases must be unique by element type")


def _expected_conversion_representation_keys(
    pair: RustFacadeConversionPair,
    shapes: _ShapeIndex,
) -> frozenset[_ConversionRepresentationKey]:
    return frozenset(
        (
            source_shape.type_tag,
            source_shape.lanes,
            source_representation.profile_name,
            target_shape.type_tag,
            target_representation.profile_name,
        )
        for source_key in pair.shape_keys
        for source_shape in (shapes[source_key],)
        for target_shape in (shapes[(pair.target_type_tag, source_shape.lanes)],)
        for source_representation in source_shape.representations
        for target_representation in target_shape.representations
        if rust_facade_representations_can_coexist(
            source_representation,
            target_representation,
        )
    )


def _conversion_arm_representation_key(
    arm: RustFacadeConversionImplementationArm,
) -> _ConversionRepresentationKey:
    return (
        arm.source_shape.type_tag,
        arm.source_shape.lanes,
        arm.source_representation.profile_name,
        arm.target_shape.type_tag,
        arm.target_representation.profile_name,
    )


__all__ = ("validate_rust_facade_plan",)
