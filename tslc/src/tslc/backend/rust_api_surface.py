"""Finalize Rust facade shapes, representations, delegates, and coverage."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from tslc.backend import rust_api_arm_planner as _arm_planner
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_candidates import _invocation_from_roles
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustCuratedTraitImplementation,
    RustFacadeConversionPair,
    RustFacadeCoreDelegate,
    RustFacadeCoreOperationRequirement,
    RustFacadeCoverageEntry,
    RustFacadeCoverageStatus,
    RustFacadeDelegate,
    RustFacadeDelegateOwner,
    RustFacadeDelegateVector,
    RustFacadeInvocation,
    RustFacadeOperationBinding,
    RustFacadeRepresentation,
    RustFacadeShape,
    RustFacadeTargetSelection,
    RustNativeAlias,
    RustNativeAliasSelection,
    rust_facade_representations_can_coexist,
)
from tslc.backend.rust_static_selection import RustStaticSelectionPlan
from tslc.catalog.memory import MemoryAccess, MemoryAddressing, MemoryAlignment
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.diagnostics import Diagnostic


_core_implementation_arms = _arm_planner.core_implementation_arms
_equality_implementations = _arm_planner.equality_implementations
_finalize_bit_conversion_implementation_arms = (
    _arm_planner.finalize_bit_conversion_implementation_arms
)
_finalize_comprehensive_implementation_arms = (
    _arm_planner.finalize_comprehensive_implementation_arms
)
_finalize_curated_implementation_arms = (
    _arm_planner.finalize_curated_implementation_arms
)
_finalize_operator_implementations = (
    _arm_planner.finalize_operator_implementations
)


@dataclass(frozen=True, slots=True)
class _CoreDelegateMatch:
    delegate: RustFacadeDelegate
    extension_name: str
    invocation: RustFacadeInvocation


def _finalize_conversion_pair(
    pair: RustFacadeConversionPair,
    shapes: tuple[RustFacadeShape, ...],
) -> RustFacadeConversionPair:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    shape_keys = tuple(
        (pair.source_type_tag, source_shape.lanes)
        for source_shape in shapes
        if source_shape.type_tag == pair.source_type_tag
        and (
            target_shape := by_key.get(
                (pair.target_type_tag, source_shape.lanes)
            )
        )
        is not None
        and _conversion_pair_shape_is_complete(
            pair,
            source_shape,
            target_shape,
        )
    )
    return replace(pair, shape_keys=shape_keys)


def _conversion_pair_shape_is_complete(
    pair: RustFacadeConversionPair,
    source_shape: RustFacadeShape,
    target_shape: RustFacadeShape,
) -> bool:
    combinations = tuple(
        (source_representation, target_representation)
        for source_representation in source_shape.representations
        for target_representation in target_shape.representations
        if rust_facade_representations_can_coexist(
            source_representation,
            target_representation,
        )
    )
    return bool(combinations) and all(
        _has_active_surface_delegate(
            pair.delegates,
            source_shape,
            source_representation,
            (
                source_representation
                if source_representation.profile_name is not None
                else target_representation
            ).profile_name,
        )
        for source_representation, target_representation in combinations
    )


def _representation_for_profile(
    shape: RustFacadeShape,
    profile_name: str | None,
) -> RustFacadeRepresentation:
    representation = next(
        (
            item
            for item in shape.representations
            if item.profile_name == profile_name
        ),
        None,
    )
    if representation is not None:
        return representation
    return next(
        item for item in shape.representations if item.profile_name is None
    )


def _finalize_delegate_owners(
    delegates: tuple[RustFacadeDelegate, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[tuple[RustFacadeDelegate, ...], tuple[Diagnostic, ...]]:
    finalized: list[RustFacadeDelegate] = []
    diagnostics: list[Diagnostic] = []
    for delegate in delegates:
        owners: list[RustFacadeDelegateOwner] = []
        for shape in shapes:
            for representation in shape.representations:
                if delegate.profile_name is None:
                    if representation.profile_name is not None:
                        continue
                elif representation.profile_name not in {
                    None,
                    delegate.profile_name,
                }:
                    continue
                candidates = _delegate_owner_candidates(
                    delegate,
                    shape,
                    representation,
                )
                if len(candidates) > 1:
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code=(
                                "TSL-BACKEND-RUST-FACADE-AMBIGUOUS-DELEGATE-OWNER"
                            ),
                            message=(
                                f"Rust facade delegate {delegate.primitive_name!r} "
                                f"has ambiguous implementation owners for "
                                f"{shape.type_tag}x{shape.lanes} under "
                                f"{delegate.profile_name or 'fallback'}: "
                                + ", ".join(candidates)
                            ),
                        )
                    )
                    continue
                if candidates:
                    owners.append(
                        RustFacadeDelegateOwner(
                            type_tag=shape.type_tag,
                            lanes=shape.lanes,
                            representation_profile_name=(
                                representation.profile_name
                            ),
                            extension_name=candidates[0],
                        )
                    )
        finalized.append(
            replace(
                delegate,
                owners=tuple(
                    sorted(
                        owners,
                        key=lambda item: (
                            item.type_tag,
                            item.lanes,
                            item.representation_profile_name is not None,
                            item.representation_profile_name or "",
                            item.extension_name,
                        ),
                    )
                ),
            )
        )
    return tuple(finalized), tuple(diagnostics)


def _delegate_owner_candidates(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> tuple[str, ...]:
    return _delegate_owner_candidates_for_mapping(
        delegate,
        type_tag=shape.type_tag,
        total_bits=shape.total_bits,
        representation=representation,
    )


def _delegate_owner_candidates_for_mapping(
    delegate: RustFacadeDelegate,
    *,
    type_tag: str,
    total_bits: int,
    representation: RustFacadeRepresentation,
) -> tuple[str, ...]:
    vectors = tuple(
        vector for vector in delegate.vectors if vector.type_tag == type_tag
    )
    hardware_extension = representation.mapping.extension_name
    if hardware_extension is not None:
        return (
            (hardware_extension,)
            if any(
                vector.extension_name == hardware_extension
                for vector in vectors
            )
            else ()
        )

    fallback_vectors = tuple(
        vector
        for vector in vectors
        if vector.implementation_fallback
        and vector.unconditional_implementation_fallback
        and vector.uses_sized_vector
        == representation.mapping.uses_sized_vector
    )
    if not representation.mapping.uses_sized_vector:
        fallback_vectors = tuple(
            vector
            for vector in fallback_vectors
            if _fallback_vector_has_exact_width(vector, total_bits)
        )
    return tuple(
        sorted(
            {vector.extension_name for vector in fallback_vectors}
        )
    )


def _fallback_vector_has_exact_width(
    vector: RustFacadeDelegateVector,
    total_bits: int,
) -> bool:
    if vector.uses_sized_vector or vector.vector_bits_kind != "fixed":
        return False
    vector_bits = vector.vector_bits
    if vector_bits == 0:
        element_bits = scalar_bit_width(vector.type_tag)
        if element_bits is None:
            return False
        vector_bits = element_bits
    return vector_bits == total_bits


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


def _has_active_surface_delegate(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
    profile_name: str | None,
) -> bool:
    return (
        sum(
            delegate.profile_name == profile_name
            and _delegate_has_owner(delegate, shape, representation)
            for delegate in delegates
        )
        == 1
    )


def _logical_shapes(
    plan: RustStaticSelectionPlan,
    admitted_type_tags: set[str],
    bindings: tuple[RustFacadeOperationBinding, ...],
) -> tuple[RustFacadeShape, ...]:
    profiles = {profile.profile_name: profile for profile in plan.profiles}
    shapes: list[RustFacadeShape] = []
    for fallback in plan.fallback_mappings:
        if fallback.type_tag not in admitted_type_tags:
            continue
        if fallback.lanes != 1 and fallback.total_bits not in _FACADE_FIXED_WIDTHS:
            continue
        representations: list[RustFacadeRepresentation] = []
        for profile_name, profile in sorted(profiles.items()):
            mapping = next(
                (
                    item
                    for item in profile.mappings
                    if (item.type_tag, item.lanes) == (fallback.type_tag, fallback.lanes)
                ),
                None,
            )
            if mapping is not None and mapping.uses_hardware:
                representation = RustFacadeRepresentation(
                    profile_name,
                    profile.requirement,
                    profile.stronger_requirements,
                    mapping,
                )
                if all(
                    len(
                        _matching_core_delegates(
                            fallback.type_tag,
                            fallback.lanes,
                            representation,
                            requirement,
                            bindings,
                        )
                    )
                    == 1
                    for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
                ):
                    representations.append(representation)
        fallback_exclusions = tuple(
            sorted(
                {
                    RustFacadeTargetSelection(
                        representation.requirement,
                        representation.stronger_requirements,
                    )
                    for representation in representations
                    if representation.requirement is not None
                },
                key=lambda item: (
                    item.requirement.target_arch,
                    item.requirement.target_features,
                ),
            )
        )
        representations.insert(
            0,
            RustFacadeRepresentation(
                None,
                None,
                (),
                fallback,
                fallback_exclusions,
            ),
        )
        shapes.append(
            RustFacadeShape(
                fallback.type_tag,
                fallback.base_spelling,
                fallback.lanes,
                fallback.total_bits,
                tuple(representations),
            )
        )
    return tuple(sorted(shapes, key=lambda item: (item.type_tag, item.lanes)))


def _native_aliases(
    emitted_profiles: tuple[EmittedProfile, ...],
    plan: RustStaticSelectionPlan,
    admitted_type_tags: set[str],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustNativeAlias, ...]:
    emitted = {profile.profile.name: profile for profile in emitted_profiles}
    aliases: dict[str, list[RustNativeAliasSelection]] = defaultdict(list)
    spellings = {mapping.type_tag: mapping.base_spelling for mapping in plan.fallback_mappings}
    fallback_by_type: dict[str, list] = defaultdict(list)
    for mapping in plan.fallback_mappings:
        if (
            mapping.type_tag in admitted_type_tags
            and (
                mapping.lanes == 1
                or mapping.total_bits in _FACADE_FIXED_WIDTHS
            )
        ):
            fallback_by_type[mapping.type_tag].append(mapping)
    fallback_lanes: dict[str, int] = {}
    admitted_hardware_shapes = {
        (representation.profile_name, shape.type_tag, shape.lanes)
        for shape in shapes
        for representation in shape.representations
        if representation.profile_name is not None
    }
    for type_tag, mappings in fallback_by_type.items():
        fixed_mappings = tuple(mapping for mapping in mappings if mapping.lanes > 1)
        best_fallback = min(
            fixed_mappings or tuple(mappings),
            key=lambda item: (item.total_bits, item.lanes),
        )
        fallback_lanes[type_tag] = best_fallback.lanes
        aliases[type_tag].append(
            RustNativeAliasSelection(None, None, (), best_fallback.lanes)
        )
    for profile in plan.profiles:
        source_profile = emitted.get(profile.profile_name)
        if source_profile is None:
            continue
        by_type: dict[str, list] = defaultdict(list)
        for mapping in profile.mappings:
            if (
                mapping.uses_hardware
                and mapping.total_bits in _FACADE_FIXED_WIDTHS
                and (profile.profile_name, mapping.type_tag, mapping.lanes)
                in admitted_hardware_shapes
            ):
                by_type[mapping.type_tag].append(mapping)
        for type_tag, fallback_lane_count in fallback_lanes.items():
            mappings = by_type.get(type_tag, [])
            best = (
                max(
                    mappings,
                    key=lambda item: (
                        source_profile.extensions[
                            item.extension_name
                        ].metadata.native_sort_order
                        if item.extension_name in source_profile.extensions
                        and source_profile.extensions[
                            item.extension_name
                        ].metadata.native_sort_order
                        is not None
                        else 0,
                        item.total_bits,
                        item.lanes,
                    ),
                )
                if mappings
                else None
            )
            aliases[type_tag].append(
                RustNativeAliasSelection(
                    profile.profile_name,
                    profile.requirement,
                    profile.stronger_requirements,
                    best.lanes if best is not None else fallback_lane_count,
                )
            )
    for type_tag, selections in aliases.items():
        hardware_requirements = tuple(
            sorted(
                {
                    selection.requirement
                    for selection in selections
                    if selection.requirement is not None
                },
                key=lambda item: (item.target_arch, item.target_features),
            )
        )
        aliases[type_tag] = [
            (
                RustNativeAliasSelection(
                    selection.profile_name,
                    selection.requirement,
                    hardware_requirements,
                    selection.lanes,
                )
                if selection.requirement is None
                else selection
            )
            for selection in selections
        ]
    return tuple(
        RustNativeAlias(
            type_tag,
            spellings[type_tag],
            tuple(
                sorted(
                    selections,
                    key=lambda item: (item.profile_name is not None, item.profile_name or ""),
                )
            ),
        )
        for type_tag, selections in sorted(aliases.items())
    )


def _core_delegates(
    shapes: tuple[RustFacadeShape, ...],
    bindings: tuple[RustFacadeOperationBinding, ...],
    *,
    require_complete: bool,
) -> tuple[tuple[RustFacadeCoreDelegate, ...], tuple[Diagnostic, ...]]:
    delegates: list[RustFacadeCoreDelegate] = []
    diagnostics: list[Diagnostic] = []
    for shape in shapes:
        for representation in shape.representations:
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS:
                candidates = _matching_core_delegates(
                    shape.type_tag,
                    shape.lanes,
                    representation,
                    requirement,
                    bindings,
                )
                if len(candidates) != 1:
                    if require_complete:
                        diagnostics.append(
                            Diagnostic(
                                severity="error",
                                code="TSL-BACKEND-RUST-FACADE-MISSING-CORE-DELEGATE",
                                message=(
                                    f"Rust facade role {requirement.role!r} has "
                                    f"{len(candidates)} delegates for "
                                    f"{shape.type_tag}x{shape.lanes} under "
                                    f"{representation.profile_name or 'fallback'}"
                                ),
                            )
                        )
                    continue
                delegates.append(
                    RustFacadeCoreDelegate(
                        role=requirement.role,
                        type_tag=shape.type_tag,
                        lanes=shape.lanes,
                        profile_name=representation.profile_name,
                        source_primitive_name=candidates[0].delegate.primitive_name,
                        extension_name=candidates[0].extension_name,
                        invocation=candidates[0].invocation,
                    )
                )
    return (
        tuple(
            sorted(
                delegates,
                key=lambda item: (
                    item.type_tag,
                    item.lanes,
                    item.profile_name is not None,
                    item.profile_name or "",
                    item.role,
                ),
            )
        ),
        tuple(diagnostics),
    )


def _matching_core_delegates(
    type_tag: str,
    lanes: int,
    representation: RustFacadeRepresentation,
    requirement: RustFacadeCoreOperationRequirement,
    bindings: tuple[RustFacadeOperationBinding, ...],
) -> tuple[_CoreDelegateMatch, ...]:
    return tuple(
        _CoreDelegateMatch(delegate, owner_candidates[0], invocation)
        for binding in bindings
        if _operation_binding_matches_requirement(binding, requirement)
        and (
            invocation := _invocation_from_roles(
                binding.parameter_kinds,
                binding.operand_roles,
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
        )
        is not None
        and type_tag in binding.type_tags
        and binding.caller_unsafe
        == (requirement.operation in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE})
        for delegate in binding.delegates
        if delegate.profile_name == representation.profile_name
        and len(
            owner_candidates := _delegate_owner_candidates_for_mapping(
                delegate,
                type_tag=type_tag,
                total_bits=representation.mapping.total_bits,
                representation=representation,
            )
        )
        == 1
    )


def _core_facade_type_tags(
    bindings: tuple[RustFacadeOperationBinding, ...],
) -> set[str] | None:
    supported_by_role: list[set[str]] = []
    for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS:
        type_tags = {
            type_tag
            for binding in bindings
            if _operation_binding_matches_requirement(binding, requirement)
            and _invocation_from_roles(
                binding.parameter_kinds,
                binding.operand_roles,
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
            is not None
            and binding.caller_unsafe
            == (
                requirement.operation
                in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
            )
            and any(delegate.profile_name is None for delegate in binding.delegates)
            for type_tag in binding.type_tags
        }
        if not type_tags:
            return None
        supported_by_role.append(type_tags)
    return set.intersection(*supported_by_role)


def _operation_binding_matches_requirement(
    binding: RustFacadeOperationBinding,
    requirement: RustFacadeCoreOperationRequirement,
) -> bool:
    return (
        binding.operation is requirement.operation
        and binding.result_kind == requirement.result_kind
        and binding.axis_names == requirement.axis_names
        and binding.memory_access is requirement.memory_access
        and binding.memory_addressing is requirement.memory_addressing
        and binding.memory_alignment_modes == requirement.memory_alignment_modes
        and binding.mask_policy is None
        and binding.overload == requirement.overload
    )


def _finalize_curated_shapes(
    methods: list[RustCuratedMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustCuratedMethod]:
    finalized: list[RustCuratedMethod] = []
    for method in methods:
        pairs = tuple(
            finalized_pair
            for pair in method.conversion_pairs
            if (
                finalized_pair := _finalize_conversion_pair(pair, shapes)
            ).shape_keys
        )
        shape_keys = (
            tuple(
                sorted(
                    {
                        shape_key
                        for pair in pairs
                        for shape_key in pair.shape_keys
                    }
                )
            )
            if pairs
            else _surface_shape_keys(method.delegates, method.type_tags, shapes)
        )
        if shape_keys:
            finalized.append(
                replace(
                    method,
                    shape_keys=shape_keys,
                    conversion_pairs=pairs,
                )
            )
    return finalized


def _finalize_comprehensive_shapes(
    methods: list[RustComprehensiveMethod],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustComprehensiveMethod]:
    finalized: list[RustComprehensiveMethod] = []
    for method in methods:
        pairs = tuple(
            finalized_pair
            for pair in method.conversion_pairs
            if (
                finalized_pair := _finalize_conversion_pair(pair, shapes)
            ).shape_keys
        )
        shape_keys = (
            tuple(
                sorted(
                    {
                        shape_key
                        for pair in pairs
                        for shape_key in pair.shape_keys
                    }
                )
            )
            if pairs
            else _surface_shape_keys(method.delegates, method.type_tags, shapes)
        )
        if shape_keys:
            type_parameters = (
                tuple(
                    replace(
                        parameter,
                        type_tags=tuple(
                            sorted(
                                {
                                    pair.target_type_tag
                                    for pair in pairs
                                }
                            )
                        ),
                    )
                    for parameter in method.type_parameters
                )
                if pairs
                else method.type_parameters
            )
            finalized.append(
                replace(
                    method,
                    shape_keys=shape_keys,
                    conversion_pairs=pairs,
                    type_parameters=type_parameters,
                )
            )
    return finalized


def _finalize_comprehensive_coverage(
    coverage: list[RustFacadeCoverageEntry],
    methods: list[RustComprehensiveMethod],
) -> list[RustFacadeCoverageEntry]:
    admitted = {
        (
            method.source_primitive_name,
            method.signature,
            method.mask_policy,
            method.public_name,
        )
        for method in methods
    }
    return [
        (
            entry
            if entry.status is RustFacadeCoverageStatus.EXCLUDED
            or (
                entry.source_primitive_name,
                entry.signature,
                entry.mask_policy,
                entry.public_name,
            )
            in admitted
            else replace(
                entry,
                status=RustFacadeCoverageStatus.EXCLUDED,
                public_name=None,
                reason="no admitted logical shape",
            )
        )
        for entry in coverage
    ]


def _finalize_trait_shapes(
    traits: list[RustCuratedTraitImplementation],
    shapes: tuple[RustFacadeShape, ...],
) -> list[RustCuratedTraitImplementation]:
    return [
        replace(trait, shape_keys=shape_keys)
        for trait in traits
        if (
            shape_keys := _surface_shape_keys(
                trait.delegates, trait.type_tags, shapes
            )
        )
    ]


def _unique_facade_base_spelling(
    type_tag: str,
    base_spellings_by_type: dict[str, set[str]],
) -> str:
    spellings = base_spellings_by_type.get(type_tag, set())
    if len(spellings) != 1:
        raise ValueError(
            "Rust facade type mapping must provide one base spelling for "
            f"{type_tag!r}"
        )
    return next(iter(spellings))


def _surface_shape_keys(
    delegates: tuple[RustFacadeDelegate, ...],
    type_tags: tuple[str, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[tuple[str, int], ...]:
    return tuple(
        (shape.type_tag, shape.lanes)
        for shape in shapes
        if shape.type_tag in type_tags
        and all(
            _has_surface_delegate(delegates, shape, representation)
            for representation in shape.representations
        )
    )


def _has_surface_delegate(
    delegates: tuple[RustFacadeDelegate, ...],
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> bool:
    return (
        sum(
            delegate.profile_name == representation.profile_name
            and _delegate_has_owner(delegate, shape, representation)
            for delegate in delegates
        )
        == 1
    )


RUST_FACADE_CORE_OPERATION_REQUIREMENTS = (
    RustFacadeCoreOperationRequirement(
        "vector_splat",
        PrimitiveOperation.VECTOR_SPLAT,
        "v",
        ("s",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_from_array",
        PrimitiveOperation.VECTOR_FROM_ARRAY,
        "v",
        ("s[]",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_to_array",
        PrimitiveOperation.VECTOR_TO_ARRAY,
        "s[]",
        ("v",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_zero", PrimitiveOperation.VECTOR_ZERO, "v", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "extract_lane",
        PrimitiveOperation.EXTRACT_LANE,
        "s",
        ("v", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX),
    ),
    RustFacadeCoreOperationRequirement(
        "insert_lane",
        PrimitiveOperation.INSERT_LANE,
        "v",
        ("v", "usize", "s"),
        (OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE),
    ),
    RustFacadeCoreOperationRequirement(
        "load",
        PrimitiveOperation.LOAD,
        "v",
        ("cptr",),
        (OperandRole.MEMORY_SOURCE,),
        axis_names=("aligned",),
        memory_access=MemoryAccess.READ,
        memory_addressing=MemoryAddressing.CONTIGUOUS,
        memory_alignment_modes=(
            MemoryAlignment.ALIGNED,
            MemoryAlignment.UNALIGNED,
        ),
    ),
    RustFacadeCoreOperationRequirement(
        "store",
        PrimitiveOperation.STORE,
        "void",
        ("ptr", "v"),
        (OperandRole.MEMORY_DESTINATION, OperandRole.VALUE),
        axis_names=("aligned",),
        memory_access=MemoryAccess.WRITE,
        memory_addressing=MemoryAddressing.CONTIGUOUS,
        memory_alignment_modes=(
            MemoryAlignment.ALIGNED,
            MemoryAlignment.UNALIGNED,
        ),
        overload=("payload_extent", "vector", True),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_false", PrimitiveOperation.MASK_ALL_FALSE, "m", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_true", PrimitiveOperation.MASK_ALL_TRUE, "m", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_to_integral",
        PrimitiveOperation.MASK_TO_INTEGRAL,
        "im",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_from_integral",
        PrimitiveOperation.MASK_FROM_INTEGRAL,
        "m",
        ("im",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "integral_mask_test",
        PrimitiveOperation.INTEGRAL_MASK_TEST,
        "im",
        ("im", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_set_lane",
        PrimitiveOperation.MASK_SET_LANE,
        "m",
        ("m", "usize", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_population_count",
        PrimitiveOperation.MASK_POPULATION_COUNT,
        "usize",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_and",
        PrimitiveOperation.MASK_AND,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_or",
        PrimitiveOperation.MASK_OR,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_xor",
        PrimitiveOperation.MASK_XOR,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_not",
        PrimitiveOperation.MASK_NOT,
        "m",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
)


_FACADE_FIXED_WIDTHS = frozenset({128, 256, 512})
