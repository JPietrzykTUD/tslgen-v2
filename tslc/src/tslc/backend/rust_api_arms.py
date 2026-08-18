"""Final implementation arms consumed by ordinary Rust facade rendering."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.rust_api_core import RUST_FACADE_CORE_CALL_ROLES
from tslc.backend.rust_api_kinds import (
    RustCuratedMethodKind,
    RustFacadeBitConversionDirection,
)
from tslc.backend.rust_api_model import (
    RustFacadeCoreDelegate,
    RustFacadeDelegate,
    RustFacadeReceiverKind,
    RustFacadeRepresentation,
    RustFacadeShape,
    rust_facade_representations_can_coexist,
)
from tslc.backend.rust_names import rust_lower_module_name
from tslc.catalog.semantics import PrimitiveOperation


@dataclass(frozen=True, slots=True)
class RustFacadeArmSelection:
    """Exact representation predicates guarding one emitted implementation."""

    representations: tuple[RustFacadeRepresentation, ...]

    def __post_init__(self) -> None:
        if len(self.representations) not in {1, 2}:
            raise ValueError(
                "Rust facade implementation arms require one or two "
                "representation predicates"
            )
        if len(set(self.representations)) != len(self.representations):
            raise ValueError(
                "Rust facade implementation-arm predicates must be unique"
            )
        if (
            len(self.representations) == 2
            and not rust_facade_representations_can_coexist(
                *self.representations
            )
        ):
            raise ValueError(
                "Rust facade implementation-arm representations cannot coexist"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeLowerCall:
    """One fully bound lower call used by an emitted facade implementation."""

    delegate: RustFacadeDelegate | RustFacadeCoreDelegate
    extension_name: str
    generic_arguments: tuple[str, ...]
    arguments: tuple[str, ...]
    result_suffix: str = ""

    def __post_init__(self) -> None:
        if not self.extension_name:
            raise ValueError("Rust facade lower calls require an extension owner")
        if not self.generic_arguments or any(
            not item for item in self.generic_arguments
        ):
            raise ValueError("Rust facade lower-call generic arguments cannot be empty")
        if any(not item for item in self.arguments):
            raise ValueError("Rust facade lower-call arguments cannot be empty")
        if isinstance(self.delegate, RustFacadeCoreDelegate):
            if self.extension_name != self.delegate.extension_name:
                raise ValueError(
                    "Rust facade core lower-call owner must match its delegate"
                )
            if len(self.arguments) != len(
                self.delegate.invocation.public_argument_index_by_source_index
            ):
                raise ValueError(
                    "Rust facade core lower-call arguments must match its invocation"
                )
        else:
            placeholder_count = len(
                self.delegate.overload_parameter_positions
            )
            if placeholder_count and self.generic_arguments[
                -placeholder_count:
            ] != ("_",) * placeholder_count:
                raise ValueError(
                    "Rust facade lower calls must retain every overload "
                    "generic placeholder"
                )

    @property
    def primitive_name(self) -> str:
        if isinstance(self.delegate, RustFacadeCoreDelegate):
            return self.delegate.source_primitive_name
        return self.delegate.primitive_name

    @property
    def module_spelling(self) -> str:
        return rust_lower_module_name(self.delegate.profile_name)


@dataclass(frozen=True, slots=True)
class RustFacadeNamedCall:
    role: str
    call: RustFacadeLowerCall

    def __post_init__(self) -> None:
        if not self.role:
            raise ValueError("Rust facade named lower calls require a role")


@dataclass(frozen=True, slots=True)
class RustFacadeCoreImplementationArm:
    shape: RustFacadeShape
    representation: RustFacadeRepresentation
    selection: RustFacadeArmSelection
    calls: tuple[RustFacadeNamedCall, ...]

    def __post_init__(self) -> None:
        if self.selection.representations != (self.representation,):
            raise ValueError(
                "Rust facade core-arm selection must match its representation"
            )
        roles = tuple(item.role for item in self.calls)
        if roles != RUST_FACADE_CORE_CALL_ROLES:
            raise ValueError(
                "Rust facade core implementation calls must match the "
                "complete FacadeOps role inventory"
            )
        if any(
            item.call.delegate.profile_name != self.representation.profile_name
            for item in self.calls
        ):
            raise ValueError(
                "Rust facade core calls must match the arm representation profile"
            )


@dataclass(frozen=True, slots=True)
class RustComprehensivePrivateImplementationArm:
    source_shape: RustFacadeShape
    source_representation: RustFacadeRepresentation
    target_shape: RustFacadeShape | None
    target_representation: RustFacadeRepresentation | None
    selection: RustFacadeArmSelection
    attribute_values: tuple[tuple[str, str], ...]
    call: RustFacadeLowerCall

    def __post_init__(self) -> None:
        if (self.target_shape is None) != (self.target_representation is None):
            raise ValueError(
                "Rust comprehensive arms require complete target representation facts"
            )
        expected = (self.source_representation,) + (
            (self.target_representation,)
            if self.target_representation is not None
            else ()
        )
        if self.selection.representations != tuple(dict.fromkeys(expected)):
            raise ValueError(
                "Rust comprehensive arm selection must match its representations"
            )
        _validate_surface_call(
            self.call,
            self.source_shape,
            self.source_representation,
        )
        names = tuple(name for name, _value in self.attribute_values)
        if len(set(names)) != len(names):
            raise ValueError(
                "Rust comprehensive arm attributes must be unique by name"
            )


@dataclass(frozen=True, slots=True)
class RustCuratedMethodImplementationArm:
    shape: RustFacadeShape
    representation: RustFacadeRepresentation
    selection: RustFacadeArmSelection
    call: RustFacadeLowerCall

    def __post_init__(self) -> None:
        if self.selection.representations != (self.representation,):
            raise ValueError(
                "Rust curated-method arm selection must match its representation"
            )
        if self.call.delegate.profile_name != self.representation.profile_name:
            raise ValueError(
                "Rust curated-method calls must match the arm representation profile"
            )
        _validate_surface_call(
            self.call,
            self.shape,
            self.representation,
        )


@dataclass(frozen=True, slots=True)
class RustFacadeConversionImplementationArm:
    source_shape: RustFacadeShape
    target_shape: RustFacadeShape
    source_representation: RustFacadeRepresentation
    target_representation: RustFacadeRepresentation
    selection: RustFacadeArmSelection
    call: RustFacadeLowerCall

    def __post_init__(self) -> None:
        if self.source_shape.lanes != self.target_shape.lanes:
            raise ValueError(
                "Rust facade conversion arms must preserve logical lane count"
            )
        expected = tuple(
            dict.fromkeys(
                (
                    self.source_representation,
                    self.target_representation,
                )
            )
        )
        if self.selection.representations != expected:
            raise ValueError(
                "Rust facade conversion-arm selection must match its representations"
            )
        _validate_surface_call(
            self.call,
            self.source_shape,
            self.source_representation,
        )


@dataclass(frozen=True, slots=True)
class RustFacadeEqualityImplementation:
    shape: RustFacadeShape
    method_name: str
    implements_eq: bool

    def __post_init__(self) -> None:
        if not self.method_name:
            raise ValueError(
                "Rust facade equality implementations require a method name"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeCanonicalOperatorArm:
    representation: RustFacadeRepresentation
    selection: RustFacadeArmSelection
    call: RustFacadeLowerCall

    def __post_init__(self) -> None:
        if self.selection.representations != (self.representation,):
            raise ValueError(
                "Rust operator-arm selection must match its representation"
            )
        if self.call.delegate.profile_name != self.representation.profile_name:
            raise ValueError(
                "Rust operator calls must match the arm representation profile"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeForwardingOperatorArm:
    self_type: str
    rhs_type: str | None
    owned_rhs_type: str | None
    self_value: str
    rhs_value: str | None

    def __post_init__(self) -> None:
        if not self.self_type or not self.self_value:
            raise ValueError("Rust forwarding operator arms require complete self facts")
        rhs_values = (self.rhs_type, self.owned_rhs_type, self.rhs_value)
        if any(item is None for item in rhs_values) and any(
            item is not None for item in rhs_values
        ):
            raise ValueError(
                "Rust forwarding operator arms require complete binary RHS facts"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeAssignmentOperatorArm:
    trait_path: str
    method_name: str
    rhs_type: str
    owned_rhs_type: str
    rhs_value: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.trait_path,
                self.method_name,
                self.rhs_type,
                self.owned_rhs_type,
                self.rhs_value,
            )
        ):
            raise ValueError(
                "Rust assignment operator arms require complete trait facts"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeOperatorImplementation:
    receiver_kind: RustFacadeReceiverKind
    shape: RustFacadeShape
    trait_path: str
    method_name: str
    rhs_type: str | None
    track_caller: bool
    canonical_arms: tuple[RustFacadeCanonicalOperatorArm, ...]
    forwarding_arms: tuple[RustFacadeForwardingOperatorArm, ...]
    assignment_arms: tuple[RustFacadeAssignmentOperatorArm, ...]

    def __post_init__(self) -> None:
        if not self.trait_path or not self.method_name or not self.canonical_arms:
            raise ValueError(
                "Rust operator implementations require trait and canonical arms"
            )
        profiles = tuple(
            arm.representation.profile_name for arm in self.canonical_arms
        )
        if len(set(profiles)) != len(profiles):
            raise ValueError(
                "Rust canonical operator arms must be unique by profile"
            )
        if set(profiles) != {
            item.profile_name for item in self.shape.representations
        }:
            raise ValueError(
                "Rust canonical operator arms must cover every shape representation"
            )
        for arm in self.canonical_arms:
            _validate_surface_call(
                arm.call,
                self.shape,
                arm.representation,
            )
        if self.rhs_type is None and self.assignment_arms:
            raise ValueError("Rust unary operators cannot have assignment arms")


@dataclass(frozen=True, slots=True)
class RustFacadeGenericMaskOperatorImplementation:
    trait_path: str
    method_name: str
    operation: PrimitiveOperation
    rhs_type: str | None
    forwarding_arms: tuple[RustFacadeForwardingOperatorArm, ...]
    assignment_arms: tuple[RustFacadeAssignmentOperatorArm, ...]

    def __post_init__(self) -> None:
        if not all(
            (
                self.trait_path,
                self.method_name,
                self.forwarding_arms,
            )
        ):
            raise ValueError(
                "Rust generic mask operators require complete trait and facade facts"
            )
        if self.operation not in _MASK_FACADE_METHODS:
            raise ValueError(
                "Rust generic mask operators require a typed mask operation"
            )
        unary = self.operation is PrimitiveOperation.MASK_NOT
        if unary != (self.rhs_type is None):
            raise ValueError(
                "Rust generic mask operator arity must match its operation"
            )
        if len(self.forwarding_arms) != (1 if unary else 3):
            raise ValueError(
                "Rust generic mask operators require complete forwarding arms"
            )
        if len(self.assignment_arms) != (0 if unary else 2):
            raise ValueError(
                "Rust generic mask operators require complete assignment arms"
            )

    @property
    def facade_method_name(self) -> str:
        return _MASK_FACADE_METHODS[self.operation]


_MASK_FACADE_METHODS = {
    PrimitiveOperation.MASK_AND: "mask_and",
    PrimitiveOperation.MASK_OR: "mask_or",
    PrimitiveOperation.MASK_XOR: "mask_xor",
    PrimitiveOperation.MASK_NOT: "mask_not",
}


@dataclass(frozen=True, slots=True)
class RustFacadeBitConversionImplementationArm:
    direction: RustFacadeBitConversionDirection
    float_shape: RustFacadeShape
    bits_shape: RustFacadeShape
    conversion: RustFacadeConversionImplementationArm

    def __post_init__(self) -> None:
        expected = (
            (self.float_shape, self.bits_shape)
            if self.direction is RustFacadeBitConversionDirection.TO_BITS
            else (self.bits_shape, self.float_shape)
        )
        if (
            self.conversion.source_shape,
            self.conversion.target_shape,
        ) != expected:
            raise ValueError(
                "Rust bit-conversion direction must match its conversion arm"
            )


def _validate_surface_call(
    call: RustFacadeLowerCall,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> None:
    if not isinstance(call.delegate, RustFacadeDelegate):
        raise ValueError("Rust facade surface arms require a surface delegate")
    owners = tuple(
        owner.extension_name
        for owner in call.delegate.owners
        if owner.type_tag == shape.type_tag
        and owner.lanes == shape.lanes
        and owner.representation_profile_name == representation.profile_name
    )
    if owners != (call.extension_name,):
        raise ValueError(
            "Rust facade lower-call owner must match its exact shape delegate"
        )


__all__ = (
    "RUST_FACADE_CORE_CALL_ROLES",
    "RustComprehensivePrivateImplementationArm",
    "RustCuratedMethodImplementationArm",
    "RustCuratedMethodKind",
    "RustFacadeArmSelection",
    "RustFacadeAssignmentOperatorArm",
    "RustFacadeBitConversionDirection",
    "RustFacadeBitConversionImplementationArm",
    "RustFacadeCanonicalOperatorArm",
    "RustFacadeConversionImplementationArm",
    "RustFacadeCoreImplementationArm",
    "RustFacadeEqualityImplementation",
    "RustFacadeForwardingOperatorArm",
    "RustFacadeGenericMaskOperatorImplementation",
    "RustFacadeLowerCall",
    "RustFacadeNamedCall",
    "RustFacadeOperatorImplementation",
)
