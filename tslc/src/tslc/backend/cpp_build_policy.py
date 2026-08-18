"""Backend-owned C++ compiler-option and target policy."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.target_families import ProfileFamilyCapability


@dataclass(frozen=True, slots=True)
class CppCompilerOption:
    """One compiler option and the CMake compiler families that accept it."""

    flag: str
    compiler_ids: tuple[str, ...]


_FEATURE_FLAG_COMPILER_IDS = ("GNU", "Clang", "AppleClang", "IntelLLVM")
_WRAPPING_ARITHMETIC_COMPILER_IDS = ("GNU", "Clang", "AppleClang")


def cpp_profile_flags(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[str, ...]:
    """Concrete C++ flags for one source profile."""

    capability = capability or ProfileFamilyCapability(profile.family)
    backend = capability.backend("cpp")
    if not backend.feature_flags:
        return profile.flags_for_backend("cpp")
    return (
        *(
            f"-m{profile.feature_spelling(feature, 'cpp')}"
            for feature in sorted(profile.features)
        ),
        *profile.flags_for_backend("cpp"),
    )


def cpp_profile_compile_options(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> tuple[CppCompilerOption, ...]:
    return tuple(
        CppCompilerOption(flag, _FEATURE_FLAG_COMPILER_IDS)
        for flag in cpp_profile_flags(profile, capability)
    )


def cpp_profile_target(
    profile: MachineProfile,
    capability: ProfileFamilyCapability | None = None,
) -> str | None:
    capability = capability or ProfileFamilyCapability(profile.family)
    return capability.backend("cpp").target


def cpp_value_test_compile_options() -> tuple[CppCompilerOption, ...]:
    """Options required by generated value-test arithmetic semantics."""

    return (CppCompilerOption("-fwrapv", _WRAPPING_ARITHMETIC_COMPILER_IDS),)


__all__ = (
    "CppCompilerOption",
    "cpp_profile_compile_options",
    "cpp_profile_flags",
    "cpp_profile_target",
    "cpp_value_test_compile_options",
)
