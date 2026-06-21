"""Assemble the generated C++ and Rust project tree."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.verify import VerifyBackend, VerifyProject
from tslc.render.cpp_project import cpp_artifacts, cpp_verify_profiles
from tslc.render.emitted_names import finalize_emitted_names
from tslc.render.rust_project import rust_artifacts, rust_verify_profiles
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


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


def render_project(
    profiles: tuple[ProfileRender, ...],
    backends: tuple[str, ...] = DEFAULT_SUPPORT_POLICY.default_backend_ids,
    immediate_split_names: frozenset[str] = frozenset(),
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

    if "cpp" in backends:
        artifacts.extend(cpp_artifacts(ordered))
        verify_backends.append(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=cpp_verify_profiles(ordered),
            )
        )
    if "rust" in backends:
        artifacts.extend(rust_artifacts(ordered))
        verify_backends.append(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=rust_verify_profiles(ordered),
            )
        )
    return RenderedProject(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        verify=VerifyProject(backends=tuple(verify_backends)),
    )


__all__ = ["ProfileRender", "RenderedProject", "render_project"]
