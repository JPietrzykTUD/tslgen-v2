"""Typed generated-project values for backend/output boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.machine_profiles import (
    FeatureFlagName,
    MachineFeatureAlternative,
    MachineFeatureProfile,
    MachineProfileFamily,
    MachineProfileName,
)

ProfileFileStem = NewType("ProfileFileStem", str)
CppProfileMacro = NewType("CppProfileMacro", str)
CppTargetFeatureOption = NewType("CppTargetFeatureOption", str)
RustProfileFeature = NewType("RustProfileFeature", str)
RustProfileModule = NewType("RustProfileModule", str)
RustTargetFeature = NewType("RustTargetFeature", str)


@dataclass(frozen=True, slots=True)
class GeneratedProfileSet:
    profiles: tuple[MachineFeatureProfile, ...]
    default_profile: MachineFeatureProfile

    @property
    def profile_names(self) -> tuple[MachineProfileName, ...]:
        return tuple(profile.name for profile in self.profiles)


@dataclass(frozen=True, slots=True)
class GeneratedProfileSelectionResult:
    profile_set: GeneratedProfileSet | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendProfileRenderModel:
    family: MachineProfileFamily
    profile_name: MachineProfileName
    features: tuple[FeatureFlagName, ...]
    alternatives: tuple[MachineFeatureAlternative, ...]
    file_stem: ProfileFileStem
    cpp_macro: CppProfileMacro
    cpp_target_feature_options: tuple[CppTargetFeatureOption, ...]
    rust_feature: RustProfileFeature
    rust_module: RustProfileModule
    rust_target_features: tuple[RustTargetFeature, ...]


@dataclass(frozen=True, slots=True)
class BackendProjectRenderModel:
    backend_id: str
    project_name: str
    root_path: str
    public_entry_path: str
    smoke_test_path: str
    profiles: tuple[BackendProfileRenderModel, ...]
    default_profile: MachineProfileName

    @property
    def allowed_profile_names(self) -> tuple[MachineProfileName, ...]:
        return tuple(profile.profile_name for profile in self.profiles)


@dataclass(frozen=True, slots=True)
class GeneratedProjectRenderModel:
    cpp: BackendProjectRenderModel
    rust: BackendProjectRenderModel

    @property
    def projects(self) -> tuple[BackendProjectRenderModel, ...]:
        return (self.cpp, self.rust)


@dataclass(frozen=True, slots=True)
class GeneratedProjectModelResult:
    model: GeneratedProjectRenderModel | None
    diagnostics: tuple[Diagnostic, ...] = ()
