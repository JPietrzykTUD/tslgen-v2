"""Profile subset selection for generated backend projects."""

from __future__ import annotations

from collections import Counter

from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.generated_project import (
    GeneratedProfileSelectionResult,
    GeneratedProfileSet,
)
from tslgen.domain.machine_profiles import (
    MachineFeatureProfile,
    MachineFeatureProfileCatalog,
    MachineProfileName,
)

_ALL_PROFILES = "all"
_DEFAULT_PROFILE = "scalar"


def select_generated_profiles(
    catalog: MachineFeatureProfileCatalog,
    requested_profiles: tuple[str, ...] | None = None,
) -> GeneratedProfileSelectionResult:
    """Resolve a generated profile subset from profile names.

    The selection syntax is deliberately small for M191: no request means the
    scalar profile, `all` means every catalog profile in catalog order, and
    any other value is matched by profile name across families.
    """

    requested = _normalize_requested_profiles(requested_profiles)
    diagnostics: list[Diagnostic] = []

    if requested == (_ALL_PROFILES,):
        if not catalog.profiles:
            return GeneratedProfileSelectionResult(
                profile_set=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-GENERATED-PROFILE-SELECTION-EMPTY-CATALOG",
                        message="cannot select all generated profiles from an empty catalog",
                    ),
                ),
            )
        profiles = catalog.profiles
        return GeneratedProfileSelectionResult(
            profile_set=GeneratedProfileSet(
                profiles=profiles,
                default_profile=_default_profile(profiles),
            )
        )

    if _ALL_PROFILES in requested:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-GENERATED-PROFILE-SELECTION-ALL-MUST-STAND-ALONE",
                message="reserved generated profile selection 'all' cannot be combined",
            )
        )

    duplicate_names = tuple(
        sorted(name for name, count in Counter(requested).items() if count > 1)
    )
    diagnostics.extend(
        Diagnostic(
            severity="error",
            code="TSL-GENERATED-PROFILE-SELECTION-DUPLICATE-PROFILE",
            message=f"generated profile {name!r} was requested more than once",
        )
        for name in duplicate_names
    )

    resolved: list[MachineFeatureProfile] = []
    seen: set[str] = set()
    for name in requested:
        if name in seen or name == _ALL_PROFILES:
            continue
        seen.add(name)
        matches = _profiles_named(catalog, name)
        if not matches:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-GENERATED-PROFILE-SELECTION-UNKNOWN-PROFILE",
                    message=f"unknown generated profile {name!r}",
                )
            )
            continue
        if len(matches) > 1:
            families = ", ".join(sorted(str(profile.family) for profile in matches))
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-GENERATED-PROFILE-SELECTION-AMBIGUOUS-PROFILE",
                    message=(
                        f"generated profile {name!r} is ambiguous across "
                        f"families: {families}"
                    ),
                )
            )
            continue
        resolved.append(matches[0])

    if diagnostics:
        return GeneratedProfileSelectionResult(
            profile_set=None,
            diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
        )

    profiles = tuple(resolved)
    return GeneratedProfileSelectionResult(
        profile_set=GeneratedProfileSet(
            profiles=profiles,
            default_profile=_default_profile(profiles),
        )
    )


def _normalize_requested_profiles(
    requested_profiles: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if requested_profiles is None or requested_profiles == ():
        return (_DEFAULT_PROFILE,)
    return tuple(str(profile) for profile in requested_profiles)


def _profiles_named(
    catalog: MachineFeatureProfileCatalog,
    name: str,
) -> tuple[MachineFeatureProfile, ...]:
    return tuple(profile for profile in catalog.profiles if str(profile.name) == name)


def _default_profile(
    profiles: tuple[MachineFeatureProfile, ...],
) -> MachineFeatureProfile:
    for profile in profiles:
        if profile.name == MachineProfileName(_DEFAULT_PROFILE):
            return profile
    return profiles[0]


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str]:
    return (diagnostic.code, diagnostic.message)
