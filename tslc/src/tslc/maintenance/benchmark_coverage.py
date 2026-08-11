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
from pathlib import Path

from tslc.api import _ARITH_TYPE_TAGS, generate_project
from tslc.authoring import check_catalog
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_policy_consumption import (
    RustPolicyCoveragePlan,
    plan_rust_policy_coverage,
)
from tslc.backend.rust_policy_selection import plan_rust_policy_selection
from tslc.benchmark.model import BenchmarkProjectPlan
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.model import Catalog
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.maintenance.benchmark_inventory import (
    render_benchmark_shape_inventory,
    shape_label,
)
from tslc.maintenance import _repo_context
from tslc.maintenance.benchmark_coverage_audit import audit_benchmark_coverage
from tslc.maintenance.benchmark_coverage_baseline import (
    benchmark_issue_baseline,
    deserialize_issue_baseline,
    deserialize_rust_benchmark_baseline,
    diff_benchmark_issues,
    diff_rust_benchmark_coverage,
    rust_benchmark_coverage_baseline,
    serialize_issue_baseline,
    serialize_rust_benchmark_baseline,
)
from tslc.maintenance.benchmark_coverage_model import (
    BenchmarkCoverageAudit,
    BenchmarkCoverageIssue,
    BenchmarkIssueBaseline,
    BenchmarkIssueDiff,
    BenchmarkIssueKey,
    BenchmarkIssueKind,
    BenchmarkSlotKey,
    RustBenchmarkCoverageBaseline,
    RustBenchmarkCoverageDiff,
)
from tslc.pipeline import CoverageEntry, SkippedEntry

_EVIDENCE_BACKENDS = ("cpp", "rust")


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
    profile_groups: tuple[tuple[str, ...] | None, ...] = (profiles,)
    if backend_id == "rust":
        loaded_profiles = load_machine_profiles_checked(
            machine_profiles,
            catalog.target_families,
        )
        profile_errors = tuple(
            format_diagnostic(diagnostic)
            for diagnostic in loaded_profiles.diagnostics
            if diagnostic.severity == "error"
        )
        if profile_errors:
            return None, profile_errors
        selected_profiles = tuple(
            sorted(
                profiles
                if profiles is not None
                else loaded_profiles.profiles
            )
        )
        unknown_profiles = tuple(
            name
            for name in selected_profiles
            if name not in loaded_profiles.profiles
        )
        if unknown_profiles:
            return None, (
                "unknown profile(s): "
                + ", ".join(unknown_profiles)
                + "; known profiles: "
                + ", ".join(sorted(loaded_profiles.profiles)),
            )
        unsupported_profiles = tuple(
            name
            for name in selected_profiles
            if not loaded_profiles.profiles[name].supports_backend(backend_id)
        )
        if profiles is not None and unsupported_profiles:
            return None, (
                "machine profile(s) "
                + ", ".join(unsupported_profiles)
                + f" do not support backend {backend_id!r}",
            )
        selected_profiles = tuple(
            name
            for name in selected_profiles
            if loaded_profiles.profiles[name].supports_backend(backend_id)
        )
        # A generated Rust crate requires compile-target predicates to form an
        # ordered chain. Benchmark evidence spans every profile, including
        # unordered alternatives, so generate each package-valid profile
        # independently and merge only the typed benchmark/selection facts.
        profile_groups = tuple((profile_name,) for profile_name in selected_profiles)

    benchmark_plans: list[BenchmarkProjectPlan] = []
    selection_coverage: list[CoverageEntry] = []
    selection_skips: list[SkippedEntry] = []
    emitted_profiles: list[EmittedProfile] = []
    for profile_group in profile_groups:
        result = generate_project(
            [sources],
            machine_profiles_path=machine_profiles,
            profiles=profile_group,
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
        benchmark_plans.append(result.rendered.benchmarks)
        selection_coverage.extend(result.coverage)
        selection_skips.extend(result.skipped)
        emitted_profiles.extend(result.emitted_profiles)

    benchmark_plan = BenchmarkProjectPlan.merge(tuple(benchmark_plans))
    merged_emitted_profiles = tuple(
        sorted(emitted_profiles, key=lambda item: item.profile.name)
    )
    rust_policy_coverage: RustPolicyCoveragePlan | None = None
    if backend_id == "rust":
        try:
            rust_policy_coverage = plan_rust_policy_coverage(
                benchmark_plan,
                plan_rust_policy_selection(merged_emitted_profiles),
            )
        except ValueError as exc:
            return None, (f"Rust policy coverage planning failed: {exc}",)
    try:
        audit = audit_benchmark_coverage(
            catalog,
            benchmark_plan,
            backend_id=backend_id,
            selection_coverage=tuple(selection_coverage),
            selection_skips=tuple(selection_skips),
            emitted_profiles=(
                merged_emitted_profiles if backend_id == "rust" else None
            ),
            rust_policy_coverage=rust_policy_coverage,
        )
    except ValueError as exc:
        return None, (f"benchmark coverage audit failed: {exc}",)
    return audit, ()


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
