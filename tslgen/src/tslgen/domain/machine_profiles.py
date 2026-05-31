"""Typed machine feature profile values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.core.diagnostics import Diagnostic, SourceLocation

FeatureFlagName = NewType("FeatureFlagName", str)
FeatureFlagSpelling = NewType("FeatureFlagSpelling", str)
MachineProfileFamily = NewType("MachineProfileFamily", str)
MachineProfileName = NewType("MachineProfileName", str)


@dataclass(frozen=True, slots=True)
class FeatureFlagNormalization:
    spelling: FeatureFlagSpelling
    normalized: FeatureFlagName
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class FeatureFlagNormalizationCatalog:
    entries: tuple[FeatureFlagNormalization, ...]

    def normalize(self, spelling: str) -> FeatureFlagName | None:
        for entry in self.entries:
            if entry.spelling == spelling:
                return entry.normalized
        known_normalized = {entry.normalized for entry in self.entries}
        candidate = FeatureFlagName(spelling)
        if candidate in known_normalized:
            return candidate
        return None


@dataclass(frozen=True, slots=True)
class MachineFeatureAlternative:
    feature: FeatureFlagName
    spelling: FeatureFlagSpelling


@dataclass(frozen=True, slots=True)
class MachineFeatureProfile:
    family: MachineProfileFamily
    name: MachineProfileName
    features: tuple[FeatureFlagName, ...]
    alternatives: tuple[MachineFeatureAlternative, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MachineFeatureProfileBuildOptions:
    family: MachineProfileFamily
    profile_name: MachineProfileName
    features: tuple[FeatureFlagName, ...]
    alternatives: tuple[MachineFeatureAlternative, ...]

    def format_values(self) -> dict[str, str]:
        alternatives = tuple(
            sorted(
                self.alternatives,
                key=lambda item: (str(item.feature), str(item.spelling)),
            )
        )
        return {
            "target_profile_family": str(self.family),
            "target_profile_name": str(self.profile_name),
            "target_profile": f"{self.family}/{self.profile_name}",
            "target_features": " ".join(str(feature) for feature in self.features),
            "target_feature_alternatives": " ".join(
                f"{alternative.feature}={alternative.spelling}"
                for alternative in alternatives
            ),
        }


@dataclass(frozen=True, slots=True)
class MachineFeatureProfileSelectionResult:
    build_options: MachineFeatureProfileBuildOptions | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class MachineFeatureProfileCatalog:
    profiles: tuple[MachineFeatureProfile, ...]

    def get(
        self,
        family: MachineProfileFamily | str,
        name: MachineProfileName | str,
    ) -> MachineFeatureProfile | None:
        family_text = str(family)
        name_text = str(name)
        for profile in self.profiles:
            if str(profile.family) == family_text and str(profile.name) == name_text:
                return profile
        return None

    def select_build_options(
        self,
        family: MachineProfileFamily | str,
        name: MachineProfileName | str,
    ) -> MachineFeatureProfileSelectionResult:
        profile = self.get(family, name)
        if profile is None:
            return MachineFeatureProfileSelectionResult(
                build_options=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-MACHINE-PROFILE-UNKNOWN-PROFILE",
                        message=(
                            "unknown machine feature profile "
                            f"{str(family)!r}/{str(name)!r}"
                        ),
                    ),
                ),
            )
        return MachineFeatureProfileSelectionResult(
            build_options=MachineFeatureProfileBuildOptions(
                family=profile.family,
                profile_name=profile.name,
                features=profile.features,
                alternatives=profile.alternatives,
            )
        )
