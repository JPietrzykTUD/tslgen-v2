"""Finalized, render-independent facts for the ordinary generated Rust API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from tslc.backend.rust_names import rust_profile_module_name
from tslc.backend.rust_static_selection import (
    RustStaticVectorMapping,
    RustTargetRequirement,
)
from tslc.catalog.arithmetic import ArithmeticOperandRole, ArithmeticOperation
from tslc.catalog.memory import MemoryAccess, MemoryAddressing, MemoryAlignment
from tslc.catalog.model import VectorBitsKind
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
class RustFacadeInvocation:
    """Maps canonical public operands to the authored lower-call order."""

    public_argument_index_by_source_index: tuple[int, ...]

    def __post_init__(self) -> None:
        if tuple(
            sorted(self.public_argument_index_by_source_index)
        ) != tuple(range(len(self.public_argument_index_by_source_index))):
            raise ValueError(
                "Rust facade invocation arguments must form an exact permutation"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeTargetSelection:
    """One exact profile-selection predicate used by a facade representation."""

    requirement: RustTargetRequirement
    stronger_requirements: tuple[RustTargetRequirement, ...]

    def __post_init__(self) -> None:
        if any(
            not item.strictly_contains(self.requirement)
            for item in self.stronger_requirements
        ):
            raise ValueError(
                "Rust facade target-selection exclusions must be stronger targets"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeRepresentation:
    """One cfg-selected private representation of a logical shape."""

    profile_name: str | None
    requirement: RustTargetRequirement | None
    stronger_requirements: tuple[RustTargetRequirement, ...]
    mapping: RustStaticVectorMapping
    fallback_exclusions: tuple[RustFacadeTargetSelection, ...] = ()
    vector_descriptor: str = field(init=False)

    def __post_init__(self) -> None:
        if (self.profile_name is None) != (self.requirement is None):
            raise ValueError(
                "Rust facade representations require profile and target facts together"
            )
        if self.requirement is None and self.mapping.uses_hardware:
            raise ValueError("Rust facade fallback representations cannot use hardware")
        if self.requirement is None and self.stronger_requirements:
            raise ValueError(
                "Rust facade fallback exclusions must retain exact selection predicates"
            )
        if self.requirement is not None and self.fallback_exclusions:
            raise ValueError(
                "Rust facade profile representations cannot have fallback exclusions"
            )
        if self.requirement is not None and any(
            not item.strictly_contains(self.requirement)
            for item in self.stronger_requirements
        ):
            raise ValueError(
                "Rust facade profile exclusions must be stronger target requirements"
            )
        object.__setattr__(
            self,
            "vector_descriptor",
            _rust_facade_vector_descriptor(self.mapping, self.profile_name),
        )


def _rust_facade_vector_descriptor(
    mapping: RustStaticVectorMapping,
    profile_name: str | None,
) -> str:
    if mapping.extension_name is None:
        extension = "Scalar" if mapping.lanes == 1 else f"Generic<{mapping.lanes}>"
        extension = f"crate::tsl_core::{extension}"
    else:
        if profile_name is None or mapping.extension_tag_spelling is None:
            raise ValueError(
                "Rust hardware facade mapping is missing qualified tag facts"
            )
        extension = (
            f"crate::{rust_profile_module_name(profile_name)}::"
            f"{mapping.extension_tag_spelling}"
        )
    return f"crate::tsl_core::Simd<{mapping.base_spelling}, {extension}>"


def rust_facade_representations_can_coexist(
    left: RustFacadeRepresentation,
    right: RustFacadeRepresentation,
) -> bool:
    """Return whether two finalized representations can be active together."""

    profile_requirements = tuple(
        requirement
        for requirement in (left.requirement, right.requirement)
        if requirement is not None
    )
    if not profile_requirements:
        return True
    arches = {item.target_arch for item in profile_requirements}
    if len(arches) != 1:
        return False
    target_arch = profile_requirements[0].target_arch
    target_features = frozenset(
        feature
        for requirement in profile_requirements
        for feature in requirement.target_features
    )
    return all(
        _rust_facade_representation_is_active(
            representation, target_arch, target_features
        )
        for representation in (left, right)
    )


def _rust_facade_representation_is_active(
    representation: RustFacadeRepresentation,
    target_arch: str,
    target_features: frozenset[str],
) -> bool:
    if representation.requirement is None:
        return not any(
            _rust_facade_target_selection_is_active(
                exclusion.requirement,
                exclusion.stronger_requirements,
                target_arch,
                target_features,
            )
            for exclusion in representation.fallback_exclusions
        )
    return _rust_facade_target_selection_is_active(
        representation.requirement,
        representation.stronger_requirements,
        target_arch,
        target_features,
    )


def _rust_facade_target_selection_is_active(
    requirement: RustTargetRequirement,
    stronger_requirements: tuple[RustTargetRequirement, ...],
    target_arch: str,
    target_features: frozenset[str],
) -> bool:
    if requirement.target_arch != target_arch or not set(
        requirement.target_features
    ) <= target_features:
        return False
    return not any(
        stronger.target_arch == target_arch
        and set(stronger.target_features) <= target_features
        for stronger in stronger_requirements
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
    uses_sized_vector: bool = False
    implementation_fallback: bool = False
    unconditional_implementation_fallback: bool = False
    vector_bits_kind: VectorBitsKind = "fixed"
    vector_bits: int = 0

    def __post_init__(self) -> None:
        if not self.extension_name or not self.type_tag:
            raise ValueError("Rust facade delegate vectors require complete source keys")
        if len(set(self.attribute_combinations)) != len(
            self.attribute_combinations
        ):
            raise ValueError("Rust facade vector attributes must be unique")
        if (
            self.unconditional_implementation_fallback
            and not self.implementation_fallback
        ):
            raise ValueError(
                "An unconditional Rust facade fallback must be an implementation fallback"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeDelegateOwner:
    """Exact source extension implementing one logical delegate shape."""

    type_tag: str
    lanes: int
    representation_profile_name: str | None
    extension_name: str

    def __post_init__(self) -> None:
        if not self.type_tag or self.lanes <= 0 or not self.extension_name:
            raise ValueError("Rust facade delegate owners require complete shape facts")


@dataclass(frozen=True, slots=True)
class RustFacadeDelegate:
    """Lower-level generated entry point used by one selected profile or fallback."""

    profile_name: str | None
    primitive_name: str
    vectors: tuple[RustFacadeDelegateVector, ...]
    overload_parameter_positions: tuple[int, ...] = ()
    owners: tuple[RustFacadeDelegateOwner, ...] = ()

    def __post_init__(self) -> None:
        if not self.primitive_name or not self.vectors:
            raise ValueError("Rust facade delegates require an entry point and vectors")
        if len(set(self.vectors)) != len(self.vectors):
            raise ValueError("Rust facade delegate vectors must be unique")
        if any(position < 0 for position in self.overload_parameter_positions):
            raise ValueError("Rust facade overload positions cannot be negative")
        owner_keys = tuple(
            (item.type_tag, item.lanes, item.representation_profile_name)
            for item in self.owners
        )
        if len(set(owner_keys)) != len(owner_keys):
            raise ValueError("Rust facade delegate owners must be unique by shape")


@dataclass(frozen=True, slots=True)
class RustFacadeConversionPair:
    """One exact source-to-target type edge and its lower delegate inventory."""

    source_type_tag: str
    target_type_tag: str
    shape_keys: tuple[tuple[str, int], ...]
    delegates: tuple[RustFacadeDelegate, ...]

    def __post_init__(self) -> None:
        if (
            not self.source_type_tag
            or not self.target_type_tag
            or not self.delegates
        ):
            raise ValueError("Rust facade conversion pairs require exact delegate facts")
        if all(delegate.profile_name is not None for delegate in self.delegates):
            raise ValueError(
                "Rust facade conversion pairs require a generic baseline delegate"
            )
        if any(
            type_tag != self.source_type_tag
            for type_tag, _lanes in self.shape_keys
        ):
            raise ValueError(
                "Rust facade conversion pair shapes must use the source type"
            )
        if len(set(self.shape_keys)) != len(self.shape_keys):
            raise ValueError("Rust facade conversion pair shapes must be unique")


@dataclass(frozen=True, slots=True)
class RustFacadeOperationBinding:
    """One source-owned semantic operation available to facade planning."""

    operation: PrimitiveOperation
    source_primitive_name: str
    result_kind: str
    parameter_kinds: tuple[str, ...]
    operand_roles: tuple[tuple[OperandRole, int, str], ...]
    axis_names: tuple[str, ...]
    memory_access: MemoryAccess | None
    memory_addressing: MemoryAddressing | None
    memory_alignment_axis_name: str | None
    memory_alignment_modes: tuple[MemoryAlignment, ...]
    mask_policy: str | None
    overload: tuple[str, str, bool] | None
    type_tags: tuple[str, ...]
    caller_unsafe: bool
    delegates: tuple[RustFacadeDelegate, ...]

    def __post_init__(self) -> None:
        if not self.source_primitive_name or not self.result_kind or not self.type_tags:
            raise ValueError("Rust facade operation bindings require complete source facts")
        has_memory = (
            self.memory_access is not None
            and self.memory_addressing is not None
        )
        if has_memory != (
            self.memory_alignment_axis_name is not None
            and bool(self.memory_alignment_modes)
        ):
            raise ValueError(
                "Rust facade memory bindings require complete typed memory facts"
            )
        if (
            self.memory_alignment_axis_name is not None
            and self.memory_alignment_axis_name not in self.axis_names
        ):
            raise ValueError(
                "Rust facade memory alignment must name a retained specialization axis"
            )
        if (self.memory_access is None) != (self.memory_addressing is None):
            raise ValueError(
                "Rust facade operation bindings cannot retain a partial memory contract"
            )
        if len(set(self.memory_alignment_modes)) != len(
            self.memory_alignment_modes
        ):
            raise ValueError(
                "Rust facade operation alignment modes must be unique"
            )
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
    public_roles: tuple[OperandRole, ...]
    axis_names: tuple[str, ...] = ()
    memory_access: MemoryAccess | None = None
    memory_addressing: MemoryAddressing | None = None
    memory_alignment_modes: tuple[MemoryAlignment, ...] = ()
    overload: tuple[str, str, bool] | None = None

    def __post_init__(self) -> None:
        if not self.role or not self.result_kind:
            raise ValueError("Rust facade core requirements require complete roles")
        if len(self.public_roles) != len(self.parameter_kinds):
            raise ValueError(
                "Rust facade core requirements must classify every public argument"
            )
        if len(set(self.public_roles)) != len(self.public_roles):
            raise ValueError("Rust facade core requirement roles must be unique")
        if (self.memory_access is None) != (self.memory_addressing is None):
            raise ValueError(
                "Rust facade core requirements cannot state a partial memory contract"
            )
        if (self.memory_access is not None) != bool(
            self.memory_alignment_modes
        ):
            raise ValueError(
                "Rust facade core memory requirements require alignment modes"
            )
        if self.memory_access is not None and len(self.axis_names) != 1:
            raise ValueError(
                "Rust facade core memory requirements require one alignment axis"
            )
        if len(set(self.memory_alignment_modes)) != len(
            self.memory_alignment_modes
        ):
            raise ValueError(
                "Rust facade core alignment modes must be unique"
            )


@dataclass(frozen=True, slots=True)
class RustFacadeCoreDelegate:
    """Final lower-level delegate for one logical shape and static selection arm."""

    role: str
    type_tag: str
    lanes: int
    profile_name: str | None
    source_primitive_name: str
    extension_name: str
    invocation: RustFacadeInvocation

    def __post_init__(self) -> None:
        if (
            not self.role
            or not self.type_tag
            or self.lanes <= 0
            or not self.source_primitive_name
            or not self.extension_name
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
    conversion_pairs: tuple[RustFacadeConversionPair, ...]
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustCuratedMethod:
    public_name: str
    receiver_kind: RustFacadeReceiverKind
    operation: PrimitiveOperation
    source_primitive_name: str
    type_tags: tuple[str, ...]
    shape_keys: tuple[tuple[str, int], ...]
    caller_unsafe: bool
    invocation: RustFacadeInvocation
    conversion_pairs: tuple[RustFacadeConversionPair, ...]
    delegates: tuple[RustFacadeDelegate, ...]


@dataclass(frozen=True, slots=True)
class RustFacadeBitConversion:
    float_type_tag: str
    bits_type_tag: str
    source_primitive_name: str
    shape_keys: tuple[tuple[str, int], ...]
    invocation: RustFacadeInvocation
    to_bits: RustFacadeConversionPair
    from_bits: RustFacadeConversionPair


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
    rhs_type_spellings: tuple[str, ...]
    shape_keys: tuple[tuple[str, int], ...]
    invocation: RustFacadeInvocation
    delegates: tuple[RustFacadeDelegate, ...]

    def __post_init__(self) -> None:
        if len(self.rhs_type_spellings) != len(
            self.rhs_type_tags
        ):
            raise ValueError(
                "Rust facade trait RHS spellings must match its type tags"
            )


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
        shape_key_set = set(shape_keys)
        method_pair_keys = tuple(
            tuple(
                (pair.source_type_tag, pair.target_type_tag)
                for pair in method.conversion_pairs
            )
            for method in self.comprehensive_methods
        ) + tuple(
            tuple(
                (pair.source_type_tag, pair.target_type_tag)
                for pair in method.conversion_pairs
            )
            for method in self.curated_methods
        )
        for pair_keys in method_pair_keys:
            if len(set(pair_keys)) != len(pair_keys):
                raise ValueError(
                    "Rust facade conversion pairs must be unique per method"
                )
        conversion_pairs = tuple(
            pair
            for method in self.comprehensive_methods
            for pair in method.conversion_pairs
        ) + tuple(
            pair
            for method in self.curated_methods
            for pair in method.conversion_pairs
        ) + tuple(
            pair
            for conversion in self.bit_conversions
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
    "RustFacadeInvocation",
    "RustFacadeBitConversion",
    "RustFacadeConstParameter",
    "RustFacadeConstParameterSource",
    "RustFacadeConversionPair",
    "RustFacadeDelegate",
    "RustFacadeDelegateOwner",
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
    "rust_facade_representations_can_coexist",
)
