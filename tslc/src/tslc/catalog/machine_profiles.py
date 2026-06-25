"""Machine feature profiles (the new notion of a generation 'profile').

A profile is a named feature-set (e.g. ``avx2`` = {sse, sse2, …, avx, avx2}).
Loaded from ``supplementary/buildsystem/machine_profiles.json``. An implementation
body is usable in a profile iff the `requires` clause applying to the type has its
flags ⊆ the profile's features; the profile thus decides which extensions'
specializations are emitted.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tslc.diagnostics import Diagnostic, SourceLocation, sort_diagnostics

# Sentinel used by the generic/scalar profile to mean "no SIMD features".
_NO_SIMD = "NOSIMD-INVALID"


@dataclass(frozen=True, slots=True)
class MachineProfile:
    name: str
    family: str  # "generic" | "x86" | "aarch64"
    features: frozenset[str]
    # feature -> its compiler/target-feature spelling when it differs from the token
    # (e.g. avx512_vpclmulqdq -> vpclmulqdq, neon -> asimd).
    alternatives: Mapping[str, str]
    # Optional Intel SDE chip alias used by the after-write verifier to run value tests
    # on hosts that do not support the profile's ISA natively.
    sde: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "alternatives", MappingProxyType(dict(self.alternatives)))


@dataclass(frozen=True, slots=True)
class MachineProfileLoadResult:
    profiles: Mapping[str, MachineProfile]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _JsonObject:
    pairs: tuple[tuple[str, Any], ...]


def load_machine_profiles(path: Path) -> Mapping[str, MachineProfile]:
    """Load every machine profile, keyed by name. The filesystem-read boundary."""

    return load_machine_profiles_checked(path).profiles


def load_machine_profiles_checked(path: Path) -> MachineProfileLoadResult:
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
        if family not in {"generic", "x86", "aarch64"}:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-INVALID-FAMILY",
                    f"machine profile family {family!r} is not supported",
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
                {"name", "flags", "alternatives", "sde"},
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
            sde = _sde_chip(name, fields.get("sde"), path, diagnostics)
            profiles[name] = MachineProfile(
                name=name,
                family=family,
                features=features,
                alternatives=alternatives,
                sde=sde,
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


def _sde_chip(
    profile_name: str,
    value: Any,
    path: Path,
    diagnostics: list[Diagnostic],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-SDE",
                f"machine profile {profile_name!r} sde chip must be a non-empty string",
            )
        )
        return None
    return value.strip().lstrip("-")


def _diagnostic(path: Path, code: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=message,
        location=SourceLocation(path, 1, 1),
    )
