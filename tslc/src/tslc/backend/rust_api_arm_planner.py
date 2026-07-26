"""Finalize exact implementation arms for the ordinary Rust facade."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.rust_api_arms import (
    RustComprehensivePrivateImplementationArm,
    RustCuratedMethodImplementationArm,
    RustCuratedMethodKind,
    RustFacadeArmSelection,
    RustFacadeAssignmentOperatorArm,
    RustFacadeBitConversionDirection,
    RustFacadeBitConversionImplementationArm,
    RustFacadeCanonicalOperatorArm,
    RustFacadeConversionImplementationArm,
    RustFacadeCoreImplementationArm,
    RustFacadeEqualityImplementation,
    RustFacadeForwardingOperatorArm,
    RustFacadeLowerCall,
    RustFacadeNamedCall,
    RustFacadeOperatorImplementation,
)
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustCuratedTraitImplementation,
    RustFacadeBitConversion,
    RustFacadeConstParameterSource,
    RustFacadeConversionPair,
    RustFacadeCoreDelegate,
    RustFacadeDelegate,
    RustFacadeInvocation,
    RustFacadeParameterPlacement,
    RustFacadeReceiverKind,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustFacadeTraitRhsKind,
    rust_facade_representations_can_coexist,
)
from tslc.backend.rust_api_types import RUST_FACADE_SIGNATURE_TYPES
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.arithmetic import ArithmeticOperation
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.semantics import PrimitiveOperation


def finalize_comprehensive_implementation_arms(
    methods: list[RustComprehensiveMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustComprehensiveMethod]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    finalized: list[RustComprehensiveMethod] = []
    for method in methods:
        source_shapes = tuple(by_key[key] for key in method.shape_keys)
        public_shapes = (
            ()
            if method.receiver_kind is RustFacadeReceiverKind.FREE
            else source_shapes
        )
        arms: list[RustComprehensivePrivateImplementationArm] = []
        if not method.type_parameters:
            for source_shape in source_shapes:
                for source_representation in source_shape.representations:
                    delegate = _surface_delegate(
                        method.delegates,
                        source_shape,
                        source_representation,
                        source_representation.profile_name,
                    )
                    arms.extend(
                        _comprehensive_private_variants(
                            method,
                            source_shape,
                            source_representation,
                            delegate,
                        )
                    )
        else:
            for pair in method.conversion_pairs:
                for source_key in pair.shape_keys:
                    source_shape = by_key[source_key]
                    target_shape = by_key[
                        (pair.target_type_tag, source_shape.lanes)
                    ]
                    for source_representation in source_shape.representations:
                        for target_representation in target_shape.representations:
                            if not rust_facade_representations_can_coexist(
                                source_representation,
                                target_representation,
                            ):
                                continue
                            active_profile = (
                                source_representation.profile_name
                                if source_representation.profile_name is not None
                                else target_representation.profile_name
                            )
                            delegate = _surface_delegate(
                                pair.delegates,
                                source_shape,
                                source_representation,
                                active_profile,
                            )
                            arms.extend(
                                _comprehensive_private_variants(
                                    method,
                                    source_shape,
                                    source_representation,
                                    delegate,
                                    target_shape=target_shape,
                                    target_representation=target_representation,
                                )
                            )
        finalized.append(
            replace(
                method,
                public_shapes=public_shapes,
                implementation_arms=tuple(arms),
            )
        )
    return finalized


def _comprehensive_private_variants(
    method: RustComprehensiveMethod,
    source_shape: RustFacadeShape,
    source_representation: RustFacadeRepresentation,
    delegate: RustFacadeDelegate,
    *,
    target_shape: RustFacadeShape | None = None,
    target_representation: RustFacadeRepresentation | None = None,
) -> tuple[RustComprehensivePrivateImplementationArm, ...]:
    identity_parameters = tuple(
        parameter
        for parameter in method.const_parameters
        if parameter.source is RustFacadeConstParameterSource.ATTRIBUTE
    )
    combinations = _delegate_attribute_combinations(
        delegate, source_shape, source_representation
    )
    if not identity_parameters:
        combinations = ((),)
    admitted = tuple(
        combination
        for combination in combinations
        if tuple(name for name, _value in combination)
        == tuple(parameter.source_name for parameter in identity_parameters)
    )
    if not admitted:
        raise ValueError(
            "Rust comprehensive implementation has no exact attribute arm for "
            f"{source_shape.type_tag}x{source_shape.lanes}"
        )
    method_consts = tuple(
        parameter
        for parameter in method.const_parameters
        if parameter.source is not RustFacadeConstParameterSource.ATTRIBUTE
    )
    lower_arguments = tuple(
        RUST_FACADE_SIGNATURE_TYPES.adapt_lower_argument(
            parameter.kind,
            _identifier(parameter.public_name),
            source_representation.mapping,
        )
        for parameter in sorted(
            (
                parameter
                for parameter in method.parameters
                if parameter.placement
                is not RustFacadeParameterPlacement.CONST_GENERIC
            ),
            key=lambda item: item.source_index,
        )
    )
    extension_name = _surface_delegate_owner(
        delegate, source_shape, source_representation
    )
    selection = _arm_selection(
        source_representation,
        *((target_representation,) if target_representation is not None else ()),
    )
    return tuple(
        RustComprehensivePrivateImplementationArm(
            source_shape=source_shape,
            source_representation=source_representation,
            target_shape=target_shape,
            target_representation=target_representation,
            selection=selection,
            attribute_values=combination,
            call=RustFacadeLowerCall(
                delegate=delegate,
                extension_name=extension_name,
                generic_arguments=(
                    source_representation.vector_descriptor,
                    *(
                        (target_representation.vector_descriptor,)
                        if target_representation is not None
                        else ()
                    ),
                    *(value for _name, value in combination),
                    *(parameter.public_name for parameter in method_consts),
                    *("_" for _ in delegate.overload_parameter_positions),
                ),
                arguments=lower_arguments,
                result_suffix=RUST_FACADE_SIGNATURE_TYPES.lower_result_suffix(
                    method.result_kind, source_representation.mapping
                ),
            ),
        )
        for combination in admitted
    )


def _delegate_attribute_combinations(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    extension_name = _surface_delegate_owner(delegate, shape, representation)
    matches = tuple(
        vector
        for vector in delegate.vectors
        if vector.extension_name == extension_name
        and vector.type_tag == shape.type_tag
    )
    if len(matches) != 1:
        raise ValueError(
            "Rust facade delegate has no unique vector attribute inventory for "
            f"{shape.type_tag}x{shape.lanes}"
        )
    return matches[0].attribute_combinations or ((),)


def finalize_curated_implementation_arms(
    methods: list[RustCuratedMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustCuratedMethod]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    finalized: list[RustCuratedMethod] = []
    for method in methods:
        kind = _curated_method_kind(method.operation)
        ordinary: list[RustCuratedMethodImplementationArm] = []
        conversions: tuple[RustFacadeConversionImplementationArm, ...] = ()
        if kind is RustCuratedMethodKind.NUMERIC_CAST:
            conversions = tuple(
                arm
                for pair in method.conversion_pairs
                for arm in _conversion_implementation_arms(
                    pair,
                    method.invocation,
                    by_key,
                    public_arguments=("value",),
                )
            )
        else:
            arguments = (
                ("self.value", "true_values.value", "false_values.value")
                if kind is RustCuratedMethodKind.SELECTION
                else ("self.value", "other.value")
            )
            for shape_key in method.shape_keys:
                shape = by_key[shape_key]
                for representation in shape.representations:
                    delegate = _surface_delegate(
                        method.delegates,
                        shape,
                        representation,
                        representation.profile_name,
                    )
                    ordinary.append(
                        RustCuratedMethodImplementationArm(
                            shape=shape,
                            representation=representation,
                            selection=_arm_selection(representation),
                            call=_surface_lower_call(
                                delegate,
                                shape,
                                representation,
                                generic_arguments=(
                                    representation.vector_descriptor,
                                    *(
                                        "_"
                                        for _ in delegate.overload_parameter_positions
                                    ),
                                ),
                                arguments=_invocation_arguments(
                                    method.invocation, arguments
                                ),
                            ),
                        )
                    )
        finalized.append(
            replace(
                method,
                kind=kind,
                implementation_arms=tuple(ordinary),
                conversion_implementation_arms=conversions,
            )
        )
    return finalized


def _curated_method_kind(
    operation: PrimitiveOperation,
) -> RustCuratedMethodKind:
    if operation is PrimitiveOperation.CONVERT:
        return RustCuratedMethodKind.NUMERIC_CAST
    if operation is PrimitiveOperation.SELECT:
        return RustCuratedMethodKind.SELECTION
    if operation in _COMPARISON_OPERATIONS:
        return RustCuratedMethodKind.COMPARISON
    raise ValueError(
        f"Rust curated method has unsupported operation {operation.value!r}"
    )


def _conversion_implementation_arms(
    pair: RustFacadeConversionPair,
    invocation: RustFacadeInvocation,
    shapes: dict[tuple[str, int], RustFacadeShape],
    *,
    public_arguments: tuple[str, ...],
) -> tuple[RustFacadeConversionImplementationArm, ...]:
    arms: list[RustFacadeConversionImplementationArm] = []
    for source_key in pair.shape_keys:
        source_shape = shapes[source_key]
        target_shape = shapes[(pair.target_type_tag, source_shape.lanes)]
        for source_representation in source_shape.representations:
            for target_representation in target_shape.representations:
                if not rust_facade_representations_can_coexist(
                    source_representation, target_representation
                ):
                    continue
                active_profile = (
                    source_representation.profile_name
                    if source_representation.profile_name is not None
                    else target_representation.profile_name
                )
                delegate = _surface_delegate(
                    pair.delegates,
                    source_shape,
                    source_representation,
                    active_profile,
                )
                arms.append(
                    RustFacadeConversionImplementationArm(
                        source_shape=source_shape,
                        target_shape=target_shape,
                        source_representation=source_representation,
                        target_representation=target_representation,
                        selection=_arm_selection(
                            source_representation, target_representation
                        ),
                        call=_surface_lower_call(
                            delegate,
                            source_shape,
                            source_representation,
                            generic_arguments=(
                                source_representation.vector_descriptor,
                                target_representation.vector_descriptor,
                                *(
                                    "_"
                                    for _ in delegate.overload_parameter_positions
                                ),
                            ),
                            arguments=_invocation_arguments(
                                invocation, public_arguments
                            ),
                        ),
                    )
                )
    return tuple(arms)


def finalize_bit_conversion_implementation_arms(
    conversions: tuple[RustFacadeBitConversion, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustFacadeBitConversion, ...]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    finalized: list[RustFacadeBitConversion] = []
    for conversion in conversions:
        to_bits = _conversion_implementation_arms(
            conversion.to_bits,
            conversion.invocation,
            by_key,
            public_arguments=("self.value",),
        )
        from_bits = _conversion_implementation_arms(
            conversion.from_bits,
            conversion.invocation,
            by_key,
            public_arguments=("bits.value",),
        )
        arms = (
            *(
                RustFacadeBitConversionImplementationArm(
                    RustFacadeBitConversionDirection.TO_BITS,
                    arm.source_shape,
                    arm.target_shape,
                    arm,
                )
                for arm in to_bits
            ),
            *(
                RustFacadeBitConversionImplementationArm(
                    RustFacadeBitConversionDirection.FROM_BITS,
                    arm.target_shape,
                    arm.source_shape,
                    arm,
                )
                for arm in from_bits
            ),
        )
        finalized.append(replace(conversion, implementation_arms=arms))
    return tuple(finalized)


def finalize_operator_implementations(
    traits: list[RustCuratedTraitImplementation],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustCuratedTraitImplementation]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    finalized: list[RustCuratedTraitImplementation] = []
    for trait in traits:
        implementations: list[RustFacadeOperatorImplementation] = []
        for shape_key in trait.shape_keys:
            shape = by_key[shape_key]
            value_type = _facade_value_type(trait.receiver_kind, shape)
            if trait.rhs_kind is RustFacadeTraitRhsKind.SCALAR:
                rhs_types: tuple[str | None, ...] = trait.rhs_type_spellings
            elif trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE:
                rhs_types = (value_type,)
            else:
                rhs_types = (None,)
            for rhs_type in rhs_types:
                canonical = tuple(
                    _canonical_operator_arm(
                        trait, shape, representation, rhs_type
                    )
                    for representation in shape.representations
                )
                forwarding, assignment = _operator_forwarding_arms(
                    trait, value_type, rhs_type
                )
                implementations.append(
                    RustFacadeOperatorImplementation(
                        receiver_kind=trait.receiver_kind,
                        shape=shape,
                        trait_path=trait.trait_path,
                        method_name=trait.method_name,
                        rhs_type=rhs_type,
                        track_caller=trait.operation
                        in {
                            ArithmeticOperation.DIVISION,
                            ArithmeticOperation.REMAINDER,
                        },
                        canonical_arms=canonical,
                        forwarding_arms=forwarding,
                        assignment_arms=assignment,
                    )
                )
        finalized.append(
            replace(trait, implementations=tuple(implementations))
        )
    return finalized


def _canonical_operator_arm(
    trait: RustCuratedTraitImplementation,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    rhs_type: str | None,
) -> RustFacadeCanonicalOperatorArm:
    delegate = _surface_delegate(
        trait.delegates,
        shape,
        representation,
        representation.profile_name,
    )
    arguments = (
        ("self.value",)
        if rhs_type is None
        else (
            "self.value",
            (
                "rhs"
                if trait.rhs_kind is RustFacadeTraitRhsKind.SCALAR
                else "rhs.value"
            ),
        )
    )
    return RustFacadeCanonicalOperatorArm(
        representation=representation,
        selection=_arm_selection(representation),
        call=_surface_lower_call(
            delegate,
            shape,
            representation,
            generic_arguments=(
                representation.vector_descriptor,
                *("_" for _ in delegate.overload_parameter_positions),
            ),
            arguments=_invocation_arguments(trait.invocation, arguments),
        ),
    )


def _operator_forwarding_arms(
    trait: RustCuratedTraitImplementation,
    value_type: str,
    rhs_type: str | None,
) -> tuple[
    tuple[RustFacadeForwardingOperatorArm, ...],
    tuple[RustFacadeAssignmentOperatorArm, ...],
]:
    if rhs_type is None:
        return (
            (
                RustFacadeForwardingOperatorArm(
                    self_type=f"&{value_type}",
                    rhs_type=None,
                    owned_rhs_type=None,
                    self_value="*self",
                    rhs_value=None,
                ),
            ),
            (),
        )
    owned_rhs = (
        value_type
        if trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
        else rhs_type
    )
    borrowed_rhs = f"&{rhs_type}"
    forwarding = (
        RustFacadeForwardingOperatorArm(
            f"&{value_type}", rhs_type, owned_rhs, "*self", "rhs"
        ),
        RustFacadeForwardingOperatorArm(
            value_type, borrowed_rhs, owned_rhs, "self", "*rhs"
        ),
        RustFacadeForwardingOperatorArm(
            f"&{value_type}", borrowed_rhs, owned_rhs, "*self", "*rhs"
        ),
    )
    assignment = _ASSIGNMENT_TRAITS.get(trait.trait_path)
    if assignment is None:
        return forwarding, ()
    assignment_trait, assignment_method = assignment
    return (
        forwarding,
        (
            RustFacadeAssignmentOperatorArm(
                assignment_trait,
                assignment_method,
                rhs_type,
                owned_rhs,
                "rhs",
            ),
            RustFacadeAssignmentOperatorArm(
                assignment_trait,
                assignment_method,
                borrowed_rhs,
                owned_rhs,
                "*rhs",
            ),
        ),
    )


def equality_implementations(
    methods: list[RustCuratedMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustFacadeEqualityImplementation, ...]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    implementations = {
        shape_key: RustFacadeEqualityImplementation(
            shape=by_key[shape_key],
            method_name=method.public_name,
            implements_eq=not SCALAR_TYPE_INFOS[shape_key[0]].floating,
        )
        for method in methods
        if method.operation is PrimitiveOperation.COMPARE_EQUAL
        for shape_key in method.shape_keys
    }
    return tuple(implementations[key] for key in sorted(implementations))


def core_implementation_arms(
    delegates: tuple[RustFacadeCoreDelegate, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustFacadeCoreImplementationArm, ...]:
    if not delegates:
        return ()
    by_key = {
        (
            delegate.role,
            delegate.type_tag,
            delegate.lanes,
            delegate.profile_name,
        ): delegate
        for delegate in delegates
    }
    required_roles = tuple(
        dict.fromkeys(form[1] for form in _CORE_CALL_FORMS)
    )
    arms: list[RustFacadeCoreImplementationArm] = []
    for shape in shapes:
        for representation in shape.representations:
            role_delegates = {
                role: by_key.get(
                    (
                        role,
                        shape.type_tag,
                        shape.lanes,
                        representation.profile_name,
                    )
                )
                for role in required_roles
            }
            if any(item is None for item in role_delegates.values()):
                continue
            calls = tuple(
                _core_named_call(
                    emitted_role,
                    role_delegates[delegate_role],
                    representation,
                    arguments,
                    generics,
                    argument_kind,
                    result_kind,
                )
                for (
                    emitted_role,
                    delegate_role,
                    arguments,
                    generics,
                    argument_kind,
                    result_kind,
                ) in _CORE_CALL_FORMS
            )
            arms.append(
                RustFacadeCoreImplementationArm(
                    shape,
                    representation,
                    _arm_selection(representation),
                    calls,
                )
            )
    return tuple(arms)


def _core_named_call(
    emitted_role: str,
    delegate: RustFacadeCoreDelegate | None,
    representation: RustFacadeRepresentation,
    arguments: tuple[str, ...],
    extra_generics: tuple[str, ...],
    argument_kind: str | None,
    result_kind: str | None,
) -> RustFacadeNamedCall:
    assert delegate is not None
    if argument_kind is not None:
        if len(arguments) != 1:
            raise ValueError(
                "Rust facade core argument adaptation requires one argument"
            )
        arguments = (
            RUST_FACADE_SIGNATURE_TYPES.adapt_lower_argument(
                argument_kind, arguments[0], representation.mapping
            ),
        )
    return RustFacadeNamedCall(
        emitted_role,
        RustFacadeLowerCall(
            delegate=delegate,
            extension_name=delegate.extension_name,
            generic_arguments=(
                representation.vector_descriptor,
                *extra_generics,
            ),
            arguments=_invocation_arguments(delegate.invocation, arguments),
            result_suffix=(
                RUST_FACADE_SIGNATURE_TYPES.lower_result_suffix(
                    result_kind, representation.mapping
                )
                if result_kind is not None
                else ""
            ),
        ),
    )


def _surface_lower_call(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    *,
    generic_arguments: tuple[str, ...],
    arguments: tuple[str, ...],
) -> RustFacadeLowerCall:
    return RustFacadeLowerCall(
        delegate,
        _surface_delegate_owner(delegate, shape, representation),
        generic_arguments,
        arguments,
    )


def _arm_selection(
    *representations: RustFacadeRepresentation,
) -> RustFacadeArmSelection:
    return RustFacadeArmSelection(tuple(dict.fromkeys(representations)))


def _surface_delegate(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    profile_name: str | None,
) -> RustFacadeDelegate:
    matches = tuple(
        delegate
        for delegate in delegates
        if delegate.profile_name == profile_name
        and _delegate_has_owner(delegate, shape, representation)
    )
    if len(matches) != 1:
        raise ValueError(
            f"Rust facade has {len(matches)} delegates for "
            f"{shape.type_tag}x{shape.lanes} under "
            f"{profile_name or 'fallback'}"
        )
    return matches[0]


def _delegate_has_owner(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> bool:
    return (
        sum(
            owner.type_tag == shape.type_tag
            and owner.lanes == shape.lanes
            and owner.representation_profile_name == representation.profile_name
            for owner in delegate.owners
        )
        == 1
    )


def _surface_delegate_owner(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> str:
    matches = tuple(
        owner.extension_name
        for owner in delegate.owners
        if owner.type_tag == shape.type_tag
        and owner.lanes == shape.lanes
        and owner.representation_profile_name == representation.profile_name
    )
    if len(matches) != 1:
        raise ValueError(
            f"Rust facade delegate {delegate.primitive_name!r} has "
            f"{len(matches)} implementation owners for "
            f"{shape.type_tag}x{shape.lanes} under "
            f"{representation.profile_name or 'fallback'}"
        )
    return matches[0]


def _invocation_arguments(
    invocation: RustFacadeInvocation,
    public_arguments: tuple[str, ...],
) -> tuple[str, ...]:
    if len(public_arguments) != len(
        invocation.public_argument_index_by_source_index
    ):
        raise ValueError(
            "Rust facade planning received an incomplete public argument inventory"
        )
    return tuple(
        public_arguments[index]
        for index in invocation.public_argument_index_by_source_index
    )


def _identifier(name: str) -> str:
    if name in {"self", "Self", "crate", "super"}:
        return f"{name.lower()}_value"
    return rust_raw_identifier(name)


def _facade_value_type(
    receiver_kind: RustFacadeReceiverKind,
    shape: RustFacadeShape,
) -> str:
    owner = "Simd" if receiver_kind is RustFacadeReceiverKind.VECTOR else "Mask"
    return f"{owner}<{shape.base_spelling}, {shape.lanes}>"


_COMPARISON_OPERATIONS = frozenset(
    {
        PrimitiveOperation.COMPARE_EQUAL,
        PrimitiveOperation.COMPARE_NOT_EQUAL,
        PrimitiveOperation.COMPARE_LESS,
        PrimitiveOperation.COMPARE_LESS_EQUAL,
        PrimitiveOperation.COMPARE_GREATER,
        PrimitiveOperation.COMPARE_GREATER_EQUAL,
    }
)
_ASSIGNMENT_TRAITS = {
    "core::ops::Add": ("core::ops::AddAssign", "add_assign"),
    "core::ops::Sub": ("core::ops::SubAssign", "sub_assign"),
    "core::ops::Mul": ("core::ops::MulAssign", "mul_assign"),
    "core::ops::Div": ("core::ops::DivAssign", "div_assign"),
    "core::ops::Rem": ("core::ops::RemAssign", "rem_assign"),
    "core::ops::BitAnd": ("core::ops::BitAndAssign", "bitand_assign"),
    "core::ops::BitOr": ("core::ops::BitOrAssign", "bitor_assign"),
    "core::ops::BitXor": ("core::ops::BitXorAssign", "bitxor_assign"),
    "core::ops::Shl": ("core::ops::ShlAssign", "shl_assign"),
    "core::ops::Shr": ("core::ops::ShrAssign", "shr_assign"),
}
_CORE_CALL_FORMS = (
    ("vector_splat", "vector_splat", ("value",), (), None, None),
    ("vector_from_array", "vector_from_array", ("&values",), (), None, None),
    ("vector_to_array", "vector_to_array", ("value",), (), None, None),
    ("vector_zero", "vector_zero", (), (), None, None),
    ("extract_lane", "extract_lane", ("value", "index"), (), None, None),
    (
        "insert_lane",
        "insert_lane",
        ("value", "index", "lane"),
        (),
        None,
        None,
    ),
    ("load", "load", ("source",), ("false",), None, None),
    (
        "store",
        "store",
        ("destination", "value"),
        ("false", "_"),
        None,
        None,
    ),
    ("mask_false", "mask_false", (), (), None, None),
    ("mask_true", "mask_true", (), (), None, None),
    (
        "mask_from_bitmask",
        "mask_from_integral",
        ("bits",),
        (),
        "im",
        None,
    ),
    (
        "mask_to_bitmask",
        "mask_to_integral",
        ("value",),
        (),
        None,
        "im",
    ),
    (
        "mask_to_integral_for_test",
        "mask_to_integral",
        ("value",),
        (),
        None,
        None,
    ),
    (
        "integral_mask_test",
        "integral_mask_test",
        ("bits", "index"),
        (),
        None,
        None,
    ),
    (
        "mask_set_lane",
        "mask_set_lane",
        ("value", "index", "if active { 1 } else { 0 }"),
        (),
        None,
        None,
    ),
    (
        "mask_population_count",
        "mask_population_count",
        ("value",),
        (),
        None,
        None,
    ),
    ("mask_and", "mask_and", ("left", "right"), (), None, None),
    ("mask_or", "mask_or", ("left", "right"), (), None, None),
    ("mask_xor", "mask_xor", ("left", "right"), (), None, None),
    ("mask_not", "mask_not", ("value",), (), None, None),
)


__all__ = (
    "core_implementation_arms",
    "equality_implementations",
    "finalize_bit_conversion_implementation_arms",
    "finalize_comprehensive_implementation_arms",
    "finalize_curated_implementation_arms",
    "finalize_operator_implementations",
)
