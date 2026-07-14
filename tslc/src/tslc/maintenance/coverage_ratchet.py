#!/usr/bin/env python3
"""Coverage ratchet gate: fail when a change drops a slot that used to lower.

The charter tracks progress by the coverage table (*primitive × extension × backend → compiles?*),
"never by a milestone number". This turns that table into a **ratchet**: it drives the compiler
over the canonical probe set (every primitive, the canonical profiles, both backends, the arith
type tags), snapshots the per-slot outcome, and compares it to a committed baseline. A slot that
*regresses* — emitted before, now skipped/gone — fails the gate. Improvements and brand-new gaps
are reported but never fail; you accept a new snapshot explicitly with ``--update``.

It is lowering-only (no compilation), like ``coverage_inventory`` — fast and deterministic. "Lowers"
is not a compile guarantee; build verification is a separate gate. The unit of coverage is the
``(profile, backend, primitive, extension, type)`` slot, counted (so a masked-variant regression
that leaves the bare name still emitting is still caught as a drop in the emitted count).

Run from the repository with ``tslc/src`` on ``PYTHONPATH``:

    # create / refresh the committed baseline after an intended coverage change
    PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_ratchet --update

    # gate: exit non-zero if any slot regressed against the baseline
    PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_ratchet
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.backend.registry import registered_backend_ids
from tslc.diagnostics import has_errors
from tslc.maintenance.coverage_inventory import (
    PROFILES,
    _DATA_ROOT,
    _PROFILES_PATH,
    _REPO_ROOT,
    skip_category,
)

_BACKENDS = registered_backend_ids()
# A lockfile-style committed snapshot: machine-generated, diffed by this gate, not hand-edited.
# It lives at the repo root (it describes whole-repo generation state, spanning tsldata/ and
# supplementary/), not under tslc/ (source) or docs/ (prose evidence).
_BASELINE = _REPO_ROOT / "coverage" / "baseline.json"
_BASELINE_VERSION = 1


@dataclass(frozen=True, slots=True)
class SlotKey:
    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str

    def as_tuple(self) -> tuple[str, str, str, str, str]:
        return (self.profile, self.backend, self.primitive, self.extension, self.type_tag)


@dataclass(frozen=True, slots=True)
class SlotRecord:
    """The per-slot outcome: how many specialization variants emitted vs skipped, and why.

    Variants collapse onto one ``SlotKey`` because coverage entries don't carry mask policy /
    axis — so ``add`` and ``add[mask=zero]`` for the same ``(profile, backend, ext, type)`` share
    a key. Counting keeps that granularity visible: a drop from 3 emitted to 2 is a regression even
    though the slot still emits something."""

    emitted: int = 0
    skipped: int = 0
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SlotChange:
    key: SlotKey
    kind: str  # "regressed" | "fixed" | "improved" | "new-gap" | "reason-changed" | "removed"
    detail: str


@dataclass(frozen=True, slots=True)
class DiffReport:
    changes: tuple[SlotChange, ...]

    @property
    def regressions(self) -> tuple[SlotChange, ...]:
        return tuple(c for c in self.changes if c.kind == "regressed")

    @property
    def improvements(self) -> tuple[SlotChange, ...]:
        return tuple(c for c in self.changes if c.kind in ("fixed", "improved"))

    def of_kind(self, kind: str) -> tuple[SlotChange, ...]:
        return tuple(c for c in self.changes if c.kind == kind)


@dataclass(frozen=True, slots=True)
class Snapshot:
    profiles: tuple[str, ...]
    backends: tuple[str, ...]
    types: tuple[str, ...]
    slots: dict[SlotKey, SlotRecord]


# --------------------------------------------------------------------------- compute


def compute_snapshot(
    *,
    sources: Path,
    machine_profiles: Path,
    profiles: tuple[str, ...],
    backends: tuple[str, ...],
    types: tuple[str, ...],
    primitives: tuple[str, ...] | None = None,
) -> tuple[Snapshot | None, list[str]]:
    """Drive generation over the probe set and fold the result into per-slot records."""

    result = generate_project(
        [sources],
        machine_profiles_path=machine_profiles,
        primitives=list(primitives) if primitives is not None else None,
        profiles=list(profiles),
        type_tags=types,
        backends=backends,
    )
    if has_errors(result.diagnostics):
        errors = [
            f"[{d.severity}] {d.code}: {d.message}"
            for d in result.diagnostics
            if d.severity == "error"
        ]
        return None, errors

    emitted: dict[SlotKey, int] = {}
    skipped: dict[SlotKey, int] = {}
    reasons: dict[SlotKey, set[str]] = {}
    for coverage_entry in result.coverage:
        key = SlotKey(
            coverage_entry.profile,
            coverage_entry.backend,
            coverage_entry.primitive,
            coverage_entry.extension,
            coverage_entry.type_tag,
        )
        emitted[key] = emitted.get(key, 0) + 1
    for skipped_entry in result.skipped:
        key = SlotKey(
            skipped_entry.profile,
            skipped_entry.backend,
            skipped_entry.primitive,
            skipped_entry.extension,
            skipped_entry.type_tag,
        )
        skipped[key] = skipped.get(key, 0) + 1
        reasons.setdefault(key, set()).add(skip_category(skipped_entry))

    slots: dict[SlotKey, SlotRecord] = {}
    for key in emitted.keys() | skipped.keys():
        slots[key] = SlotRecord(
            emitted=emitted.get(key, 0),
            skipped=skipped.get(key, 0),
            reasons=tuple(sorted(reasons.get(key, set()))),
        )
    return Snapshot(profiles, backends, types, slots), []


# --------------------------------------------------------------------------- diff


def diff_snapshots(baseline: Snapshot, current: Snapshot) -> DiffReport:
    """Classify every slot change. The only failing kind is ``regressed`` (emitted count dropped)."""

    changes: list[SlotChange] = []
    absent = SlotRecord()
    for key in sorted(baseline.slots.keys() | current.slots.keys(), key=SlotKey.as_tuple):
        was = baseline.slots.get(key, absent)
        now = current.slots.get(key, absent)
        if was == now:
            continue
        if now.emitted < was.emitted:
            lost = was.emitted - now.emitted
            where = "now skipped" if now.skipped else "now absent"
            changes.append(
                SlotChange(
                    key,
                    "regressed",
                    f"emitted {was.emitted} -> {now.emitted} ({lost} lost, {where}"
                    + (f": {', '.join(now.reasons)}" if now.reasons else "")
                    + ")",
                )
            )
        elif now.emitted > was.emitted:
            kind = "fixed" if was.emitted == 0 else "improved"
            changes.append(
                SlotChange(key, kind, f"emitted {was.emitted} -> {now.emitted}")
            )
        elif was.emitted == 0 and now.emitted == 0:
            # never emitted; only the skip picture moved
            if was == absent:
                changes.append(SlotChange(key, "new-gap", f"new skipped slot: {', '.join(now.reasons)}"))
            elif now == absent:
                changes.append(SlotChange(key, "removed", "slot no longer attempted"))
            elif now.reasons != was.reasons:
                changes.append(
                    SlotChange(
                        key,
                        "reason-changed",
                        f"skip reason {list(was.reasons)} -> {list(now.reasons)}",
                    )
                )
        elif now.reasons != was.reasons:
            changes.append(
                SlotChange(
                    key,
                    "reason-changed",
                    f"skip reason {list(was.reasons)} -> {list(now.reasons)}",
                )
            )
    return DiffReport(tuple(changes))


# --------------------------------------------------------------------------- (de)serialize


def serialize(snapshot: Snapshot) -> str:
    """A compact, line-diffable baseline.

    Each slot is one ``"profile|backend|primitive|extension|type": "<record>"`` line — a scalar
    string value so ``indent=2`` keeps one slot per line (a regression shows up as a single
    changed line in review). The record is ``"E"`` when nothing skips, else ``"E/S:reason;…"``."""

    payload = {
        "version": _BASELINE_VERSION,
        "canonical": {
            "profiles": list(snapshot.profiles),
            "backends": list(snapshot.backends),
            "types": list(snapshot.types),
        },
        "slots": {
            "|".join(key.as_tuple()): _encode_record(record)
            for key, record in sorted(snapshot.slots.items(), key=lambda item: item[0].as_tuple())
        },
    }
    return json.dumps(payload, indent=2) + "\n"


def deserialize(text: str) -> Snapshot:
    payload = json.loads(text)
    canonical = payload.get("canonical", {})
    slots: dict[SlotKey, SlotRecord] = {}
    for key_str, value in payload.get("slots", {}).items():
        profile, backend, primitive, extension, type_tag = key_str.split("|")
        slots[SlotKey(profile, backend, primitive, extension, type_tag)] = _decode_record(value)
    return Snapshot(
        profiles=tuple(canonical.get("profiles", ())),
        backends=tuple(canonical.get("backends", ())),
        types=tuple(canonical.get("types", ())),
        slots=slots,
    )


def _encode_record(record: SlotRecord) -> str:
    if record.skipped == 0 and not record.reasons:
        return str(record.emitted)
    reasons = ";".join(reason.replace(";", ",") for reason in record.reasons)
    return f"{record.emitted}/{record.skipped}:{reasons}"


def _decode_record(value: str) -> SlotRecord:
    if "/" not in value:
        return SlotRecord(emitted=int(value))
    emitted_str, rest = value.split("/", 1)
    skipped_str, _, reasons_str = rest.partition(":")
    reasons = tuple(reasons_str.split(";")) if reasons_str else ()
    return SlotRecord(emitted=int(emitted_str), skipped=int(skipped_str), reasons=reasons)


# --------------------------------------------------------------------------- report


def format_report(diff: DiffReport, *, baseline: Snapshot, current: Snapshot) -> str:
    lines: list[str] = []
    if (baseline.profiles, baseline.backends, baseline.types) != (
        current.profiles,
        current.backends,
        current.types,
    ):
        lines.append(
            "WARNING: baseline probe set differs from current — comparison may be unreliable.\n"
            f"  baseline: profiles={list(baseline.profiles)} types={list(baseline.types)}\n"
            f"  current : profiles={list(current.profiles)} types={list(current.types)}"
        )
    total_emitted = sum(r.emitted for r in current.slots.values())
    total_skipped = sum(r.skipped for r in current.slots.values())
    lines.append(
        f"coverage: {total_emitted} emitted / {total_emitted + total_skipped} slot-variants "
        f"across {len(current.slots)} keys"
    )
    counts = {
        kind: len(diff.of_kind(kind))
        for kind in ("regressed", "fixed", "improved", "new-gap", "reason-changed", "removed")
    }
    lines.append(
        "changes: "
        + ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        + (" (none)" if not any(counts.values()) else "")
    )

    def _block(title: str, kind: str, limit: int | None = None) -> None:
        items = diff.of_kind(kind)
        if not items:
            return
        lines.append("")
        lines.append(f"{title} ({len(items)}):")
        shown = items if limit is None else items[:limit]
        for change in shown:
            lines.append(f"  {_label(change.key)}  {change.detail}")
        if limit is not None and len(items) > limit:
            lines.append(f"  … and {len(items) - limit} more")

    _block("🚨 REGRESSIONS", "regressed")
    _block("✅ fixed (now emits)", "fixed")
    _block("➕ improved (more variants emit)", "improved", limit=20)
    _block("🆕 new gaps", "new-gap", limit=20)
    _block("✏️  skip-reason changed", "reason-changed", limit=20)
    _block("➖ removed (no longer attempted)", "removed", limit=20)
    return "\n".join(lines)


def _label(key: SlotKey) -> str:
    return f"{key.profile}/{key.backend} {key.primitive}<{key.extension}, {key.type_tag}>"


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc-coverage-ratchet",
        description="Fail when a change drops a coverage slot that used to lower.",
    )
    parser.add_argument("--baseline", default=str(_BASELINE), help="path to the baseline JSON")
    parser.add_argument(
        "--update",
        action="store_true",
        help="recompute and overwrite the baseline (accept the current coverage); never fails",
    )
    parser.add_argument("--sources", default=str(_DATA_ROOT))
    parser.add_argument("--machine-profiles", default=str(_PROFILES_PATH))
    parser.add_argument("--profiles", default=",".join(PROFILES))
    parser.add_argument("--backends", default=",".join(_BACKENDS))
    parser.add_argument("--types", default=",".join(_ARITH_TYPE_TAGS))
    args = parser.parse_args(argv)

    snapshot, errors = compute_snapshot(
        sources=Path(args.sources),
        machine_profiles=Path(args.machine_profiles),
        profiles=tuple(_split(args.profiles)),
        backends=tuple(_split(args.backends)),
        types=tuple(_split(args.types)),
    )
    if snapshot is None:
        print("coverage ratchet: generation failed with errors:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 2

    baseline_path = Path(args.baseline)

    if args.update:
        previous = (
            deserialize(baseline_path.read_text()) if baseline_path.exists() else None
        )
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(serialize(snapshot))
        if previous is not None:
            diff = diff_snapshots(previous, snapshot)
            print(format_report(diff, baseline=previous, current=snapshot))
            if diff.regressions:
                print(
                    f"\nnote: baseline updated despite {len(diff.regressions)} regression(s) "
                    "(--update accepts them)."
                )
        print(f"\nwrote baseline {baseline_path}")
        return 0

    if not baseline_path.exists():
        print(
            f"coverage ratchet: no baseline at {baseline_path}. "
            "Create one with: python -m tslc.maintenance.coverage_ratchet --update",
            file=sys.stderr,
        )
        return 2

    baseline = deserialize(baseline_path.read_text())
    diff = diff_snapshots(baseline, snapshot)
    print(format_report(diff, baseline=baseline, current=snapshot))
    if diff.regressions:
        print(
            f"\nFAIL: {len(diff.regressions)} slot(s) regressed. If intended, accept with "
            "`python -m tslc.maintenance.coverage_ratchet --update`."
        )
        return 1
    print("\nOK: no coverage regressions.")
    return 0


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
