"""Exact target-support trace and release-ratchet tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tslc.api import generate_project
from tslc.lower.implementation_facts import ImplementationState
from tslc.maintenance.target_support_ratchet import (
    SlotOutcome,
    SlotRecord,
    Snapshot,
    deserialize,
    diff_snapshots,
    serialize,
)
from tslc.target_support import (
    TargetSupportKey,
    TargetSupportRealizationKey,
    TargetSupportStatus,
)


_KEY = TargetSupportKey(
    profile="rvv",
    backend="cpp",
    primitive="probe",
    signature="v:=(v)",
    attributes=(),
    result_target=None,
    overload=None,
    type_tag="si32",
    target_extension="rvv",
    conversion_target=None,
)
_REALIZATION = TargetSupportRealizationKey(
    source_extension="rvv",
    selector_path=("rvv", "arith"),
    required_features=("v",),
    required_compiler_capabilities=(),
    concrete_lanes=None,
    simd_type_base_bindings=(),
    variant_names=(),
)


def _snapshot(record: SlotRecord) -> Snapshot:
    return Snapshot(
        profile_targets=(("rvv", "cpp", "rvv"),),
        types=("si32",),
        exclusions=(),
        slots={_KEY: record},
    )


def test_completely_absent_target_candidate_regresses_emitted_slot() -> None:
    baseline = _snapshot(
        SlotRecord(
            (
                SlotOutcome(
                    _REALIZATION,
                    TargetSupportStatus.EMITTED,
                    implementation_state=ImplementationState.NATIVE.value,
                ),
            )
        )
    )
    current = _snapshot(
        SlotRecord(
            (
                SlotOutcome(
                    None,
                    TargetSupportStatus.ABSENT,
                    reason_id="TSL-SELECT-NO-CANDIDATE",
                ),
            )
        )
    )

    diff = diff_snapshots(baseline, current)

    assert len(diff.regressions) == 1
    assert "lost 1 emitted realization" in diff.regressions[0].detail


def test_implementation_quality_degradation_is_a_regression() -> None:
    native = _snapshot(
        SlotRecord(
            (
                SlotOutcome(
                    _REALIZATION,
                    TargetSupportStatus.EMITTED,
                    implementation_state="native",
                ),
            )
        )
    )
    fallback = _snapshot(
        SlotRecord(
            (
                SlotOutcome(
                    _REALIZATION,
                    TargetSupportStatus.EMITTED,
                    implementation_state="fallback",
                ),
            )
        )
    )

    assert "state degraded" in diff_snapshots(native, fallback).regressions[0].detail


def test_new_complete_primitive_slot_is_additive() -> None:
    record = SlotRecord(
        (
            SlotOutcome(
                _REALIZATION,
                TargetSupportStatus.EMITTED,
                implementation_state="native",
            ),
        )
    )
    baseline = _snapshot(record)
    current = replace(
        baseline,
        slots={
            _KEY: record,
            replace(_KEY, primitive="unrelated"): record,
        },
    )

    diff = diff_snapshots(baseline, current)

    assert not diff.regressions
    assert [item.kind for item in diff.changes] == ["added"]


def test_resolving_an_absent_conversion_target_is_an_improvement() -> None:
    unresolved_key = replace(
        _KEY,
        primitive="convert",
        result_target=("base", "ToBase"),
    )
    absent = SlotRecord(
        (
            SlotOutcome(
                None,
                TargetSupportStatus.ABSENT,
                reason_id="TSL-SELECT-NO-CANDIDATE",
            ),
        )
    )
    emitted = SlotRecord(
        (
            SlotOutcome(
                _REALIZATION,
                TargetSupportStatus.EMITTED,
                implementation_state="native",
            ),
        )
    )
    baseline = replace(_snapshot(absent), slots={unresolved_key: absent})
    concrete_key = replace(unresolved_key, conversion_target="ui32")
    current = replace(baseline, slots={concrete_key: emitted})

    diff = diff_snapshots(baseline, current)

    assert not diff.regressions
    assert [item.kind for item in diff.changes] == ["improved", "added"]


def test_exact_snapshot_serialization_is_deterministic_and_round_trips() -> None:
    snapshot = _snapshot(
        SlotRecord(
            (
                SlotOutcome(
                    _REALIZATION,
                    TargetSupportStatus.EMITTED,
                    implementation_state="native",
                ),
            )
        )
    )

    text = serialize(snapshot)

    assert serialize(snapshot) == text
    assert deserialize(text) == snapshot
    assert len([line for line in text.splitlines() if '"key"' in line]) == 1


def test_pipeline_trace_uses_selector_identity_and_final_generation_state(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=("add",),
        profiles=("rvv",),
        type_tags=("si32",),
        extensions=("rvv",),
        backends=("cpp",),
        render_artifacts=False,
        collect_target_support=True,
    )

    assert result.target_support is not None
    add = tuple(
        entry
        for entry in result.target_support.entries
        if entry.key.primitive == "add"
        and entry.key.target_extension == "rvv"
        and entry.key.type_tag == "si32"
    )
    assert {entry.key.declaration_identity for entry in add} == {
        "add#v:=(v,v)",
        "add[mask=zero]#v:=(m,v,v)",
        "add[mask=pass_through]#v:=(m,v,v)",
    }
    assert all(entry.realization is not None for entry in add)
    assert all(entry.status is TargetSupportStatus.EMITTED for entry in add)
    assert all(entry.implementation_state is not None for entry in add)
    assert tuple(entry.sort_key() for entry in result.target_support.entries) == tuple(
        sorted(entry.sort_key() for entry in result.target_support.entries)
    )
