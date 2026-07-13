#!/usr/bin/env python3
"""Audit full-corpus implementation-variant benchmark coverage.

Every selected C++ implementation variant must survive lowering and dependency
closure, receive correctness facts and a typed workload scenario, and reach at
least one emitted candidate set. Default-only shapes remain explicitly outside
this gate and are inventoried as not applicable.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.benchmark.model import (
    BenchmarkCandidateSet,
    BenchmarkCoverageEntry,
    BenchmarkProjectPlan,
)
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import has_errors
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
    kind: Literal[
        "coverage-gap",
        "inactive-authored-shape",
        "selected-slot-skipped",
        "selected-slot-missing-planner",
        "emitted-without-candidates",
        "candidate-without-coverage",
    ]
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
        f"[{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}"
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
            f"[{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}"
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


def _split(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc-benchmark-coverage",
        description=(
            "Require complete benchmark coverage for all selected "
            "implementation variants."
        ),
    )
    parser.add_argument("--inventory", default=str(_INVENTORY))
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the deterministic shape inventory after a complete audit",
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
    if not audit.complete:
        print(
            f"benchmark coverage: {len(audit.issues)} strict issue(s) across "
            f"{audit.selected_slots} selected variant slots",
            file=sys.stderr,
        )
        for issue in audit.issues:
            where = ""
            if issue.slot is not None:
                where = (
                    f" [{issue.slot.profile_name}/{issue.slot.backend_id} "
                    f"{issue.slot.extension_name}/{issue.slot.type_tag}]"
                )
            print(
                f"  {issue.kind}: {shape_label(issue.source_shape)}{where}: "
                f"{issue.detail}",
                file=sys.stderr,
            )
        return 1

    rendered = render_benchmark_shape_inventory(audit)
    inventory_path = Path(args.inventory)
    if args.update:
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(rendered)
        print(
            f"benchmark coverage: {audit.selected_slots} selected slots, "
            f"{audit.candidate_sets} candidate sets, 0 gaps"
        )
        print(f"wrote inventory {inventory_path}")
        return 0
    if not inventory_path.exists() or inventory_path.read_text() != rendered:
        print(
            "benchmark coverage: committed shape inventory is missing or stale; "
            "run './dev.sh benchmark-ratchet --update'",
            file=sys.stderr,
        )
        return 1
    print(
        f"benchmark coverage: {audit.selected_slots} selected slots, "
        f"{audit.candidate_sets} candidate sets, 0 gaps; inventory current"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "BenchmarkCoverageAudit",
    "BenchmarkCoverageIssue",
    "BenchmarkSlotKey",
    "audit_benchmark_coverage",
    "compute_benchmark_coverage_audit",
)
