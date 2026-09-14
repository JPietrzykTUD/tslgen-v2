"""Plan profile-local Rust algorithm support before target formatting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.algorithm_admission import (
    AlgorithmFamilyRequirements,
    AlgorithmFormRequirements,
    AlgorithmHelperAdmission,
    AlgorithmProfileAdmission,
    AlgorithmRequirementGap,
    BackendAlgorithmRequirements,
    plan_algorithm_profile_admission,
)
from tslc.backend.algorithm_surface import (
    ALGORITHM_SURFACE_FAMILIES,
    AlgorithmCallableForm,
    AlgorithmMaskForm,
    AlgorithmSemanticFamily,
    AlgorithmShape,
    AlgorithmSurfaceFamily,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.helper_requirements import (
    BackendHelperPlan,
    PrimitiveRequirement,
    RUST_HELPER_MANIFEST,
)
from tslc.backend.primitive_facade import plan_contiguous_memory_primitive_facades
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.backend.rust_algorithm_public_declarations import (
    rust_algorithm_form_support,
)
from tslc.backend.rust_facades import (
    RustAlgorithmPrimitiveFacade,
    plan_rust_algorithm_helper_facade,
    plan_rust_algorithm_primitive_facades,
)
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
)
from tslc.catalog.memory import MemoryAccess
from tslc.catalog.semantics import ResolvedPrimitiveProvider
from tslc.lower.lowerer import LoweredSpecialization


def _rust_family_features(family: AlgorithmSurfaceFamily) -> tuple[str, ...]:
    """Primitive-backed support traits called by one Rust algorithm family."""

    features: list[str] = []
    if family.shape in {AlgorithmShape.SELECTED, AlgorithmShape.SELECTED_INDICES}:
        features.append("selected_load")
    if family.semantic_family is AlgorithmSemanticFamily.PREDICATE:
        features.append("integral_mask")
    if family.semantic_family is AlgorithmSemanticFamily.COUNT:
        features.append("integral_mask")
    if family.semantic_family is AlgorithmSemanticFamily.SELECT:
        features.append("integral_mask")
        if family.shape in {AlgorithmShape.PLAIN, AlgorithmShape.MASKED}:
            features.extend(("compress_store", "mask_population_count"))
    if (
        family.semantic_family is AlgorithmSemanticFamily.TRANSFORM
        and family.shape is AlgorithmShape.WHERE
    ):
        features.append("masked_store")
    if family.shape is AlgorithmShape.WHERE or (
        family.shape is AlgorithmShape.MASKED
        and family.semantic_family
        in {
            AlgorithmSemanticFamily.SELECT,
            AlgorithmSemanticFamily.TRANSFORM,
            AlgorithmSemanticFamily.CONSUME,
            AlgorithmSemanticFamily.AGGREGATE,
        }
    ):
        features.append("mask_from_integral")
    return tuple(dict.fromkeys(features))


def _rust_form_features(form: AlgorithmCallableForm) -> tuple[str, ...]:
    features = list(_rust_family_features(form.family))
    if form.mask_form is AlgorithmMaskForm.LAYOUT:
        features.extend(("integral_mask", "mask_from_integral"))
    return tuple(dict.fromkeys(features))


RUST_ALGORITHM_REQUIREMENTS = BackendAlgorithmRequirements(
    "rust",
    RUST_HELPER_MANIFEST,
    tuple(
        AlgorithmFamilyRequirements(
            family,
            tuple(
                AlgorithmFormRequirements(form, _rust_form_features(form))
                for form in family.callable_forms
            ),
        )
        for family in ALGORITHM_SURFACE_FAMILIES
    ),
    mandatory_features=("contiguous_memory",),
    optional_features=("gather_narrow",),
)


@dataclass(frozen=True, slots=True)
class RustAlgorithmHelperBinding:
    """One semantic helper bound to its source and emitted Rust identities."""

    feature_name: str
    requirement: PrimitiveRequirement
    provider: ResolvedPrimitiveProvider | None
    facade: RustAlgorithmPrimitiveFacade | None

    def __post_init__(self) -> None:
        if not self.feature_name:
            raise ValueError("Rust algorithm helper bindings require a feature")
        if (
            self.provider is not None
            and self.provider.requirement != self.requirement.provider
        ):
            raise ValueError("Rust algorithm helper binding has a foreign provider")
        if self.provider is None and self.facade is not None:
            raise ValueError(
                "Rust algorithm helper facade requires a resolved source provider"
            )
        if self.facade is not None and self.facade.kind is not None:
            raise ValueError("Rust algorithm helper bindings require helper-only facades")

    @property
    def supported(self) -> bool:
        return self.facade is not None


@dataclass(frozen=True, slots=True)
class RustAlgorithmImplTarget:
    """One Rust vector family receiving profile algorithm trait impls."""

    type_parameters: str
    vector: str

    def __post_init__(self) -> None:
        if not self.type_parameters or not self.vector:
            raise ValueError("Rust algorithm implementation targets must be complete")


@dataclass(frozen=True, slots=True)
class RustAlgorithmSelectedLoadTarget:
    """One exact static mapping admitted for a hardware selected-load impl."""

    mapping: RustStaticVectorMapping
    use_gather_narrow: bool

    def __post_init__(self) -> None:
        if not self.mapping.uses_hardware:
            raise ValueError("Rust selected-load targets require hardware mappings")


@dataclass(frozen=True, slots=True)
class RustAlgorithmFamilyModulePlan:
    """One private profile wrapper module and its admitted callable forms."""

    semantic_family: AlgorithmSemanticFamily
    forms: tuple[AlgorithmCallableForm, ...]

    def __post_init__(self) -> None:
        if not self.forms or any(
            form.family.semantic_family is not self.semantic_family
            for form in self.forms
        ):
            raise ValueError(
                "Rust algorithm family modules require matching admitted forms"
            )

    @property
    def module_name(self) -> str:
        return self.semantic_family.value

    @property
    def admitted_form_names(self) -> tuple[str, ...]:
        return tuple(form.name for form in self.forms)


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
    helper_bindings: tuple[RustAlgorithmHelperBinding, ...]
    admission: AlgorithmProfileAdmission
    family_modules: tuple[RustAlgorithmFamilyModulePlan, ...]
    selected_load_targets: tuple[RustAlgorithmSelectedLoadTarget, ...]
    primitive_facades: tuple[RustAlgorithmPrimitiveFacade, ...]
    requires_rebind: bool

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
        if self.admission.backend_id != "rust":
            raise ValueError("Rust algorithm admission must use the Rust backend")
        if self.admission.profile_name != self.profile_name:
            raise ValueError("Rust algorithm admission must match its profile")
        expected_families = tuple(
            family
            for family in AlgorithmSemanticFamily
            if any(
                form.family.semantic_family is family
                for form in self.admission.admitted_forms
            )
        )
        if tuple(
            module.semantic_family for module in self.family_modules
        ) != expected_families:
            raise ValueError(
                "Rust algorithm family modules must follow semantic family order"
            )
        if tuple(
            form for module in self.family_modules for form in module.forms
        ) != self.admission.admitted_forms:
            raise ValueError(
                "Rust algorithm family modules must partition admitted forms"
            )
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
        expected_helper_keys = tuple(
            (feature.name, requirement)
            for feature in RUST_HELPER_MANIFEST.features
            if feature.name != "contiguous_memory"
            for requirement in feature.requirements
        )
        if tuple(
            (binding.feature_name, binding.requirement)
            for binding in self.helper_bindings
        ) != expected_helper_keys:
            raise ValueError(
                "Rust algorithm helper bindings must follow the helper manifest"
            )
        for feature in RUST_HELPER_MANIFEST.features:
            if feature.name == "contiguous_memory":
                continue
            bound = all(
                binding.supported
                for binding in self.helper_bindings_for(feature.name)
            )
            if bound != self.admission.helper(feature.name).supported:
                raise ValueError(
                    "Rust algorithm helper binding disagrees with feature admission"
                )
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
        return self.admission.supported

    @property
    def admitted_family_names(self) -> tuple[str, ...]:
        return tuple(family.name for family in self.admission.admitted_families)

    @property
    def admitted_form_names(self) -> tuple[str, ...]:
        return tuple(form.name for form in self.admission.admitted_forms)

    @property
    def gaps(self) -> tuple[AlgorithmRequirementGap, ...]:
        return self.admission.gaps

    def helper(self, feature_name: str) -> AlgorithmHelperAdmission:
        return self.admission.helper(feature_name)

    def helper_bindings_for(
        self, feature_name: str
    ) -> tuple[RustAlgorithmHelperBinding, ...]:
        bindings = tuple(
            binding
            for binding in self.helper_bindings
            if binding.feature_name == feature_name
        )
        if not bindings:
            raise KeyError(f"Rust algorithm helper feature {feature_name!r} is unknown")
        return bindings

    def helper_binding(self, feature_name: str) -> RustAlgorithmHelperBinding:
        bindings = self.helper_bindings_for(feature_name)
        if len(bindings) != 1:
            raise ValueError(
                f"Rust algorithm helper feature {feature_name!r} does not bind "
                "exactly one primitive"
            )
        return bindings[0]


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
    helper_plan: BackendHelperPlan,
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
                helper_plan=helper_plan,
            )
        )
    fallback_module = static_selection.fallback_module
    fallback = _plan_profile(
        fallback_module.metadata_profile_name,
        fallback_module.specializations_by_primitive(),
        static_selection.fallback_mappings,
        static_selection.fallback_native_mappings,
        is_fallback=True,
        helper_plan=helper_plan,
    )
    return RustAlgorithmPlan(tuple(planned_profiles), fallback)


def _plan_profile(
    profile_name: str,
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    static_mappings: tuple[RustStaticVectorMapping, ...],
    native_mappings: tuple[RustStaticVectorMapping, ...],
    *,
    is_fallback: bool,
    helper_plan: BackendHelperPlan,
) -> RustAlgorithmProfilePlan:
    memory = plan_contiguous_memory_primitive_facades(by_primitive)
    helper_bindings = _rust_algorithm_helper_bindings(by_primitive, helper_plan)
    admission = plan_algorithm_profile_admission(
        profile_name,
        by_primitive,
        RUST_ALGORITHM_REQUIREMENTS,
        helper_plan,
        rust_algorithm_form_support,
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
        helper_bindings=helper_bindings,
        admission=admission,
        family_modules=_family_modules(admission),
        selected_load_targets=_selected_load_targets(
            static_mappings,
            by_primitive,
            admission.helpers,
            helper_plan,
        ),
        primitive_facades=primitive_facades,
        requires_rebind=any(facade.requires_rebind for facade in primitive_facades),
    )


def _rust_algorithm_helper_bindings(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    helper_plan: BackendHelperPlan,
) -> tuple[RustAlgorithmHelperBinding, ...]:
    """Bind each semantic helper form to its finalized profile-local facade."""

    if helper_plan.manifest != RUST_HELPER_MANIFEST:
        raise ValueError("Rust algorithm planning requires the Rust helper plan")
    bindings: list[RustAlgorithmHelperBinding] = []
    for feature in RUST_HELPER_MANIFEST.features:
        if feature.name == "contiguous_memory":
            continue
        for requirement in feature.requirements:
            specializations = helper_plan.matching_specializations(
                requirement,
                by_primitive,
            )
            bindings.append(
                RustAlgorithmHelperBinding(
                    feature_name=feature.name,
                    requirement=requirement,
                    provider=helper_plan.provider(requirement),
                    facade=(
                        plan_rust_algorithm_helper_facade(specializations)
                        if specializations
                        else None
                    ),
                )
            )
    return tuple(bindings)


def _family_modules(
    admission: AlgorithmProfileAdmission,
) -> tuple[RustAlgorithmFamilyModulePlan, ...]:
    return tuple(
        RustAlgorithmFamilyModulePlan(
            semantic_family,
            tuple(
                form
                for form in admission.admitted_forms
                if form.family.semantic_family is semantic_family
            ),
        )
        for semantic_family in AlgorithmSemanticFamily
        if any(
            form.family.semantic_family is semantic_family
            for form in admission.admitted_forms
        )
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
            RustAlgorithmImplTarget("T", f"Simd<T, super::super::{tag}>")
            for tag in concrete_tags
        ),
    )


def _selected_load_targets(
    mappings: tuple[RustStaticVectorMapping, ...],
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    admissions: tuple[AlgorithmHelperAdmission, ...],
    helper_plan: BackendHelperPlan,
) -> tuple[RustAlgorithmSelectedLoadTarget, ...]:
    selected_load = next(
        item for item in admissions if item.feature_name == "selected_load"
    )
    if not selected_load.supported:
        return ()
    gather_requirement = helper_plan.manifest.requirements("gather_narrow")[0]
    gather_vectors = {
        (spec.extension_name, spec.base_type_spelling)
        for spec in helper_plan.matching_specializations(
            gather_requirement, by_primitive
        )
    }
    array_vector_sets = [
        {
            (spec.extension_name, spec.base_type_spelling)
            for spec in helper_plan.matching_specializations(
                requirement, by_primitive
            )
        }
        for requirement in helper_plan.manifest.requirements("selected_load")
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
    "RUST_ALGORITHM_REQUIREMENTS",
    "RustAlgorithmFamilyModulePlan",
    "RustAlgorithmHelperBinding",
    "RustAlgorithmImplTarget",
    "RustAlgorithmPlan",
    "RustAlgorithmProfilePlan",
    "RustAlgorithmSelectedLoadTarget",
    "plan_rust_algorithm",
)
