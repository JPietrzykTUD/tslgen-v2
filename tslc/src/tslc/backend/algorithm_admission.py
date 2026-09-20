"""Typed algorithm-family admission from backend helper requirements."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tslc.backend.algorithm_surface import (
    ALGORITHM_SURFACE_FAMILIES,
    AlgorithmBackendFormSupport,
    AlgorithmCallableForm,
    AlgorithmSurfaceFamily,
)
from tslc.backend.helper_requirements import (
    BackendHelperManifest,
    BackendHelperPlan,
    PrimitiveRequirement,
)
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.semantics import ResolvedPrimitiveProvider
from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization


@dataclass(frozen=True, slots=True)
class AlgorithmFormRequirements:
    """Backend helper feature groups required by one callable form."""

    form: AlgorithmCallableForm
    feature_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(set(self.feature_names)) != len(self.feature_names):
            raise ValueError("algorithm form helper features must be unique")

    @property
    def form_name(self) -> str:
        return self.form.name


@dataclass(frozen=True, slots=True)
class AlgorithmFamilyRequirements:
    """Complete callable-form requirements for one semantic family."""

    family: AlgorithmSurfaceFamily
    forms: tuple[AlgorithmFormRequirements, ...]

    def __post_init__(self) -> None:
        forms = tuple(item.form for item in self.forms)
        if forms != self.family.callable_forms:
            raise ValueError(
                "algorithm form requirements must follow their shared family"
            )

    @property
    def family_name(self) -> str:
        return self.family.name

    def requirement_for(
        self, form: AlgorithmCallableForm
    ) -> AlgorithmFormRequirements:
        try:
            return next(item for item in self.forms if item.form == form)
        except StopIteration as exc:
            raise KeyError(
                f"algorithm family {self.family.name!r} has no form {form.name!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class BackendAlgorithmRequirements:
    """One backend's complete, validated family-to-helper projection."""

    backend_id: str
    helpers: BackendHelperManifest
    families: tuple[AlgorithmFamilyRequirements, ...]
    mandatory_features: tuple[str, ...] = ()
    optional_features: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.backend_id != self.helpers.backend_id:
            raise ValueError("algorithm requirements must match their helper backend")
        family_names = tuple(item.family_name for item in self.families)
        expected_names = tuple(family.name for family in ALGORITHM_SURFACE_FAMILIES)
        if family_names != expected_names:
            raise ValueError(
                "algorithm requirements must cover shared families in inventory order"
            )
        helper_names = {feature.name for feature in self.helpers.features}
        if len(set(self.mandatory_features)) != len(self.mandatory_features):
            raise ValueError("mandatory algorithm helper features must be unique")
        if len(set(self.optional_features)) != len(self.optional_features):
            raise ValueError("optional algorithm helper features must be unique")
        if set(self.mandatory_features) & set(self.optional_features):
            raise ValueError("algorithm helper features cannot be mandatory and optional")
        referenced = {
            *self.mandatory_features,
            *self.optional_features,
            *(
                feature_name
                for family in self.families
                for form in family.forms
                for feature_name in form.feature_names
            ),
        }
        unknown = sorted(referenced - helper_names)
        if unknown:
            raise ValueError(
                f"algorithm requirements reference unknown helper features: {unknown}"
            )
        unused = sorted(helper_names - referenced)
        if unused:
            raise ValueError(
                f"algorithm helper features are not consumed by admission: {unused}"
            )

    def family(self, family_name: str) -> AlgorithmFamilyRequirements:
        try:
            return next(item for item in self.families if item.family_name == family_name)
        except StopIteration as exc:
            raise KeyError(
                f"backend {self.backend_id!r} has no algorithm family {family_name!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class AlgorithmRequirementGap:
    """One exact backend/profile/family helper requirement that is unavailable."""

    backend_id: str
    profile_name: str
    feature_name: str
    family_name: str
    form_name: str
    requirement: PrimitiveRequirement
    provider: ResolvedPrimitiveProvider | None
    provider_diagnostic: Diagnostic | None

    def __post_init__(self) -> None:
        if not all(
            (
                self.backend_id,
                self.profile_name,
                self.feature_name,
                self.family_name,
                self.form_name,
            )
        ):
            raise ValueError("algorithm requirement gaps require complete context")
        if (self.provider is None) == (self.provider_diagnostic is None):
            raise ValueError(
                "algorithm requirement gaps require either a provider or a diagnostic"
            )

    @property
    def primitive_name(self) -> str | None:
        return None if self.provider is None else self.provider.primitive_name

    @property
    def mask_policy(self) -> PrimitiveMaskMode | None:
        return self.requirement.mask_policy

    @property
    def reason(self) -> str:
        mask = (
            "unmasked"
            if self.requirement.mask_policy is None
            else f"mask policy {self.requirement.mask_policy}"
        )
        context = (
            f"{self.backend_id} profile {self.profile_name!r} algorithm family "
            f"{self.family_name!r} form {self.form_name!r} requires helper "
            f"feature {self.feature_name!r}: "
        )
        if self.provider is not None:
            return (
                context
                + f"resolved primitive {self.provider.primitive_name!r} has no "
                + f"profile specialization ({mask})"
            )
        assert self.provider_diagnostic is not None
        return (
            context
            + "no semantic provider in the corpus; "
            + self.provider_diagnostic.message
        )


@dataclass(frozen=True, slots=True)
class AlgorithmHelperAdmission:
    """One helper feature and the exact primitive requirements it is missing."""

    feature_name: str
    missing_requirements: tuple[PrimitiveRequirement, ...]

    def __post_init__(self) -> None:
        if not self.feature_name:
            raise ValueError("algorithm helper admissions require a feature")

    @property
    def supported(self) -> bool:
        return not self.missing_requirements


@dataclass(frozen=True, slots=True)
class AlgorithmFamilyAdmission:
    """One semantic family admitted or rejected for one backend profile."""

    family: AlgorithmSurfaceFamily
    forms: tuple[AlgorithmCallableForm, ...]
    admitted_forms: tuple[AlgorithmCallableForm, ...]
    gaps: tuple[AlgorithmRequirementGap, ...]

    def __post_init__(self) -> None:
        expected_forms = tuple(
            form for form in self.family.callable_forms if form in self.forms
        )
        if self.forms != expected_forms:
            raise ValueError(
                "algorithm admission forms must belong to their family in order"
            )
        gapped_names = {gap.form_name for gap in self.gaps}
        expected_admitted = tuple(
            form for form in self.forms if form.name not in gapped_names
        )
        if self.admitted_forms != expected_admitted:
            raise ValueError(
                "algorithm admitted forms must be exactly the gap-free forms"
            )
        if any(
            gap.family_name != self.family.name
            or gap.form_name not in {form.name for form in self.forms}
            for gap in self.gaps
        ):
            raise ValueError("algorithm family gaps must match their forms")

    @property
    def admitted(self) -> bool:
        return bool(self.admitted_forms)


@dataclass(frozen=True, slots=True)
class AlgorithmProfileAdmission:
    """Deterministic algorithm availability for one backend profile."""

    backend_id: str
    profile_name: str
    mandatory_features: tuple[str, ...]
    helpers: tuple[AlgorithmHelperAdmission, ...]
    families: tuple[AlgorithmFamilyAdmission, ...]

    def __post_init__(self) -> None:
        if not self.backend_id or not self.profile_name:
            raise ValueError("algorithm profile admissions require complete identity")
        helper_names = tuple(helper.feature_name for helper in self.helpers)
        if len(set(helper_names)) != len(helper_names):
            raise ValueError("algorithm helper admissions must be unique")
        if (
            len(set(self.mandatory_features)) != len(self.mandatory_features)
            or not set(self.mandatory_features) <= set(helper_names)
        ):
            raise ValueError(
                "mandatory algorithm features must uniquely name admitted helpers"
            )
        family_names = tuple(item.family.name for item in self.families)
        expected_names = tuple(family.name for family in ALGORITHM_SURFACE_FAMILIES)
        if family_names != expected_names:
            raise ValueError("algorithm admissions must follow shared family order")
        if any(
            gap.backend_id != self.backend_id
            or gap.profile_name != self.profile_name
            or gap.family_name != family.family.name
            or gap.form_name not in {form.name for form in family.forms}
            for family in self.families
            for gap in family.gaps
        ):
            raise ValueError("algorithm gaps must match their profile and family")

    @property
    def supported(self) -> bool:
        return all(self.helper(name).supported for name in self.mandatory_features)

    @property
    def admitted_families(self) -> tuple[AlgorithmSurfaceFamily, ...]:
        return tuple(item.family for item in self.families if item.admitted)

    @property
    def admitted_forms(self) -> tuple[AlgorithmCallableForm, ...]:
        return tuple(
            form
            for family in self.families
            for form in family.admitted_forms
        )

    @property
    def gaps(self) -> tuple[AlgorithmRequirementGap, ...]:
        return tuple(gap for family in self.families for gap in family.gaps)

    def helper(self, feature_name: str) -> AlgorithmHelperAdmission:
        try:
            return next(
                item for item in self.helpers if item.feature_name == feature_name
            )
        except StopIteration as exc:
            raise KeyError(
                f"{self.backend_id} algorithm plan has no helper feature "
                f"{feature_name!r}"
            ) from exc

    def family(self, family_name: str) -> AlgorithmFamilyAdmission:
        try:
            return next(
                item for item in self.families if item.family.name == family_name
            )
        except StopIteration as exc:
            raise KeyError(
                f"{self.backend_id} algorithm plan has no family {family_name!r}"
            ) from exc


def plan_algorithm_profile_admission(
    profile_name: str,
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    requirements: BackendAlgorithmRequirements,
    helper_plan: BackendHelperPlan,
    form_support: Callable[[AlgorithmCallableForm], AlgorithmBackendFormSupport],
) -> AlgorithmProfileAdmission:
    """Apply the same helper groups used for closure to one lowered profile."""

    if helper_plan.manifest != requirements.helpers:
        raise ValueError("algorithm admission helper plan does not match requirements")
    helpers = tuple(
        AlgorithmHelperAdmission(
            feature.name,
            tuple(
                requirement
                for requirement in helper_plan.missing_requirements(
                    feature.name, by_primitive
                )
            ),
        )
        for feature in requirements.helpers.features
    )
    missing_by_feature = {
        helper.feature_name: helper.missing_requirements for helper in helpers
    }
    families = tuple(
        _family_admission(
            requirements.backend_id,
            profile_name,
            family,
            requirements.family(family.name),
            requirements.mandatory_features,
            missing_by_feature,
            helper_plan,
            form_support,
        )
        for family in ALGORITHM_SURFACE_FAMILIES
    )
    return AlgorithmProfileAdmission(
        requirements.backend_id,
        profile_name,
        requirements.mandatory_features,
        helpers,
        families,
    )


def _family_admission(
    backend_id: str,
    profile_name: str,
    family: AlgorithmSurfaceFamily,
    requirements: AlgorithmFamilyRequirements,
    mandatory_features: tuple[str, ...],
    missing_by_feature: Mapping[str, tuple[PrimitiveRequirement, ...]],
    helper_plan: BackendHelperPlan,
    form_support: Callable[[AlgorithmCallableForm], AlgorithmBackendFormSupport],
) -> AlgorithmFamilyAdmission:
    support = tuple(form_support(form) for form in family.callable_forms)
    if any(item.backend_id != backend_id for item in support):
        raise ValueError("algorithm form support must match its admission backend")
    forms = tuple(item.form for item in support if item.supported)
    gaps_by_form = {
        form.name: tuple(
            AlgorithmRequirementGap(
                backend_id,
                profile_name,
                feature_name,
                family.name,
                form.name,
                requirement,
                helper_plan.provider(requirement),
                helper_plan.unresolved_diagnostic(requirement),
            )
            for feature_name in tuple(
                dict.fromkeys(
                    (
                        *mandatory_features,
                        *requirements.requirement_for(form).feature_names,
                    )
                )
            )
            for requirement in missing_by_feature[feature_name]
        )
        for form in forms
    }
    admitted_forms = tuple(form for form in forms if not gaps_by_form[form.name])
    gaps = tuple(form_gap for form in forms for form_gap in gaps_by_form[form.name])
    return AlgorithmFamilyAdmission(family, forms, admitted_forms, gaps)


__all__ = (
    "AlgorithmFamilyAdmission",
    "AlgorithmFamilyRequirements",
    "AlgorithmFormRequirements",
    "AlgorithmHelperAdmission",
    "AlgorithmProfileAdmission",
    "AlgorithmRequirementGap",
    "BackendAlgorithmRequirements",
    "plan_algorithm_profile_admission",
)
