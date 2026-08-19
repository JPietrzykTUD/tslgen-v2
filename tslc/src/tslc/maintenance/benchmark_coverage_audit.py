"""Core backend-scoped implementation-variant benchmark coverage audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_policy_consumption import RustPolicyCoveragePlan
from tslc.benchmark.identity import (
    benchmark_slot_identity_hash,
    is_sha256_digest,
    specialization_identity_hash,
)
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkCoverageEntry,
    BenchmarkProjectPlan,
)
from tslc.catalog.model import Catalog
from tslc.maintenance.benchmark_coverage_model import (
    BenchmarkCoverageAudit,
    BenchmarkCoverageIssue,
    BenchmarkSlotKey,
    SelectedBenchmarkSlot as _SelectedBenchmarkSlot,
)
from tslc.maintenance.benchmark_inventory import (
    SourceShapeKey,
    build_shape_inventory,
    build_special_case_inventory,
    has_variants,
    source_shape,
)
from tslc.maintenance.rust_benchmark_evidence import (
    RustBenchmarkEvidence,
    build_rust_benchmark_evidence,
)
from tslc.pipeline import CoverageEntry, SkippedEntry


def audit_benchmark_coverage(
    catalog: Catalog,
    plan: BenchmarkProjectPlan,
    *,
    backend_id: str = "cpp",
    primitive_names: tuple[str, ...] | None = None,
    selection_coverage: tuple[CoverageEntry, ...] | None = None,
    selection_skips: tuple[SkippedEntry, ...] | None = None,
    emitted_profiles: tuple[EmittedProfile, ...] | None = None,
    rust_policy_coverage: RustPolicyCoveragePlan | None = None,
) -> BenchmarkCoverageAudit:
    """Join authored shapes, selected coverage, and emitted candidate sets.

    ``primitive_names`` only narrows focused tests and local diagnostics; the
    maintenance CLI deliberately leaves it unset and audits the full corpus.
    """

    if not backend_id:
        raise ValueError("benchmark coverage audits require a backend ID")
    if backend_id == "rust" and rust_policy_coverage is None:
        raise ValueError("Rust benchmark coverage requires typed policy evidence")
    if backend_id == "rust" and emitted_profiles is None:
        raise ValueError("Rust benchmark coverage requires emitted profile evidence")
    if backend_id != "rust" and rust_policy_coverage is not None:
        raise ValueError("Rust policy evidence cannot be joined to another backend")

    scope = None if primitive_names is None else frozenset(primitive_names)
    primitives = tuple(
        primitive
        for primitive in catalog.primitives
        if scope is None or primitive.name in scope
    )
    authored_shapes = {
        source_shape(primitive)
        for primitive in primitives
        if has_variants(primitive)
    }
    planner_coverage = tuple(
        entry
        for entry in plan.coverage
        if entry.backend_id == backend_id
        and (scope is None or entry.source_primitive_name in scope)
    )
    candidate_sets = tuple(
        candidate_set
        for profile in plan.profiles_for(backend_id)
        for candidate_set in profile.candidate_sets
        if scope is None
        or candidate_set.specialization.source_primitive_name in scope
    )
    selected_coverage = _selected_variant_coverage(
        selection_coverage, scope, backend_id
    )
    selected_skips = _selected_variant_skips(selection_skips, scope, backend_id)
    exact_selected_slots = (
        _emitted_variant_slots(emitted_profiles, backend_id, scope)
        if backend_id == "rust" and emitted_profiles is not None
        else ()
    )

    issues = _coverage_issues(
        backend_id=backend_id,
        authored_shapes=authored_shapes,
        planner_coverage=planner_coverage,
        candidate_sets=candidate_sets,
        selected_coverage=selected_coverage,
        selected_skips=selected_skips,
        exact_selected_slots=exact_selected_slots,
        use_selection_facts=(
            selection_coverage is not None or selection_skips is not None
        ),
    )
    if rust_policy_coverage is not None:
        issues = tuple(
            sorted(
                (*issues, *(_policy_coverage_issues(rust_policy_coverage, scope))),
                key=BenchmarkCoverageIssue.sort_key,
            )
        )
    selected_by_shape: dict[SourceShapeKey, int] = defaultdict(int)
    candidates_by_shape: dict[SourceShapeKey, int] = defaultdict(int)
    if backend_id == "rust":
        selected_slot_count = len(exact_selected_slots) + len(selected_skips)
        for selected_slot in exact_selected_slots:
            selected_by_shape[selected_slot.slot.source_shape] += 1
        for skipped_entry in selected_skips:
            selected_by_shape[_selection_shape(skipped_entry)] += 1
    else:
        selected_entries: tuple[
            BenchmarkCoverageEntry | CoverageEntry | SkippedEntry,
            ...,
        ]
        if selection_coverage is not None or selection_skips is not None:
            selected_entries = (*selected_coverage, *selected_skips)
        else:
            selected_entries = planner_coverage
        selected_slot_count = len(selected_entries)
        for selected_entry in selected_entries:
            shape = (
                _coverage_shape(selected_entry)
                if isinstance(selected_entry, BenchmarkCoverageEntry)
                else _selection_shape(selected_entry)
            )
            selected_by_shape[shape] += 1
    for candidate_set in candidate_sets:
        candidates_by_shape[_candidate_shape(candidate_set)] += 1
    issue_shapes = {issue.source_shape for issue in issues}

    policy_supported_by_shape: dict[SourceShapeKey, int] = defaultdict(int)
    policy_report_only_by_shape: dict[SourceShapeKey, int] = defaultdict(int)
    rust_evidence: RustBenchmarkEvidence | None = None
    if rust_policy_coverage is not None:
        candidates_by_key = {
            candidate_set.key: candidate_set for candidate_set in candidate_sets
        }
        for profile in rust_policy_coverage.profiles:
            for decision in profile.decisions:
                matching_candidate = candidates_by_key.get(decision.key)
                if matching_candidate is None:
                    continue
                shape = _candidate_shape(matching_candidate)
                if decision.status == "supported":
                    policy_supported_by_shape[shape] += 1
                else:
                    policy_report_only_by_shape[shape] += 1
        rust_evidence = build_rust_benchmark_evidence(plan, rust_policy_coverage)

    return BenchmarkCoverageAudit(
        backend_id=backend_id,
        profiles=tuple(
            sorted(
                profile.profile_name for profile in plan.profiles_for(backend_id)
            )
        ),
        selected_slots=selected_slot_count,
        candidate_sets=len(candidate_sets),
        issues=issues,
        shapes=build_shape_inventory(
            primitives,
            selected_by_shape,
            candidates_by_shape,
            issue_shapes,
            policy_supported_by_shape=policy_supported_by_shape,
            policy_report_only_by_shape=policy_report_only_by_shape,
        ),
        special_cases=build_special_case_inventory(
            catalog,
            primitives,
            selected_by_shape,
            candidates_by_shape,
            issue_shapes,
            backend_id=backend_id,
        ),
        policy_supported_reports=sum(policy_supported_by_shape.values()),
        policy_report_only_reports=sum(policy_report_only_by_shape.values()),
        rust_evidence=rust_evidence,
    )


def _coverage_issues(
    *,
    backend_id: str,
    authored_shapes: set[SourceShapeKey],
    planner_coverage: tuple[BenchmarkCoverageEntry, ...],
    candidate_sets: tuple[BenchmarkCandidateSet, ...],
    selected_coverage: tuple[CoverageEntry, ...],
    selected_skips: tuple[SkippedEntry, ...],
    exact_selected_slots: tuple[_SelectedBenchmarkSlot, ...],
    use_selection_facts: bool,
) -> tuple[BenchmarkCoverageIssue, ...]:
    if backend_id == "cpp":
        return _cpp_coverage_issues(
            authored_shapes=authored_shapes,
            planner_coverage=planner_coverage,
            candidate_sets=candidate_sets,
            selected_coverage=selected_coverage,
            selected_skips=selected_skips,
            use_selection_facts=use_selection_facts,
        )
    return _exact_coverage_issues(
        backend_id=backend_id,
        authored_shapes=authored_shapes,
        planner_coverage=planner_coverage,
        candidate_sets=candidate_sets,
        selected_skips=selected_skips,
        exact_selected_slots=exact_selected_slots,
    )


def _cpp_coverage_issues(
    *,
    authored_shapes: set[SourceShapeKey],
    planner_coverage: tuple[BenchmarkCoverageEntry, ...],
    candidate_sets: tuple[BenchmarkCandidateSet, ...],
    selected_coverage: tuple[CoverageEntry, ...],
    selected_skips: tuple[SkippedEntry, ...],
    use_selection_facts: bool,
) -> tuple[BenchmarkCoverageIssue, ...]:
    """Retain the original C++ issue membership and baseline identity."""

    coverage_slots = {_coverage_slot(entry): entry for entry in planner_coverage}
    candidate_slots: dict[BenchmarkSlotKey, int] = defaultdict(int)
    for candidate_set in candidate_sets:
        candidate_slots[_candidate_slot(candidate_set)] += 1
    issues: list[BenchmarkCoverageIssue] = []
    selected_shapes = (
        {
            *(_selection_shape(entry) for entry in selected_coverage),
            *(_selection_shape(entry) for entry in selected_skips),
        }
        if use_selection_facts
        else {_coverage_shape(entry) for entry in planner_coverage}
    )
    for shape in sorted(
        authored_shapes - selected_shapes,
        key=SourceShapeKey.sort_key,
    ):
        issues.append(
            BenchmarkCoverageIssue(
                kind="inactive-authored-shape",
                detail=(
                    "authored variants were not selected by any probed "
                    "C++ profile/type"
                ),
                source_shape=shape,
            )
        )
    for skipped_entry in selected_skips:
        slot = _selection_slot(skipped_entry)
        issues.append(
            BenchmarkCoverageIssue(
                kind="selected-slot-skipped",
                detail=f"{skipped_entry.status}: {skipped_entry.reason}",
                source_shape=slot.source_shape,
                slot=slot,
            )
        )
    for selected_entry in selected_coverage:
        slot = _selection_slot(selected_entry)
        if slot not in coverage_slots:
            issues.append(
                BenchmarkCoverageIssue(
                    kind="selected-slot-missing-planner",
                    detail=(
                        "lowered variant slot has no benchmark planner "
                        "coverage entry"
                    ),
                    source_shape=slot.source_shape,
                    slot=slot,
                )
            )
    for slot, planner_entry in coverage_slots.items():
        if planner_entry.status != "emitted":
            issues.append(
                BenchmarkCoverageIssue(
                    kind="coverage-gap",
                    detail=f"{planner_entry.status}: {planner_entry.reason}",
                    source_shape=slot.source_shape,
                    slot=slot,
                )
            )
        elif slot not in candidate_slots:
            issues.append(
                BenchmarkCoverageIssue(
                    kind="emitted-without-candidates",
                    detail=(
                        "coverage says emitted but no candidate set has this "
                        "slot identity"
                    ),
                    source_shape=slot.source_shape,
                    slot=slot,
                )
            )
    for slot in candidate_slots.keys() - coverage_slots.keys():
        issues.append(
            BenchmarkCoverageIssue(
                kind="candidate-without-coverage",
                detail="candidate set has no matching selected-slot coverage entry",
                source_shape=slot.source_shape,
                slot=slot,
            )
        )
    return tuple(sorted(issues, key=BenchmarkCoverageIssue.sort_key))


def _exact_coverage_issues(
    *,
    backend_id: str,
    authored_shapes: set[SourceShapeKey],
    planner_coverage: tuple[BenchmarkCoverageEntry, ...],
    candidate_sets: tuple[BenchmarkCandidateSet, ...],
    selected_skips: tuple[SkippedEntry, ...],
    exact_selected_slots: tuple[_SelectedBenchmarkSlot, ...],
) -> tuple[BenchmarkCoverageIssue, ...]:
    """Keep every non-C++ slot membership instead of collapsing equal keys."""

    planner_by_slot: dict[
        BenchmarkSlotKey, list[BenchmarkCoverageEntry]
    ] = defaultdict(list)
    candidates_by_slot: dict[
        BenchmarkSlotKey, list[BenchmarkCandidateSet]
    ] = defaultdict(list)
    selected_by_slot: dict[
        BenchmarkSlotKey, list[_SelectedBenchmarkSlot]
    ] = defaultdict(list)
    skipped_by_slot: dict[BenchmarkSlotKey, list[SkippedEntry]] = defaultdict(list)
    for planner_entry in planner_coverage:
        planner_by_slot[_coverage_slot(planner_entry)].append(planner_entry)
    for candidate_set in candidate_sets:
        candidates_by_slot[_candidate_slot(candidate_set)].append(candidate_set)
    for selected_slot in exact_selected_slots:
        selected_by_slot[selected_slot.slot].append(selected_slot)
    for skipped_entry in selected_skips:
        skipped_by_slot[_selection_slot(skipped_entry)].append(skipped_entry)

    selected_shapes = {
        *(selected.slot.source_shape for selected in exact_selected_slots),
        *(_selection_shape(entry) for entry in selected_skips),
    }
    issues: list[BenchmarkCoverageIssue] = []
    for shape in sorted(
        authored_shapes - selected_shapes,
        key=SourceShapeKey.sort_key,
    ):
        issues.append(
            BenchmarkCoverageIssue(
                kind="inactive-authored-shape",
                detail=(
                    "authored variants were not selected by any probed "
                    f"{backend_id} profile/type"
                ),
                source_shape=shape,
            )
        )

    for slot in sorted(skipped_by_slot, key=BenchmarkSlotKey.sort_key):
        for membership, skipped_entry in enumerate(skipped_by_slot[slot]):
            issue_slot = replace(slot, membership=membership)
            issues.append(
                BenchmarkCoverageIssue(
                    kind="selected-slot-skipped",
                    detail=f"{skipped_entry.status}: {skipped_entry.reason}",
                    source_shape=slot.source_shape,
                    slot=issue_slot,
                )
            )

    for slot in sorted(
        selected_by_slot.keys() | planner_by_slot.keys(),
        key=BenchmarkSlotKey.sort_key,
    ):
        selected_hashes = Counter(
            selected.slot_hash for selected in selected_by_slot.get(slot, ())
        )
        planner_hashes = Counter(
            entry.slot_hash for entry in planner_by_slot.get(slot, ())
        )
        if any(not is_sha256_digest(slot_hash) for slot_hash in planner_hashes):
            raise ValueError(
                f"{backend_id} benchmark coverage lacks exact slot identity"
            )
        for slot_hash, count in sorted((selected_hashes - planner_hashes).items()):
            for membership in range(count):
                issue_slot = replace(
                    slot,
                    membership=membership,
                    specialization_hash=slot_hash,
                )
                issues.append(
                    BenchmarkCoverageIssue(
                        kind="selected-slot-missing-planner",
                        detail=(
                            "emitted variant slot has no exact benchmark planner entry"
                        ),
                        source_shape=slot.source_shape,
                        slot=issue_slot,
                    )
                )
        for slot_hash, count in sorted((planner_hashes - selected_hashes).items()):
            for membership in range(count):
                issue_slot = replace(
                    slot,
                    membership=membership,
                    specialization_hash=slot_hash,
                )
                issues.append(
                    BenchmarkCoverageIssue(
                        kind="planner-slot-without-selection",
                        detail=(
                            "benchmark planner entry has no exact emitted variant slot"
                        ),
                        source_shape=slot.source_shape,
                        slot=issue_slot,
                    )
                )

    for slot in sorted(planner_by_slot, key=BenchmarkSlotKey.sort_key):
        candidate_hashes = {
            benchmark_slot_identity_hash(
                candidate_set.key.profile_name,
                candidate_set.specialization,
            )
            for candidate_set in candidates_by_slot.get(slot, ())
        }
        planner_memberships: dict[str, int] = defaultdict(int)
        for planner_entry in planner_by_slot[slot]:
            if not is_sha256_digest(planner_entry.slot_hash):
                raise ValueError(
                    f"{backend_id} benchmark coverage lacks exact slot identity"
                )
            membership = planner_memberships[planner_entry.slot_hash]
            planner_memberships[planner_entry.slot_hash] += 1
            issue_slot = replace(
                slot,
                membership=membership,
                specialization_hash=planner_entry.slot_hash,
            )
            if planner_entry.status != "emitted":
                issues.append(
                    BenchmarkCoverageIssue(
                        kind="coverage-gap",
                        detail=f"{planner_entry.status}: {planner_entry.reason}",
                        source_shape=slot.source_shape,
                        slot=issue_slot,
                    )
                )
                continue
            if planner_entry.slot_hash not in candidate_hashes:
                issues.append(
                    BenchmarkCoverageIssue(
                        kind="emitted-without-candidates",
                        detail=(
                            "coverage says emitted but no candidate set has this "
                            "slot membership"
                        ),
                        source_shape=slot.source_shape,
                        slot=issue_slot,
                    )
                )

    for slot in sorted(candidates_by_slot, key=BenchmarkSlotKey.sort_key):
        emitted_hashes = {
            entry.slot_hash
            for entry in planner_by_slot.get(slot, ())
            if entry.status == "emitted"
        }
        candidate_memberships: dict[str, int] = defaultdict(int)
        for candidate_set in candidates_by_slot[slot]:
            candidate_hash = benchmark_slot_identity_hash(
                candidate_set.key.profile_name,
                candidate_set.specialization,
            )
            membership = candidate_memberships[candidate_hash]
            candidate_memberships[candidate_hash] += 1
            if candidate_hash in emitted_hashes:
                continue
            issue_slot = replace(
                slot,
                membership=membership,
                specialization_hash=candidate_hash,
            )
            issues.append(
                BenchmarkCoverageIssue(
                    kind="candidate-without-coverage",
                    detail="candidate set has no matching selected-slot coverage entry",
                    source_shape=slot.source_shape,
                    slot=issue_slot,
                )
            )
    return tuple(sorted(issues, key=BenchmarkCoverageIssue.sort_key))


def _policy_coverage_issues(
    coverage: RustPolicyCoveragePlan,
    scope: frozenset[str] | None,
) -> tuple[BenchmarkCoverageIssue, ...]:
    issues: list[BenchmarkCoverageIssue] = []
    for gap in coverage.gaps:
        key = gap.key
        if scope is not None and key.source_primitive_name not in scope:
            continue
        shape = SourceShapeKey(
            primitive_name=key.source_primitive_name,
            result_kind=key.result_kind,
            param_kinds=key.param_kinds,
            mask_policy=None,
        )
        issues.append(
            BenchmarkCoverageIssue(
                kind="policy-supported-without-report",
                detail=gap.reason,
                source_shape=shape,
                slot=BenchmarkSlotKey(
                    backend_id=key.backend_id,
                    profile_name=key.profile_name,
                    source_shape=shape,
                    extension_name=key.extension_name,
                    type_tag=key.type_tag,
                    axis=key.axis,
                    variant_names=gap.candidate_ids[1:],
                    primitive_name=key.primitive_name,
                    specialization_hash=specialization_identity_hash(key),
                ),
            )
        )
    return tuple(sorted(issues, key=BenchmarkCoverageIssue.sort_key))


def _selected_variant_coverage(
    entries: tuple[CoverageEntry, ...] | None,
    scope: frozenset[str] | None,
    backend_id: str,
) -> tuple[CoverageEntry, ...]:
    return tuple(
        entry
        for entry in (() if entries is None else entries)
        if entry.backend == backend_id
        and entry.variant_names
        and (scope is None or entry.source_primitive_name in scope)
    )


def _selected_variant_skips(
    entries: tuple[SkippedEntry, ...] | None,
    scope: frozenset[str] | None,
    backend_id: str,
) -> tuple[SkippedEntry, ...]:
    return tuple(
        entry
        for entry in (() if entries is None else entries)
        if entry.backend == backend_id
        and entry.variant_names
        and (scope is None or entry.source_primitive_name in scope)
    )


def _emitted_variant_slots(
    profiles: tuple[EmittedProfile, ...],
    backend_id: str,
    scope: frozenset[str] | None,
) -> tuple[_SelectedBenchmarkSlot, ...]:
    """Project exact variant slots from finalized backend-emission facts."""

    slots: list[_SelectedBenchmarkSlot] = []
    for profile in profiles:
        for specializations in profile.specializations(backend_id).values():
            for specialization in specializations:
                if not specialization.variant_bodies or (
                    scope is not None
                    and specialization.source_primitive_name not in scope
                ):
                    continue
                shape = SourceShapeKey(
                    primitive_name=specialization.source_primitive_name,
                    result_kind=specialization.result_kind,
                    param_kinds=specialization.param_kinds,
                    mask_policy=specialization.mask_policy,
                )
                slot = BenchmarkSlotKey(
                    backend_id=backend_id,
                    profile_name=profile.profile.name,
                    source_shape=shape,
                    extension_name=specialization.extension_name,
                    type_tag=specialization.type_tag,
                    axis=specialization.axis,
                    variant_names=specialization.variant_names,
                    primitive_name=(
                        specialization.primitive_name
                        if backend_id != "cpp"
                        else None
                    ),
                )
                slots.append(
                    _SelectedBenchmarkSlot(
                        slot=slot,
                        slot_hash=benchmark_slot_identity_hash(
                            profile.profile.name,
                            specialization,
                        ),
                    )
                )
    return tuple(
        sorted(
            slots,
            key=lambda selected: (
                selected.slot.sort_key(),
                selected.slot_hash,
            ),
        )
    )


def _coverage_shape(entry: BenchmarkCoverageEntry) -> SourceShapeKey:
    return SourceShapeKey(
        primitive_name=entry.source_primitive_name,
        result_kind=entry.result_kind,
        param_kinds=entry.param_kinds,
        mask_policy=entry.mask_policy,
    )


def _candidate_shape(candidate_set: BenchmarkCandidateSet) -> SourceShapeKey:
    spec = candidate_set.specialization
    return SourceShapeKey(
        primitive_name=spec.source_primitive_name,
        result_kind=spec.result_kind,
        param_kinds=spec.param_kinds,
        mask_policy=spec.mask_policy,
    )


def _selection_shape(entry: CoverageEntry | SkippedEntry) -> SourceShapeKey:
    return SourceShapeKey(
        primitive_name=entry.source_primitive_name,
        result_kind=entry.result_kind,
        param_kinds=entry.param_kinds,
        mask_policy=entry.mask_policy,
    )


def _coverage_slot(entry: BenchmarkCoverageEntry) -> BenchmarkSlotKey:
    return BenchmarkSlotKey(
        backend_id=entry.backend_id,
        profile_name=entry.profile_name,
        source_shape=_coverage_shape(entry),
        extension_name=entry.extension_name,
        type_tag=entry.type_tag,
        axis=entry.axis,
        variant_names=entry.variant_names,
        primitive_name=(
            entry.primitive_name if entry.backend_id != "cpp" else None
        ),
    )


def _candidate_slot(candidate_set: BenchmarkCandidateSet) -> BenchmarkSlotKey:
    spec = candidate_set.specialization
    return BenchmarkSlotKey(
        backend_id=candidate_set.key.backend_id,
        profile_name=candidate_set.key.profile_name,
        source_shape=_candidate_shape(candidate_set),
        extension_name=spec.extension_name,
        type_tag=spec.type_tag,
        axis=spec.axis,
        variant_names=spec.variant_names,
        primitive_name=(
            spec.primitive_name if candidate_set.key.backend_id != "cpp" else None
        ),
    )


def _selection_slot(entry: CoverageEntry | SkippedEntry) -> BenchmarkSlotKey:
    return BenchmarkSlotKey(
        backend_id=entry.backend,
        profile_name=entry.profile,
        source_shape=_selection_shape(entry),
        extension_name=entry.extension,
        type_tag=entry.type_tag,
        axis=entry.axis,
        variant_names=entry.variant_names,
        primitive_name=(entry.primitive if entry.backend != "cpp" else None),
    )



__all__ = ("audit_benchmark_coverage",)
