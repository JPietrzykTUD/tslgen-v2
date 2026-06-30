"""Typed target-family routing facts promoted from source data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class ProfileFamilyCapability:
    """One machine-profile family and the extension/toolchain behavior it owns."""

    name: str
    extension_families: frozenset[str] = frozenset()
    emulator_kinds: frozenset[str] = frozenset()
    sort_order: int = 100
    cpp_feature_flags: bool = True
    cpp_target: str | None = None
    cpp_detection: str | None = None
    rust_target_features: bool = True
    rust_target: str | None = None
    rust_linker: str | None = None
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class TargetFamilyCatalog:
    """Catalog-owned family routing policy.

    Concrete family names are source data. Compiler code owns only the mechanics:
    universal extension families are routed to every profile family, while a
    profile family routes the extension families it explicitly declares.
    """

    known_extension_families: frozenset[str] = frozenset()
    universal_extension_families: frozenset[str] = frozenset()
    profile_families: Mapping[str, ProfileFamilyCapability] = field(default_factory=dict)

    def __post_init__(self) -> None:
        profile_families = MappingProxyType(
            {
                name: capability
                for name, capability in sorted(self.profile_families.items())
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
        object.__setattr__(self, "profile_families", profile_families)

    @property
    def emitted_extension_families(self) -> frozenset[str]:
        families = set(self.universal_extension_families)
        for capability in self.profile_families.values():
            families.update(capability.extension_families)
        return frozenset(families)

    @property
    def profile_family_names(self) -> frozenset[str]:
        return frozenset(self.profile_families)

    def supports_extension_family(self, family: str) -> bool:
        return family in self.emitted_extension_families

    def supports_profile_family(self, family: str) -> bool:
        return family in self.profile_families

    def profile_family(self, family: str) -> ProfileFamilyCapability | None:
        return self.profile_families.get(family)

    def extension_targets_profile(
        self,
        extension_family: str,
        profile_family: str,
    ) -> bool:
        if extension_family in self.universal_extension_families:
            return True
        capability = self.profile_families.get(profile_family)
        return capability is not None and extension_family in capability.extension_families

    def emulator_kinds_for_profile_family(self, profile_family: str) -> frozenset[str]:
        capability = self.profile_families.get(profile_family)
        return frozenset() if capability is None else capability.emulator_kinds


__all__ = ("ProfileFamilyCapability", "TargetFamilyCatalog")
