"""Machine target-feature and compile-mode profiles.

A profile is a named feature-set (e.g. ``avx2`` = {sse, sse2, …, avx, avx2}).
Loaded from ``supplementary/buildsystem/machine_profiles.json``. An implementation
body is usable in a profile iff the `requires` clause applying to the type has its
target features ⊆ the profile's features; the profile thus decides which
specializations are emitted. Extension activation may additionally require a
compiler mode such as a fixed SVE vector width.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tslc.catalog.target_families import TargetFamilyCatalog, TargetFeatureCapability
from tslc.diagnostics import Diagnostic, SourceSpan, sort_diagnostics

# Sentinel used by the generic/scalar profile to mean "no target features".
_NO_SIMD = "NOSIMD-INVALID"


@dataclass(frozen=True, slots=True)
class MachineProfileRunner:
    """Runner metadata for after-write value-test execution.

    Executable paths are deliberately not catalog data; the CLI/verifier provide
    those. This record only says which runner family and profile/CPU a machine
    profile should use when tests cannot run directly.
    """

    kind: str
    profile: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MachineProfile:
    name: str
    family: str
    features: frozenset[str]
    # Profile-specific feature spelling overrides. Shared spelling differences
    # belong to the source target-feature catalog.
    alternatives: Mapping[str, str]
    feature_capabilities: Mapping[str, TargetFeatureCapability] = field(
        default_factory=dict
    )
    # Compiler-selected modes that are not hardware target features, e.g. fixed SVE width.
    compile_modes: frozenset[str] = frozenset()
    # Extra compiler flags keyed by backend. These are full compiler arguments,
    # not feature-token spellings.
    backend_flags: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # Backends intentionally emitted for this profile. None on a manually
    # constructed profile preserves the historical unrestricted behavior.
    supported_backends: frozenset[str] | None = None
    # Optional runner profile used by the after-write verifier to execute value
    # tests on hosts that cannot run the profile directly.
    runner: MachineProfileRunner | None = None
    # Optional opt-in gate for generated profile auto-detection. Ungated profiles
    # may participate in auto-detection by default; gated profiles require an
    # explicit generated build-system option.
    auto_detect_gate: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", frozenset(self.features))
        object.__setattr__(self, "compile_modes", frozenset(self.compile_modes))
        if self.supported_backends is not None:
            object.__setattr__(
                self, "supported_backends", frozenset(self.supported_backends)
            )
        object.__setattr__(self, "alternatives", MappingProxyType(dict(self.alternatives)))
        object.__setattr__(
            self,
            "feature_capabilities",
            MappingProxyType(dict(sorted(self.feature_capabilities.items()))),
        )
        object.__setattr__(
            self,
            "backend_flags",
            MappingProxyType(
                {
                    backend_id: tuple(flags)
                    for backend_id, flags in sorted(self.backend_flags.items())
                }
            ),
        )

    def flags_for_backend(self, backend_id: str) -> tuple[str, ...]:
        return self.backend_flags.get(backend_id, ())

    def supports_backend(self, backend_id: str) -> bool:
        return (
            self.supported_backends is None
            or backend_id in self.supported_backends
        )

    def feature_spelling(self, feature: str, backend_id: str) -> str:
        override = self.alternatives.get(feature)
        if override is not None:
            return override
        capability = self.feature_capabilities.get(feature)
        return feature if capability is None else capability.spelling(backend_id)

    def feature_spellings(self, backend_id: str) -> Mapping[str, str]:
        return MappingProxyType(
            {
                feature: self.feature_spelling(feature, backend_id)
                for feature in sorted(self.features)
            }
        )


@dataclass(frozen=True, slots=True)
class MachineProfileLoadResult:
    profiles: Mapping[str, MachineProfile]
    diagnostics: tuple[Diagnostic, ...]
    digest: str | None = None


@dataclass(frozen=True, slots=True)
class _JsonObject:
    pairs: tuple[tuple[str, Any], ...]


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
            digest=None,
        )

    digest = sha256(text.encode("utf-8")).hexdigest()

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
                    span=SourceSpan(
                        path,
                        exc.lineno,
                        exc.colno,
                        exc.lineno,
                        exc.colno + 1,
                    ),
                ),
            ),
            digest=digest,
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
            digest=digest,
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
                {
                    "name",
                    "target_features",
                    "compile_modes",
                    "alternatives",
                    "backend_flags",
                    "supported_backends",
                    "runner",
                    "auto_detect_gate",
                },
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
            features = _token_set_field(
                name,
                fields.get("target_features", ""),
                "target_features",
                "TSL-PROFILE-MALFORMED-TARGET-FEATURES",
                path,
                diagnostics,
                allow_no_simd=True,
            )
            if features is None:
                continue
            compile_modes = _token_set_field(
                name,
                fields.get("compile_modes", ""),
                "compile_modes",
                "TSL-PROFILE-MALFORMED-COMPILE-MODES",
                path,
                diagnostics,
            )
            if compile_modes is None:
                continue
            alternatives_value = fields.get("alternatives", _JsonObject(()))
            alternatives = _alternatives(
                name,
                alternatives_value,
                features,
                path,
                diagnostics,
            )
            feature_capabilities = _feature_capabilities(
                name,
                features,
                target_families,
                path,
                diagnostics,
            )
            backend_flags = _backend_flags(
                name,
                fields.get("backend_flags", _JsonObject(())),
                target_families,
                path,
                diagnostics,
            )
            supported_backends = _supported_backends(
                name,
                family,
                fields.get("supported_backends"),
                target_families,
                path,
                diagnostics,
            )
            runner = _runner(
                name,
                family,
                fields.get("runner"),
                target_families,
                path,
                diagnostics,
            )
            auto_detect_gate = _optional_token_field(
                name,
                fields.get("auto_detect_gate"),
                "auto_detect_gate",
                path,
                diagnostics,
            )
            profiles[name] = MachineProfile(
                name=name,
                family=family,
                features=features,
                alternatives=alternatives,
                feature_capabilities=feature_capabilities,
                compile_modes=compile_modes,
                backend_flags=backend_flags,
                supported_backends=supported_backends,
                runner=runner,
                auto_detect_gate=auto_detect_gate,
            )
    return MachineProfileLoadResult(
        profiles=MappingProxyType(profiles),
        diagnostics=sort_diagnostics(diagnostics),
        digest=digest,
    )


def target_feature_names(
    profiles: Mapping[str, MachineProfile],
) -> tuple[str, ...]:
    """Return the author-facing feature tokens accepted by ``requires`` clauses."""

    return tuple(
        sorted(
            {
                feature
                for profile in profiles.values()
                for feature in profile.features
                if feature != _NO_SIMD
            }
        )
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
    features: frozenset[str],
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
        if key not in features:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNKNOWN-ALTERNATIVE",
                    (
                        f"machine profile {profile_name!r} alternative {key!r} "
                        "does not name one of its target features"
                    ),
                )
            )
        if not isinstance(spelling, str) or not spelling:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-MALFORMED-ALTERNATIVES",
                    (
                        f"machine profile {profile_name!r} alternative {key!r} "
                        "must be a non-empty string"
                    ),
                )
            )
            continue
        alternatives[key] = spelling
    return alternatives


def _feature_capabilities(
    profile_name: str,
    features: frozenset[str],
    target_families: TargetFamilyCatalog | None,
    path: Path,
    diagnostics: list[Diagnostic],
) -> dict[str, TargetFeatureCapability]:
    if target_families is None or not target_families.target_feature_names:
        return {}
    capabilities: dict[str, TargetFeatureCapability] = {}
    for feature in sorted(features):
        capability = target_families.target_feature(feature)
        if capability is None:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNKNOWN-TARGET-FEATURE",
                    (
                        f"machine profile {profile_name!r} target feature "
                        f"{feature!r} is not declared in target_families"
                    ),
                )
            )
            continue
        capabilities[feature] = capability
    return capabilities


def _token_set_field(
    profile_name: str,
    value: Any,
    field_name: str,
    code: str,
    path: Path,
    diagnostics: list[Diagnostic],
    *,
    allow_no_simd: bool = False,
) -> frozenset[str] | None:
    if not isinstance(value, str):
        diagnostics.append(
            _diagnostic(
                path,
                code,
                f"machine profile {profile_name!r} {field_name} must be a string",
            )
        )
        return None
    if allow_no_simd and value.strip() == _NO_SIMD:
        return frozenset()
    return frozenset(value.split())


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


def _backend_flags(
    profile_name: str,
    value: Any,
    target_families: TargetFamilyCatalog | None,
    path: Path,
    diagnostics: list[Diagnostic],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, _JsonObject):
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-FIELD",
                f"machine profile {profile_name!r} backend_flags must be an object",
            )
        )
        return {}
    fields = _object_fields(value, path, diagnostics)
    known_backends = (
        target_families.backend_ids if target_families is not None else frozenset()
    )
    result: dict[str, tuple[str, ...]] = {}
    for backend_id, flags in fields.items():
        if known_backends and backend_id not in known_backends:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNKNOWN-BACKEND",
                    (
                        f"machine profile {profile_name!r} backend_flags declares "
                        f"unknown backend {backend_id!r}"
                    ),
                )
            )
        result[backend_id] = _string_list_field(
            profile_name,
            flags,
            f"backend_flags {backend_id!r}",
            path,
            diagnostics,
        )
    return result


def _supported_backends(
    profile_name: str,
    family: str,
    value: Any,
    target_families: TargetFamilyCatalog | None,
    path: Path,
    diagnostics: list[Diagnostic],
) -> frozenset[str] | None:
    family_capability = (
        target_families.profile_family(family)
        if target_families is not None
        else None
    )
    known = (
        frozenset(family_capability.backends)
        if family_capability is not None
        else frozenset()
    )
    if value is None:
        return known or None
    backends = _string_list_field(
        profile_name, value, "supported_backends", path, diagnostics
    )
    result = frozenset(backends)
    if len(result) != len(backends):
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-DUPLICATE-BACKEND",
                f"machine profile {profile_name!r} supported_backends contains duplicates",
            )
        )
    for backend_id in sorted(result - known):
        if family_capability is not None:
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNKNOWN-BACKEND",
                    (
                        f"machine profile {profile_name!r} supported_backends "
                        f"declares unknown backend {backend_id!r}"
                    ),
                )
            )
    return result


def _optional_token_field(
    profile_name: str,
    value: Any,
    field_name: str,
    path: Path,
    diagnostics: list[Diagnostic],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-FIELD",
                f"machine profile {profile_name!r} {field_name} must be a string",
            )
        )
        return None
    tokens = value.split()
    if len(tokens) != 1:
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-FIELD",
                f"machine profile {profile_name!r} {field_name} must be one token",
            )
        )
        return None
    return tokens[0]


def _runner(
    profile_name: str,
    family: str,
    value: Any,
    target_families: TargetFamilyCatalog | None,
    path: Path,
    diagnostics: list[Diagnostic],
) -> MachineProfileRunner | None:
    if value is None:
        return None
    if not isinstance(value, _JsonObject):
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-RUNNER",
                f"machine profile {profile_name!r} runner must be an object",
            )
        )
        return None
    fields = _object_fields(value, path, diagnostics)
    _unknown_fields(
        fields,
        {"kind", "profile", "args"},
        path,
        diagnostics,
        owner=f"runner for machine profile {profile_name!r}",
    )
    kind_value = fields.get("kind")
    if not isinstance(kind_value, str) or not kind_value.strip():
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-RUNNER",
                f"machine profile {profile_name!r} runner kind must be a non-empty string",
            )
        )
        return None
    kind = kind_value.strip()
    allowed = (
        target_families.runner_kinds_for_profile_family(family)
        if target_families is not None and target_families.supports_profile_family(family)
        else frozenset()
    )
    if allowed or (
        target_families is not None and target_families.supports_profile_family(family)
    ):
        if kind not in allowed:
            expected = ", ".join(sorted(allowed)) if allowed else "no runner"
            diagnostics.append(
                _diagnostic(
                    path,
                    "TSL-PROFILE-UNSUPPORTED-RUNNER",
                    (
                        f"machine profile {profile_name!r} runner kind {kind!r} is not "
                        f"declared for family {family!r}; expected {expected}"
                    ),
                )
            )
    profile_value = fields.get("profile")
    if not isinstance(profile_value, str) or not profile_value.strip():
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-RUNNER",
                f"machine profile {profile_name!r} runner profile must be a non-empty string",
            )
        )
        return None
    if profile_value.strip().startswith("-"):
        # The runner invocation adds the flag prefix itself; authored data keeps
        # the bare profile name. Diagnose rather than silently repairing.
        diagnostics.append(
            _diagnostic(
                path,
                "TSL-PROFILE-MALFORMED-RUNNER",
                (
                    f"machine profile {profile_name!r} runner profile must not start"
                    f" with '-'; write the bare profile name"
                    f" (got {profile_value.strip()!r})"
                ),
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
                "TSL-PROFILE-MALFORMED-RUNNER",
                f"machine profile {profile_name!r} runner args must be a string list",
            )
        )
        args = ()
    return MachineProfileRunner(kind=kind, profile=profile_value.strip(), args=args)


def _diagnostic(path: Path, code: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=message,
        span=SourceSpan(path, 1, 1, 1, 2),
    )
