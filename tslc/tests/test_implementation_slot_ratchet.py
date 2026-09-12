"""Four-way implementation-slot classification and exact-ratchet tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.lower.implementation_facts import ImplementationState
from tslc.maintenance.implementation_slot_ratchet import (
    SlotIdentity,
    SlotRecord,
    Snapshot,
    classify_entries,
    deserialize,
    diff_snapshots,
    implementation_coverage_gaps,
    implementation_quality_gaps,
    serialize,
)
from tslc.target_support import (
    ImplementationSlotClass,
    TargetSupportEntry,
    TargetSupportKey,
    TargetSupportRealizationKey,
    TargetSupportStatus,
    UNCLASSIFIED_IMPLEMENTATION_REASON,
    implementation_slot_class,
    implementation_slot_reason,
)


_KEY = TargetSupportKey(
    profile="avx2",
    backend="cpp",
    primitive="probe",
    signature="v:=(v)",
    attributes=(),
    result_target=None,
    overload=None,
    type_tag="si32",
    target_extension="avx2",
    conversion_target=None,
)
_REALIZATION = TargetSupportRealizationKey(
    source_extension="avx2",
    selector_path=("avx2", "arith"),
    required_features=("avx2",),
    required_compiler_capabilities=(),
    concrete_lanes=None,
    simd_type_base_bindings=(),
    variant_names=(),
)


def _entry(
    state: ImplementationState | None,
    *,
    status: TargetSupportStatus = TargetSupportStatus.EMITTED,
    reason_id: str | None = None,
    key: TargetSupportKey = _KEY,
    realization: TargetSupportRealizationKey | None = _REALIZATION,
) -> TargetSupportEntry:
    return TargetSupportEntry(
        key=key,
        realization=realization,
        status=status,
        reason_id=reason_id,
        implementation_state=state,
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        (ImplementationState.NATIVE, ImplementationSlotClass.NATIVE),
        (ImplementationState.COMPOSED, ImplementationSlotClass.COMPOSED),
        (ImplementationState.FALLBACK, ImplementationSlotClass.GENERIC_FALLBACK),
        (ImplementationState.UNKNOWN, ImplementationSlotClass.UNSUPPORTED),
        (None, ImplementationSlotClass.UNSUPPORTED),
    ),
)
def test_emitted_state_projects_to_four_way_classification(
    state: ImplementationState | None,
    expected: ImplementationSlotClass,
) -> None:
    entry = _entry(state)

    assert implementation_slot_class(entry) is expected
    assert implementation_slot_reason(entry) == (
        UNCLASSIFIED_IMPLEMENTATION_REASON
        if expected is ImplementationSlotClass.UNSUPPORTED
        else None
    )


@pytest.mark.parametrize(
    "status",
    tuple(
        status
        for status in TargetSupportStatus
        if status is not TargetSupportStatus.EMITTED
    ),
)
def test_every_non_emitted_pipeline_outcome_is_explicitly_unsupported(
    status: TargetSupportStatus,
) -> None:
    entry = _entry(
        None,
        status=status,
        reason_id="TSL-TEST-UNSUPPORTED",
        realization=None,
    )

    assert implementation_slot_class(entry) is ImplementationSlotClass.UNSUPPORTED
    assert implementation_slot_reason(entry) == "TSL-TEST-UNSUPPORTED"


def test_classification_consumes_exact_compiler_owned_trace_identity() -> None:
    entries = (
        _entry(ImplementationState.NATIVE),
        _entry(
            None,
            status=TargetSupportStatus.ABSENT,
            reason_id="TSL-SELECT-NO-CANDIDATE",
            key=replace(_KEY, primitive="missing"),
            realization=None,
        ),
    )

    snapshot = classify_entries(
        entries,
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
    )

    assert set(snapshot.slots) == {
        SlotIdentity(entries[0].key, entries[0].realization),
        SlotIdentity(entries[1].key, entries[1].realization),
    }
    assert snapshot.slots[SlotIdentity(_KEY, _REALIZATION)].classification is (
        ImplementationSlotClass.NATIVE
    )


@pytest.mark.parametrize(
    ("before", "after"),
    (
        (ImplementationSlotClass.NATIVE, ImplementationSlotClass.COMPOSED),
        (
            ImplementationSlotClass.COMPOSED,
            ImplementationSlotClass.GENERIC_FALLBACK,
        ),
        (
            ImplementationSlotClass.GENERIC_FALLBACK,
            ImplementationSlotClass.UNSUPPORTED,
        ),
    ),
)
def test_quality_degradation_is_a_regression(
    before: ImplementationSlotClass,
    after: ImplementationSlotClass,
) -> None:
    baseline = _snapshot(before)
    current = _snapshot(after)

    regressions = diff_snapshots(baseline, current).regressions

    assert len(regressions) == 1
    assert regressions[0].detail == f"{before.value} -> {after.value}"


def test_quality_improvement_is_not_a_regression() -> None:
    baseline = _snapshot(ImplementationSlotClass.GENERIC_FALLBACK)
    current = _snapshot(ImplementationSlotClass.COMPOSED)

    diff = diff_snapshots(baseline, current)

    assert not diff.regressions
    assert [change.kind for change in diff.changes] == ["improved"]


def test_portable_primitive_becoming_target_specific_is_a_regression() -> None:
    baseline = _snapshot(ImplementationSlotClass.COMPOSED)
    current = replace(baseline, target_specific_primitives=("probe",))

    regressions = diff_snapshots(baseline, current).regressions

    assert len(regressions) == 1
    assert regressions[0].detail == (
        "portable primitive contract became target-specific: probe"
    )


def test_target_specific_primitive_becoming_portable_is_an_improvement() -> None:
    current = _snapshot(ImplementationSlotClass.COMPOSED)
    baseline = replace(current, target_specific_primitives=("probe",))

    diff = diff_snapshots(baseline, current)

    assert not diff.regressions
    assert [change.kind for change in diff.changes] == ["improved"]


def test_new_target_specific_primitive_is_additive() -> None:
    baseline = _snapshot(ImplementationSlotClass.COMPOSED)
    new_key = replace(_KEY, primitive="new_target_primitive")
    current = replace(
        baseline,
        slots={
            **baseline.slots,
            SlotIdentity(new_key, None): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.NOT_APPLICABLE,
                "TSL-SELECT-TARGET-SPECIFIC-UNAVAILABLE",
                None,
            ),
        },
        target_specific_primitives=("new_target_primitive",),
    )

    diff = diff_snapshots(baseline, current)

    assert not diff.regressions
    assert [change.kind for change in diff.changes] == ["added"]


def test_absent_slot_replaced_by_native_realization_is_an_improvement() -> None:
    absent = Snapshot(
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
        slots={
            SlotIdentity(_KEY, None): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.ABSENT,
                "TSL-SELECT-NO-CANDIDATE",
                None,
            )
        },
    )
    native = _snapshot(ImplementationSlotClass.NATIVE)

    diff = diff_snapshots(absent, native)

    assert not diff.regressions
    assert [change.kind for change in diff.changes] == ["improved"]


def test_emitted_unknown_becoming_native_is_one_improvement() -> None:
    unknown = _snapshot(ImplementationSlotClass.UNSUPPORTED)
    native = _snapshot(ImplementationSlotClass.NATIVE)

    diff = diff_snapshots(unknown, native)

    assert not diff.regressions
    assert [change.kind for change in diff.changes] == ["improved"]


def test_emitted_unknown_is_an_implementation_quality_gap() -> None:
    gaps = implementation_quality_gaps(_snapshot(ImplementationSlotClass.UNSUPPORTED))

    assert len(gaps) == 1
    assert gaps[0].kind == "quality-gap"
    assert "no classified implementation state" in gaps[0].detail


def test_absent_unsupported_slot_is_not_an_implementation_quality_gap() -> None:
    snapshot = Snapshot(
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
        slots={
            SlotIdentity(_KEY, None): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.ABSENT,
                "TSL-SELECT-NO-CANDIDATE",
                None,
            )
        },
    )

    assert not implementation_quality_gaps(snapshot)


def test_absent_shared_logical_slot_is_an_implementation_coverage_gap() -> None:
    snapshot = Snapshot(
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
        slots={
            SlotIdentity(_KEY, None): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.ABSENT,
                "TSL-SELECT-NO-CANDIDATE",
                None,
            )
        },
        parity_extensions=("avx2",),
    )

    gaps = implementation_coverage_gaps(snapshot)

    assert len(gaps) == 1
    assert gaps[0].kind == "coverage-gap"


def test_not_applicable_axis_is_not_an_implementation_coverage_gap() -> None:
    snapshot = Snapshot(
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
        slots={
            SlotIdentity(_KEY, None): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.NOT_APPLICABLE,
                "TSL-SELECT-NO-COMPATIBLE-BASE-TARGET",
                None,
            )
        },
        parity_extensions=("avx2",),
    )

    assert not implementation_coverage_gaps(snapshot)


def test_one_supported_profile_satisfies_the_logical_coverage_slot() -> None:
    absent = SlotIdentity(_KEY, None)
    supported = SlotIdentity(replace(_KEY, profile="skylake"), _REALIZATION)
    snapshot = Snapshot(
        backend_profiles=(("cpp", ("avx2", "skylake")),),
        types=("si32",),
        slots={
            absent: SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.ABSENT,
                "TSL-SELECT-NO-CANDIDATE",
                None,
            ),
            supported: SlotRecord(
                ImplementationSlotClass.COMPOSED,
                TargetSupportStatus.EMITTED,
                None,
                ImplementationState.COMPOSED.value,
            ),
        },
        parity_extensions=("avx2",),
    )

    assert not implementation_coverage_gaps(snapshot)


def test_new_unsupported_primitive_slot_is_additive_not_a_regression() -> None:
    baseline = _snapshot(ImplementationSlotClass.NATIVE)
    unsupported_key = replace(_KEY, primitive="new_primitive")
    current = replace(
        baseline,
        slots={
            **baseline.slots,
            SlotIdentity(unsupported_key, None): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.ABSENT,
                "TSL-SELECT-NO-CANDIDATE",
                None,
            ),
        },
    )

    diff = diff_snapshots(baseline, current)

    assert not diff.regressions
    assert [change.kind for change in diff.changes] == ["added"]


def test_lost_supported_realization_is_a_regression() -> None:
    baseline = _snapshot(ImplementationSlotClass.NATIVE)
    current = replace(baseline, slots={})

    regressions = diff_snapshots(baseline, current).regressions

    assert len(regressions) == 1
    assert regressions[0].detail == "expected slot disappeared"


def test_supported_slot_gaining_unsupported_realization_is_a_regression() -> None:
    baseline = _snapshot(ImplementationSlotClass.NATIVE)
    unsupported_realization = replace(
        _REALIZATION,
        required_compiler_capabilities=("new_capability",),
    )
    current = replace(
        baseline,
        slots={
            **baseline.slots,
            SlotIdentity(_KEY, unsupported_realization): SlotRecord(
                ImplementationSlotClass.UNSUPPORTED,
                TargetSupportStatus.EMITTED,
                UNCLASSIFIED_IMPLEMENTATION_REASON,
                ImplementationState.UNKNOWN.value,
            ),
        },
    )

    regressions = diff_snapshots(baseline, current).regressions

    assert len(regressions) == 1
    assert regressions[0].detail == (
        "supported slot gained an unsupported realization"
    )


def test_serialization_groups_profiles_but_round_trips_exact_slots() -> None:
    avx2 = _snapshot(ImplementationSlotClass.NATIVE)
    skylake_identity = SlotIdentity(replace(_KEY, profile="skylake"), _REALIZATION)
    snapshot = Snapshot(
        backend_profiles=(("cpp", ("avx2", "skylake")),),
        types=("si32",),
        slots={
            **avx2.slots,
            skylake_identity: next(iter(avx2.slots.values())),
        },
    )

    text = serialize(snapshot)

    assert text.count('"classification"') == 1
    assert deserialize(text) == snapshot
    assert serialize(snapshot) == text


def test_additive_backend_and_profile_need_no_classifier_branch() -> None:
    third_key = replace(_KEY, profile="third-profile", backend="third")
    entry = _entry(
        ImplementationState.COMPOSED,
        key=third_key,
        realization=replace(_REALIZATION, source_extension="third"),
    )

    snapshot = classify_entries(
        (entry,),
        backend_profiles=(("third", ("third-profile",)),),
        types=("si32",),
    )

    assert next(iter(snapshot.slots.values())).classification is (
        ImplementationSlotClass.COMPOSED
    )
    assert deserialize(serialize(snapshot)) == snapshot


def test_projection_agrees_with_real_final_pipeline_states(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=("add",),
        profiles=("avx2",),
        type_tags=("si32",),
        extensions=("avx2",),
        backends=("cpp",),
        render_artifacts=False,
        collect_target_support=True,
    )
    assert result.target_support is not None
    entries = tuple(
        entry
        for entry in result.target_support.entries
        if entry.key.primitive == "add"
    )

    snapshot = classify_entries(
        entries,
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
    )

    assert set(snapshot.slots) == {
        SlotIdentity(entry.key, entry.realization) for entry in entries
    }
    assert {
        record.classification for record in snapshot.slots.values()
    } == {ImplementationSlotClass.NATIVE, ImplementationSlotClass.COMPOSED}


def _snapshot(classification: ImplementationSlotClass) -> Snapshot:
    state = {
        ImplementationSlotClass.NATIVE: ImplementationState.NATIVE.value,
        ImplementationSlotClass.COMPOSED: ImplementationState.COMPOSED.value,
        ImplementationSlotClass.GENERIC_FALLBACK: ImplementationState.FALLBACK.value,
        ImplementationSlotClass.UNSUPPORTED: ImplementationState.UNKNOWN.value,
    }[classification]
    return Snapshot(
        backend_profiles=(("cpp", ("avx2",)),),
        types=("si32",),
        slots={
            SlotIdentity(_KEY, _REALIZATION): SlotRecord(
                classification,
                TargetSupportStatus.EMITTED,
                (
                    UNCLASSIFIED_IMPLEMENTATION_REASON
                    if classification is ImplementationSlotClass.UNSUPPORTED
                    else None
                ),
                state,
            )
        },
    )
