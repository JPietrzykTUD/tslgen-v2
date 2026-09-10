"""Plan C++ whole-array algorithm admission before project rendering."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.algorithm_admission import (
    AlgorithmFamilyRequirements,
    AlgorithmFormRequirements,
    AlgorithmProfileAdmission,
    AlgorithmRequirementGap,
    BackendAlgorithmRequirements,
    plan_algorithm_profile_admission,
)
from tslc.backend.algorithm_surface import (
    ALGORITHM_SURFACE_FAMILIES,
    AlgorithmCallableForm,
    AlgorithmSemanticFamily,
    AlgorithmShape,
    AlgorithmSurfaceFamily,
)
from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_form_support,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import CPP_HELPER_MANIFEST, PrimitiveRequirement
from tslc.names import identifier_slug


def _cpp_family_features(family: AlgorithmSurfaceFamily) -> tuple[str, ...]:
    """Primitive-backed helpers called by one C++ algorithm family."""

    features: list[str] = []
    if family.semantic_family not in {
        AlgorithmSemanticFamily.UTILITY,
        AlgorithmSemanticFamily.ITERATION,
    }:
        features.append("contiguous_read")
    if family.shape in {AlgorithmShape.SELECTED, AlgorithmShape.SELECTED_INDICES}:
        features.append("selected_read")
    if family.semantic_family is AlgorithmSemanticFamily.PREDICATE:
        features.extend(("integral_mask", "mask_from_integral"))
    if family.semantic_family is AlgorithmSemanticFamily.COUNT:
        features.append("integral_mask")
        if family.shape in {AlgorithmShape.PLAIN, AlgorithmShape.MASKED}:
            features.append("mask_population_count")
    if family.semantic_family is AlgorithmSemanticFamily.SELECT:
        features.append("integral_mask")
        if family.shape in {AlgorithmShape.PLAIN, AlgorithmShape.MASKED}:
            features.extend(
                ("contiguous_write", "compaction", "mask_population_count")
            )
    if family.semantic_family is AlgorithmSemanticFamily.TRANSFORM:
        features.append("contiguous_write")
        if family.shape is AlgorithmShape.WHERE:
            features.append("masked_write")
    if family.shape in {AlgorithmShape.MASKED, AlgorithmShape.WHERE}:
        features.extend(("integral_mask", "mask_from_integral"))
    if (
        family.shape is AlgorithmShape.MASKED
        and family.semantic_family
        in {AlgorithmSemanticFamily.COUNT, AlgorithmSemanticFamily.SELECT}
    ):
        features.append("mask_intersection")
    return tuple(dict.fromkeys(features))


CPP_ALGORITHM_REQUIREMENTS = BackendAlgorithmRequirements(
    "cpp",
    CPP_HELPER_MANIFEST,
    tuple(
        AlgorithmFamilyRequirements(
            family,
            tuple(
                AlgorithmFormRequirements(
                    form, _cpp_family_features(family)
                )
                for form in family.callable_forms
            ),
        )
        for family in ALGORITHM_SURFACE_FAMILIES
    ),
)


@dataclass(frozen=True, slots=True)
class CppUnavailableAlgorithmHelpers:
    """One profile guard and the exact missing helpers needed for header lookup."""

    profile_name: str
    profile_macro: str
    requirements: tuple[PrimitiveRequirement, ...]

    def __post_init__(self) -> None:
        if not self.profile_name or not self.profile_macro or not self.requirements:
            raise ValueError("unavailable C++ algorithm helpers require context")
        if len(set(self.requirements)) != len(self.requirements):
            raise ValueError("unavailable C++ algorithm helpers must be unique")


@dataclass(frozen=True, slots=True)
class CppAlgorithmFamilyHeader:
    """Generated public/detail headers owned by one semantic family."""

    semantic_family: AlgorithmSemanticFamily
    public_header: str
    detail_header: str | None

    def __post_init__(self) -> None:
        family_name = self.semantic_family.value
        if self.public_header != f"tsl_algorithm_{family_name}.hpp":
            raise ValueError("C++ algorithm public header must follow family identity")
        expected_detail = (
            None
            if self.semantic_family is AlgorithmSemanticFamily.UTILITY
            else f"tsl_algorithm_detail_{family_name}.hpp"
        )
        if self.detail_header != expected_detail:
            raise ValueError("C++ algorithm detail header must follow family identity")


@dataclass(frozen=True, slots=True)
class CppAlgorithmAdmissionPlan:
    """Project-wide C++ forms supported by every selectable profile."""

    profiles: tuple[AlgorithmProfileAdmission, ...]
    admitted_families: tuple[AlgorithmSurfaceFamily, ...]
    admitted_forms: tuple[AlgorithmCallableForm, ...]
    family_headers: tuple[CppAlgorithmFamilyHeader, ...]
    unavailable_helpers: tuple[CppUnavailableAlgorithmHelpers, ...]

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError(
                "C++ algorithm profile admissions must be sorted and unique"
            )
        if any(profile.backend_id != "cpp" for profile in self.profiles):
            raise ValueError("C++ algorithm admissions must use the C++ backend")
        unavailable_names = tuple(
            group.profile_name for group in self.unavailable_helpers
        )
        if (
            unavailable_names != tuple(sorted(unavailable_names))
            or len(set(unavailable_names)) != len(unavailable_names)
            or any(name not in names for name in unavailable_names)
        ):
            raise ValueError(
                "unavailable C++ helpers must uniquely follow planned profile order"
            )
        admitted_form_set = frozenset(self.admitted_forms)
        expected_families = tuple(
            family
            for family in ALGORITHM_SURFACE_FAMILIES
            if any(form in admitted_form_set for form in family.callable_forms)
        )
        if self.admitted_families != expected_families:
            raise ValueError("C++ admitted families must derive from admitted forms")
        expected_header_families = tuple(
            family
            for family in _CPP_SPLIT_ALGORITHM_SEMANTIC_FAMILIES
            if family in self.admitted_semantic_families
        )
        if tuple(
            header.semantic_family for header in self.family_headers
        ) != expected_header_families:
            raise ValueError(
                "C++ algorithm family headers must follow admitted semantic order"
            )

    @property
    def supported(self) -> bool:
        return bool(self.admitted_forms)

    @property
    def admitted_family_names(self) -> tuple[str, ...]:
        return tuple(family.name for family in self.admitted_families)

    @property
    def admitted_form_names(self) -> tuple[str, ...]:
        return tuple(form.name for form in self.admitted_forms)

    @property
    def admitted_semantic_families(self) -> tuple[AlgorithmSemanticFamily, ...]:
        admitted = frozenset(
            family.semantic_family for family in self.admitted_families
        )
        return tuple(
            family for family in AlgorithmSemanticFamily if family in admitted
        )

    @property
    def remaining_semantic_families(self) -> tuple[AlgorithmSemanticFamily, ...]:
        split = frozenset(
            header.semantic_family for header in self.family_headers
        )
        return tuple(
            family for family in self.admitted_semantic_families if family not in split
        )

    @property
    def gaps(self) -> tuple[AlgorithmRequirementGap, ...]:
        return tuple(gap for profile in self.profiles for gap in profile.gaps)

    def profile(self, profile_name: str) -> AlgorithmProfileAdmission | None:
        return next(
            (profile for profile in self.profiles if profile.profile_name == profile_name),
            None,
        )


def plan_cpp_algorithm_admission(
    profiles: tuple[EmittedProfile, ...],
) -> CppAlgorithmAdmissionPlan:
    """Admit only forms whose exact helper groups exist in every profile."""

    profile_plans = tuple(
        plan_algorithm_profile_admission(
            profile.profile.name,
            profile.specializations("cpp"),
            CPP_ALGORITHM_REQUIREMENTS,
            cpp_algorithm_form_support,
        )
        for profile in sorted(profiles, key=lambda item: item.profile.name)
    )
    admitted_forms = tuple(
        form
        for family in ALGORITHM_SURFACE_FAMILIES
        for form in family.callable_forms
        if cpp_algorithm_form_support(form).supported
        if profile_plans
        and all(
            form in profile.family(family.name).admitted_forms
            for profile in profile_plans
        )
    )
    admitted_form_set = frozenset(admitted_forms)
    admitted_families = tuple(
        family
        for family in ALGORITHM_SURFACE_FAMILIES
        if any(form in admitted_form_set for form in family.callable_forms)
    )
    admitted_semantic_families = frozenset(
        family.semantic_family for family in admitted_families
    )
    return CppAlgorithmAdmissionPlan(
        profile_plans,
        admitted_families,
        admitted_forms,
        tuple(
            _cpp_algorithm_family_header(family)
            for family in _CPP_SPLIT_ALGORITHM_SEMANTIC_FAMILIES
            if family in admitted_semantic_families
        ),
        tuple(
            CppUnavailableAlgorithmHelpers(
                profile.profile_name,
                f"TSL_PROFILE_{identifier_slug(profile.profile_name).upper()}",
                tuple(
                    dict.fromkeys(gap.requirement for gap in profile.gaps)
                ),
            )
            for profile in profile_plans
            if profile.gaps
        ),
    )


def _cpp_algorithm_family_header(
    family: AlgorithmSemanticFamily,
) -> CppAlgorithmFamilyHeader:
    family_name = family.value
    return CppAlgorithmFamilyHeader(
        family,
        f"tsl_algorithm_{family_name}.hpp",
        None
        if family is AlgorithmSemanticFamily.UTILITY
        else f"tsl_algorithm_detail_{family_name}.hpp",
    )


_CPP_SPLIT_ALGORITHM_SEMANTIC_FAMILIES = (
    AlgorithmSemanticFamily.UTILITY,
    AlgorithmSemanticFamily.ITERATION,
    AlgorithmSemanticFamily.PREDICATE,
    AlgorithmSemanticFamily.COUNT,
    AlgorithmSemanticFamily.SELECT,
)


__all__ = (
    "CPP_ALGORITHM_REQUIREMENTS",
    "CppAlgorithmAdmissionPlan",
    "CppAlgorithmFamilyHeader",
    "CppUnavailableAlgorithmHelpers",
    "plan_cpp_algorithm_admission",
)
