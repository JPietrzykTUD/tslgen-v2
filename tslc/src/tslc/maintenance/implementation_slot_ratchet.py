#!/usr/bin/env python3
"""Exact four-way implementation-slot ratchet for the complete TSL v1 corpus."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import cast

from tslc.api import generate_project
from tslc.authoring import check_catalog
from tslc.catalog.model import PrimitivePortability
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.diagnostics import has_errors
from tslc.maintenance import _repo_context
from tslc.maintenance._repo_context import RepoContext
from tslc.maintenance.release_contract import build_release_contract
from tslc.target_support import (
    ImplementationSlotClass,
    TargetSupportEntry,
    TargetSupportKey,
    TargetSupportRealizationKey,
    TargetSupportStatus,
    implementation_slot_class,
    implementation_slot_reason,
)


_BASELINE_VERSION = 2


@dataclass(frozen=True, slots=True)
class SlotIdentity:
    """Exact expected-slot and selected-realization identity."""

    key: TargetSupportKey
    realization: TargetSupportRealizationKey | None

    def sort_key(self) -> tuple[object, ...]:
        return (
            *self.key.sort_key(),
            () if self.realization is None else self.realization.sort_key(),
        )


@dataclass(frozen=True, slots=True)
class SlotRecord:
    """Final pipeline evidence and its fail-closed four-way classification."""

    classification: ImplementationSlotClass
    status: TargetSupportStatus
    reason_id: str | None
    implementation_state: str | None


@dataclass(frozen=True, slots=True)
class Snapshot:
    backend_profiles: tuple[tuple[str, tuple[str, ...]], ...]
    types: tuple[str, ...]
    slots: dict[SlotIdentity, SlotRecord]
    parity_extensions: tuple[str, ...] = ()
    target_specific_primitives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SlotChange:
    identity: SlotIdentity | None
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


@dataclass(frozen=True, slots=True)
class _SerializedPattern:
    """Profile-independent record used only to keep the baseline compact."""

    backend: str
    primitive: str
    signature: str
    attributes: tuple[tuple[str, str], ...]
    result_target: tuple[str, str] | None
    overload: tuple[str, str, bool] | None
    type_tag: str
    target_extension: str
    conversion_target: str | None
    realization: TargetSupportRealizationKey | None
    record: SlotRecord

    @classmethod
    def from_slot(
        cls, identity: SlotIdentity, record: SlotRecord
    ) -> _SerializedPattern:
        key = identity.key
        return cls(
            backend=key.backend,
            primitive=key.primitive,
            signature=key.signature,
            attributes=key.attributes,
            result_target=key.result_target,
            overload=key.overload,
            type_tag=key.type_tag,
            target_extension=key.target_extension,
            conversion_target=key.conversion_target,
            realization=identity.realization,
            record=record,
        )

    def identity(self, profile: str) -> SlotIdentity:
        return SlotIdentity(
            TargetSupportKey(
                profile=profile,
                backend=self.backend,
                primitive=self.primitive,
                signature=self.signature,
                attributes=self.attributes,
                result_target=self.result_target,
                overload=self.overload,
                type_tag=self.type_tag,
                target_extension=self.target_extension,
                conversion_target=self.conversion_target,
            ),
            self.realization,
        )

    def sort_key(self) -> tuple[object, ...]:
        return (
            *self.identity("").sort_key(),
            self.record.classification.value,
            self.record.status.value,
            self.record.reason_id or "",
            self.record.implementation_state or "",
        )


def canonical_baseline_path(context: RepoContext) -> Path:
    return context.coverage_root / "tsl-v1-implementation-slots.json"


def classify_entries(
    entries: tuple[TargetSupportEntry, ...],
    *,
    backend_profiles: tuple[tuple[str, tuple[str, ...]], ...],
    types: tuple[str, ...],
    parity_extensions: tuple[str, ...] = (),
    target_specific_primitives: tuple[str, ...] = (),
) -> Snapshot:
    """Project compiler-owned exact outcomes without selecting or inspecting text."""

    slots: dict[SlotIdentity, SlotRecord] = {}
    for entry in entries:
        identity = SlotIdentity(entry.key, entry.realization)
        record = SlotRecord(
            classification=implementation_slot_class(entry),
            status=entry.status,
            reason_id=implementation_slot_reason(entry),
            implementation_state=(
                None
                if entry.implementation_state is None
                else entry.implementation_state.value
            ),
        )
        previous = slots.setdefault(identity, record)
        if previous != record:
            raise ValueError(f"conflicting target-support outcome for {_label(identity)}")
    return Snapshot(
        backend_profiles,
        types,
        slots,
        parity_extensions,
        target_specific_primitives,
    )


def compute_snapshot(
    context: RepoContext,
    *,
    sources: Path | None = None,
    machine_profiles: Path | None = None,
) -> tuple[Snapshot | None, tuple[str, ...]]:
    """Classify every exact slot in the generated-library v1 backend/profile scope."""

    try:
        contract = build_release_contract(context)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        return None, (str(error),)
    backend_profiles = tuple(
        (
            backend.backend_id,
            tuple(profile.name for profile in backend.profiles),
        )
        for backend in contract.backends
    )
    profiles = tuple(
        dict.fromkeys(
            profile
            for _backend, profile_names in backend_profiles
            for profile in profile_names
        )
    )
    backends = tuple(backend for backend, _profiles in backend_profiles)
    source_root = sources or context.data_root
    checked = check_catalog((source_root,), backends=backends)
    if checked.catalog is None or has_errors(checked.diagnostics):
        return None, tuple(
            f"[{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}"
            for diagnostic in checked.diagnostics
            if diagnostic.severity == "error"
        )
    parity_extensions = tuple(
        sorted(
            extension.name
            for extension in checked.catalog.extensions.values()
            if all(extension.supports_backend(backend) for backend in backends)
        )
    )
    target_specific_primitives = tuple(
        sorted(
            {
                primitive.name
                for primitive in checked.catalog.primitives
                if primitive.portability is PrimitivePortability.TARGET_SPECIFIC
            }
        )
    )
    result = generate_project(
        [source_root],
        machine_profiles_path=machine_profiles or context.machine_profiles_path,
        profiles=profiles,
        backend_profiles=dict(backend_profiles),
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
    try:
        return (
            classify_entries(
                result.target_support.entries,
                backend_profiles=backend_profiles,
                types=DEFAULT_SCALAR_TYPE_TAGS,
                parity_extensions=parity_extensions,
                target_specific_primitives=target_specific_primitives,
            ),
            (),
        )
    except ValueError as error:
        return None, (str(error),)


def diff_snapshots(baseline: Snapshot, current: Snapshot) -> DiffReport:
    """Compare exact identities and reject only degradation of existing support."""

    changes: list[SlotChange] = []
    if (
        baseline.backend_profiles != current.backend_profiles
        or baseline.types != current.types
        or baseline.parity_extensions != current.parity_extensions
    ):
        changes.append(
            SlotChange(None, "regressed", "canonical backend/profile/type scope changed")
        )
    baseline_primitives = {identity.key.primitive for identity in baseline.slots}
    newly_target_specific = sorted(
        (
            set(current.target_specific_primitives)
            - set(baseline.target_specific_primitives)
        )
        & baseline_primitives
    )
    if newly_target_specific:
        changes.append(
            SlotChange(
                None,
                "regressed",
                "portable primitive contract became target-specific: "
                + ", ".join(newly_target_specific),
            )
        )
    newly_portable = sorted(
        set(baseline.target_specific_primitives)
        - set(current.target_specific_primitives)
    )
    if newly_portable:
        changes.append(
            SlotChange(
                None,
                "improved",
                "target-specific primitive contract became portable: "
                + ", ".join(newly_portable),
            )
        )

    old_by_key = _by_expected_key(baseline)
    new_by_key = _by_expected_key(current)
    keys = sorted(old_by_key.keys() | new_by_key.keys(), key=TargetSupportKey.sort_key)
    for key in keys:
        old = old_by_key.get(key)
        new = new_by_key.get(key)
        if old is None:
            assert new is not None
            representative = SlotIdentity(key, next(iter(new)))
            detail = (
                "new unsupported slot"
                if all(
                    record.classification is ImplementationSlotClass.UNSUPPORTED
                    for record in new.values()
                )
                else "new classified slot"
            )
            changes.append(SlotChange(representative, "added", detail))
            continue
        if new is None:
            representative = SlotIdentity(key, next(iter(old)))
            changes.append(
                SlotChange(representative, "regressed", "expected slot disappeared")
            )
            continue
        _diff_realizations(key, old, new, changes)
    return DiffReport(tuple(changes))


def implementation_quality_gaps(snapshot: Snapshot) -> tuple[SlotChange, ...]:
    """Return emitted implementations that lack a supported classification."""

    return tuple(
        SlotChange(
            identity,
            "quality-gap",
            "emitted realization has no classified implementation state",
        )
        for identity, record in sorted(
            snapshot.slots.items(), key=lambda item: item[0].sort_key()
        )
        if record.status is TargetSupportStatus.EMITTED
        and record.classification is ImplementationSlotClass.UNSUPPORTED
    )


def implementation_coverage_gaps(snapshot: Snapshot) -> tuple[SlotChange, ...]:
    """Return shared-extension logical slots with no supported realization."""

    gaps: list[SlotChange] = []
    grouped: dict[tuple[object, ...], list[tuple[SlotIdentity, SlotRecord]]] = (
        defaultdict(list)
    )
    for identity, record in snapshot.slots.items():
        if identity.key.target_extension not in snapshot.parity_extensions:
            continue
        grouped[_logical_slot_key(identity.key)].append((identity, record))
    for _key, outcomes in sorted(grouped.items(), key=lambda item: item[0]):
        records = tuple(record for _identity, record in outcomes)
        if all(
            record.status is TargetSupportStatus.NOT_APPLICABLE
            for record in records
        ):
            continue
        if any(_supported(record) for record in records):
            continue
        representative = min(
            (identity for identity, _record in outcomes),
            key=SlotIdentity.sort_key,
        )
        reasons = ", ".join(
            sorted({record.reason_id or record.status.value for record in records})
        )
        gaps.append(
            SlotChange(
                representative,
                "coverage-gap",
                f"applicable slot has no supported realization ({reasons})",
            )
        )
    return tuple(gaps)


def _logical_slot_key(key: TargetSupportKey) -> tuple[object, ...]:
    """Profile/backend-independent primitive × extension × datatype identity."""

    return (
        key.primitive,
        key.signature,
        key.attributes,
        key.result_target or (),
        key.overload or (),
        key.type_tag,
        key.target_extension,
        key.conversion_target or "",
    )


def _by_expected_key(
    snapshot: Snapshot,
) -> dict[TargetSupportKey, dict[TargetSupportRealizationKey | None, SlotRecord]]:
    grouped: dict[
        TargetSupportKey,
        dict[TargetSupportRealizationKey | None, SlotRecord],
    ] = defaultdict(dict)
    for identity, record in snapshot.slots.items():
        grouped[identity.key][identity.realization] = record
    return dict(grouped)


def _diff_realizations(
    key: TargetSupportKey,
    old: dict[TargetSupportRealizationKey | None, SlotRecord],
    new: dict[TargetSupportRealizationKey | None, SlotRecord],
    changes: list[SlotChange],
) -> None:
    old_supported = any(_supported(record) for record in old.values())
    new_supported = any(_supported(record) for record in new.values())

    common = sorted(
        old.keys() & new.keys(),
        key=_realization_sort_key,
    )
    for realization in common:
        was = old[realization]
        now = new[realization]
        if was == now:
            continue
        rank_change = _class_rank(now.classification) - _class_rank(
            was.classification
        )
        kind = "regressed" if rank_change > 0 else "improved" if rank_change < 0 else "changed"
        changes.append(
            SlotChange(
                SlotIdentity(key, realization),
                kind,
                _record_change(was, now),
            )
        )

    for realization in sorted(old.keys() - new.keys(), key=_realization_sort_key):
        was = old[realization]
        if not _supported(was):
            if not new_supported:
                changes.append(
                    SlotChange(
                        SlotIdentity(key, realization),
                        "changed",
                        "unsupported realization identity changed",
                    )
                )
            continue
        changes.append(
            SlotChange(
                SlotIdentity(key, realization),
                "regressed",
                f"lost {was.classification.value} realization",
            )
        )

    for realization in sorted(new.keys() - old.keys(), key=_realization_sort_key):
        now = new[realization]
        kind = "added"
        if old_supported and not _supported(now):
            kind = "regressed"
        elif not old_supported and _supported(now):
            kind = "improved"
        detail = (
            "supported slot gained an unsupported realization"
            if kind == "regressed"
            else (
                "unsupported slot gained a supported realization"
                if kind == "improved"
                else f"gained {now.classification.value} realization"
            )
        )
        changes.append(SlotChange(SlotIdentity(key, realization), kind, detail))


def _supported(record: SlotRecord) -> bool:
    return record.classification is not ImplementationSlotClass.UNSUPPORTED


def _class_rank(value: ImplementationSlotClass) -> int:
    return {
        ImplementationSlotClass.NATIVE: 0,
        ImplementationSlotClass.COMPOSED: 1,
        ImplementationSlotClass.GENERIC_FALLBACK: 2,
        ImplementationSlotClass.UNSUPPORTED: 3,
    }[value]


def _realization_sort_key(
    value: TargetSupportRealizationKey | None,
) -> tuple[object, ...]:
    return () if value is None else value.sort_key()


def _record_change(was: SlotRecord, now: SlotRecord) -> str:
    if was.classification != now.classification:
        return f"{was.classification.value} -> {now.classification.value}"
    return (
        f"{was.status.value}/{was.reason_id or '-'} -> "
        f"{now.status.value}/{now.reason_id or '-'}"
    )


def serialize(snapshot: Snapshot) -> str:
    """Serialize one line per profile-grouped exact outcome."""

    grouped: dict[_SerializedPattern, list[str]] = defaultdict(list)
    for identity, record in snapshot.slots.items():
        grouped[_SerializedPattern.from_slot(identity, record)].append(
            identity.key.profile
        )
    lines = [
        "{",
        f'  "version": {_BASELINE_VERSION},',
        '  "backend_profiles": '
        + json.dumps(snapshot.backend_profiles, separators=(",", ":"))
        + ",",
        '  "types": ' + json.dumps(snapshot.types, separators=(",", ":")) + ",",
        '  "parity_extensions": '
        + json.dumps(snapshot.parity_extensions, separators=(",", ":"))
        + ",",
        '  "target_specific_primitives": '
        + json.dumps(snapshot.target_specific_primitives, separators=(",", ":"))
        + ",",
        '  "slots": [',
    ]
    ordered = sorted(grouped.items(), key=lambda item: item[0].sort_key())
    for index, (pattern, profiles) in enumerate(ordered):
        suffix = "," if index + 1 < len(ordered) else ""
        lines.append(
            "    "
            + json.dumps(
                _pattern_payload(pattern, tuple(sorted(profiles))),
                separators=(",", ":"),
            )
            + suffix
        )
    lines.extend(("  ]", "}"))
    return "\n".join(lines) + "\n"


def deserialize(text: str) -> Snapshot:
    payload = json.loads(text)
    if payload.get("version") != _BASELINE_VERSION:
        raise ValueError(
            f"unsupported implementation-slot baseline version {payload.get('version')!r}"
        )
    slots: dict[SlotIdentity, SlotRecord] = {}
    for item in payload["slots"]:
        pattern, profiles = _pattern_from_payload(item)
        for profile in profiles:
            identity = pattern.identity(profile)
            if identity in slots:
                raise ValueError(f"duplicate implementation slot {_label(identity)}")
            slots[identity] = pattern.record
    return Snapshot(
        backend_profiles=tuple(
            (str(item[0]), tuple(cast(list[str], item[1])))
            for item in payload["backend_profiles"]
        ),
        types=tuple(payload["types"]),
        slots=slots,
        parity_extensions=tuple(payload["parity_extensions"]),
        target_specific_primitives=tuple(payload["target_specific_primitives"]),
    )


def _pattern_payload(
    pattern: _SerializedPattern, profiles: tuple[str, ...]
) -> dict[str, object]:
    return {
        "profiles": profiles,
        "key": [
            pattern.backend,
            pattern.primitive,
            pattern.signature,
            pattern.attributes,
            pattern.result_target,
            pattern.overload,
            pattern.type_tag,
            pattern.target_extension,
            pattern.conversion_target,
        ],
        "realization": _realization_payload(pattern.realization),
        "classification": pattern.record.classification.value,
        "status": pattern.record.status.value,
        "reason_id": pattern.record.reason_id,
        "implementation_state": pattern.record.implementation_state,
    }


def _pattern_from_payload(
    payload: dict[str, object],
) -> tuple[_SerializedPattern, tuple[str, ...]]:
    key = cast(list[object], payload["key"])
    attributes = cast(list[list[str]], key[3])
    result_target = cast(list[str] | None, key[4])
    overload = cast(list[object] | None, key[5])
    pattern = _SerializedPattern(
        backend=str(key[0]),
        primitive=str(key[1]),
        signature=str(key[2]),
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
        type_tag=str(key[6]),
        target_extension=str(key[7]),
        conversion_target=None if key[8] is None else str(key[8]),
        realization=_realization_from_payload(payload["realization"]),
        record=SlotRecord(
            classification=ImplementationSlotClass(str(payload["classification"])),
            status=TargetSupportStatus(str(payload["status"])),
            reason_id=(
                None if payload["reason_id"] is None else str(payload["reason_id"])
            ),
            implementation_state=(
                None
                if payload["implementation_state"] is None
                else str(payload["implementation_state"])
            ),
        ),
    )
    return pattern, tuple(cast(list[str], payload["profiles"]))


def _realization_payload(
    realization: TargetSupportRealizationKey | None,
) -> list[object] | None:
    if realization is None:
        return None
    return [
        realization.source_extension,
        realization.selector_path,
        realization.required_features,
        realization.required_compiler_capabilities,
        realization.concrete_lanes,
        realization.simd_type_base_bindings,
        realization.variant_names,
    ]


def _realization_from_payload(value: object) -> TargetSupportRealizationKey | None:
    if value is None:
        return None
    values = cast(list[object], value)
    lanes = values[4]
    if lanes is not None and not isinstance(lanes, int):
        raise ValueError("implementation-slot concrete lanes must be an integer")
    bindings = cast(list[list[str]], values[5])
    return TargetSupportRealizationKey(
        source_extension=str(values[0]),
        selector_path=tuple(cast(list[str], values[1])),
        required_features=tuple(cast(list[str], values[2])),
        required_compiler_capabilities=tuple(cast(list[str], values[3])),
        concrete_lanes=lanes,
        simd_type_base_bindings=tuple((item[0], item[1]) for item in bindings),
        variant_names=tuple(cast(list[str], values[6])),
    )


def format_report(diff: DiffReport, snapshot: Snapshot) -> str:
    not_applicable = sum(
        record.status is TargetSupportStatus.NOT_APPLICABLE
        for record in snapshot.slots.values()
    )
    classifications = Counter(
        record.classification.value
        for record in snapshot.slots.values()
        if record.status is not TargetSupportStatus.NOT_APPLICABLE
    )
    lines = [
        f"implementation slots: {len(snapshot.slots) - not_applicable} applicable "
        f"exact outcomes and {not_applicable} not-applicable axes across "
        f"{sum(len(profiles) for _backend, profiles in snapshot.backend_profiles)} "
        f"backend/profile scopes; parity scope={len(snapshot.parity_extensions)} "
        f"shared extensions; target-specific primitives="
        f"{len(snapshot.target_specific_primitives)}",
        "classifications: "
        + ", ".join(
            f"{classification.value}={classifications[classification.value]}"
            for classification in ImplementationSlotClass
        ),
        f"shared logical coverage gaps: {len(implementation_coverage_gaps(snapshot))}",
    ]
    counts = Counter(item.kind for item in diff.changes)
    lines.append(
        "changes: "
        + (", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none")
    )
    for change in diff.changes[:100]:
        label = "scope" if change.identity is None else _label(change.identity)
        lines.append(f"  {change.kind}: {label}: {change.detail}")
    if len(diff.changes) > 100:
        lines.append(f"  ... and {len(diff.changes) - 100} more")
    return "\n".join(lines)


def _label(identity: SlotIdentity) -> str:
    key = identity.key
    conversion = "" if key.conversion_target is None else f" -> {key.conversion_target}"
    source = (
        "absent"
        if identity.realization is None
        else identity.realization.source_extension
    )
    return (
        f"{key.profile}/{key.backend} {key.declaration_identity}"
        f"<{key.target_extension},{key.type_tag}>{conversion} via {source}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc coverage implementation-ratchet",
        description=(
            "Classify and ratchet every exact TSL v1 implementation slot as "
            "native, composed, generic fallback, or unsupported."
        ),
    )
    parser.add_argument("--sources")
    parser.add_argument("--machine-profiles")
    parser.add_argument("--baseline")
    parser.add_argument("--update", action="store_true")
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
        print("implementation-slot ratchet generation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 2
    quality_gaps = implementation_quality_gaps(snapshot)
    if quality_gaps:
        for gap in quality_gaps[:100]:
            assert gap.identity is not None
            print(f"  quality-gap: {_label(gap.identity)}: {gap.detail}")
        if len(quality_gaps) > 100:
            print(f"  ... and {len(quality_gaps) - 100} more")
        print(f"FAIL: {len(quality_gaps)} implementation-quality gap(s)")
        return 1
    coverage_gaps = implementation_coverage_gaps(snapshot)
    if coverage_gaps:
        for gap in coverage_gaps[:100]:
            assert gap.identity is not None
            print(f"  coverage-gap: {_label(gap.identity)}: {gap.detail}")
        if len(coverage_gaps) > 100:
            print(f"  ... and {len(coverage_gaps) - 100} more")
        print(f"FAIL: {len(coverage_gaps)} applicable implementation gap(s)")
        return 1
    path = Path(args.baseline) if args.baseline else canonical_baseline_path(context)
    if args.update:
        previous = None
        if path.is_file():
            try:
                previous = deserialize(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                print(
                    f"replacing incompatible implementation-slot baseline {path}",
                    file=sys.stderr,
                )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize(snapshot), encoding="utf-8")
        if previous is not None:
            print(format_report(diff_snapshots(previous, snapshot), snapshot))
        print(f"wrote {path}")
        return 0
    if not path.is_file():
        print(f"implementation-slot baseline is missing: {path}", file=sys.stderr)
        return 2
    try:
        baseline = deserialize(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"invalid implementation-slot baseline: {error}", file=sys.stderr)
        return 2
    diff = diff_snapshots(baseline, snapshot)
    print(format_report(diff, snapshot))
    if diff.regressions:
        print(f"FAIL: {len(diff.regressions)} implementation-slot regression(s)")
        return 1
    print("OK: no implementation-slot regressions")
    return 0


__all__ = (
    "DiffReport",
    "SlotChange",
    "SlotIdentity",
    "SlotRecord",
    "Snapshot",
    "canonical_baseline_path",
    "classify_entries",
    "compute_snapshot",
    "deserialize",
    "diff_snapshots",
    "format_report",
    "implementation_coverage_gaps",
    "implementation_quality_gaps",
    "main",
    "serialize",
)


if __name__ == "__main__":
    raise SystemExit(main())
