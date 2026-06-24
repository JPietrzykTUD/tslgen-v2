"""Assemble the generated C++ and Rust project tree."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProject
from tslc.render.cpp_project import cpp_artifacts, cpp_verify_profiles
from tslc.render.emitted_names import finalize_emitted_names
from tslc.render.rust_project import rust_artifacts, rust_verify_profiles
from tslc.render.tests_project import cpp_test_artifacts, rust_test_artifacts
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.diagnostics import Diagnostic
from tslc.value_tests import (
    ValueTestBackendProfileInput,
    ValueTestBackendSupport,
    ValueTestPlanner,
    ValueTestProjectPlan,
)
from tslc.value_tests.render_cpp import CPP_VALUE_TEST_SUPPORT
from tslc.value_tests.render_rust import RUST_VALUE_TEST_SUPPORT


@dataclass(frozen=True, slots=True)
class ProfileRender:
    profile: MachineProfile
    # primitive name -> its specializations (one backend each)
    cpp: dict[str, tuple[LoweredSpecialization, ...]]
    rust: dict[str, tuple[LoweredSpecialization, ...]]
    # isa_name -> the extension block this profile actually selected for that ISA tag
    # (so registrations know whether `avx2` here is lane-bitmask `avx2` or native
    # `avx2_vl`). Per (profile, isa) exactly one block is selected, so this is 1:1.
    extensions: dict[str, Extension] = field(default_factory=dict)


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
        ValueTestPlanner(catalog, _value_test_supports(backends)).plan(
            _value_test_inputs(ordered, backends)
        )
        if catalog is not None
        else ValueTestProjectPlan(profiles=())
    )

    if "cpp" in backends:
        artifacts.extend(cpp_artifacts(ordered))
        artifacts.extend(cpp_test_artifacts(test_plan))
        verify_backends.append(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=cpp_verify_profiles(ordered),
            )
        )
    if "rust" in backends:
        artifacts.extend(rust_artifacts(ordered))
        artifacts.extend(rust_test_artifacts(test_plan))
        verify_backends.append(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=rust_verify_profiles(ordered),
            )
        )
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


def _value_test_supports(backends: tuple[str, ...]) -> tuple[ValueTestBackendSupport, ...]:
    supports = []
    if "cpp" in backends:
        supports.append(CPP_VALUE_TEST_SUPPORT)
    if "rust" in backends:
        supports.append(RUST_VALUE_TEST_SUPPORT)
    return tuple(supports)


def _value_test_inputs(
    profiles: tuple[ProfileRender, ...],
    backends: tuple[str, ...],
) -> tuple[ValueTestBackendProfileInput, ...]:
    inputs: list[ValueTestBackendProfileInput] = []
    for profile in profiles:
        if "cpp" in backends:
            inputs.append(
                ValueTestBackendProfileInput("cpp", profile.profile.name, profile.cpp)
            )
        if "rust" in backends:
            inputs.append(
                ValueTestBackendProfileInput("rust", profile.profile.name, profile.rust)
            )
    return tuple(inputs)


__all__ = ["ProfileRender", "RenderedProject", "render_project"]
