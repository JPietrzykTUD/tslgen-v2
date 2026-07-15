#!/usr/bin/env python3
"""Audit full-corpus implementation-variant benchmark coverage.

The audit tracks whether each selected C++ implementation variant survives
lowering and dependency closure, receives correctness facts and a typed workload
scenario, and reaches an emitted candidate set. Newly introduced issue identities
fail against a committed baseline; known gaps can be closed incrementally.
Default-only shapes remain explicitly outside this gate and are inventoried as
not applicable.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkCoverageEntry,
    BenchmarkProjectPlan,
)
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_tsl_grammar
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
from tslc.maintenance.coverage_inventory import (
    _DATA_ROOT,
    _PROFILES_PATH,
    _REPO_ROOT,
)
from tslc.pipeline import CoverageEntry, SkippedEntry
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser

_INVENTORY = _REPO_ROOT / "coverage" / "benchmark-shape-inventory.md"
_BASELINE = _REPO_ROOT / "coverage" / "benchmark-baseline.json"
_BASELINE_VERSION = 1

BenchmarkIssueKind = Literal[
    "coverage-gap",
    "inactive-authored-shape",
    "selected-slot-skipped",
    "selected-slot-missing-planner",
    "emitted-without-candidates",
    "candidate-without-coverage",
]
_ISSUE_KINDS = frozenset(
    (
        "coverage-gap",
        "inactive-authored-shape",
        "selected-slot-skipped",
        "selected-slot-missing-planner",
        "emitted-without-candidates",
        "candidate-without-coverage",
    )
)


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

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.backend_id,
            self.profile_name,
            *self.source_shape.sort_key(),
            self.extension_name,
            self.type_tag,
            self.axis,
            self.variant_names,
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
class BenchmarkIssueDiff:
    new_issues: tuple[BenchmarkCoverageIssue, ...]
    resolved_issues: tuple[BenchmarkIssueKey, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkCoverageAudit:
    profiles: tuple[str, ...]
    selected_slots: int
    candidate_sets: int
    issues: tuple[BenchmarkCoverageIssue, ...]
    shapes: tuple[BenchmarkShapeInventoryEntry, ...]
    special_cases: tuple[BenchmarkSpecialCaseInventoryEntry, ...]

    @property
    def complete(self) -> bool:
        return not self.issues


def audit_benchmark_coverage(
    catalog: Catalog,
    plan: BenchmarkProjectPlan,
    *,
    primitive_names: tuple[str, ...] | None = None,
    selection_coverage: tuple[CoverageEntry, ...] | None = None,
    selection_skips: tuple[SkippedEntry, ...] | None = None,
) -> BenchmarkCoverageAudit:
    """Join authored shapes, selected coverage, and emitted candidate sets.

    ``primitive_names`` only narrows focused tests and local diagnostics; the
    maintenance CLI deliberately leaves it unset and audits the full corpus.
    """

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
        if scope is None or entry.source_primitive_name in scope
    )
    candidate_sets = tuple(
        candidate_set
        for profile in plan.profiles
        for candidate_set in profile.candidate_sets
        if scope is None
        or candidate_set.specialization.source_primitive_name in scope
    )
    selected_coverage = _selected_variant_coverage(selection_coverage, scope)
    selected_skips = _selected_variant_skips(selection_skips, scope)

    coverage_slots = {
        _coverage_slot(entry): entry for entry in planner_coverage
    }
    candidate_slots: dict[BenchmarkSlotKey, int] = defaultdict(int)
    for candidate_set in candidate_sets:
        candidate_slots[_candidate_slot(candidate_set)] += 1

    issues = _coverage_issues(
        authored_shapes=authored_shapes,
        planner_coverage=planner_coverage,
        coverage_slots=coverage_slots,
        candidate_slots=candidate_slots,
        selected_coverage=selected_coverage,
        selected_skips=selected_skips,
        use_selection_facts=(
            selection_coverage is not None or selection_skips is not None
        ),
    )
    selected_entries: tuple[
        BenchmarkCoverageEntry | CoverageEntry | SkippedEntry,
        ...,
    ]
    if selection_coverage is not None or selection_skips is not None:
        selected_entries = (*selected_coverage, *selected_skips)
    else:
        selected_entries = planner_coverage
    selected_by_shape: dict[SourceShapeKey, int] = defaultdict(int)
    candidates_by_shape: dict[SourceShapeKey, int] = defaultdict(int)
    for entry in selected_entries:
        shape = (
            _coverage_shape(entry)
            if isinstance(entry, BenchmarkCoverageEntry)
            else _selection_shape(entry)
        )
        selected_by_shape[shape] += 1
    for candidate_set in candidate_sets:
        candidates_by_shape[_candidate_shape(candidate_set)] += 1
    issue_shapes = {issue.source_shape for issue in issues}

    return BenchmarkCoverageAudit(
        profiles=tuple(sorted({profile.profile_name for profile in plan.profiles})),
        selected_slots=len(selected_entries),
        candidate_sets=len(candidate_sets),
        issues=issues,
        shapes=build_shape_inventory(
            primitives,
            selected_by_shape,
            candidates_by_shape,
            issue_shapes,
        ),
        special_cases=build_special_case_inventory(
            catalog,
            primitives,
            selected_by_shape,
            candidates_by_shape,
            issue_shapes,
        ),
    )


def _coverage_issues(
    *,
    authored_shapes: set[SourceShapeKey],
    planner_coverage: tuple[BenchmarkCoverageEntry, ...],
    coverage_slots: dict[BenchmarkSlotKey, BenchmarkCoverageEntry],
    candidate_slots: dict[BenchmarkSlotKey, int],
    selected_coverage: tuple[CoverageEntry, ...],
    selected_skips: tuple[SkippedEntry, ...],
    use_selection_facts: bool,
) -> tuple[BenchmarkCoverageIssue, ...]:
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


def _selected_variant_coverage(
    entries: tuple[CoverageEntry, ...] | None,
    scope: frozenset[str] | None,
) -> tuple[CoverageEntry, ...]:
    return tuple(
        entry
        for entry in (() if entries is None else entries)
        if entry.backend == "cpp"
        and entry.variant_names
        and (scope is None or entry.source_primitive_name in scope)
    )


def _selected_variant_skips(
    entries: tuple[SkippedEntry, ...] | None,
    scope: frozenset[str] | None,
) -> tuple[SkippedEntry, ...]:
    return tuple(
        entry
        for entry in (() if entries is None else entries)
        if entry.backend == "cpp"
        and entry.variant_names
        and (scope is None or entry.source_primitive_name in scope)
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
    )


def _load_catalog(sources: Path) -> tuple[Catalog | None, tuple[str, ...]]:
    parsed = TslParser(load_default_tsl_grammar()).parse(
        SourceLoader().load_dir(sources).documents
    )
    built = CatalogBuilder().build(parsed)
    errors = tuple(
        format_diagnostic(diagnostic)
        for diagnostic in built.diagnostics
        if diagnostic.severity == "error"
    )
    return built.catalog, errors


def compute_benchmark_coverage_audit(
    *,
    sources: Path,
    machine_profiles: Path,
    profiles: tuple[str, ...] | None,
    types: tuple[str, ...],
) -> tuple[BenchmarkCoverageAudit | None, tuple[str, ...]]:
    catalog, catalog_errors = _load_catalog(sources)
    if catalog is None or catalog_errors:
        return None, catalog_errors or ("catalog promotion failed",)
    result = generate_project(
        [sources],
        machine_profiles_path=machine_profiles,
        profiles=profiles,
        type_tags=types,
        backends=("cpp",),
        test_harness=True,
    )
    if has_errors(result.diagnostics) or result.rendered is None:
        errors = tuple(
            format_diagnostic(diagnostic)
            for diagnostic in result.diagnostics
            if diagnostic.severity == "error"
        )
        return None, errors or ("generation produced no rendered project",)
    return (
        audit_benchmark_coverage(
            catalog,
            result.rendered.benchmarks,
            selection_coverage=result.coverage,
            selection_skips=result.skipped,
        ),
        (),
    )


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


def deserialize_issue_baseline(text: str) -> BenchmarkIssueBaseline:
    """Load and validate the deterministic benchmark issue baseline."""

    payload: Any = json.loads(text)
    if not isinstance(payload, dict) or payload.get("version") != _BASELINE_VERSION:
        raise ValueError(
            f"expected benchmark baseline version {_BASELINE_VERSION}"
        )
    records = payload.get("issues")
    if not isinstance(records, list):
        raise ValueError("benchmark baseline issues must be a list")
    issues = tuple(_issue_key_from_record(record) for record in records)
    if len(frozenset(issues)) != len(issues):
        raise ValueError("benchmark baseline contains duplicate issue identities")
    return BenchmarkIssueBaseline(
        tuple(sorted(issues, key=BenchmarkIssueKey.sort_key))
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


def _issue_key_from_record(record: object) -> BenchmarkIssueKey:
    if not isinstance(record, list) or len(record) != 3:
        raise ValueError("benchmark issue record must contain kind, shape, and slot")
    kind_value, shape_value, slot_value = record
    if not isinstance(kind_value, str) or kind_value not in _ISSUE_KINDS:
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
        if not isinstance(slot_value, list) or len(slot_value) != 6:
            raise ValueError("benchmark issue slot must contain six fields")
        (
            backend_id,
            profile_name,
            extension_name,
            type_tag,
            axis_value,
            variants_value,
        ) = slot_value
        scalar_values = (backend_id, profile_name, extension_name, type_tag)
        if not all(isinstance(value, str) for value in scalar_values):
            raise ValueError("benchmark issue slot contains invalid scalar fields")
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
        slot = BenchmarkSlotKey(
            cast(str, backend_id),
            cast(str, profile_name),
            source_shape,
            cast(str, extension_name),
            cast(str, type_tag),
            tuple(axis),
            tuple(cast(list[str], variants_value)),
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
    parser.add_argument("--inventory", default=str(_INVENTORY))
    parser.add_argument("--baseline", default=str(_BASELINE))
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the deterministic issue baseline and shape inventory",
    )
    parser.add_argument("--sources", default=str(_DATA_ROOT))
    parser.add_argument("--machine-profiles", default=str(_PROFILES_PATH))
    parser.add_argument(
        "--profiles",
        default="",
        help="comma-separated profile subset; empty means every loaded profile",
    )
    parser.add_argument("--types", default=",".join(_ARITH_TYPE_TAGS))
    args = parser.parse_args(argv)

    audit, errors = compute_benchmark_coverage_audit(
        sources=Path(args.sources),
        machine_profiles=Path(args.machine_profiles),
        profiles=_split(args.profiles) or None,
        types=_split(args.types),
    )
    if audit is None:
        print("benchmark coverage: generation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 2
    rendered = render_benchmark_shape_inventory(audit)
    inventory_path = Path(args.inventory)
    baseline_path = Path(args.baseline)
    if args.update:
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(rendered, encoding="utf-8")
        baseline_path.write_text(
            serialize_issue_baseline(benchmark_issue_baseline(audit.issues)),
            encoding="utf-8",
        )
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
            "run './dev.sh benchmark-ratchet --update'",
            file=sys.stderr,
        )
        return 1
    try:
        baseline = deserialize_issue_baseline(
            baseline_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"benchmark coverage: invalid issue baseline {baseline_path}: {exc}",
            file=sys.stderr,
        )
        return 1
    diff = diff_benchmark_issues(baseline, audit.issues)
    if diff.new_issues:
        print(
            f"benchmark coverage: {len(diff.new_issues)} new issue(s) across "
            f"{audit.selected_slots} selected variant slots "
            f"({len(audit.issues)} current, {len(baseline.issues)} baselined)",
            file=sys.stderr,
        )
        for issue in diff.new_issues:
            print(f"  {_format_issue(issue)}", file=sys.stderr)
        return 1
    if (
        not inventory_path.exists()
        or inventory_path.read_text(encoding="utf-8") != rendered
    ):
        print(
            "benchmark coverage: committed shape inventory is missing or stale; "
            "run './dev.sh benchmark-ratchet --update'",
            file=sys.stderr,
        )
        return 1
    print(
        f"benchmark coverage: {audit.selected_slots} selected slots, "
        f"{audit.candidate_sets} candidate sets, {len(audit.issues)} known issues, "
        f"{len(diff.resolved_issues)} resolved since baseline; evidence current"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "BenchmarkCoverageAudit",
    "BenchmarkCoverageIssue",
    "BenchmarkIssueBaseline",
    "BenchmarkIssueDiff",
    "BenchmarkIssueKey",
    "BenchmarkSlotKey",
    "audit_benchmark_coverage",
    "benchmark_issue_baseline",
    "compute_benchmark_coverage_audit",
    "deserialize_issue_baseline",
    "diff_benchmark_issues",
    "serialize_issue_baseline",
)
