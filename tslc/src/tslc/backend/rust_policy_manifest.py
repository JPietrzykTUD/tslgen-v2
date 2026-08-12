"""Validated backend-owned evidence for the narrow Rust policy pilot."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.resources import files
import json
from typing import Any, cast, get_args

from tslc.benchmark.model import BenchmarkScenarioFamily, SpecializationKey
from tslc.benchmark.planner import BenchmarkScenarioAdmission
from tslc.backend.capability import BackendPolicyInput
from tslc.lower.lowerer import LoweredSpecialization

RUST_POLICY_MANIFEST_VERSION = 1
_SCENARIO_FAMILIES = frozenset(get_args(BenchmarkScenarioFamily))


@dataclass(frozen=True, slots=True)
class RustPolicySelectionPilot:
    """One exact specialization and candidate inventory admitted for selection."""

    pilot_id: str
    profile_name: str
    primitive_name: str
    source_primitive_name: str
    extension_name: str
    type_tag: str
    result_kind: str
    param_kinds: tuple[str, ...]
    lanes: int
    vector_spelling: str
    caller_unsafe: bool
    candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.pilot_id:
            raise ValueError("Rust policy pilots require an ID")
        if self.lanes <= 0:
            raise ValueError("Rust policy pilots require a positive lane count")
        if not self.candidate_ids or self.candidate_ids[0] != "default":
            raise ValueError(
                "Rust policy pilot candidates must start with 'default'"
            )
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("Rust policy pilot candidate IDs must be unique")

    @property
    def match_identity(self) -> tuple[object, ...]:
        return (
            self.profile_name,
            self.primitive_name,
            self.source_primitive_name,
            self.extension_name,
            self.type_tag,
            self.result_kind,
            self.param_kinds,
            self.lanes,
            self.vector_spelling,
            self.caller_unsafe,
            self.candidate_ids,
        )

    def matches(
        self,
        key: SpecializationKey,
        spec: LoweredSpecialization,
        candidate_ids: tuple[str, ...],
    ) -> bool:
        return (
            key.profile_name,
            key.primitive_name,
            key.source_primitive_name,
            key.extension_name,
            key.type_tag,
            key.result_kind,
            key.param_kinds,
            key.lanes,
            spec.vector_spelling,
            spec.safety.caller_unsafe,
            candidate_ids,
        ) == self.match_identity


@dataclass(frozen=True, slots=True)
class RustPolicyManifest(BackendPolicyInput):
    """Complete static evidence consumed by Rust benchmark and selection plans."""

    version: int
    benchmark_admissions: tuple[BenchmarkScenarioAdmission, ...]
    selection_pilots: tuple[RustPolicySelectionPilot, ...]

    def __post_init__(self) -> None:
        if self.version != RUST_POLICY_MANIFEST_VERSION:
            raise ValueError(
                f"unsupported Rust policy manifest version {self.version!r}; "
                f"expected {RUST_POLICY_MANIFEST_VERSION}"
            )
        if len(set(self.benchmark_admissions)) != len(self.benchmark_admissions):
            raise ValueError("duplicate Rust policy benchmark admissions")
        pilot_ids = tuple(pilot.pilot_id for pilot in self.selection_pilots)
        if len(set(pilot_ids)) != len(pilot_ids):
            raise ValueError("duplicate Rust policy pilot IDs")
        identities = tuple(
            pilot.match_identity for pilot in self.selection_pilots
        )
        if len(set(identities)) != len(identities):
            raise ValueError(
                "ambiguous Rust policy pilots match the same specialization"
            )

    @property
    def benchmark_admission_set(
        self,
    ) -> frozenset[BenchmarkScenarioAdmission]:
        return frozenset(self.benchmark_admissions)

    def matching_pilots(
        self,
        key: SpecializationKey,
        spec: LoweredSpecialization,
        candidate_ids: tuple[str, ...],
    ) -> tuple[RustPolicySelectionPilot, ...]:
        return tuple(
            pilot
            for pilot in self.selection_pilots
            if pilot.matches(key, spec, candidate_ids)
        )


def parse_rust_policy_manifest(text: str) -> RustPolicyManifest:
    """Parse JSON strictly; unknown or mistyped evidence fails closed."""

    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid Rust policy manifest JSON: {error}") from error
    root = _object(raw, "Rust policy manifest")
    _exact_fields(
        root,
        {"version", "benchmark_admissions", "selection_pilots"},
        "Rust policy manifest",
    )
    version = _integer(root.get("version"), "manifest version")
    admissions = tuple(
        _parse_admission(value, index)
        for index, value in enumerate(
            _list(root.get("benchmark_admissions"), "benchmark_admissions")
        )
    )
    pilots = tuple(
        _parse_pilot(value, index)
        for index, value in enumerate(
            _list(root.get("selection_pilots"), "selection_pilots")
        )
    )
    return RustPolicyManifest(version, admissions, pilots)


def load_rust_policy_manifest(
    read_text: Callable[[], str] | None = None,
) -> RustPolicyManifest:
    """Load package data at an explicit input boundary."""

    if read_text is None:
        resource = files("tslc.backend").joinpath(
            "policy_assets",
            "rust_policy.json",
        )
        read_text = lambda: resource.read_text(encoding="utf-8")
    return parse_rust_policy_manifest(read_text())


def _parse_admission(value: Any, index: int) -> BenchmarkScenarioAdmission:
    owner = f"benchmark_admissions[{index}]"
    raw = _object(value, owner)
    _exact_fields(raw, {"profile_name", "scenario_family"}, owner)
    profile = _string(raw.get("profile_name"), f"{owner}.profile_name")
    family = _string(raw.get("scenario_family"), f"{owner}.scenario_family")
    if family not in _SCENARIO_FAMILIES:
        raise ValueError(
            f"{owner}.scenario_family has unknown value {family!r}; "
            f"expected one of: {', '.join(sorted(_SCENARIO_FAMILIES))}"
        )
    return BenchmarkScenarioAdmission(
        profile,
        cast(BenchmarkScenarioFamily, family),
    )


def _parse_pilot(value: Any, index: int) -> RustPolicySelectionPilot:
    owner = f"selection_pilots[{index}]"
    raw = _object(value, owner)
    fields = {
        "candidate_ids",
        "caller_unsafe",
        "extension_name",
        "lanes",
        "param_kinds",
        "pilot_id",
        "primitive_name",
        "profile_name",
        "result_kind",
        "source_primitive_name",
        "type_tag",
        "vector_spelling",
    }
    _exact_fields(raw, fields, owner)
    return RustPolicySelectionPilot(
        pilot_id=_string(raw.get("pilot_id"), f"{owner}.pilot_id"),
        profile_name=_string(raw.get("profile_name"), f"{owner}.profile_name"),
        primitive_name=_string(
            raw.get("primitive_name"), f"{owner}.primitive_name"
        ),
        source_primitive_name=_string(
            raw.get("source_primitive_name"),
            f"{owner}.source_primitive_name",
        ),
        extension_name=_string(
            raw.get("extension_name"), f"{owner}.extension_name"
        ),
        type_tag=_string(raw.get("type_tag"), f"{owner}.type_tag"),
        result_kind=_string(raw.get("result_kind"), f"{owner}.result_kind"),
        param_kinds=_string_tuple(
            raw.get("param_kinds"), f"{owner}.param_kinds"
        ),
        lanes=_integer(raw.get("lanes"), f"{owner}.lanes"),
        vector_spelling=_string(
            raw.get("vector_spelling"), f"{owner}.vector_spelling"
        ),
        caller_unsafe=_boolean(
            raw.get("caller_unsafe"), f"{owner}.caller_unsafe"
        ),
        candidate_ids=_string_tuple(
            raw.get("candidate_ids"), f"{owner}.candidate_ids"
        ),
    )


def _object(value: Any, owner: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in value
    ):
        raise ValueError(f"{owner} must be an object with string keys")
    return value


def _list(value: Any, owner: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{owner} must be a list")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    owner: str,
) -> None:
    actual = set(value)
    unknown = actual - expected
    missing = expected - actual
    if unknown:
        raise ValueError(
            f"{owner} has unknown fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise ValueError(
            f"{owner} is missing fields: {', '.join(sorted(missing))}"
        )


def _string(value: Any, owner: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{owner} must be a non-empty string")
    return value


def _string_tuple(value: Any, owner: str) -> tuple[str, ...]:
    values = _list(value, owner)
    return tuple(
        _string(item, f"{owner}[{index}]")
        for index, item in enumerate(values)
    )


def _integer(value: Any, owner: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{owner} must be an integer")
    return value


def _boolean(value: Any, owner: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{owner} must be a boolean")
    return value


__all__ = (
    "RUST_POLICY_MANIFEST_VERSION",
    "RustPolicyManifest",
    "RustPolicySelectionPilot",
    "load_rust_policy_manifest",
    "parse_rust_policy_manifest",
)
