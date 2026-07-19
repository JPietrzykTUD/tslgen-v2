"""Typed target-family routing facts promoted from source data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class BackendProfileFamily:
    """One backend's behavior for a machine-profile family."""

    feature_flags: bool = True
    target: str | None = None
    linker: str | None = None
    detection: str | None = None
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class TargetFeatureCapability:
    """One source feature and its compiler spelling per backend."""

    name: str
    default_spelling: str | None = None
    backend_spellings: Mapping[str, str] = field(default_factory=dict)
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "backend_spellings",
            MappingProxyType(dict(sorted(self.backend_spellings.items()))),
        )

    def spelling(self, backend_id: str) -> str:
        return self.backend_spellings.get(
            backend_id,
            self.default_spelling or self.name,
        )


@dataclass(frozen=True, slots=True)
class ExtensionFamilyCapability:
    """Compiler behavior shared by extensions in one source-named family."""

    name: str
    implementation_fallback: bool = False
    free_function_owner: bool = True
    requires_declared_vector_register: bool = True
    index_vector_register: bool = False
    documentation_family: str | None = None
    documentation_sort_order: int | None = None
    source: SourceSpan | None = None

    @property
    def documented_family(self) -> str:
        return self.documentation_family or self.name

    @property
    def documented_sort_order(self) -> int:
        return (
            90
            if self.documentation_sort_order is None
            else self.documentation_sort_order
        )


@dataclass(frozen=True, slots=True)
class ProfileFamilyCapability:
    """One machine-profile family and the backend behavior it owns."""

    name: str
    extension_families: frozenset[str] = frozenset()
    runner_kinds: frozenset[str] = frozenset()
    native_without_runner: bool = False
    sort_order: int = 100
    backends: Mapping[str, BackendProfileFamily] = field(default_factory=dict)
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "backends",
            MappingProxyType(dict(sorted(self.backends.items()))),
        )

    def backend(self, backend_id: str) -> BackendProfileFamily:
        return self.backends.get(backend_id, BackendProfileFamily())


@dataclass(frozen=True, slots=True)
class TargetFamilyCatalog:
    """Catalog-owned family routing policy.

    Concrete family names are source data. Compiler code owns only the mechanics:
    universal extension families are routed to every profile family, while a
    profile family routes the extension families it explicitly declares.
    """

    known_extension_families: frozenset[str] = frozenset()
    universal_extension_families: frozenset[str] = frozenset()
    extension_families: Mapping[str, ExtensionFamilyCapability] = field(
        default_factory=dict
    )
    profile_families: Mapping[str, ProfileFamilyCapability] = field(default_factory=dict)
    target_features: Mapping[str, TargetFeatureCapability] = field(default_factory=dict)

    def __post_init__(self) -> None:
        profile_families = MappingProxyType(
            {
                name: capability
                for name, capability in sorted(self.profile_families.items())
            }
        )
        extension_families = MappingProxyType(
            {
                name: _resolved_documentation_order(capability, profile_families)
                for name, capability in sorted(self.extension_families.items())
            }
        )
        target_features = MappingProxyType(
            {
                name: capability
                for name, capability in sorted(self.target_features.items())
            }
        )
        emitted = set(self.universal_extension_families)
        for capability in profile_families.values():
            emitted.update(capability.extension_families)
        object.__setattr__(
            self,
            "known_extension_families",
            frozenset(self.known_extension_families | frozenset(emitted)),
        )
        object.__setattr__(
            self,
            "universal_extension_families",
            frozenset(self.universal_extension_families),
        )
        object.__setattr__(self, "extension_families", extension_families)
        object.__setattr__(self, "profile_families", profile_families)
        object.__setattr__(self, "target_features", target_features)

    @property
    def emitted_extension_families(self) -> frozenset[str]:
        families = set(self.universal_extension_families)
        for capability in self.profile_families.values():
            families.update(capability.extension_families)
        return frozenset(families)

    @property
    def profile_family_names(self) -> frozenset[str]:
        return frozenset(self.profile_families)

    @property
    def backend_ids(self) -> frozenset[str]:
        return frozenset(
            backend_id
            for capability in self.profile_families.values()
            for backend_id in capability.backends
        )

    @property
    def target_feature_names(self) -> frozenset[str]:
        return frozenset(self.target_features)

    def supports_extension_family(self, family: str) -> bool:
        return family in self.emitted_extension_families

    def supports_profile_family(self, family: str) -> bool:
        return family in self.profile_families

    def profile_family(self, family: str) -> ProfileFamilyCapability | None:
        return self.profile_families.get(family)

    def extension_family(self, family: str) -> ExtensionFamilyCapability:
        return self.extension_families.get(
            family,
            ExtensionFamilyCapability(family),
        )

    def target_feature(self, feature: str) -> TargetFeatureCapability | None:
        return self.target_features.get(feature)

    def extension_targets_profile(
        self,
        extension_family: str,
        profile_family: str,
    ) -> bool:
        if extension_family in self.universal_extension_families:
            return True
        capability = self.profile_families.get(profile_family)
        return capability is not None and extension_family in capability.extension_families

    def runner_kinds_for_profile_family(self, profile_family: str) -> frozenset[str]:
        capability = self.profile_families.get(profile_family)
        return frozenset() if capability is None else capability.runner_kinds


def _resolved_documentation_order(
    capability: ExtensionFamilyCapability,
    profile_families: Mapping[str, ProfileFamilyCapability],
) -> ExtensionFamilyCapability:
    if capability.documentation_sort_order is not None:
        return capability
    profile = profile_families.get(capability.documented_family)
    return replace(
        capability,
        documentation_sort_order=profile.sort_order if profile is not None else 90,
    )


__all__ = (
    "BackendProfileFamily",
    "ExtensionFamilyCapability",
    "ProfileFamilyCapability",
    "TargetFeatureCapability",
    "TargetFamilyCatalog",
)
