"""Assemble the generated C++ and Rust project tree."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension
from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProject
from tslc.render.backend_drivers import render_backend_drivers, value_test_supports
from tslc.render.emitted_names import finalize_emitted_names
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    ValueTestProjectPlan,
)


@dataclass(frozen=True, slots=True)
class ProfileRender:
    profile: MachineProfile
    # primitive name -> its specializations (one backend each)
    cpp: Mapping[str, tuple[LoweredSpecialization, ...]]
    rust: Mapping[str, tuple[LoweredSpecialization, ...]]
    # isa_name -> the extension block this profile actually selected for that ISA tag
    # (so registrations know whether `avx2` here is lane-bitmask `avx2` or native
    # `avx2_vl`). Per (profile, isa) exactly one block is selected, so this is 1:1.
    extensions: Mapping[str, Extension] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cpp", _freeze_specializations(self.cpp))
        object.__setattr__(self, "rust", _freeze_specializations(self.rust))
        object.__setattr__(
            self,
            "extensions",
            MappingProxyType(dict(sorted(self.extensions.items()))),
        )


@dataclass(frozen=True, slots=True)
class RenderedProject:
    artifacts: ArtifactSet
    verify: VerifyProject
    diagnostics: tuple[Diagnostic, ...] = ()
    value_tests: ValueTestProjectPlan = field(
        default_factory=lambda: ValueTestProjectPlan(profiles=())
    )


def render_project(
    profiles: tuple[ProfileRender, ...],
    backends: tuple[str, ...] = DEFAULT_SUPPORT_POLICY.default_backend_ids,
    immediate_split_names: frozenset[str] = frozenset(),
    catalog: Catalog | None = None,
    value_test_warnings: bool = False,
    value_test_fuzz: bool = False,
) -> RenderedProject:
    ordered = tuple(
        replace(
            profile_render,
            cpp=finalize_emitted_names(profile_render.cpp, immediate_split_names),
            rust=finalize_emitted_names(profile_render.rust, immediate_split_names),
        )
        for profile_render in sorted(profiles, key=lambda p: p.profile.name)
    )
    artifacts: list[Artifact] = []
    verify_backends: list[VerifyBackend] = []
    test_plan = (
        ValueTestPlanner(
            catalog, value_test_supports(backends), fuzz=value_test_fuzz
        ).plan(_value_test_inputs(ordered, backends))
        if catalog is not None
        else ValueTestProjectPlan(profiles=())
    )

    for driver in render_backend_drivers(backends):
        artifacts.extend(driver.project_artifacts(ordered))
        artifacts.extend(driver.test_artifacts(test_plan))
        verify_backends.append(driver.verify_backend(ordered))
    test_diagnostics = tuple(
        diagnostic
        for diagnostic in test_plan.diagnostics
        if value_test_warnings or diagnostic.severity == "error"
    )
    return RenderedProject(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        verify=VerifyProject(backends=tuple(verify_backends)),
        diagnostics=test_diagnostics,
        value_tests=test_plan,
    )


def _value_test_inputs(
    profiles: tuple[ProfileRender, ...],
    backends: tuple[str, ...],
) -> tuple[ValueTestBackendProfileInput, ...]:
    inputs: list[ValueTestBackendProfileInput] = []
    drivers = render_backend_drivers(backends)
    for profile in profiles:
        for driver in drivers:
            inputs.append(
                ValueTestBackendProfileInput(
                    driver.backend_id,
                    profile.profile.name,
                    driver.specializations(profile),
                )
            )
    return tuple(inputs)


def _freeze_specializations(
    mapping: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
    return MappingProxyType(
        {name: tuple(specs) for name, specs in sorted(mapping.items())}
    )


__all__ = ["ProfileRender", "RenderedProject", "render_project"]
