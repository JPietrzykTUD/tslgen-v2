"""C++ machine-profile projection for generated-project verification."""

from __future__ import annotations

from tslc.backend.cpp_build_policy import cpp_profile_flags, cpp_profile_target
from tslc.backend.emitted_profile import EmittedProfile, used_extensions
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.names import identifier_slug
from tslc.output.verify_model import VerifyProfile, VerifyRunner


def _cpp_preflight_headers(profile: EmittedProfile) -> tuple[str, ...]:
    used = used_extensions(profile.specializations("cpp"))
    return tuple(
        sorted(
            {
                header
                for extension_name in used
                if (extension := profile.extensions.get(extension_name)) is not None
                for header in extension.headers_for_backend("cpp")
            }
        )
    )


def cpp_verify_profiles(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[VerifyProfile, ...]:
    return tuple(
        cpp_verify_profile(
            emitted_profile.profile,
            emitted_profile.profile_family,
            preflight_headers=_cpp_preflight_headers(emitted_profile),
        )
        for emitted_profile in profiles
    )


def cpp_verify_profile(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
    *,
    preflight_headers: tuple[str, ...] = (),
) -> VerifyProfile:
    """Project a source machine profile into verifier-owned C++ facts."""

    capability = capability or ProfileFamilyCapability(profile.family)
    backend = capability.backend("cpp")

    return VerifyProfile(
        profile_name=identifier_slug(profile.name),
        file_stem=identifier_slug(profile.name),
        family=profile.family,
        native_without_runner=capability.native_without_runner,
        compile_modes=profile.compile_modes,
        flags=cpp_profile_flags(profile, capability),
        target=cpp_profile_target(profile, capability),
        compiler_role=(
            profile.compiler_role_for_backend("cpp") or backend.compiler_role
        ),
        cmake_system_name=backend.cmake_system_name,
        cmake_system_processor=backend.cmake_system_processor,
        pass_target_to_compiler=backend.pass_target_to_compiler,
        preflight_headers=preflight_headers,
        runner=_verify_runner(profile),
    )


def _verify_runner(profile: MachineProfile) -> VerifyRunner | None:
    if profile.runner is None:
        return None
    return VerifyRunner(
        kind=profile.runner.kind,
        profile=profile.runner.profile,
        args=profile.runner.args,
    )


__all__ = ("cpp_verify_profile", "cpp_verify_profiles")
