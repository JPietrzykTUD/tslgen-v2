"""Typed records shared by benchmark coverage auditing and baselines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tslc.maintenance.benchmark_inventory import (
    BenchmarkShapeInventoryEntry,
    BenchmarkSpecialCaseInventoryEntry,
    SourceShapeKey,
)
from tslc.maintenance.rust_benchmark_evidence import RustBenchmarkEvidence

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
class SelectedBenchmarkSlot:
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


__all__ = (
    "BenchmarkCoverageAudit",
    "BenchmarkCoverageIssue",
    "BenchmarkIssueBaseline",
    "BenchmarkIssueDiff",
    "BenchmarkIssueKey",
    "BenchmarkIssueKind",
    "BenchmarkSlotKey",
    "RustBenchmarkCoverageBaseline",
    "RustBenchmarkCoverageDiff",
    "SelectedBenchmarkSlot",
)
