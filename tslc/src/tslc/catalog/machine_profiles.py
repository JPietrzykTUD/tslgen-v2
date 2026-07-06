"""Machine feature profiles (the new notion of a generation 'profile').

A profile is a named feature-set (e.g. ``avx2`` = {sse, sse2, …, avx, avx2}).
Loaded from ``supplementary/buildsystem/machine_profiles.json``. An implementation
body is usable in a profile iff the `requires` clause applying to the type has its
target features ⊆ the profile's features; the profile thus decides which
specializations are emitted.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.diagnostics import Diagnostic, SourceLocation, sort_diagnostics

# Sentinel used by the generic/scalar profile to mean "no SIMD features".
_NO_SIMD = "NOSIMD-INVALID"


@dataclass(frozen=True, slots=True)
class MachineProfileEmulator:
    """Emulator profile metadata for after-write value-test execution.

    Executable paths are deliberately not catalog data; the CLI/verifier provide
    those. This record only says which emulator family and profile/CPU a machine
    profile should use when tests cannot run natively.
    """

    kind: str
    profile: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MachineProfile:
    name: str
    family: str
    features: frozenset[str]
    # feature -> its compiler/target-feature spelling when it differs from the token
    # (e.g. avx512_vpclmulqdq -> vpclmulqdq, neon -> asimd).
    alternatives: Mapping[str, str]
    # Extra C++ compiler flags owned by this machine profile. These are full
    # compiler arguments, not feature-token spellings.
    cpp_flags: tuple[str, ...] = ()
    # Optional emulator profile used by the after-write verifier to run value
    # tests on hosts that do not support the profile's ISA natively.
    emulator: MachineProfileEmulator | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "alternatives", MappingProxyType(dict(self.alternatives)))
        object.__setattr__(self, "cpp_flags", tuple(self.cpp_flags))


@dataclass(frozen=True, slots=True)
class MachineProfileLoadResult:
    profiles: Mapping[str, MachineProfile]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _JsonObject:
    pairs: tuple[tuple[str, Any], ...]


def load_machine_profiles(
    path: Path,
    target_families: TargetFamilyCatalog | None = None,
) -> Mapping[str, MachineProfile]:
    """Load every machine profile, keyed by name. The filesystem-read boundary."""

    return load_machine_profiles_checked(path, target_families).profiles


def load_machine_profiles_checked(
    path: Path,
    target_families: TargetFamilyCatalog | None = None,
) -> MachineProfileLoadResult:
    """Load machine profiles with structural validation diagnostics."""

    diagnostics: list[Diagnostic] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return MachineProfileLoadResult(
            profiles=MappingProxyType({}),
            diagnostics=(
                _diagnostic(
                    path,
                    "TSL-PROFILE-READ-ERROR",
                    f"could not read machine profiles {path}: {exc}",
                ),
            ),
        )

    try:
        data = json.loads(text, object_pairs_hook=lambda pairs: _JsonObject(tuple(pairs)))
    except json.JSONDecodeError as exc:
        return MachineProfileLoadResult(
            profiles=MappingProxyType({}),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="TSL-PROFILE-MALFORMED-JSON",
                    message=f"could not parse machine profiles {path}: {exc.msg}",
                    location=SourceLocation(path, exc.lineno, exc.colno),
                ),
            ),
        )

    if not isinstance(data, _JsonObject):
        return MachineProfileLoadResult(
            profiles=MappingProxyType({}),
            diagnostics=(
                _diagnostic(
                    path,
                    "TSL-PROFILE-MALFORMED-SHAPE",
                    "machine profiles root must be a JSON object",
                ),
            ),
        )

    profiles: dict[str, MachineProfile] = {}
    _seen_names(data.pairs, "TSL-PROFILE-DUPLICATE-FAMILY", path, diagnostics)
    for family, entries in data.pairs:
        if (
            target_families is not None
            and target_families.profile_family_names
            and not target_families.supports_profile_family(family)
        ):
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-INVALID-FAMILY",
                    (
                        f"machine profile family {family!r} is not declared in "
                        "target_families"
                    ),
                )
            )
        if not isinstance(entries, list):
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-MALFORMED-SHAPE",
                    f"machine profile family {family!r} must contain a list",
                )
            )
            continue
        for entry in entries:
            if not isinstance(entry, _JsonObject):
                diagnostics.append(
                    _diagnostic(
                        path,
                        "TSL-PROFILE-MALFORMED-SHAPE",
                        f"machine profile entry under {family!r} must be an object",
                    )
                )
                continue
            fields = _object_fields(entry, path, diagnostics)
            _unknown_fields(
                fields,
                {"name", "flags", "alternatives", "cpp_flags", "emulator"},
                path,
                diagnostics,
                owner=f"profile entry under {family!r}",
            )
            name_value = fields.get("name")
            if not isinstance(name_value, str) or not name_value:
                diagnostics.append(
                    _diagnostic(
                        path,
                        "TSL-PROFILE-MISSING-NAME",
                        f"machine profile entry under {family!r} must have a string name",
                    )
                )
                continue
            name = name_value
            if name in profiles:
                diagnostics.append(
                    _diagnostic(
                        path,
                        "TSL-PROFILE-DUPLICATE-NAME",
                        f"duplicate machine profile name {name!r}",
                    )
                )
            flags_value = fields.get("flags", "")
            if not isinstance(flags_value, str):
                diagnostics.append(
                    _diagnostic(
                        path,
                        "TSL-PROFILE-MALFORMED-FLAGS",
                        f"machine profile {name!r} flags must be a string",
                    )
                )
                continue
            flags_text = flags_value
            features = (
                frozenset()
                if flags_text.strip() == _NO_SIMD
                else frozenset(flags_text.split())
            )
            alternatives_value = fields.get("alternatives", _JsonObject(()))
            alternatives = _alternatives(name, alternatives_value, path, diagnostics)
            cpp_flags = _string_list_field(
                name,
                fields.get("cpp_flags", ()),
                "cpp_flags",
                path,
                diagnostics,
            )
            emulator = _emulator(
                name,
                family,
                fields.get("emulator"),
                target_families,
                path,
                diagnostics,
            )
            profiles[name] = MachineProfile(
                name=name,
                family=family,
                features=features,
                alternatives=alternatives,
                cpp_flags=cpp_flags,
                emulator=emulator,
            )
    return MachineProfileLoadResult(
        profiles=MappingProxyType(profiles),
        diagnostics=sort_diagnostics(diagnostics),
    )


def _object_fields(
    obj: _JsonObject,
    path: Path,
    diagnostics: list[Diagnostic],
) -> dict[str, Any]:
    _seen_names(obj.pairs, "TSL-PROFILE-DUPLICATE-KEY", path, diagnostics)
    fields: dict[str, Any] = {}
    for key, value in obj.pairs:
        fields[key] = value
    return fields


def _seen_names(
    pairs: tuple[tuple[str, Any], ...],
    code: str,
    path: Path,
    diagnostics: list[Diagnostic],
) -> set[str]:
    seen: set[str] = set()
    for key, _value in pairs:
        if key in seen:
            diagnostics.append(
                _diagnostic(path, code, f"duplicate key {key!r} in machine profiles")
            )
        seen.add(key)
    return seen


def _unknown_fields(
    fields: Mapping[str, Any],
    allowed: set[str],
    path: Path,
    diagnostics: list[Diagnostic],
    *,
    owner: str,
) -> None:
    for key in sorted(fields):
        if key not in allowed:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNKNOWN-FIELD",
                    f"unknown field {key!r} in {owner}",
                )
            )


def _alternatives(
    profile_name: str,
    value: Any,
    path: Path,
    diagnostics: list[Diagnostic],
) -> dict[str, str]:
    if not isinstance(value, _JsonObject):
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-ALTERNATIVES",
                f"machine profile {profile_name!r} alternatives must be an object",
            )
        )
        return {}
    fields = _object_fields(value, path, diagnostics)
    alternatives: dict[str, str] = {}
    for key, spelling in fields.items():
        if not isinstance(spelling, str):
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-MALFORMED-ALTERNATIVES",
                    f"machine profile {profile_name!r} alternative {key!r} must be a string",
                )
            )
            continue
        alternatives[key] = spelling
    return alternatives


def _string_list_field(
    profile_name: str,
    value: Any,
    field_name: str,
    path: Path,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    if value == ():
        return ()
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    diagnostics.append(
        _diagnostic(
            path,
            "TSL-PROFILE-MALFORMED-FIELD",
            f"machine profile {profile_name!r} {field_name} must be a string list",
        )
    )
    return ()


def _emulator(
    profile_name: str,
    family: str,
    value: Any,
    target_families: TargetFamilyCatalog | None,
    path: Path,
    diagnostics: list[Diagnostic],
) -> MachineProfileEmulator | None:
    if value is None:
        return None
    if not isinstance(value, _JsonObject):
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-EMULATOR",
                f"machine profile {profile_name!r} emulator must be an object",
            )
        )
        return None
    fields = _object_fields(value, path, diagnostics)
    _unknown_fields(
        fields,
        {"kind", "profile", "args"},
        path,
        diagnostics,
        owner=f"emulator for machine profile {profile_name!r}",
    )
    kind_value = fields.get("kind")
    if not isinstance(kind_value, str) or not kind_value.strip():
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-EMULATOR",
                f"machine profile {profile_name!r} emulator kind must be a non-empty string",
            )
        )
        return None
    kind = kind_value.strip()
    allowed = (
        target_families.emulator_kinds_for_profile_family(family)
        if target_families is not None and target_families.supports_profile_family(family)
        else frozenset()
    )
    if allowed or (
        target_families is not None and target_families.supports_profile_family(family)
    ):
        if kind not in allowed:
            expected = ", ".join(sorted(allowed)) if allowed else "no emulator"
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNSUPPORTED-EMULATOR",
                    (
                        f"machine profile {profile_name!r} emulator kind {kind!r} is not "
                        f"declared for family {family!r}; expected {expected}"
                    ),
                )
            )
    profile_value = fields.get("profile")
    if not isinstance(profile_value, str) or not profile_value.strip():
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-EMULATOR",
                f"machine profile {profile_name!r} emulator profile must be a non-empty string",
            )
        )
        return None
    args_value = fields.get("args", ())
    args: tuple[str, ...]
    if args_value == ():
        args = ()
    elif isinstance(args_value, list) and all(isinstance(item, str) for item in args_value):
        args = tuple(args_value)
    else:
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-EMULATOR",
                f"machine profile {profile_name!r} emulator args must be a string list",
            )
        )
        args = ()
    cleaned_profile = profile_value.strip().lstrip("-") if kind == "sde" else profile_value.strip()
    return MachineProfileEmulator(kind=kind, profile=cleaned_profile, args=args)


def _diagnostic(path: Path, code: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=message,
        location=SourceLocation(path, 1, 1),
    )
