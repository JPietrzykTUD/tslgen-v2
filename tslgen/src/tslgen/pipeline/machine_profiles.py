"""Machine feature profile loading and normalization."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.machine_profiles import (
    FeatureFlagName,
    FeatureFlagNormalization,
    FeatureFlagNormalizationCatalog,
    FeatureFlagSpelling,
    MachineFeatureAlternative,
    MachineFeatureProfile,
    MachineFeatureProfileCatalog,
    MachineProfileFamily,
    MachineProfileName,
)

_FLAG_HEADER = "flags:"
_FLAG_LINE_PATTERN = re.compile(
    r'^  (?P<spelling>[A-Za-z0-9_.]+) \{normalized "(?P<normalized>[A-Za-z0-9_.]+)"\}$'
)
_SCALAR_NO_SIMD_SENTINEL = "NOSIMD-INVALID"


@dataclass(frozen=True, slots=True)
class FeatureFlagNormalizationParseResult:
    catalog: FeatureFlagNormalizationCatalog | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class MachineFeatureProfileCatalogBuildResult:
    catalog: MachineFeatureProfileCatalog | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class MachineFeatureProfileCatalogLoadResult:
    catalog: MachineFeatureProfileCatalog | None
    flag_catalog: FeatureFlagNormalizationCatalog | None
    diagnostics: tuple[Diagnostic, ...]


def parse_feature_flag_normalizations(
    text: str,
    path: Path,
) -> FeatureFlagNormalizationParseResult:
    diagnostics: list[Diagnostic] = []
    entries: list[FeatureFlagNormalization] = []
    seen_spellings: dict[str, SourceLocation] = {}

    lines = text.splitlines()
    if not lines or lines[0] != _FLAG_HEADER:
        return FeatureFlagNormalizationParseResult(
            catalog=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-FLAGS-MALFORMED-FORM",
                    message="flag normalization source must start with 'flags:'",
                    location=SourceLocation(path, 1, 1),
                ),
            ),
        )

    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        match = _FLAG_LINE_PATTERN.match(line)
        if match is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-FLAGS-MALFORMED-FORM",
                    message=(
                        "unsupported flag normalization line; expected "
                        "'  NAME {normalized \"NAME\"}'"
                    ),
                    location=SourceLocation(path, line_number, _first_column(line)),
                )
            )
            continue

        spelling = match.group("spelling")
        source = SourceLocation(path, line_number, 3)
        first_source = seen_spellings.get(spelling)
        if first_source is not None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-FLAGS-DUPLICATE-SPELLING",
                    message=(
                        f"feature flag spelling {spelling!r} is declared more "
                        "than once; first declaration is at "
                        f"{first_source.path}:{first_source.line}:{first_source.column}"
                    ),
                    location=source,
                )
            )
            continue
        seen_spellings[spelling] = source
        entries.append(
            FeatureFlagNormalization(
                spelling=FeatureFlagSpelling(spelling),
                normalized=FeatureFlagName(match.group("normalized")),
                source=source,
            )
        )

    if diagnostics:
        return FeatureFlagNormalizationParseResult(
            catalog=None,
            diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
        )

    return FeatureFlagNormalizationParseResult(
        catalog=FeatureFlagNormalizationCatalog(
            entries=tuple(sorted(entries, key=lambda item: str(item.spelling)))
        ),
        diagnostics=(),
    )


def build_machine_feature_profile_catalog(
    text: str,
    path: Path,
    flag_catalog: FeatureFlagNormalizationCatalog,
) -> MachineFeatureProfileCatalogBuildResult:
    try:
        data = json.loads(text)
    except JSONDecodeError as error:
        return MachineFeatureProfileCatalogBuildResult(
            catalog=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-MALFORMED-JSON",
                    message=f"machine profile JSON is malformed: {error.msg}",
                    location=SourceLocation(path, error.lineno, error.colno),
                ),
            ),
        )

    if not isinstance(data, dict):
        return MachineFeatureProfileCatalogBuildResult(
            catalog=None,
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-MALFORMED-JSON-SHAPE",
                    message="machine profile JSON root must be an object",
                    location=SourceLocation(path, 1, 1),
                ),
            ),
        )

    diagnostics: list[Diagnostic] = []
    profiles: list[MachineFeatureProfile] = []
    for family in sorted(data):
        raw_profiles = data[family]
        family_source = _find_json_location(text, path, f'"{family}"')
        if not isinstance(family, str) or not family:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-MALFORMED-FAMILY",
                    message="machine profile family names must be non-empty strings",
                    location=family_source,
                )
            )
            continue
        if not isinstance(raw_profiles, list):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-MALFORMED-FAMILY",
                    message=f"machine profile family {family!r} must contain a list",
                    location=family_source,
                )
            )
            continue

        profiles.extend(
            _build_family_profiles(
                family,
                raw_profiles,
                text,
                path,
                flag_catalog,
                diagnostics,
            )
        )

    if diagnostics:
        return MachineFeatureProfileCatalogBuildResult(
            catalog=None,
            diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
        )

    return MachineFeatureProfileCatalogBuildResult(
        catalog=MachineFeatureProfileCatalog(
            profiles=tuple(
                sorted(
                    profiles,
                    key=lambda item: (str(item.family), str(item.name)),
                )
            )
        ),
        diagnostics=(),
    )


def load_machine_feature_profile_catalog(
    profile_path: Path,
    flags_path: Path,
) -> MachineFeatureProfileCatalogLoadResult:
    flag_text = flags_path.read_text(encoding="utf-8")
    flag_result = parse_feature_flag_normalizations(flag_text, flags_path.resolve())
    diagnostics = list(flag_result.diagnostics)
    if flag_result.catalog is None:
        return MachineFeatureProfileCatalogLoadResult(
            catalog=None,
            flag_catalog=None,
            diagnostics=tuple(diagnostics),
        )

    profile_text = profile_path.read_text(encoding="utf-8")
    profile_result = build_machine_feature_profile_catalog(
        profile_text,
        profile_path.resolve(),
        flag_result.catalog,
    )
    diagnostics.extend(profile_result.diagnostics)
    return MachineFeatureProfileCatalogLoadResult(
        catalog=profile_result.catalog,
        flag_catalog=flag_result.catalog,
        diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
    )


def _build_family_profiles(
    family: str,
    raw_profiles: list[object],
    text: str,
    path: Path,
    flag_catalog: FeatureFlagNormalizationCatalog,
    diagnostics: list[Diagnostic],
) -> tuple[MachineFeatureProfile, ...]:
    profiles: list[MachineFeatureProfile] = []
    seen_names: dict[str, SourceLocation] = {}

    for raw_profile in raw_profiles:
        if not isinstance(raw_profile, dict):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-MALFORMED-ENTRY",
                    message=f"machine profile entry in family {family!r} must be an object",
                    location=_find_json_location(text, path, f'"{family}"'),
                )
            )
            continue

        profile = _build_profile(
            family,
            raw_profile,
            text,
            path,
            flag_catalog,
            diagnostics,
        )
        if profile is None:
            continue
        first_source = seen_names.get(str(profile.name))
        if first_source is not None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-DUPLICATE-PROFILE",
                    message=(
                        f"machine profile {family!r}/{str(profile.name)!r} is "
                        "declared more than once; first declaration is at "
                        f"{first_source.path}:{first_source.line}:{first_source.column}"
                    ),
                    location=profile.source,
                )
            )
            continue
        seen_names[str(profile.name)] = profile.source
        profiles.append(profile)

    return tuple(profiles)


def _build_profile(
    family: str,
    raw_profile: Mapping[object, object],
    text: str,
    path: Path,
    flag_catalog: FeatureFlagNormalizationCatalog,
    diagnostics: list[Diagnostic],
) -> MachineFeatureProfile | None:
    raw_name = raw_profile.get("name")
    source = _profile_source(raw_name, family, text, path)
    if not isinstance(raw_name, str) or not raw_name:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-MACHINE-PROFILE-MALFORMED-NAME",
                message=f"machine profile in family {family!r} must have a non-empty name",
                location=source,
            )
        )
        return None

    raw_flags = raw_profile.get("flags")
    if not isinstance(raw_flags, str):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-MACHINE-PROFILE-MALFORMED-FLAGS",
                message=(
                    f"machine profile {family!r}/{raw_name!r} must have a "
                    "space-separated flags string"
                ),
                location=source,
            )
        )
        return None

    features = _normalize_profile_flags(
        family,
        raw_name,
        raw_flags,
        source,
        flag_catalog,
        diagnostics,
    )
    alternatives = _normalize_profile_alternatives(
        family,
        raw_name,
        raw_profile.get("alternatives", {}),
        source,
        flag_catalog,
        diagnostics,
    )
    if features is None or alternatives is None:
        return None

    return MachineFeatureProfile(
        family=MachineProfileFamily(family),
        name=MachineProfileName(raw_name),
        features=features,
        alternatives=alternatives,
        source=source,
    )


def _normalize_profile_flags(
    family: str,
    profile_name: str,
    flags: str,
    source: SourceLocation,
    flag_catalog: FeatureFlagNormalizationCatalog,
    diagnostics: list[Diagnostic],
) -> tuple[FeatureFlagName, ...] | None:
    diagnostic_start = len(diagnostics)
    if flags == _SCALAR_NO_SIMD_SENTINEL:
        return ()

    raw_flags = tuple(flag for flag in flags.split(" ") if flag)
    if not raw_flags:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-MACHINE-PROFILE-MALFORMED-FLAGS",
                message=(
                    f"machine profile {family!r}/{profile_name!r} must list "
                    "at least one flag or the scalar sentinel"
                ),
                location=source,
            )
        )
        return None

    normalized_flags: list[FeatureFlagName] = []
    seen: set[FeatureFlagName] = set()
    for raw_flag in raw_flags:
        normalized = flag_catalog.normalize(raw_flag)
        if normalized is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-UNKNOWN-FLAG",
                    message=(
                        f"machine profile {family!r}/{profile_name!r} uses "
                        f"unknown feature flag {raw_flag!r}"
                    ),
                    location=source,
                )
            )
            continue
        if normalized in seen:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-DUPLICATE-FLAG",
                    message=(
                        f"machine profile {family!r}/{profile_name!r} repeats "
                        f"normalized feature flag {str(normalized)!r}"
                    ),
                    location=source,
                )
            )
            continue
        seen.add(normalized)
        normalized_flags.append(normalized)

    if len(diagnostics) != diagnostic_start:
        return None
    return tuple(normalized_flags)


def _normalize_profile_alternatives(
    family: str,
    profile_name: str,
    raw_alternatives: object,
    source: SourceLocation,
    flag_catalog: FeatureFlagNormalizationCatalog,
    diagnostics: list[Diagnostic],
) -> tuple[MachineFeatureAlternative, ...] | None:
    diagnostic_start = len(diagnostics)
    if not isinstance(raw_alternatives, dict):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-MACHINE-PROFILE-MALFORMED-ALTERNATIVES",
                message=(
                    f"machine profile {family!r}/{profile_name!r} alternatives "
                    "must be an object"
                ),
                location=source,
            )
        )
        return None

    alternatives: list[MachineFeatureAlternative] = []
    seen: set[FeatureFlagName] = set()
    for raw_key in sorted(raw_alternatives):
        raw_value = raw_alternatives[raw_key]
        if not isinstance(raw_key, str) or not raw_key:
            diagnostics.append(
                _malformed_alternative_diagnostic(family, profile_name, source)
            )
            continue
        if not isinstance(raw_value, str) or not raw_value:
            diagnostics.append(
                _malformed_alternative_diagnostic(family, profile_name, source)
            )
            continue

        feature = flag_catalog.normalize(raw_key)
        if feature is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-UNKNOWN-FLAG",
                    message=(
                        f"machine profile {family!r}/{profile_name!r} "
                        f"alternative references unknown feature flag {raw_key!r}"
                    ),
                    location=source,
                )
            )
            continue
        if feature in seen:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-MACHINE-PROFILE-DUPLICATE-ALTERNATIVE",
                    message=(
                        f"machine profile {family!r}/{profile_name!r} repeats "
                        f"alternative spelling for feature {str(feature)!r}"
                    ),
                    location=source,
                )
            )
            continue

        seen.add(feature)
        alternatives.append(
            MachineFeatureAlternative(
                feature=feature,
                spelling=FeatureFlagSpelling(raw_value),
            )
        )

    if len(diagnostics) != diagnostic_start:
        return None
    return tuple(
        sorted(alternatives, key=lambda item: (str(item.feature), str(item.spelling)))
    )


def _malformed_alternative_diagnostic(
    family: str,
    profile_name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-MACHINE-PROFILE-MALFORMED-ALTERNATIVES",
        message=(
            f"machine profile {family!r}/{profile_name!r} alternatives must map "
            "non-empty feature names to non-empty spelling strings"
        ),
        location=source,
    )


def _profile_source(
    raw_name: object,
    family: str,
    text: str,
    path: Path,
) -> SourceLocation:
    if isinstance(raw_name, str) and raw_name:
        return _find_json_location(text, path, f'"{raw_name}"')
    return _find_json_location(text, path, f'"{family}"')


def _find_json_location(text: str, path: Path, needle: str) -> SourceLocation:
    offset = text.find(needle)
    if offset < 0:
        return SourceLocation(path, 1, 1)
    return _location_for_offset(text, path, offset)


def _location_for_offset(text: str, path: Path, offset: int) -> SourceLocation:
    preceding = text[:offset]
    line = preceding.count("\n") + 1
    line_start = preceding.rfind("\n")
    if line_start < 0:
        column = offset + 1
    else:
        column = offset - line_start
    return SourceLocation(path, line, column)


def _first_column(line: str) -> int:
    stripped = line.lstrip(" ")
    return len(line) - len(stripped) + 1


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str, int, int, str]:
    location = diagnostic.location
    if location is None:
        return diagnostic.code, "", 0, 0, diagnostic.message
    return (
        diagnostic.code,
        location.path.as_posix(),
        location.line,
        location.column,
        diagnostic.message,
    )
