"""Tests for the coverage ratchet gate (maintenance/coverage_ratchet.py)."""

from __future__ import annotations

from pathlib import Path

from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.diagnostics import Diagnostic
from tslc.maintenance.coverage_ratchet import (
    _BASELINE,
    Snapshot,
    SlotKey,
    SlotRecord,
    compute_snapshot,
    deserialize,
    diff_snapshots,
    serialize,
)
from tslc.maintenance.coverage_inventory import (
    PROFILES,
    _OUT as COVERAGE_INVENTORY_OUTPUT,
    skip_category,
)
from tslc.pipeline import SkippedEntry


def _snapshot(slots: dict[SlotKey, SlotRecord]) -> Snapshot:
    return Snapshot(
        profiles=("avx2", "scalar"),
        backends=("cpp",),
        types=("si32", "f32"),
        slots=slots,
    )


_A = SlotKey("avx2", "cpp", "add", "avx2", "si32")
_B = SlotKey("avx2", "cpp", "sub", "avx2", "si32")
_C = SlotKey("scalar", "cpp", "mul", "scalar", "f32")


def test_skip_category_uses_diagnostic_code_not_message() -> None:
    entry = SkippedEntry(
        profile="scalar",
        backend="cpp",
        primitive="probe",
        extension="scalar",
        type_tag="si32",
        reason="wording may change freely",
        diagnostics=(
            Diagnostic(
                severity="info",
                code="TSL-LOWER-UNRESOLVED-TYPE-QUERY",
                message="different wording",
            ),
        ),
    )

    assert skip_category(entry) == "unresolved type query"


def test_emitted_drop_is_a_regression() -> None:
    baseline = _snapshot({_A: SlotRecord(emitted=3)})
    current = _snapshot({_A: SlotRecord(emitted=1)})
    diff = diff_snapshots(baseline, current)
    assert len(diff.regressions) == 1
    assert diff.regressions[0].key == _A
    assert "3 -> 1" in diff.regressions[0].detail


def test_emitted_to_absent_is_a_regression() -> None:
    baseline = _snapshot({_A: SlotRecord(emitted=2)})
    current = _snapshot({})
    diff = diff_snapshots(baseline, current)
    assert len(diff.regressions) == 1
    assert "now absent" in diff.regressions[0].detail


def test_skipped_to_emitted_is_a_fix_not_a_regression() -> None:
    baseline = _snapshot({_A: SlotRecord(emitted=0, skipped=1, reasons=("pruned (closure)",))})
    current = _snapshot({_A: SlotRecord(emitted=1)})
    diff = diff_snapshots(baseline, current)
    assert not diff.regressions
    assert [c.kind for c in diff.improvements] == ["fixed"]


def test_more_variants_emit_is_an_improvement() -> None:
    baseline = _snapshot({_A: SlotRecord(emitted=1)})
    current = _snapshot({_A: SlotRecord(emitted=3)})
    diff = diff_snapshots(baseline, current)
    assert not diff.regressions
    assert diff.of_kind("improved") and not diff.of_kind("fixed")


def test_new_slot_is_a_gap_not_a_regression() -> None:
    baseline = _snapshot({})
    current = _snapshot({_B: SlotRecord(emitted=0, skipped=1, reasons=("unresolved value query",))})
    diff = diff_snapshots(baseline, current)
    assert not diff.regressions
    assert diff.of_kind("new-gap")


def test_reason_change_is_informational() -> None:
    baseline = _snapshot({_C: SlotRecord(skipped=1, reasons=("unresolved type query",))})
    current = _snapshot({_C: SlotRecord(skipped=1, reasons=("no top-level complete",))})
    diff = diff_snapshots(baseline, current)
    assert not diff.regressions
    assert diff.of_kind("reason-changed")


def test_identical_snapshots_have_no_changes() -> None:
    snap = _snapshot({_A: SlotRecord(emitted=2), _C: SlotRecord(skipped=1, reasons=("x",))})
    assert diff_snapshots(snap, snap).changes == ()


def test_serialize_round_trips() -> None:
    snap = _snapshot(
        {
            _A: SlotRecord(emitted=2),
            _C: SlotRecord(emitted=0, skipped=3, reasons=("pruned (closure)", "x")),
        }
    )
    restored = deserialize(serialize(snap))
    assert restored.slots == snap.slots
    assert restored.profiles == snap.profiles
    assert restored.types == snap.types


def test_serialize_is_deterministic() -> None:
    snap = _snapshot({_B: SlotRecord(emitted=1), _A: SlotRecord(emitted=1)})
    assert serialize(snap) == serialize(snap)
    # keys are emitted in sorted order regardless of dict insertion order
    text = serialize(snap)
    assert text.index("add|avx2|si32") < text.index("sub|avx2|si32")


def test_skip_record_round_trips_with_reasons() -> None:
    snap = _snapshot({_C: SlotRecord(emitted=0, skipped=2, reasons=("pruned (closure)", "x"))})
    restored = deserialize(serialize(snap))
    assert restored.slots[_C] == SlotRecord(emitted=0, skipped=2, reasons=("pruned (closure)", "x"))


def test_compute_snapshot_self_diff_is_clean(
    data_root: Path, machine_profiles_path: Path
) -> None:
    # A real (small-scope) snapshot diffed against itself must report no changes.
    snapshot, errors = compute_snapshot(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        profiles=("avx2", "scalar"),
        backends=("cpp",),
        types=("si32", "f32"),
        primitives=("add", "sub"),
    )
    assert errors == []
    assert snapshot is not None
    assert snapshot.slots  # produced something
    assert diff_snapshots(snapshot, snapshot).changes == ()
    # add on avx2/cpp/si32 should be emitted
    assert snapshot.slots[SlotKey("avx2", "cpp", "add", "avx2", "si32")].emitted >= 1


def test_canonical_coverage_profiles_exist_in_machine_profiles(
    machine_profiles_path: Path,
) -> None:
    machine_profiles = load_machine_profiles_checked(machine_profiles_path).profiles
    assert set(PROFILES) <= set(machine_profiles)


def test_committed_baseline_uses_canonical_profiles() -> None:
    baseline = deserialize(_BASELINE.read_text(encoding="utf-8"))
    assert baseline.profiles == PROFILES


def test_coverage_inventory_output_is_not_under_top_level_docs() -> None:
    assert COVERAGE_INVENTORY_OUTPUT.parent.name == "coverage"
    assert COVERAGE_INVENTORY_OUTPUT.name == "primitive-coverage-inventory.md"
