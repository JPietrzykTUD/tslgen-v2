"""Assemble generated backend project trees."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.diagnostics import Diagnostic
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify_model import VerifyBackend, VerifyProject
from tslc.render.backend_drivers import render_backend_drivers, value_test_supports
from tslc.render.documentation_project import documentation_artifacts
from tslc.render.emitted_names import finalize_emitted_names
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestPlanner,
    ValueTestProjectPlan,
)

_EMPTY_SPECIALIZATIONS: Mapping[str, tuple[LoweredSpecialization, ...]] = MappingProxyType(
    {}
)


@dataclass(frozen=True, slots=True)
class ProfileRender:
    profile: MachineProfile
    # backend id -> primitive name -> its specializations
    specializations_by_backend: Mapping[
        str, Mapping[str, tuple[LoweredSpecialization, ...]]
    ]
    # isa_name -> the extension block this profile actually selected for that ISA tag
    # (so registrations know whether `avx2` here is lane-bitmask `avx2` or native
    # `avx2_vl`). Per (profile, isa) exactly one block is selected, so this is 1:1.
    extensions: Mapping[str, Extension] = field(default_factory=dict)
    profile_family: ProfileFamilyCapability | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "specializations_by_backend",
            _freeze_backend_specializations(self.specializations_by_backend),
        )
        object.__setattr__(
            self,
            "extensions",
            MappingProxyType(dict(sorted(self.extensions.items()))),
        )

    def specializations(
        self, backend_id: str
    ) -> Mapping[str, tuple[LoweredSpecialization, ...]]:
        return self.specializations_by_backend.get(backend_id, _EMPTY_SPECIALIZATIONS)


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
            specializations_by_backend=_finalize_backend_names(
                profile_render.specializations_by_backend,
                immediate_split_names,
            ),
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
    artifacts.extend(documentation_artifacts(ordered))
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


def _freeze_backend_specializations(
    mapping: Mapping[str, Mapping[str, tuple[LoweredSpecialization, ...]]],
) -> Mapping[str, Mapping[str, tuple[LoweredSpecialization, ...]]]:
    return MappingProxyType(
        {
            backend_id: _freeze_specializations(by_primitive)
            for backend_id, by_primitive in sorted(mapping.items())
        }
    )


def _finalize_backend_names(
    mapping: Mapping[str, Mapping[str, tuple[LoweredSpecialization, ...]]],
    immediate_split_names: frozenset[str],
) -> Mapping[str, Mapping[str, tuple[LoweredSpecialization, ...]]]:
    return {
        backend_id: finalize_emitted_names(by_primitive, immediate_split_names)
        for backend_id, by_primitive in mapping.items()
    }


__all__ = ["ProfileRender", "RenderedProject", "render_project"]
