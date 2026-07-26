"""Finalized, render-independent facts for the ordinary generated Rust API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tslc.backend.rust_static_selection import (
    RustStaticVectorMapping,
    RustTargetRequirement,
)
from tslc.catalog.arithmetic import ArithmeticOperandRole, ArithmeticOperation
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.documentation import PrimitiveDocumentation


class RustFacadeReceiverKind(StrEnum):
    VECTOR = "vector"
    MASK = "mask"
    FREE = "free"


class RustFacadeTraitRhsKind(StrEnum):
    SAME_TYPE = "same_type"
    SCALAR = "scalar"


class RustFacadeParameterPlacement(StrEnum):
    RECEIVER = "receiver"
    ARGUMENT = "argument"
    CONST_GENERIC = "const_generic"


class RustFacadeTypeParameterRole(StrEnum):
    RESULT_ELEMENT = "result_element"


class RustFacadeConstParameterSource(StrEnum):
    ATTRIBUTE = "attribute"
    IMMEDIATE = "immediate"
    GENERIC = "generic"


class RustFacadeCoverageStatus(StrEnum):
    ADMITTED = "admitted"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class RustFacadeRepresentation:
    """One cfg-selected private representation of a logical shape."""

    profile_name: str | None
    requirement: RustTargetRequirement | None
    stronger_requirements: tuple[RustTargetRequirement, ...]
    mapping: RustStaticVectorMapping

    def __post_init__(self) -> None:
        if (self.profile_name is None) != (self.requirement is None):
            raise ValueError(
                "Rust facade representations require profile and target facts together"
            )
        if self.requirement is None and self.mapping.uses_hardware:
            raise ValueError("Rust facade fallback representations cannot use hardware")
        if self.requirement is not None and any(
            not item.strictly_contains(self.requirement)
            for item in self.stronger_requirements
        ):
            raise ValueError(
                "Rust facade profile exclusions must be stronger target requirements"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeShape:
    type_tag: str
    base_spelling: str
    lanes: int
    total_bits: int
    representations: tuple[RustFacadeRepresentation, ...]

    def __post_init__(self) -> None:
        if not self.type_tag or not self.base_spelling or self.lanes <= 0:
            raise ValueError("Rust facade shapes require complete positive type facts")
        if self.lanes != 1 and self.total_bits not in {128, 256, 512}:
            raise ValueError(
                "Rust facade fixed shapes must have 128, 256, or 512 total bits"
            )
        if sum(item.requirement is None for item in self.representations) != 1:
            raise ValueError("Rust facade shapes require exactly one generic fallback")
        if any(
            (
                item.mapping.type_tag,
                item.mapping.base_spelling,
                item.mapping.lanes,
                item.mapping.total_bits,
            )
            != (self.type_tag, self.base_spelling, self.lanes, self.total_bits)
            for item in self.representations
        ):
            raise ValueError(
                "Rust facade shape representations must preserve the logical shape"
            )
        profiles = tuple(item.profile_name for item in self.representations)
        if len(set(profiles)) != len(profiles):
            raise ValueError("Rust facade shape representations must be unique by profile")


@dataclass(frozen=True, slots=True)
class RustFacadeParameter:
    source_name: str
    public_name: str
    kind: str
    source_index: int
    placement: RustFacadeParameterPlacement
    role: OperandRole | ArithmeticOperandRole | None = None


@dataclass(frozen=True, slots=True)
class RustFacadeConstParameter:
    source_name: str
    public_name: str
    type_spelling: str
    source: RustFacadeConstParameterSource
    source_default: str | None = None


@dataclass(frozen=True, slots=True)
class RustFacadeTypeParameter:
    source_name: str
    public_name: str
    role: RustFacadeTypeParameterRole
    type_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RustFacadeDelegateVector:
    extension_name: str
    type_tag: str
    attribute_combinations: tuple[tuple[tuple[str, str], ...], ...] = ()

    def __post_init__(self) -> None:
        if not self.extension_name or not self.type_tag:
            raise ValueError("Rust facade delegate vectors require complete source keys")
        if len(set(self.attribute_combinations)) != len(
            self.attribute_combinations
        ):
            raise ValueError("Rust facade vector attributes must be unique")


@dataclass(frozen=True, slots=True)
class RustFacadeDelegate:
    """Lower-level generated entry point used by one selected profile or fallback."""

    profile_name: str | None
    primitive_name: str
    vectors: tuple[RustFacadeDelegateVector, ...]
    overload_parameter_positions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.primitive_name or not self.vectors:
            raise ValueError("Rust facade delegates require an entry point and vectors")
        if len(set(self.vectors)) != len(self.vectors):
            raise ValueError("Rust facade delegate vectors must be unique")
        if any(position < 0 for position in self.overload_parameter_positions):
            raise ValueError("Rust facade overload positions cannot be negative")


@dataclass(frozen=True, slots=True)
class RustFacadeOperationBinding:
    """One source-owned semantic operation available to facade planning."""

    operation: PrimitiveOperation
    source_primitive_name: str
    result_kind: str
    parameter_kinds: tuple[str, ...]
    axis_names: tuple[str, ...]
    mask_policy: str | None
    overload: tuple[str, str, bool] | None
    type_tags: tuple[str, ...]
    caller_unsafe: bool
    delegates: tuple[RustFacadeDelegate, ...]

    def __post_init__(self) -> None:
        if not self.source_primitive_name or not self.result_kind or not self.type_tags:
            raise ValueError("Rust facade operation bindings require complete source facts")
        if not self.delegates or all(
            delegate.profile_name is not None for delegate in self.delegates
        ):
            raise ValueError(
                "Rust facade operation bindings require a generic baseline delegate"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeCoreOperationRequirement:
    role: str
    operation: PrimitiveOperation
    result_kind: str
    parameter_kinds: tuple[str, ...]
    axis_names: tuple[str, ...] = ()
    overload: tuple[str, str, bool] | None = None

    def __post_init__(self) -> None:
        if not self.role or not self.result_kind:
            raise ValueError("Rust facade core requirements require complete roles")


@dataclass(frozen=True, slots=True)
class RustFacadeCoreDelegate:
    """Final lower-level delegate for one logical shape and static selection arm."""

    role: str
    type_tag: str
    lanes: int
    profile_name: str | None
    source_primitive_name: str

    def __post_init__(self) -> None:
        if (
            not self.role
            or not self.type_tag
            or self.lanes <= 0
            or not self.source_primitive_name
        ):
            raise ValueError("Rust facade core delegates require complete shape facts")


@dataclass(frozen=True, slots=True)
class RustComprehensiveMethod:
    public_name: str
    source_primitive_name: str
    signature: str
    mask_policy: str | None
    receiver_kind: RustFacadeReceiverKind
    parameters: tuple[RustFacadeParameter, ...]
    const_parameters: tuple[RustFacadeConstParameter, ...]
    type_parameters: tuple[RustFacadeTypeParameter, ...]
    result_kind: str
    type_tags: tuple[str, ...]
    shape_keys: tuple[tuple[str, int], ...]
    caller_unsafe: bool
    safety_requirements: tuple[str, ...]
    panic_conditions: tuple[str, ...]
    bounds_checked_parameters: tuple[str, ...]
    must_use: bool
    documentation: PrimitiveDocumentation
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustCuratedMethod:
    public_name: str
    receiver_kind: RustFacadeReceiverKind
    operation: PrimitiveOperation
    source_primitive_name: str
    type_tags: tuple[str, ...]
    target_type_tags: tuple[str, ...]
    shape_keys: tuple[tuple[str, int], ...]
    caller_unsafe: bool
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustFacadeBitConversion:
    float_type_tag: str
    bits_type_tag: str
    source_primitive_name: str
    shape_keys: tuple[tuple[str, int], ...]
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustCuratedTraitImplementation:
    trait_path: str
    method_name: str
    receiver_kind: RustFacadeReceiverKind
    operation: ArithmeticOperation | PrimitiveOperation
    source_primitive_name: str
    type_tags: tuple[str, ...]
    rhs_kind: RustFacadeTraitRhsKind | None
    rhs_type_tags: tuple[str, ...]
    shape_keys: tuple[tuple[str, int], ...]
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustNativeAliasSelection:
    profile_name: str | None
    requirement: RustTargetRequirement | None
    stronger_requirements: tuple[RustTargetRequirement, ...]
    lanes: int

    def __post_init__(self) -> None:
        if (self.profile_name is None) != (self.requirement is None):
            raise ValueError(
                "Rust native alias selections require profile and target facts together"
            )
        if self.lanes <= 0:
            raise ValueError("Rust native alias selections require positive lane counts")
        if self.requirement is not None and any(
            not item.strictly_contains(self.requirement)
            for item in self.stronger_requirements
        ):
            raise ValueError(
                "Rust native profile exclusions must be stronger target requirements"
            )


@dataclass(frozen=True, slots=True)
class RustNativeAlias:
    type_tag: str
    base_spelling: str
    selections: tuple[RustNativeAliasSelection, ...]

    def __post_init__(self) -> None:
        if not self.type_tag or not self.base_spelling:
            raise ValueError("Rust native aliases require complete type facts")
        if sum(item.requirement is None for item in self.selections) != 1:
            raise ValueError("Rust native aliases require exactly one generic fallback")
        profiles = tuple(item.profile_name for item in self.selections)
        if len(set(profiles)) != len(profiles):
            raise ValueError("Rust native alias selections must be unique by profile")


@dataclass(frozen=True, slots=True)
class RustOperationValue:
    public_name: str
    operation: ArithmeticOperation | PrimitiveOperation
    source_primitive_name: str
    type_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RustFacadeCoverageEntry:
    source_primitive_name: str
    signature: str
    mask_policy: str | None
    status: RustFacadeCoverageStatus
    public_name: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RustFacadePlan:
    shapes: tuple[RustFacadeShape, ...]
    operation_bindings: tuple[RustFacadeOperationBinding, ...]
    core_delegates: tuple[RustFacadeCoreDelegate, ...]
    comprehensive_methods: tuple[RustComprehensiveMethod, ...]
    curated_methods: tuple[RustCuratedMethod, ...]
    bit_conversions: tuple[RustFacadeBitConversion, ...]
    trait_implementations: tuple[RustCuratedTraitImplementation, ...]
    native_aliases: tuple[RustNativeAlias, ...]
    operation_values: tuple[RustOperationValue, ...]
    coverage: tuple[RustFacadeCoverageEntry, ...]

    def __post_init__(self) -> None:
        method_keys = tuple(
            (item.receiver_kind, item.public_name)
            for item in self.comprehensive_methods
        ) + tuple(
            (item.receiver_kind, item.public_name) for item in self.curated_methods
        )
        if len(set(method_keys)) != len(method_keys):
            raise ValueError("Rust facade method names must be unique per receiver")
        shape_keys = tuple((item.type_tag, item.lanes) for item in self.shapes)
        if len(set(shape_keys)) != len(shape_keys):
            raise ValueError("Rust facade logical shapes must be unique")
        operation_keys = tuple(
            (
                item.operation,
                item.source_primitive_name,
                item.result_kind,
                item.parameter_kinds,
                item.axis_names,
                item.mask_policy,
                item.overload,
            )
            for item in self.operation_bindings
        )
        if len(set(operation_keys)) != len(operation_keys):
            raise ValueError("Rust facade operation bindings must be unique")
        core_delegate_keys = tuple(
            (item.role, item.type_tag, item.lanes, item.profile_name)
            for item in self.core_delegates
        )
        if len(set(core_delegate_keys)) != len(core_delegate_keys):
            raise ValueError("Rust facade core delegates must be unique")
        shape_key_set = set(shape_keys)
        if any(
            (alias.type_tag, selection.lanes) not in shape_key_set
            for alias in self.native_aliases
            for selection in alias.selections
        ):
            raise ValueError("Rust native aliases must select an admitted logical shape")
        native_type_tags = tuple(item.type_tag for item in self.native_aliases)
        if len(set(native_type_tags)) != len(native_type_tags):
            raise ValueError("Rust native aliases must be unique by element type")


__all__ = (
    "RustComprehensiveMethod",
    "RustCuratedMethod",
    "RustCuratedTraitImplementation",
    "RustFacadeCoverageEntry",
    "RustFacadeCoverageStatus",
    "RustFacadeBitConversion",
    "RustFacadeConstParameter",
    "RustFacadeConstParameterSource",
    "RustFacadeDelegate",
    "RustFacadeDelegateVector",
    "RustFacadeCoreDelegate",
    "RustFacadeCoreOperationRequirement",
    "RustFacadeOperationBinding",
    "RustFacadeParameter",
    "RustFacadeParameterPlacement",
    "RustFacadePlan",
    "RustFacadeReceiverKind",
    "RustFacadeRepresentation",
    "RustFacadeShape",
    "RustFacadeTraitRhsKind",
    "RustFacadeTypeParameter",
    "RustFacadeTypeParameterRole",
    "RustNativeAlias",
    "RustNativeAliasSelection",
    "RustOperationValue",
)
