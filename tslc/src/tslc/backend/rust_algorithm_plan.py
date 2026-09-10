"""Plan profile-local Rust algorithm support before target formatting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import (
    PrimitiveRequirement,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.primitive_facade import plan_contiguous_memory_primitive_facades
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.backend.rust_facades import (
    RustAlgorithmPrimitiveFacade,
    plan_rust_algorithm_primitive_facades,
)
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
)
from tslc.catalog.memory import MemoryAccess
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class RustAlgorithmImplTarget:
    """One Rust vector family receiving profile algorithm trait impls."""

    type_parameters: str
    vector: str

    def __post_init__(self) -> None:
        if not self.type_parameters or not self.vector:
            raise ValueError("Rust algorithm implementation targets must be complete")


@dataclass(frozen=True, slots=True)
class RustAlgorithmHelperAdmission:
    """One optional helper feature and its exact missing source requirements."""

    feature_name: str
    missing_requirements: tuple[PrimitiveRequirement, ...]

    def __post_init__(self) -> None:
        if not self.feature_name:
            raise ValueError("Rust algorithm helper admissions require a feature")

    @property
    def supported(self) -> bool:
        return not self.missing_requirements


@dataclass(frozen=True, slots=True)
class RustAlgorithmSelectedLoadTarget:
    """One exact static mapping admitted for a hardware selected-load impl."""

    mapping: RustStaticVectorMapping
    use_gather_narrow: bool

    def __post_init__(self) -> None:
        if not self.mapping.uses_hardware:
            raise ValueError("Rust selected-load targets require hardware mappings")


@dataclass(frozen=True, slots=True)
class RustAlgorithmSupportGap:
    """One missing mandatory primitive requirement for an algorithm module."""

    profile_name: str
    requirement: PrimitiveRequirement
    reason: str

    def __post_init__(self) -> None:
        if not self.profile_name or not self.reason:
            raise ValueError("Rust algorithm support gaps require context")


@dataclass(frozen=True, slots=True)
class RustAlgorithmProfilePlan:
    """All decided facts needed to format one profile-local algorithm module."""

    profile_name: str
    is_fallback: bool
    static_mappings: tuple[RustStaticVectorMapping, ...]
    fixed_mappings: tuple[RustStaticVectorMapping, ...]
    native_mappings: tuple[RustStaticVectorMapping, ...]
    implementation_targets: tuple[RustAlgorithmImplTarget, ...]
    read_facade: RustAlgorithmPrimitiveFacade | None
    write_facade: RustAlgorithmPrimitiveFacade | None
    helper_admissions: tuple[RustAlgorithmHelperAdmission, ...]
    selected_load_targets: tuple[RustAlgorithmSelectedLoadTarget, ...]
    primitive_facades: tuple[RustAlgorithmPrimitiveFacade, ...]
    requires_rebind: bool
    unsupported: tuple[RustAlgorithmSupportGap, ...]

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("Rust algorithm profile plans require an identity")
        if any(mapping not in self.static_mappings for mapping in self.native_mappings):
            raise ValueError(
                "Rust algorithm native mappings must reuse exact static mappings"
            )
        if any(mapping not in self.static_mappings for mapping in self.fixed_mappings):
            raise ValueError(
                "Rust algorithm fixed mappings must reuse exact static mappings"
            )
        if any(mapping.uses_sized_vector for mapping in self.fixed_mappings):
            raise ValueError("Rust algorithm fixed policies require fixed mappings")
        helper_names = tuple(item.feature_name for item in self.helper_admissions)
        if len(set(helper_names)) != len(helper_names):
            raise ValueError("Rust algorithm helper admissions must be unique")
        if any(gap.profile_name != self.profile_name for gap in self.unsupported):
            raise ValueError("Rust algorithm support gaps must match their profile")
        if (
            self.read_facade is not None
            and self.read_facade.memory_access is not MemoryAccess.READ
        ):
            raise ValueError("Rust algorithm read binding has the wrong access")
        if (
            self.write_facade is not None
            and self.write_facade.memory_access is not MemoryAccess.WRITE
        ):
            raise ValueError("Rust algorithm write binding has the wrong access")
        selected_mappings = tuple(
            target.mapping for target in self.selected_load_targets
        )
        if len(set(selected_mappings)) != len(selected_mappings) or any(
            mapping not in self.static_mappings for mapping in selected_mappings
        ):
            raise ValueError(
                "Rust selected-load targets must uniquely reuse static mappings"
            )
        expected_rebind = any(
            facade.requires_rebind for facade in self.primitive_facades
        )
        if self.requires_rebind != expected_rebind:
            raise ValueError("Rust algorithm rebind admission disagrees with facades")
        if self.supported != (
            self.read_facade is not None and self.write_facade is not None
        ):
            raise ValueError(
                "Rust algorithm support must match contiguous memory bindings"
            )

    @property
    def supported(self) -> bool:
        return not self.unsupported

    def helper(self, feature_name: str) -> RustAlgorithmHelperAdmission:
        try:
            return next(
                item
                for item in self.helper_admissions
                if item.feature_name == feature_name
            )
        except StopIteration as exc:
            raise KeyError(
                f"Rust algorithm plan has no helper feature {feature_name!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class RustAlgorithmPlan:
    """Deterministic Rust algorithm support for emitted profiles and fallback."""

    profiles: tuple[RustAlgorithmProfilePlan, ...]
    fallback: RustAlgorithmProfilePlan

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError(
                "Rust algorithm profile plans must be sorted and uniquely named"
            )
        if any(profile.is_fallback for profile in self.profiles):
            raise ValueError("Only the Rust algorithm fallback may be marked fallback")
        if not self.fallback.is_fallback:
            raise ValueError("Rust algorithm plans require one marked fallback")
        if self.fallback.profile_name in names:
            raise ValueError("Rust algorithm fallback identity must be unique")

    def profile(self, profile_name: str) -> RustAlgorithmProfilePlan | None:
        return next(
            (profile for profile in self.profiles if profile.profile_name == profile_name),
            None,
        )


def plan_rust_algorithm(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> RustAlgorithmPlan:
    """Finalize algorithm support from lowered facts and exact static mappings."""

    profiles_by_name = {profile.profile.name: profile for profile in profiles}
    if len(profiles_by_name) != len(profiles):
        raise ValueError("Rust algorithm planning requires unique emitted profiles")
    static_names = {selection.profile_name for selection in static_selection.profiles}
    if not static_names <= set(profiles_by_name):
        raise ValueError("Rust algorithm static selection is foreign to the profiles")
    planned_profiles: list[RustAlgorithmProfilePlan] = []
    for profile_name in sorted(profiles_by_name):
        selection = static_selection.profile(profile_name)
        planned_profiles.append(
            _plan_profile(
                profile_name,
                profiles_by_name[profile_name].specializations("rust"),
                (
                    selection.mappings
                    if selection is not None
                    else static_selection.fallback_mappings
                ),
                (
                    selection.native_mappings
                    if selection is not None
                    else static_selection.fallback_native_mappings
                ),
                is_fallback=False,
            )
        )
    fallback_module = static_selection.fallback_module
    fallback = _plan_profile(
        fallback_module.metadata_profile_name,
        fallback_module.specializations_by_primitive(),
        static_selection.fallback_mappings,
        static_selection.fallback_native_mappings,
        is_fallback=True,
    )
    return RustAlgorithmPlan(tuple(planned_profiles), fallback)


def _plan_profile(
    profile_name: str,
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    static_mappings: tuple[RustStaticVectorMapping, ...],
    native_mappings: tuple[RustStaticVectorMapping, ...],
    *,
    is_fallback: bool,
) -> RustAlgorithmProfilePlan:
    memory = plan_contiguous_memory_primitive_facades(by_primitive)
    unsupported = tuple(
        RustAlgorithmSupportGap(
            profile_name=profile_name,
            requirement=PrimitiveRequirement(
                "load" if access is MemoryAccess.READ else "store"
            ),
            reason=f"missing contiguous {access.value} primitive facade",
        )
        for access in memory.missing_accesses
    )
    helper_admissions = tuple(
        RustAlgorithmHelperAdmission(
            feature.name,
            RUST_HELPER_MANIFEST.missing_requirements(feature.name, by_primitive),
        )
        for feature in RUST_HELPER_MANIFEST.features
    )
    primitive_facades = plan_rust_algorithm_primitive_facades(
        by_primitive,
        reserved_names=RUST_ALGORITHM_RESERVED_NAMES,
    )
    read_facade = _memory_primitive_facade(
        primitive_facades,
        MemoryAccess.READ,
        memory.read.primitive_name if memory.read is not None else None,
    )
    write_facade = _memory_primitive_facade(
        primitive_facades,
        MemoryAccess.WRITE,
        memory.write.primitive_name if memory.write is not None else None,
    )
    return RustAlgorithmProfilePlan(
        profile_name=profile_name,
        is_fallback=is_fallback,
        static_mappings=static_mappings,
        fixed_mappings=tuple(
            mapping for mapping in static_mappings if not mapping.uses_sized_vector
        ),
        native_mappings=native_mappings,
        implementation_targets=_implementation_targets(static_mappings),
        read_facade=read_facade,
        write_facade=write_facade,
        helper_admissions=helper_admissions,
        selected_load_targets=_selected_load_targets(
            static_mappings,
            by_primitive,
            helper_admissions,
        ),
        primitive_facades=primitive_facades,
        requires_rebind=any(facade.requires_rebind for facade in primitive_facades),
        unsupported=unsupported,
    )


def _memory_primitive_facade(
    facades: tuple[RustAlgorithmPrimitiveFacade, ...],
    access: MemoryAccess,
    primitive_name: str | None,
) -> RustAlgorithmPrimitiveFacade | None:
    if primitive_name is None:
        return None
    matches = tuple(
        facade
        for facade in facades
        if facade.primitive_name == primitive_name
        and facade.memory_access is access
    )
    if len(matches) != 1:
        raise ValueError("Rust algorithm memory facade planning is inconsistent")
    return matches[0]


def _implementation_targets(
    mappings: tuple[RustStaticVectorMapping, ...],
) -> tuple[RustAlgorithmImplTarget, ...]:
    concrete_tags = sorted(
        {
            mapping.extension_tag_spelling
            for mapping in mappings
            if mapping.extension_tag_spelling is not None
        }
    )
    return (
        RustAlgorithmImplTarget("T", "Simd<T, Scalar>"),
        RustAlgorithmImplTarget("T, const N: usize", "Simd<T, Generic<N>>"),
        *(
            RustAlgorithmImplTarget("T", f"Simd<T, super::{tag}>")
            for tag in concrete_tags
        ),
    )


def _selected_load_targets(
    mappings: tuple[RustStaticVectorMapping, ...],
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    admissions: tuple[RustAlgorithmHelperAdmission, ...],
) -> tuple[RustAlgorithmSelectedLoadTarget, ...]:
    selected_load = next(
        item for item in admissions if item.feature_name == "selected_load"
    )
    if not selected_load.supported:
        return ()
    gather_requirement = RUST_HELPER_MANIFEST.requirements("gather_narrow")[0]
    gather_vectors = {
        (spec.extension_name, spec.base_type_spelling)
        for spec in RUST_HELPER_MANIFEST.matching_specializations(
            gather_requirement, by_primitive
        )
    }
    array_vector_sets = [
        {
            (spec.extension_name, spec.base_type_spelling)
            for spec in RUST_HELPER_MANIFEST.matching_specializations(
                requirement, by_primitive
            )
        }
        for requirement in RUST_HELPER_MANIFEST.requirements("selected_load")
    ]
    array_vectors = (
        set.intersection(*array_vector_sets) if array_vector_sets else set()
    )
    admitted_vectors = gather_vectors | array_vectors
    return tuple(
        RustAlgorithmSelectedLoadTarget(
            mapping,
            (mapping.extension_name, mapping.base_spelling) in gather_vectors,
        )
        for mapping in sorted(
            (
                item
                for item in mappings
                if item.uses_hardware
                and (item.extension_name, item.base_spelling) in admitted_vectors
            ),
            key=lambda item: (
                item.extension_name or "",
                item.type_tag,
                item.vector_spelling,
            ),
        )
    )


__all__ = (
    "RustAlgorithmHelperAdmission",
    "RustAlgorithmImplTarget",
    "RustAlgorithmPlan",
    "RustAlgorithmProfilePlan",
    "RustAlgorithmSelectedLoadTarget",
    "RustAlgorithmSupportGap",
    "plan_rust_algorithm",
)
