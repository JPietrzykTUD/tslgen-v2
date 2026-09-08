#!/usr/bin/env python3
"""Exact release-target support ratchet over compiler-owned generation facts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import cast

from tslc.api import generate_project
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import has_errors
from tslc.maintenance import _repo_context
from tslc.maintenance._repo_context import RepoContext
from tslc.maintenance.release_contract import build_release_contract
from tslc.target_support import (
    TargetSupportEntry,
    TargetSupportKey,
    TargetSupportRealizationKey,
    TargetSupportStatus,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_BASELINE_VERSION = 1
_TARGET_SPECIFIC = "TSL-V1-TARGET-SPECIFIC-CALLABLE"
_FIXED_SHAPE = "TSL-V1-RUNTIME-SCALABLE-FIXED-SHAPE"
_NO_VECTOR_AXIS = "TSL-V1-NO-TARGET-VECTOR-AXIS"


@dataclass(frozen=True, slots=True)
class SlotOutcome:
    realization: TargetSupportRealizationKey | None
    status: TargetSupportStatus
    reason_id: str | None = None
    implementation_state: str | None = None

    def sort_key(self) -> tuple[object, ...]:
        return (
            () if self.realization is None else self.realization.sort_key(),
            self.status.value,
            self.reason_id or "",
            self.implementation_state or "",
        )


@dataclass(frozen=True, slots=True)
class SlotRecord:
    outcomes: tuple[SlotOutcome, ...]

    @property
    def emitted(self) -> int:
        return sum(item.status is TargetSupportStatus.EMITTED for item in self.outcomes)


@dataclass(frozen=True, slots=True)
class Exclusion:
    profile: str
    backend: str
    declaration_identity: str
    reason_id: str

    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.profile,
            self.backend,
            self.declaration_identity,
            self.reason_id,
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    profile_targets: tuple[tuple[str, str, str], ...]
    types: tuple[str, ...]
    exclusions: tuple[Exclusion, ...]
    slots: dict[TargetSupportKey, SlotRecord]


@dataclass(frozen=True, slots=True)
class SlotChange:
    key: TargetSupportKey | None
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class DiffReport:
    changes: tuple[SlotChange, ...]

    @property
    def regressions(self) -> tuple[SlotChange, ...]:
        return tuple(item for item in self.changes if item.kind == "regressed")

    def of_kind(self, kind: str) -> tuple[SlotChange, ...]:
        return tuple(item for item in self.changes if item.kind == kind)


def canonical_baseline_path(context: RepoContext) -> Path:
    return context.coverage_root / "tsl-v1-target-support.json"


def compute_snapshot(
    context: RepoContext,
    *,
    sources: Path | None = None,
    machine_profiles: Path | None = None,
) -> tuple[Snapshot | None, tuple[str, ...]]:
    """Generate the reviewed release-target scope and project its exact trace."""

    try:
        contract = build_release_contract(context)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        return None, (str(error),)
    profile_targets = tuple(
        (profile, scope.backend_id, extension)
        for scope in contract.policy.target_scopes
        for profile, extension in scope.profile_extensions
    )
    profiles = tuple(profile for profile, _backend, _extension in profile_targets)
    backends = tuple(sorted({backend for _profile, backend, _extension in profile_targets}))
    result = generate_project(
        [sources or context.data_root],
        machine_profiles_path=machine_profiles or context.machine_profiles_path,
        profiles=profiles,
        type_tags=DEFAULT_SCALAR_TYPE_TAGS,
        backends=backends,
        render_artifacts=False,
        collect_target_support=True,
    )
    if has_errors(result.diagnostics):
        return None, tuple(
            f"[{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}"
            for diagnostic in result.diagnostics
            if diagnostic.severity == "error"
        )
    if result.target_support is None:
        return None, ("generation did not retain target-support facts",)

    declared = {family.identity: family for family in contract.callable_families}
    target_by_profile = {
        (profile, backend): extension
        for profile, backend, extension in profile_targets
    }
    runtime_scalable = {
        (profile, scope.backend_id)
        for scope in contract.policy.target_scopes
        for profile in scope.runtime_scalable_profiles
    }
    target_specific = frozenset(
        item.name for item in contract.policy.target_specific_callables
    )
    exclusions: set[Exclusion] = set()
    grouped: dict[TargetSupportKey, list[SlotOutcome]] = defaultdict(list)
    accounted: set[tuple[str, str, str]] = set()
    for entry in result.target_support.entries:
        scope = (entry.key.profile, entry.key.backend)
        target_extension = target_by_profile.get(scope)
        if target_extension is None or entry.key.target_extension != target_extension:
            continue
        family = declared.get(entry.key.declaration_identity)
        if family is None:
            continue
        reason_id: str | None = None
        if family.name in target_specific:
            reason_id = _TARGET_SPECIFIC
        elif family.fixed_shape_only and scope in runtime_scalable:
            reason_id = _FIXED_SHAPE
        if reason_id is not None:
            exclusions.add(
                Exclusion(
                    entry.key.profile,
                    entry.key.backend,
                    family.identity,
                    reason_id,
                )
            )
            accounted.add((*scope, family.identity))
            continue
        grouped[entry.key].append(_outcome(entry))
        accounted.add((*scope, family.identity))

    unaccounted: list[str] = []
    for profile, backend, _extension in profile_targets:
        for family in contract.callable_families:
            identity = (profile, backend, family.identity)
            if identity in accounted:
                continue
            if family.name in target_specific:
                exclusions.add(
                    Exclusion(profile, backend, family.identity, _TARGET_SPECIFIC)
                )
                continue
            if family.fixed_shape_only and (profile, backend) in runtime_scalable:
                exclusions.add(
                    Exclusion(profile, backend, family.identity, _FIXED_SHAPE)
                )
                continue
            shape = parse_signature(family.signature)
            if shape is not None and DEFAULT_SUPPORT_POLICY.shape_is_free_function(shape):
                exclusions.add(Exclusion(profile, backend, family.identity, _NO_VECTOR_AXIS))
                continue
            unaccounted.append(
                f"{profile}/{backend} {family.identity}"
            )
    if unaccounted:
        return None, (
            "selector target-support trace omitted stable declarations: "
            + ", ".join(unaccounted),
        )

    slots = {
        key: SlotRecord(tuple(sorted(outcomes, key=SlotOutcome.sort_key)))
        for key, outcomes in grouped.items()
    }
    return (
        Snapshot(
            profile_targets=profile_targets,
            types=DEFAULT_SCALAR_TYPE_TAGS,
            exclusions=tuple(sorted(exclusions, key=Exclusion.sort_key)),
            slots=slots,
        ),
        (),
    )


def _outcome(entry: TargetSupportEntry) -> SlotOutcome:
    return SlotOutcome(
        realization=entry.realization,
        status=entry.status,
        reason_id=entry.reason_id,
        implementation_state=(
            None
            if entry.implementation_state is None
            else entry.implementation_state.value
        ),
    )


def diff_snapshots(baseline: Snapshot, current: Snapshot) -> DiffReport:
    changes: list[SlotChange] = []
    if baseline.profile_targets != current.profile_targets or baseline.types != current.types:
        changes.append(
            SlotChange(None, "regressed", "canonical profile/target/type scope changed")
        )
    if baseline.exclusions != current.exclusions:
        changes.append(
            SlotChange(None, "regressed", "reviewed exclusion set changed")
        )
    keys = sorted(baseline.slots.keys() | current.slots.keys(), key=TargetSupportKey.sort_key)
    for key in keys:
        was = baseline.slots.get(key)
        now = current.slots.get(key)
        if was == now:
            continue
        if was is None:
            assert now is not None
            kind = "added" if _complete(now) else "regressed"
            detail = "new complete slot" if kind == "added" else "new support gap"
            changes.append(SlotChange(key, kind, detail))
            continue
        if now is None:
            if _resolved_absence(key, was, current):
                changes.append(
                    SlotChange(
                        key,
                        "improved",
                        "unresolved conversion target gained complete concrete slots",
                    )
                )
                continue
            changes.append(SlotChange(key, "regressed", "expected slot disappeared"))
            continue
        regression = _record_regression(was, now)
        if regression is not None:
            changes.append(SlotChange(key, "regressed", regression))
        elif now.emitted > was.emitted or (_complete(now) and not _complete(was)):
            changes.append(SlotChange(key, "improved", _record_change(was, now)))
        else:
            changes.append(SlotChange(key, "changed", _record_change(was, now)))
    return DiffReport(tuple(changes))


def _complete(record: SlotRecord) -> bool:
    return bool(record.outcomes) and all(
        item.status is TargetSupportStatus.EMITTED for item in record.outcomes
    )


def _resolved_absence(
    key: TargetSupportKey,
    record: SlotRecord,
    current: Snapshot,
) -> bool:
    if key.conversion_target is not None or any(
        item.status is not TargetSupportStatus.ABSENT for item in record.outcomes
    ):
        return False
    matches = tuple(
        candidate_record
        for candidate, candidate_record in current.slots.items()
        if candidate.conversion_target is not None
        and _key_without_conversion_target(candidate)
        == _key_without_conversion_target(key)
    )
    return bool(matches) and all(_complete(item) for item in matches)


def _key_without_conversion_target(key: TargetSupportKey) -> tuple[object, ...]:
    return (
        key.profile,
        key.backend,
        key.primitive,
        key.signature,
        key.attributes,
        key.result_target,
        key.overload,
        key.type_tag,
        key.target_extension,
    )


def _record_regression(was: SlotRecord, now: SlotRecord) -> str | None:
    old_emitted = {
        item.realization: item
        for item in was.outcomes
        if item.status is TargetSupportStatus.EMITTED
    }
    new_by_realization = {item.realization: item for item in now.outcomes}
    lost = tuple(item for key, item in old_emitted.items() if key not in new_by_realization)
    if lost:
        return f"lost {len(lost)} emitted realization(s)"
    for realization, old in old_emitted.items():
        new = new_by_realization[realization]
        if new.status is not TargetSupportStatus.EMITTED:
            return f"emitted -> {new.status.value} ({new.reason_id or 'no reason'})"
        if _state_rank(new.implementation_state) > _state_rank(old.implementation_state):
            return (
                "implementation state degraded "
                f"{old.implementation_state} -> {new.implementation_state}"
            )
    if not _complete(now) and _complete(was):
        return "complete slot gained a non-emitted realization"
    return None


def _state_rank(value: str | None) -> int:
    if value is None:
        return 4
    return {"native": 0, "composed": 1, "unknown": 2, "fallback": 3}.get(value, 4)


def _record_change(was: SlotRecord, now: SlotRecord) -> str:
    return f"{_record_summary(was)} -> {_record_summary(now)}"


def _record_summary(record: SlotRecord) -> str:
    counts = Counter(item.status.value for item in record.outcomes)
    return ",".join(f"{key}={counts[key]}" for key in sorted(counts))


def serialize(snapshot: Snapshot) -> str:
    lines = [
        "{",
        f'  "version": {_BASELINE_VERSION},',
        '  "profile_targets": '
        + json.dumps(snapshot.profile_targets, separators=(",", ":"))
        + ",",
        '  "types": ' + json.dumps(snapshot.types, separators=(",", ":")) + ",",
        '  "exclusions": [',
    ]
    for index, exclusion in enumerate(snapshot.exclusions):
        suffix = "," if index + 1 < len(snapshot.exclusions) else ""
        lines.append(
            "    "
            + json.dumps(
                [*exclusion.sort_key()],
                separators=(",", ":"),
            )
            + suffix
        )
    lines.extend(("  ],", '  "slots": ['))
    ordered = sorted(snapshot.slots.items(), key=lambda item: item[0].sort_key())
    for index, (key, record) in enumerate(ordered):
        suffix = "," if index + 1 < len(ordered) else ""
        lines.append(
            "    "
            + json.dumps(
                {
                    "key": _key_payload(key),
                    "outcomes": [
                        _outcome_payload(item) for item in record.outcomes
                    ],
                },
                separators=(",", ":"),
            )
            + suffix
        )
    lines.extend(("  ]", "}"))
    return "\n".join(lines) + "\n"


def deserialize(text: str) -> Snapshot:
    payload = json.loads(text)
    if payload.get("version") != _BASELINE_VERSION:
        raise ValueError(f"unsupported target-support baseline version {payload.get('version')!r}")
    return Snapshot(
        profile_targets=tuple(tuple(item) for item in payload["profile_targets"]),
        types=tuple(payload["types"]),
        exclusions=tuple(Exclusion(*item) for item in payload["exclusions"]),
        slots={
            (key := _key_from_payload(item["key"])): SlotRecord(
                tuple(_outcome_from_payload(outcome) for outcome in item["outcomes"])
            )
            for item in payload["slots"]
        },
    )


def _key_payload(key: TargetSupportKey) -> list[object]:
    return [
        key.profile,
        key.backend,
        key.primitive,
        key.signature,
        key.attributes,
        key.result_target,
        key.overload,
        key.type_tag,
        key.target_extension,
        key.conversion_target,
    ]


def _key_from_payload(value: list[object]) -> TargetSupportKey:
    attributes = cast(list[list[str]], value[4])
    result_target = cast(list[str] | None, value[5])
    overload = cast(list[object] | None, value[6])
    return TargetSupportKey(
        profile=str(value[0]),
        backend=str(value[1]),
        primitive=str(value[2]),
        signature=str(value[3]),
        attributes=tuple((item[0], item[1]) for item in attributes),
        result_target=(
            None
            if result_target is None
            else (result_target[0], result_target[1])
        ),
        overload=(
            None
            if overload is None
            else (str(overload[0]), str(overload[1]), bool(overload[2]))
        ),
        type_tag=str(value[7]),
        target_extension=str(value[8]),
        conversion_target=None if value[9] is None else str(value[9]),
    )


def _outcome_payload(item: SlotOutcome) -> list[object]:
    realization = item.realization
    realization_payload: list[object] | None = None
    if realization is not None:
        realization_payload = [
            realization.source_extension,
            realization.selector_path,
            realization.required_features,
            realization.required_compiler_capabilities,
            realization.concrete_lanes,
            realization.simd_type_base_bindings,
            realization.variant_names,
        ]
    return [
        realization_payload,
        item.status.value,
        item.reason_id,
        item.implementation_state,
    ]


def _outcome_from_payload(value: list[object]) -> SlotOutcome:
    raw = value[0]
    realization = None
    if raw is not None:
        values = cast(list[object], raw)
        lanes = values[4]
        if lanes is not None and not isinstance(lanes, int):
            raise ValueError("target-support concrete lanes must be an integer")
        bindings = cast(list[list[str]], values[5])
        realization = TargetSupportRealizationKey(
            source_extension=str(values[0]),
            selector_path=tuple(cast(list[str], values[1])),
            required_features=tuple(cast(list[str], values[2])),
            required_compiler_capabilities=tuple(cast(list[str], values[3])),
            concrete_lanes=lanes,
            simd_type_base_bindings=tuple(
                (item[0], item[1]) for item in bindings
            ),
            variant_names=tuple(cast(list[str], values[6])),
        )
    return SlotOutcome(
        realization=realization,
        status=TargetSupportStatus(str(value[1])),
        reason_id=None if value[2] is None else str(value[2]),
        implementation_state=None if value[3] is None else str(value[3]),
    )


def format_report(diff: DiffReport, snapshot: Snapshot) -> str:
    statuses = Counter(
        outcome.status.value
        for record in snapshot.slots.values()
        for outcome in record.outcomes
    )
    states = Counter(
        outcome.implementation_state
        for record in snapshot.slots.values()
        for outcome in record.outcomes
        if outcome.implementation_state is not None
    )
    lines = [
        f"target support: {len(snapshot.slots)} exact slots; "
        + ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses)),
        "implementation states: "
        + (", ".join(f"{key}={states[key]}" for key in sorted(states)) or "none"),
        f"reviewed exclusions: {len(snapshot.exclusions)}",
    ]
    counts = Counter(item.kind for item in diff.changes)
    lines.append(
        "changes: "
        + (", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none")
    )
    for change in diff.changes[:100]:
        label = "scope" if change.key is None else _label(change.key)
        lines.append(f"  {change.kind}: {label}: {change.detail}")
    if len(diff.changes) > 100:
        lines.append(f"  ... and {len(diff.changes) - 100} more")
    return "\n".join(lines)


def _label(key: TargetSupportKey) -> str:
    conversion = "" if key.conversion_target is None else f" -> {key.conversion_target}"
    return (
        f"{key.profile}/{key.backend} {key.declaration_identity}"
        f"<{key.target_extension},{key.type_tag}>{conversion}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc coverage target-ratchet",
        description="Check exact SVE and RVV release-target support.",
    )
    parser.add_argument("--sources")
    parser.add_argument("--machine-profiles")
    parser.add_argument("--baseline")
    parser.add_argument("--update", action="store_true")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="also fail when any stable slot is not emitted",
    )
    args = parser.parse_args(argv)
    context = _repo_context.require_repo_context(parser)
    snapshot, errors = compute_snapshot(
        context,
        sources=None if args.sources is None else Path(args.sources),
        machine_profiles=(
            None if args.machine_profiles is None else Path(args.machine_profiles)
        ),
    )
    if snapshot is None:
        print("target-support ratchet generation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 2
    path = Path(args.baseline) if args.baseline else canonical_baseline_path(context)
    if args.update:
        previous = deserialize(path.read_text(encoding="utf-8")) if path.is_file() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize(snapshot), encoding="utf-8")
        if previous is not None:
            print(format_report(diff_snapshots(previous, snapshot), snapshot))
        print(f"wrote {path}")
        return 0
    if not path.is_file():
        print(f"target-support baseline is missing: {path}", file=sys.stderr)
        return 2
    baseline = deserialize(path.read_text(encoding="utf-8"))
    diff = diff_snapshots(baseline, snapshot)
    print(format_report(diff, snapshot))
    if diff.regressions:
        print(f"FAIL: {len(diff.regressions)} target-support regression(s)")
        return 1
    incomplete = tuple(
        key for key, record in snapshot.slots.items() if not _complete(record)
    )
    if args.require_complete and incomplete:
        print(f"FAIL: {len(incomplete)} target-support slot(s) are incomplete")
        return 1
    print("OK: no target-support regressions")
    return 0


__all__ = (
    "DiffReport",
    "Exclusion",
    "SlotOutcome",
    "SlotRecord",
    "Snapshot",
    "canonical_baseline_path",
    "compute_snapshot",
    "deserialize",
    "diff_snapshots",
    "format_report",
    "main",
    "serialize",
)


if __name__ == "__main__":
    raise SystemExit(main())
