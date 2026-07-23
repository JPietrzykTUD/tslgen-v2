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
    GENERIC = "generic"


class RustFacadeCoverageStatus(StrEnum):
    ADMITTED = "admitted"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class RustFacadeRepresentation:
    """One cfg-selected private representation of a logical shape."""

    profile_name: str | None
    requirement: RustTargetRequirement | None
    mapping: RustStaticVectorMapping


@dataclass(frozen=True, slots=True)
class RustFacadeShape:
    type_tag: str
    base_spelling: str
    lanes: int
    total_bits: int
    representations: tuple[RustFacadeRepresentation, ...]


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
class RustFacadeDelegate:
    """Lower-level generated entry point used by one selected profile or fallback."""

    profile_name: str | None
    primitive_name: str


@dataclass(frozen=True, slots=True)
class RustComprehensiveMethod:
    public_name: str
    source_primitive_name: str
    receiver_kind: RustFacadeReceiverKind
    parameters: tuple[RustFacadeParameter, ...]
    const_parameters: tuple[RustFacadeConstParameter, ...]
    type_parameters: tuple[RustFacadeTypeParameter, ...]
    result_kind: str
    type_tags: tuple[str, ...]
    caller_unsafe: bool
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
    caller_unsafe: bool
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
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustNativeAliasSelection:
    profile_name: str
    requirement: RustTargetRequirement
    lanes: int


@dataclass(frozen=True, slots=True)
class RustNativeAlias:
    type_tag: str
    base_spelling: str
    selections: tuple[RustNativeAliasSelection, ...]


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
    comprehensive_methods: tuple[RustComprehensiveMethod, ...]
    curated_methods: tuple[RustCuratedMethod, ...]
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


__all__ = (
    "RustComprehensiveMethod",
    "RustCuratedMethod",
    "RustCuratedTraitImplementation",
    "RustFacadeCoverageEntry",
    "RustFacadeCoverageStatus",
    "RustFacadeConstParameter",
    "RustFacadeConstParameterSource",
    "RustFacadeDelegate",
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
