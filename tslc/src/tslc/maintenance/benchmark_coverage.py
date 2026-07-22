#!/usr/bin/env python3
"""Audit backend-scoped implementation-variant benchmark coverage.

The audit tracks whether each selected implementation variant survives lowering
and dependency closure, receives correctness facts and a typed workload scenario,
and reaches an emitted candidate set. Newly introduced issue identities fail
against a backend-local committed baseline; known gaps can be closed
incrementally. Default-only shapes remain explicitly outside this gate and are
inventoried as not applicable.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.authoring import check_catalog
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_policy_consumption import (
    RustPolicyCoveragePlan,
    plan_rust_policy_coverage,
)
from tslc.backend.rust_policy_selection import plan_rust_policy_selection
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
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.maintenance.benchmark_inventory import (
    BenchmarkShapeInventoryEntry,
    BenchmarkSpecialCaseInventoryEntry,
    SourceShapeKey,
    build_shape_inventory,
    build_special_case_inventory,
    has_variants,
    render_benchmark_shape_inventory,
    shape_label,
    source_shape,
)
from tslc.maintenance import _repo_context
from tslc.maintenance.rust_benchmark_evidence import (
    RustBenchmarkEvidence,
    build_rust_benchmark_evidence,
    deserialize_rust_benchmark_evidence,
)
from tslc.pipeline import CoverageEntry, SkippedEntry

_BASELINE_VERSION = 1
_RUST_BASELINE_VERSION = 1
_EVIDENCE_BACKENDS = ("cpp", "rust")

BenchmarkIssueKind = Literal[
    "coverage-gap",
    "inactive-authored-shape",
    "selected-slot-skipped",
    "selected-slot-missing-planner",
    "emitted-without-candidates",
    "candidate-without-coverage",
    "planner-slot-without-selection",
    "policy-supported-without-report",
]
_CPP_ISSUE_KINDS = frozenset(
    (
        "coverage-gap",
        "inactive-authored-shape",
        "selected-slot-skipped",
        "selected-slot-missing-planner",
        "emitted-without-candidates",
        "candidate-without-coverage",
    )
)
_RUST_ISSUE_KINDS = _CPP_ISSUE_KINDS | {
    "planner-slot-without-selection",
    "policy-supported-without-report",
}


@dataclass(frozen=True, slots=True)
class BenchmarkSlotKey:
    """One selected variant slot that must reach an emitted candidate set."""

    backend_id: str
    profile_name: str
    source_shape: SourceShapeKey
    extension_name: str
    type_tag: str
    axis: tuple[tuple[str, str], ...]
    variant_names: tuple[str, ...]
    primitive_name: str | None = None
    membership: int | None = None
    specialization_hash: str | None = None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.backend_id,
            self.profile_name,
            *self.source_shape.sort_key(),
            self.extension_name,
            self.type_tag,
            self.axis,
            self.variant_names,
            self.primitive_name or "",
            -1 if self.membership is None else self.membership,
            self.specialization_hash or "",
        )


@dataclass(frozen=True, slots=True)
class BenchmarkCoverageIssue:
    kind: BenchmarkIssueKind
    detail: str
    source_shape: SourceShapeKey
    slot: BenchmarkSlotKey | None = None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.kind,
            self.source_shape.sort_key(),
            () if self.slot is None else self.slot.sort_key(),
            self.detail,
        )


@dataclass(frozen=True, slots=True)
class _SelectedBenchmarkSlot:
    slot: BenchmarkSlotKey
    slot_hash: str


@dataclass(frozen=True, slots=True)
class BenchmarkIssueKey:
    """Stable issue identity; explanatory reason text is intentionally excluded."""

    kind: BenchmarkIssueKind
    source_shape: SourceShapeKey
    slot: BenchmarkSlotKey | None = None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.kind,
            self.source_shape.sort_key(),
            () if self.slot is None else self.slot.sort_key(),
        )

    @classmethod
    def from_issue(cls, issue: BenchmarkCoverageIssue) -> BenchmarkIssueKey:
        return cls(issue.kind, issue.source_shape, issue.slot)


@dataclass(frozen=True, slots=True)
class BenchmarkIssueBaseline:
    issues: tuple[BenchmarkIssueKey, ...]


@dataclass(frozen=True, slots=True)
class RustBenchmarkCoverageBaseline:
    """Exact Rust gap, profile, report-candidate, and policy evidence."""

    issues: tuple[BenchmarkIssueKey, ...]
    evidence: RustBenchmarkEvidence


@dataclass(frozen=True, slots=True)
class BenchmarkIssueDiff:
    new_issues: tuple[BenchmarkCoverageIssue, ...]
    resolved_issues: tuple[BenchmarkIssueKey, ...]


@dataclass(frozen=True, slots=True)
class RustBenchmarkCoverageDiff:
    issue_diff: BenchmarkIssueDiff
    evidence_changed: bool


@dataclass(frozen=True, slots=True)
class BenchmarkCoverageAudit:
    backend_id: str
    profiles: tuple[str, ...]
    selected_slots: int
    candidate_sets: int
    issues: tuple[BenchmarkCoverageIssue, ...]
    shapes: tuple[BenchmarkShapeInventoryEntry, ...]
    special_cases: tuple[BenchmarkSpecialCaseInventoryEntry, ...]
    policy_supported_reports: int = 0
    policy_report_only_reports: int = 0
    rust_evidence: RustBenchmarkEvidence | None = None

    @property
    def complete(self) -> bool:
        return not self.issues


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


def _load_catalog(
    sources: Path,
    backend_id: str = "cpp",
) -> tuple[Catalog | None, tuple[str, ...]]:
    """Load and validate the corpus through the authoring boundary.

    Validation is scoped to the same backend as the generation call.
    """

    checked = check_catalog((sources,), backends=(backend_id,))
    errors = tuple(
        format_diagnostic(diagnostic)
        for diagnostic in checked.diagnostics
        if diagnostic.severity == "error"
    )
    return checked.catalog, errors


def compute_benchmark_coverage_audit(
    *,
    sources: Path,
    machine_profiles: Path,
    profiles: tuple[str, ...] | None,
    types: tuple[str, ...],
    backend_id: str = "cpp",
) -> tuple[BenchmarkCoverageAudit | None, tuple[str, ...]]:
    catalog, catalog_errors = _load_catalog(sources, backend_id)
    if catalog is None or catalog_errors:
        return None, catalog_errors or ("catalog promotion failed",)
    result = generate_project(
        [sources],
        machine_profiles_path=machine_profiles,
        profiles=profiles,
        type_tags=types,
        backends=(backend_id,),
        test_harness=True,
    )
    if has_errors(result.diagnostics) or result.rendered is None:
        errors = tuple(
            format_diagnostic(diagnostic)
            for diagnostic in result.diagnostics
            if diagnostic.severity == "error"
        )
        return None, errors or ("generation produced no rendered project",)
    rust_policy_coverage: RustPolicyCoveragePlan | None = None
    if backend_id == "rust":
        try:
            rust_policy_coverage = plan_rust_policy_coverage(
                result.rendered.benchmarks,
                plan_rust_policy_selection(result.emitted_profiles),
            )
        except ValueError as exc:
            return None, (f"Rust policy coverage planning failed: {exc}",)
    try:
        audit = audit_benchmark_coverage(
            catalog,
            result.rendered.benchmarks,
            backend_id=backend_id,
            selection_coverage=result.coverage,
            selection_skips=result.skipped,
            emitted_profiles=(
                result.emitted_profiles if backend_id == "rust" else None
            ),
            rust_policy_coverage=rust_policy_coverage,
        )
    except ValueError as exc:
        return None, (f"benchmark coverage audit failed: {exc}",)
    return audit, ()


def benchmark_issue_baseline(
    issues: tuple[BenchmarkCoverageIssue, ...],
) -> BenchmarkIssueBaseline:
    """Collapse current issues to their stable, reason-independent identities."""

    keys = {BenchmarkIssueKey.from_issue(issue) for issue in issues}
    return BenchmarkIssueBaseline(tuple(sorted(keys, key=BenchmarkIssueKey.sort_key)))


def diff_benchmark_issues(
    baseline: BenchmarkIssueBaseline,
    current: tuple[BenchmarkCoverageIssue, ...],
) -> BenchmarkIssueDiff:
    """Report newly introduced and resolved strict issue identities."""

    baseline_keys = frozenset(baseline.issues)
    current_by_key = {
        BenchmarkIssueKey.from_issue(issue): issue for issue in current
    }
    new_issues = tuple(
        sorted(
            (
                issue
                for key, issue in current_by_key.items()
                if key not in baseline_keys
            ),
            key=BenchmarkCoverageIssue.sort_key,
        )
    )
    resolved_issues = tuple(
        sorted(
            baseline_keys - current_by_key.keys(),
            key=BenchmarkIssueKey.sort_key,
        )
    )
    return BenchmarkIssueDiff(new_issues, resolved_issues)


def rust_benchmark_coverage_baseline(
    audit: BenchmarkCoverageAudit,
) -> RustBenchmarkCoverageBaseline:
    """Freeze exact Rust issue and successful report/policy evidence."""

    if audit.backend_id != "rust" or audit.rust_evidence is None:
        raise ValueError("Rust benchmark baselines require a Rust coverage audit")
    issues = benchmark_issue_baseline(audit.issues).issues
    return RustBenchmarkCoverageBaseline(issues, audit.rust_evidence)


def diff_rust_benchmark_coverage(
    baseline: RustBenchmarkCoverageBaseline,
    audit: BenchmarkCoverageAudit,
) -> RustBenchmarkCoverageDiff:
    """Reject new gaps and any drift in exact successful Rust evidence."""

    current = rust_benchmark_coverage_baseline(audit)
    return RustBenchmarkCoverageDiff(
        issue_diff=diff_benchmark_issues(
            BenchmarkIssueBaseline(baseline.issues), audit.issues
        ),
        evidence_changed=baseline.evidence != current.evidence,
    )


def serialize_issue_baseline(baseline: BenchmarkIssueBaseline) -> str:
    """Render one compact JSON record per stable issue for reviewable diffs."""

    records = [
        json.dumps(_issue_key_record(issue), separators=(",", ":"))
        for issue in sorted(baseline.issues, key=BenchmarkIssueKey.sort_key)
    ]
    lines = ["{", f'  "version": {_BASELINE_VERSION},', '  "issues": [']
    for index, record in enumerate(records):
        comma = "," if index + 1 < len(records) else ""
        lines.append(f"    {record}{comma}")
    lines.extend(("  ]", "}"))
    return "\n".join(lines) + "\n"


def serialize_rust_benchmark_baseline(
    baseline: RustBenchmarkCoverageBaseline,
) -> str:
    """Render Rust issues and exact report/policy facts as line-diffable JSON."""

    sections: tuple[tuple[str, list[list[object]]], ...] = (
        (
            "issues",
            [
                _rust_issue_key_record(issue)
                for issue in sorted(
                    baseline.issues, key=BenchmarkIssueKey.sort_key
                )
            ],
        ),
        (
            "profiles",
            [
                cast(list[object], profile.record())
                for profile in baseline.evidence.profiles
            ],
        ),
        (
            "candidates",
            [candidate.record() for candidate in baseline.evidence.candidates],
        ),
        (
            "policies",
            [policy.record() for policy in baseline.evidence.policies],
        ),
    )
    lines = [
        "{",
        f'  "version": {_RUST_BASELINE_VERSION},',
        '  "backend": "rust",',
    ]
    for section_index, (name, records) in enumerate(sections):
        lines.append(f'  "{name}": [')
        for index, record in enumerate(records):
            comma = "," if index + 1 < len(records) else ""
            encoded = json.dumps(record, separators=(",", ":"))
            lines.append(f"    {encoded}{comma}")
        section_comma = "," if section_index + 1 < len(sections) else ""
        lines.append(f"  ]{section_comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def deserialize_issue_baseline(text: str) -> BenchmarkIssueBaseline:
    """Load and validate the deterministic benchmark issue baseline."""

    payload: Any = json.loads(text)
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload.get("version") != _BASELINE_VERSION
        or payload.get("backend") not in (None, "cpp")
    ):
        raise ValueError(
            f"expected benchmark baseline version {_BASELINE_VERSION}"
        )
    records = payload.get("issues")
    if not isinstance(records, list):
        raise ValueError("benchmark baseline issues must be a list")
    issues = tuple(
        _issue_key_from_record(
            record,
            expected_backend="cpp",
            allowed_kinds=_CPP_ISSUE_KINDS,
        )
        for record in records
    )
    if len(frozenset(issues)) != len(issues):
        raise ValueError("benchmark baseline contains duplicate issue identities")
    return BenchmarkIssueBaseline(
        tuple(sorted(issues, key=BenchmarkIssueKey.sort_key))
    )


def deserialize_rust_benchmark_baseline(
    text: str,
) -> RustBenchmarkCoverageBaseline:
    """Load and validate the backend-separated exact Rust baseline."""

    payload: Any = json.loads(text)
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload.get("version") != _RUST_BASELINE_VERSION
        or payload.get("backend") != "rust"
    ):
        raise ValueError(
            f"expected Rust benchmark baseline version {_RUST_BASELINE_VERSION}"
        )
    issue_records = payload.get("issues")
    if not isinstance(issue_records, list):
        raise ValueError("Rust benchmark baseline issues must be a list")
    issues = tuple(_rust_issue_key_from_record(record) for record in issue_records)
    if len(frozenset(issues)) != len(issues):
        raise ValueError("Rust benchmark baseline contains duplicate issue identities")
    evidence = deserialize_rust_benchmark_evidence(
        payload.get("profiles"),
        payload.get("candidates"),
        payload.get("policies"),
    )
    return RustBenchmarkCoverageBaseline(
        issues=tuple(sorted(issues, key=BenchmarkIssueKey.sort_key)),
        evidence=evidence,
    )


def _issue_key_record(issue: BenchmarkIssueKey) -> list[object]:
    shape = issue.source_shape
    shape_record: list[object] = [
        shape.primitive_name,
        shape.result_kind,
        list(shape.param_kinds),
        shape.mask_policy,
    ]
    slot = issue.slot
    slot_record: list[object] | None = None
    if slot is not None:
        slot_record = [
            slot.backend_id,
            slot.profile_name,
            slot.extension_name,
            slot.type_tag,
            [list(pair) for pair in slot.axis],
            list(slot.variant_names),
        ]
    return [issue.kind, shape_record, slot_record]


def _rust_issue_key_record(issue: BenchmarkIssueKey) -> list[object]:
    record = _issue_key_record(issue)
    slot_record = record[2]
    if isinstance(slot_record, list) and issue.slot is not None:
        slot_record.extend(
            (
                issue.slot.primitive_name,
                issue.slot.membership,
                issue.slot.specialization_hash,
            )
        )
    return record


def _rust_issue_key_from_record(record: object) -> BenchmarkIssueKey:
    return _issue_key_from_record(
        record,
        rust=True,
        expected_backend="rust",
        allowed_kinds=_RUST_ISSUE_KINDS,
    )


def _issue_key_from_record(
    record: object,
    *,
    rust: bool = False,
    expected_backend: str,
    allowed_kinds: frozenset[str] | set[str],
) -> BenchmarkIssueKey:
    if not isinstance(record, list) or len(record) != 3:
        raise ValueError("benchmark issue record must contain kind, shape, and slot")
    kind_value, shape_value, slot_value = record
    if not isinstance(kind_value, str) or kind_value not in allowed_kinds:
        raise ValueError(f"unknown benchmark issue kind: {kind_value!r}")
    if not isinstance(shape_value, list) or len(shape_value) != 4:
        raise ValueError("benchmark issue shape must contain four fields")
    primitive_name, result_kind, param_kinds_value, mask_policy = shape_value
    if (
        not isinstance(primitive_name, str)
        or not isinstance(result_kind, str)
        or not isinstance(param_kinds_value, list)
        or not all(isinstance(value, str) for value in param_kinds_value)
        or (mask_policy is not None and not isinstance(mask_policy, str))
    ):
        raise ValueError("benchmark issue shape contains invalid field types")
    source_shape = SourceShapeKey(
        primitive_name,
        result_kind,
        tuple(cast(list[str], param_kinds_value)),
        mask_policy,
    )
    slot: BenchmarkSlotKey | None = None
    if slot_value is not None:
        expected_fields = 9 if rust else 6
        if not isinstance(slot_value, list) or len(slot_value) != expected_fields:
            raise ValueError(
                f"benchmark issue slot must contain {expected_fields} fields"
            )
        (
            backend_id,
            profile_name,
            extension_name,
            type_tag,
            axis_value,
            variants_value,
            *rust_values,
        ) = slot_value
        scalar_values = (backend_id, profile_name, extension_name, type_tag)
        if not all(isinstance(value, str) for value in scalar_values):
            raise ValueError("benchmark issue slot contains invalid scalar fields")
        if backend_id != expected_backend:
            raise ValueError(
                f"benchmark issue slot backend must be {expected_backend!r}"
            )
        if not isinstance(axis_value, list):
            raise ValueError("benchmark issue slot axis must be a list")
        axis: list[tuple[str, str]] = []
        for pair in axis_value:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(value, str) for value in pair)
            ):
                raise ValueError("benchmark issue slot contains an invalid axis")
            axis.append((cast(str, pair[0]), cast(str, pair[1])))
        if not isinstance(variants_value, list) or not all(
            isinstance(value, str) for value in variants_value
        ):
            raise ValueError("benchmark issue slot variants must be strings")
        membership: int | None = None
        specialization_hash: str | None = None
        slot_primitive_name: str | None = None
        if rust:
            (
                primitive_name_value,
                membership_value,
                specialization_hash_value,
            ) = rust_values
            if not isinstance(primitive_name_value, str) or not primitive_name_value:
                raise ValueError(
                    "Rust benchmark issue primitive name must be a non-empty string"
                )
            if membership_value is not None and (
                type(membership_value) is not int or membership_value < 0
            ):
                raise ValueError(
                    "Rust benchmark issue membership must be a non-negative integer"
                )
            if specialization_hash_value is not None and not is_sha256_digest(
                specialization_hash_value
            ):
                raise ValueError(
                    "Rust benchmark issue specialization hash must be a "
                    "canonical SHA-256 digest"
                )
            membership = membership_value
            specialization_hash = specialization_hash_value
            slot_primitive_name = primitive_name_value
        slot = BenchmarkSlotKey(
            backend_id=cast(str, backend_id),
            profile_name=cast(str, profile_name),
            source_shape=source_shape,
            extension_name=cast(str, extension_name),
            type_tag=cast(str, type_tag),
            axis=tuple(axis),
            variant_names=tuple(cast(list[str], variants_value)),
            primitive_name=slot_primitive_name,
            membership=membership,
            specialization_hash=specialization_hash,
        )
    return BenchmarkIssueKey(
        cast(BenchmarkIssueKind, kind_value), source_shape, slot
    )


def _format_issue(issue: BenchmarkCoverageIssue) -> str:
    where = ""
    if issue.slot is not None:
        where = (
            f" [{issue.slot.profile_name}/{issue.slot.backend_id} "
            f"{issue.slot.extension_name}/{issue.slot.type_tag}]"
        )
    return (
        f"{issue.kind}: {shape_label(issue.source_shape)}{where}: "
        f"{issue.detail}"
    )


def _split(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc-benchmark-coverage",
        description=(
            "Reject new benchmark coverage issues for selected "
            "implementation variants."
        ),
    )
    parser.add_argument(
        "--backend",
        default="cpp",
        choices=_EVIDENCE_BACKENDS,
        help="backend-scoped evidence to audit (default: cpp)",
    )
    parser.add_argument(
        "--inventory",
        default=None,
        help="tracked shape inventory path (default: the backend's checkout "
        "evidence path)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="baseline path (default: the backend's checkout evidence path)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the deterministic issue baseline and shape inventory",
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="corpus root (default: the checkout's tsldata/)",
    )
    parser.add_argument(
        "--machine-profiles",
        default=None,
        help="machine profile catalog (default: the checkout's "
        "supplementary/buildsystem/machine_profiles.json)",
    )
    parser.add_argument(
        "--profiles",
        default="",
        help="comma-separated profile subset; empty means every loaded profile",
    )
    parser.add_argument("--types", default=",".join(_ARITH_TYPE_TAGS))
    args = parser.parse_args(argv)

    sources, machine_profiles = _repo_context.resolve_corpus_paths(
        parser, args.sources, args.machine_profiles
    )
    if args.inventory is not None and args.baseline is not None:
        inventory_path = Path(args.inventory)
        baseline_path = Path(args.baseline)
    else:
        context = _repo_context.require_repo_context(parser)
        inventory_name, baseline_name = _default_evidence_names(args.backend)
        inventory_path = (
            Path(args.inventory)
            if args.inventory is not None
            else context.coverage_root / inventory_name
        )
        baseline_path = (
            Path(args.baseline)
            if args.baseline is not None
            else context.coverage_root / baseline_name
        )

    audit, errors = compute_benchmark_coverage_audit(
        sources=sources,
        machine_profiles=machine_profiles,
        profiles=_split(args.profiles) or None,
        types=_split(args.types),
        backend_id=args.backend,
    )
    if audit is None:
        print("benchmark coverage: generation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 2
    rendered = render_benchmark_shape_inventory(audit)
    update_command = _benchmark_update_command(args.backend)
    if args.update:
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(rendered, encoding="utf-8")
        baseline_text = (
            serialize_issue_baseline(benchmark_issue_baseline(audit.issues))
            if args.backend == "cpp"
            else serialize_rust_benchmark_baseline(
                rust_benchmark_coverage_baseline(audit)
            )
        )
        baseline_path.write_text(baseline_text, encoding="utf-8")
        print(
            f"benchmark coverage: {audit.selected_slots} selected slots, "
            f"{audit.candidate_sets} candidate sets, "
            f"{len(audit.issues)} known issues"
        )
        print(f"wrote inventory {inventory_path}")
        print(f"wrote baseline {baseline_path}")
        return 0
    if not baseline_path.exists():
        print(
            "benchmark coverage: committed issue baseline is missing; "
            f"run '{update_command}'",
            file=sys.stderr,
        )
        return 1
    try:
        baseline_text = baseline_path.read_text(encoding="utf-8")
        baseline = (
            deserialize_issue_baseline(baseline_text)
            if args.backend == "cpp"
            else deserialize_rust_benchmark_baseline(baseline_text)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"benchmark coverage: invalid issue baseline {baseline_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    if isinstance(baseline, RustBenchmarkCoverageBaseline):
        rust_diff = diff_rust_benchmark_coverage(baseline, audit)
        diff = rust_diff.issue_diff
        evidence_changed = rust_diff.evidence_changed
        baseline_issue_count = len(baseline.issues)
    else:
        diff = diff_benchmark_issues(baseline, audit.issues)
        evidence_changed = False
        baseline_issue_count = len(baseline.issues)
    if diff.new_issues:
        print(
            f"benchmark coverage: {len(diff.new_issues)} new issue(s) across "
            f"{audit.selected_slots} selected variant slots "
            f"({len(audit.issues)} current, {baseline_issue_count} baselined)",
            file=sys.stderr,
        )
        for issue in diff.new_issues:
            print(f"  {_format_issue(issue)}", file=sys.stderr)
        return 1
    if evidence_changed:
        print(
            "benchmark coverage: exact Rust profile/report/policy evidence is "
            f"stale; run '{update_command}'",
            file=sys.stderr,
        )
        return 1
    if (
        not inventory_path.exists()
        or inventory_path.read_text(encoding="utf-8") != rendered
    ):
        print(
            "benchmark coverage: committed shape inventory is missing or stale; "
            f"run '{update_command}'",
            file=sys.stderr,
        )
        return 1
    print(
        f"benchmark coverage: {audit.selected_slots} selected slots, "
        f"{audit.candidate_sets} candidate sets, {len(audit.issues)} known issues, "
        f"{len(diff.resolved_issues)} resolved since baseline; evidence current"
    )
    return 0


def _default_evidence_names(backend_id: str) -> tuple[str, str]:
    if backend_id == "cpp":
        return "benchmark-shape-inventory.md", "benchmark-baseline.json"
    return (
        f"benchmark-{backend_id}-shape-inventory.md",
        f"benchmark-{backend_id}-baseline.json",
    )


def _benchmark_update_command(backend_id: str) -> str:
    if backend_id == "cpp":
        return "./dev.sh benchmark-ratchet --update"
    return f"./dev.sh benchmark-ratchet --backend {backend_id} --update"


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "BenchmarkCoverageAudit",
    "BenchmarkCoverageIssue",
    "BenchmarkIssueBaseline",
    "BenchmarkIssueDiff",
    "BenchmarkIssueKey",
    "BenchmarkSlotKey",
    "RustBenchmarkCoverageBaseline",
    "RustBenchmarkCoverageDiff",
    "audit_benchmark_coverage",
    "benchmark_issue_baseline",
    "compute_benchmark_coverage_audit",
    "deserialize_issue_baseline",
    "deserialize_rust_benchmark_baseline",
    "diff_benchmark_issues",
    "diff_rust_benchmark_coverage",
    "rust_benchmark_coverage_baseline",
    "serialize_issue_baseline",
    "serialize_rust_benchmark_baseline",
)
