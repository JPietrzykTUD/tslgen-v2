"""Rust machine-profile and target projection for verification."""

from __future__ import annotations

from tslc.backend.emitted_profile import EmittedProfile
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.target_families import ProfileFamilyCapability
from tslc.names import identifier_slug
from tslc.output.verify_model import VerifyProfile, VerifyRunner


def rust_verify_profiles(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[VerifyProfile, ...]:
    return tuple(
        rust_verify_profile(emitted_profile.profile, emitted_profile.profile_family)
        for emitted_profile in profiles
    )


def rust_verify_profile(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> VerifyProfile:
    """Project a source machine profile into verifier-owned Rust facts."""

    return VerifyProfile(
        profile_name=identifier_slug(profile.name),
        file_stem=identifier_slug(profile.name),
        family=profile.family,
        native_without_runner=(
            capability.native_without_runner if capability is not None else False
        ),
        compile_modes=profile.compile_modes,
        target_features=rust_target_features(profile, capability),
        target=rust_target(profile, capability),
        linker=rust_linker(profile, capability),
        runner=_verify_runner(profile),
    )


def rust_target_features(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    capability = capability or ProfileFamilyCapability(profile.family)
    if not capability.backend("rust").feature_flags:
        return ()
    return tuple(
        f"+{profile.feature_spelling(feature, 'rust')}"
        for feature in sorted(profile.features)
    )


def rust_target(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.backend("rust").target


def rust_linker(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.backend("rust").linker


def _verify_runner(profile: MachineProfile) -> VerifyRunner | None:
    if profile.runner is None:
        return None
    return VerifyRunner(
        kind=profile.runner.kind,
        profile=profile.runner.profile,
        args=profile.runner.args,
    )


__all__ = (
    "rust_linker",
    "rust_target",
    "rust_target_features",
    "rust_verify_profile",
    "rust_verify_profiles",
)
