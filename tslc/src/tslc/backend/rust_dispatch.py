"""Typed planning for optional Rust whole-algorithm runtime dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import RUST_HELPER_MANIFEST
from tslc.backend.rust_api_model import (
    RustCuratedTraitImplementation,
    RustFacadeDelegate,
    RustFacadePlan,
    RustFacadeTraitRhsKind,
    RustNativeAlias,
)
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
    RustTargetRequirement,
)
from tslc.catalog.arithmetic import ArithmeticOperation
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS


class RustDispatchAlgorithm(StrEnum):
    """A typed static-algorithm entry point admitted for runtime dispatch."""

    TRANSFORM_BINARY = "transform_binary"


class RustDispatchKernel(StrEnum):
    """The existing Rust algorithm-kernel contract required by an entry."""

    BINARY = "BinaryKernel"


class RustDispatchOperationKind(StrEnum):
    """How an operation value crosses the hardware-neutral public boundary."""

    BUILTIN_ZST = "builtin_zst"
    STATEFUL_MUTABLE = "stateful_mutable"


@dataclass(frozen=True, slots=True)
class RustDispatchPublicParameter:
    name: str
    type_spelling: str

    def __post_init__(self) -> None:
        if not self.name or not self.type_spelling:
            raise ValueError("Rust dispatch parameters require a name and type")


@dataclass(frozen=True, slots=True)
class RustDispatchPublicSignature:
    """The hardware-neutral signature shared by every candidate entry."""

    method_name: str
    type_parameters: tuple[str, ...]
    parameters: tuple[RustDispatchPublicParameter, ...]
    return_type: str

    def __post_init__(self) -> None:
        if not self.method_name or not self.parameters:
            raise ValueError("Rust dispatch signatures require a method and parameters")
        names = tuple(parameter.name for parameter in self.parameters)
        if len(set(names)) != len(names):
            raise ValueError("Rust dispatch signature parameters must be unique")


@dataclass(frozen=True, slots=True)
class RustDispatchOperationRequirement:
    """One operation-value form and its typed kernel requirement."""

    kind: RustDispatchOperationKind
    kernel: RustDispatchKernel
    public_name: str | None
    operation: ArithmeticOperation | None
    source_primitive_name: str | None

    def __post_init__(self) -> None:
        builtin_facts = (
            self.public_name,
            self.operation,
            self.source_primitive_name,
        )
        if self.kind is RustDispatchOperationKind.BUILTIN_ZST:
            if any(item is None for item in builtin_facts):
                raise ValueError(
                    "Rust built-in dispatch operations require complete typed facts"
                )
        elif any(item is not None for item in builtin_facts):
            raise ValueError(
                "Rust stateful dispatch requirements are kernel contracts, not built-ins"
            )


@dataclass(frozen=True, slots=True)
class RustDispatchEntryPoint:
    """One whole-loop candidate with a fully decided source delegate."""

    entry_index: int
    profile_name: str | None
    requirement: RustTargetRequirement | None
    mapping: RustStaticVectorMapping
    delegate_primitive_name: str

    def __post_init__(self) -> None:
        if self.entry_index < 0 or not self.delegate_primitive_name:
            raise ValueError("Rust dispatch entries require an index and delegate")
        if (self.profile_name is None) != (self.requirement is None):
            raise ValueError(
                "Rust dispatch hardware profiles and requirements must occur together"
            )
        if self.requirement is None and self.mapping.uses_hardware:
            raise ValueError("Rust dispatch baselines cannot use hardware storage")
        if self.requirement is not None and not self.mapping.uses_hardware:
            raise ValueError("Rust dispatch hardware entries require hardware storage")


@dataclass(frozen=True, slots=True)
class RustDispatchSlot:
    """One operation/type slot with mandatory generic coverage."""

    algorithm: RustDispatchAlgorithm
    operation: RustDispatchOperationRequirement
    type_tag: str
    base_spelling: str
    public_signature: RustDispatchPublicSignature
    ordered_candidates: tuple[RustDispatchEntryPoint, ...]
    generic_baseline: RustDispatchEntryPoint

    def __post_init__(self) -> None:
        if not self.type_tag or not self.base_spelling:
            raise ValueError("Rust dispatch slots require complete scalar type facts")
        if self.generic_baseline.entry_index != 0:
            raise ValueError("Rust dispatch generic baselines must occupy entry zero")
        if self.generic_baseline.requirement is not None:
            raise ValueError("Rust dispatch slots require an unconditional baseline")
        indices = tuple(
            entry.entry_index
            for entry in (*self.ordered_candidates, self.generic_baseline)
        )
        if len(set(indices)) != len(indices):
            raise ValueError("Rust dispatch entry indices must be unique")
        if any(entry.requirement is None for entry in self.ordered_candidates):
            raise ValueError("Rust dispatch candidates must be hardware-guarded")
        if any(
            (entry.mapping.type_tag, entry.mapping.base_spelling)
            != (self.type_tag, self.base_spelling)
            for entry in (*self.ordered_candidates, self.generic_baseline)
        ):
            raise ValueError("Rust dispatch entries must preserve the slot scalar type")


@dataclass(frozen=True, slots=True)
class RustDispatchPlan:
    """Frozen whole-algorithm dispatch facts consumed by Rust rendering."""

    slots: tuple[RustDispatchSlot, ...]

    def __post_init__(self) -> None:
        keys = tuple(
            (
                slot.algorithm,
                slot.operation.kind,
                slot.operation.operation,
                slot.type_tag,
            )
            for slot in self.slots
        )
        if len(set(keys)) != len(keys):
            raise ValueError("Rust dispatch slots must be unique")

    @property
    def prototype_slots(self) -> tuple[RustDispatchSlot, RustDispatchSlot] | None:
        builtins = tuple(
            slot
            for slot in self.slots
            if slot.operation.kind is RustDispatchOperationKind.BUILTIN_ZST
        )
        stateful = tuple(
            slot
            for slot in self.slots
            if slot.operation.kind is RustDispatchOperationKind.STATEFUL_MUTABLE
        )
        for builtin in builtins:
            matching = next(
                (
                    slot
                    for slot in stateful
                    if (
                        slot.algorithm,
                        slot.type_tag,
                        slot.ordered_candidates,
                        slot.generic_baseline,
                    )
                    == (
                        builtin.algorithm,
                        builtin.type_tag,
                        builtin.ordered_candidates,
                        builtin.generic_baseline,
                    )
                ),
                None,
            )
            if matching is not None:
                return builtin, matching
        return None


EMPTY_RUST_DISPATCH_PLAN = RustDispatchPlan(())


def plan_rust_dispatch(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    facade: RustFacadePlan,
) -> RustDispatchPlan:
    """Plan the minimal binary/stateful prototype from finalized typed facts."""

    addition = _addition_trait(facade)
    if addition is None or not _fallback_supports_algorithms(static_selection):
        return EMPTY_RUST_DISPATCH_PLAN
    candidate = _prototype_candidate(
        profiles,
        static_selection,
        facade,
        addition,
    )
    if candidate is None:
        return EMPTY_RUST_DISPATCH_PLAN
    type_tag, base_spelling, baseline, hardware = candidate
    signature = RustDispatchPublicSignature(
        RustDispatchAlgorithm.TRANSFORM_BINARY.value,
        ("Op",),
        (
            RustDispatchPublicParameter("operation", "Op"),
            RustDispatchPublicParameter("left", f"&[{base_spelling}]"),
            RustDispatchPublicParameter("right", f"&[{base_spelling}]"),
            RustDispatchPublicParameter("output", f"&mut [{base_spelling}]"),
        ),
        "()",
    )
    builtin = RustDispatchOperationRequirement(
        RustDispatchOperationKind.BUILTIN_ZST,
        RustDispatchKernel.BINARY,
        next(
            value.public_name
            for value in facade.operation_values
            if value.operation is ArithmeticOperation.ADDITION
        ),
        ArithmeticOperation.ADDITION,
        addition.source_primitive_name,
    )
    stateful = RustDispatchOperationRequirement(
        RustDispatchOperationKind.STATEFUL_MUTABLE,
        RustDispatchKernel.BINARY,
        None,
        None,
        None,
    )
    slot_args = (
        RustDispatchAlgorithm.TRANSFORM_BINARY,
        type_tag,
        base_spelling,
        signature,
        (hardware,),
        baseline,
    )
    return RustDispatchPlan(
        (
            RustDispatchSlot(slot_args[0], builtin, *slot_args[1:]),
            RustDispatchSlot(slot_args[0], stateful, *slot_args[1:]),
        )
    )


def validate_rust_dispatch_plan(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    facade: RustFacadePlan,
    plan: RustDispatchPlan,
) -> None:
    """Reject stale or foreign runtime-dispatch facts before rendering."""

    if plan != plan_rust_dispatch(profiles, static_selection, facade):
        raise ValueError("Rust dispatch plan does not match the emitted project facts")


def _addition_trait(
    facade: RustFacadePlan,
) -> RustCuratedTraitImplementation | None:
    operation_value = next(
        (
            value
            for value in facade.operation_values
            if value.operation is ArithmeticOperation.ADDITION
        ),
        None,
    )
    if operation_value is None:
        return None
    return next(
        (
            trait
            for trait in facade.trait_implementations
            if trait.operation is ArithmeticOperation.ADDITION
            and trait.source_primitive_name == operation_value.source_primitive_name
            and trait.rhs_kind is RustFacadeTraitRhsKind.SAME_TYPE
        ),
        None,
    )


def _fallback_supports_algorithms(
    static_selection: RustStaticSelectionPlan,
) -> bool:
    return RUST_HELPER_MANIFEST.supports(
        "algorithm",
        static_selection.fallback_module.specializations_by_primitive(),
    )


def _prototype_candidate(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
    facade: RustFacadePlan,
    addition: RustCuratedTraitImplementation,
) -> tuple[
    str,
    str,
    RustDispatchEntryPoint,
    RustDispatchEntryPoint,
] | None:
    profiles_by_name = {profile.profile.name: profile for profile in profiles}
    aliases = {alias.type_tag: alias for alias in facade.native_aliases}
    choices: list[
        tuple[
            tuple[int, str, int, int, str],
            str,
            str,
            RustDispatchEntryPoint,
            RustDispatchEntryPoint,
        ]
    ] = []
    for type_tag in addition.type_tags:
        alias = aliases.get(type_tag)
        if alias is None:
            continue
        baseline = _baseline_entry(static_selection, addition, alias)
        if baseline is None:
            continue
        for selection in alias.selections:
            if selection.profile_name is None or selection.requirement is None:
                continue
            emitted = profiles_by_name.get(selection.profile_name)
            static_profile = static_selection.profile(selection.profile_name)
            delegate = _delegate_for(
                addition.delegates,
                selection.profile_name,
                type_tag,
            )
            if (
                emitted is None
                or static_profile is None
                or delegate is None
                or not RUST_HELPER_MANIFEST.supports(
                    "algorithm", emitted.specializations("rust")
                )
                or not _runtime_detectable(selection.requirement)
            ):
                continue
            mapping = next(
                (
                    item
                    for item in static_profile.mappings
                    if item.type_tag == type_tag
                    and item.lanes == selection.lanes
                    and item.uses_hardware
                ),
                None,
            )
            if mapping is None:
                continue
            info = SCALAR_TYPE_INFOS.get(type_tag)
            type_preference = (
                0
                if info is not None
                and info.bit_width == 32
                and info.signed
                and not info.floating
                else 1
            )
            choices.append(
                (
                    (
                        type_preference,
                        selection.requirement.target_arch,
                        -len(selection.requirement.target_features),
                        -selection.lanes,
                        selection.profile_name,
                    ),
                    type_tag,
                    alias.base_spelling,
                    baseline,
                    RustDispatchEntryPoint(
                        1,
                        selection.profile_name,
                        selection.requirement,
                        mapping,
                        delegate.primitive_name,
                    ),
                )
            )
    if not choices:
        return None
    _preference, type_tag, base_spelling, baseline, hardware = min(choices)
    return type_tag, base_spelling, baseline, hardware


def _baseline_entry(
    static_selection: RustStaticSelectionPlan,
    addition: RustCuratedTraitImplementation,
    alias: RustNativeAlias,
) -> RustDispatchEntryPoint | None:
    selection = next(
        (item for item in alias.selections if item.profile_name is None),
        None,
    )
    delegate = _delegate_for(addition.delegates, None, alias.type_tag)
    if selection is None or delegate is None:
        return None
    mapping = next(
        (
            item
            for item in static_selection.fallback_mappings
            if item.type_tag == alias.type_tag and item.lanes == selection.lanes
        ),
        None,
    )
    if mapping is None:
        return None
    return RustDispatchEntryPoint(
        0,
        None,
        None,
        mapping,
        delegate.primitive_name,
    )


def _delegate_for(
    delegates: tuple[RustFacadeDelegate, ...],
    profile_name: str | None,
    type_tag: str,
) -> RustFacadeDelegate | None:
    return next(
        (
            delegate
            for delegate in delegates
            if delegate.profile_name == profile_name
            and any(vector.type_tag == type_tag for vector in delegate.vectors)
        ),
        None,
    )


_RUNTIME_DETECTABLE_FEATURES = {
    "x86": frozenset(
        {
            "adx",
            "aes",
            "avx",
            "avx2",
            "bmi1",
            "bmi2",
            "fma",
            "lzcnt",
            "pclmulqdq",
            "popcnt",
            "rdrand",
            "rdseed",
            "sha",
            "sse",
            "sse2",
            "sse3",
            "sse4.1",
            "sse4.2",
            "ssse3",
        }
    ),
    "x86_64": frozenset(
        {
            "adx",
            "aes",
            "avx",
            "avx2",
            "bmi1",
            "bmi2",
            "fma",
            "lzcnt",
            "pclmulqdq",
            "popcnt",
            "rdrand",
            "rdseed",
            "sha",
            "sse",
            "sse2",
            "sse3",
            "sse4.1",
            "sse4.2",
            "ssse3",
        }
    ),
    "aarch64": frozenset(
        {
            "aes",
            "asimd",
            "bf16",
            "crc",
            "dotprod",
            "fhm",
            "fp",
            "fp16",
            "i8mm",
            "lse",
            "neon",
            "pmull",
            "sha2",
            "sha3",
            "sve",
            "sve2",
        }
    ),
}


def _runtime_detectable(requirement: RustTargetRequirement) -> bool:
    supported = _RUNTIME_DETECTABLE_FEATURES.get(requirement.target_arch)
    return supported is not None and set(requirement.target_features) <= supported


__all__ = (
    "EMPTY_RUST_DISPATCH_PLAN",
    "RustDispatchAlgorithm",
    "RustDispatchEntryPoint",
    "RustDispatchKernel",
    "RustDispatchOperationKind",
    "RustDispatchOperationRequirement",
    "RustDispatchPlan",
    "RustDispatchPublicParameter",
    "RustDispatchPublicSignature",
    "RustDispatchSlot",
    "plan_rust_dispatch",
    "validate_rust_dispatch_plan",
)
