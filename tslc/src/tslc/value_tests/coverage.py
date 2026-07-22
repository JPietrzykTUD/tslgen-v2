"""Coverage accounting for generated value-test plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.value_tests.model import (
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestCoverageEntry,
    ValueTestParityEntry,
    ValueTestCoverageStatus,
)

CoverageIdentity = tuple[str, str, str, str | None]
ParityIdentity = tuple[str, str, str | None]

ValueTestCaseDropCause = Literal[
    "renderer_unsupported",
    "profile_unsupported",
    "fuzz_unsupported",
    "differential_harness_missing",
    "header_group_conflict",
]

_DETAIL_CAUSES = frozenset(
    {
        "profile_unsupported",
        "differential_harness_missing",
        "header_group_conflict",
    }
)


@dataclass(frozen=True, slots=True)
class ValueTestCaseDrop:
    """One planned case a backend profile could not accept, with its typed cause."""

    case: ValueTestCasePlan
    cause: ValueTestCaseDropCause
    detail: str = ""

    def __post_init__(self) -> None:
        if self.cause in _DETAIL_CAUSES and not self.detail:
            raise ValueError(
                f"value-test case drop cause {self.cause!r} requires a detail"
            )

    def reason(self, backend_id: str) -> str:
        if self.cause == "renderer_unsupported":
            return (
                f"planned case kind {self.case.kind!r} is not supported by the "
                f"{backend_id} value-test renderer"
            )
        if self.cause == "fuzz_unsupported":
            return (
                f"synthetic fuzz case kind {self.case.kind!r} is not supported by "
                f"the {backend_id} value-test renderer"
            )
        return self.detail

BLOCKING_COVERAGE_STATUSES = frozenset(
    {"missing_authored_tests", "authored_unplanned", "backend_unsupported"}
)
SUCCESS_COVERAGE_STATUSES = frozenset({"emitted", "compile_only_emitted"})

_COVERAGE_PRIORITY = {
    "missing_authored_tests": 0,
    "authored_unplanned": 1,
    "backend_unsupported": 2,
    "compile_only_emitted": 3,
    "emitted": 4,
}


def case_coverage(
    *,
    backend: ValueTestBackendSupport,
    profile_name: str,
    primitive_name: str,
    case_name: str,
    planned: tuple[ValueTestCasePlan, ...],
    supported: tuple[ValueTestCasePlan, ...],
    drops: tuple[ValueTestCaseDrop, ...] = (),
    unplanned_reason: str | None = None,
) -> ValueTestCoverageEntry:
    if supported:
        status: ValueTestCoverageStatus = (
            "compile_only_emitted"
            if all(case.kind == "compile_only" for case in supported)
            else "emitted"
        )
        return ValueTestCoverageEntry(
            backend_id=backend.backend_id,
            profile_name=profile_name,
            primitive_name=primitive_name,
            case_name=case_name,
            status=status,
            case_kind=_case_kinds(supported),
        )
    if planned:
        return ValueTestCoverageEntry(
            backend_id=backend.backend_id,
            profile_name=profile_name,
            primitive_name=primitive_name,
            case_name=case_name,
            status="backend_unsupported",
            reason=_drop_reason(drops, backend.backend_id),
            case_kind=_case_kinds(planned),
        )
    return ValueTestCoverageEntry(
        backend_id=backend.backend_id,
        profile_name=profile_name,
        primitive_name=primitive_name,
        case_name=case_name,
        status="authored_unplanned",
        reason=unplanned_reason or "no value-test pattern accepted the authored case shape",
    )


def dropped_fuzz_coverage(
    *,
    backend: ValueTestBackendSupport,
    profile_name: str,
    primitive_name: str,
    drop: ValueTestCaseDrop,
) -> ValueTestCoverageEntry:
    """Coverage for a suppressed synthetic fuzz case, which has no authored case."""

    return ValueTestCoverageEntry(
        backend_id=backend.backend_id,
        profile_name=profile_name,
        primitive_name=primitive_name,
        case_name=drop.case.case_name,
        status="backend_unsupported",
        reason=drop.reason(backend.backend_id),
        case_kind=drop.case.kind,
    )


def _drop_reason(drops: tuple[ValueTestCaseDrop, ...], backend_id: str) -> str:
    reasons = dict.fromkeys(drop.reason(backend_id) for drop in drops)
    if not reasons:
        return "planned case kind is not supported by this backend renderer"
    return "; ".join(reasons)


def merge_coverage(
    entries: list[ValueTestCoverageEntry],
) -> tuple[ValueTestCoverageEntry, ...]:
    merged: dict[CoverageIdentity, ValueTestCoverageEntry] = {}
    for entry in entries:
        key = coverage_identity(entry)
        current = merged.get(key)
        if current is None or _COVERAGE_PRIORITY[entry.status] > _COVERAGE_PRIORITY[current.status]:
            merged[key] = entry
    return tuple(merged.values())


def parity_inventory(
    entries: tuple[ValueTestCoverageEntry, ...],
    backend_ids: tuple[str, ...],
) -> tuple[ValueTestParityEntry, ...]:
    """Group coverage by authored value-test identity across requested backends."""

    by_case: dict[ParityIdentity, dict[str, ValueTestCoverageEntry]] = {}
    for entry in entries:
        if entry.backend_id not in backend_ids:
            continue
        key = (entry.profile_name, entry.primitive_name, entry.case_name)
        by_case.setdefault(key, {})[entry.backend_id] = entry
    result: list[ValueTestParityEntry] = []
    for key, statuses in by_case.items():
        profile_name, primitive_name, case_name = key
        result.append(
            ValueTestParityEntry(
                profile_name=profile_name,
                primitive_name=primitive_name,
                case_name=case_name,
                backend_statuses=tuple(
                    statuses[backend_id]
                    for backend_id in backend_ids
                    if backend_id in statuses
                ),
            )
        )
    return tuple(sorted(result, key=parity_key))


def parity_gaps(
    entries: tuple[ValueTestCoverageEntry, ...],
    backend_ids: tuple[str, ...],
) -> tuple[ValueTestParityEntry, ...]:
    """Coverage identities that are not equivalent successful outcomes on every backend."""

    gaps: list[ValueTestParityEntry] = []
    expected = set(backend_ids)
    for entry in parity_inventory(entries, backend_ids):
        statuses = {status.backend_id: status.status for status in entry.backend_statuses}
        if set(statuses) != expected:
            gaps.append(entry)
            continue
        unique_statuses = set(statuses.values())
        if len(unique_statuses) != 1 or not unique_statuses <= SUCCESS_COVERAGE_STATUSES:
            gaps.append(entry)
    return tuple(gaps)


def coverage_diagnostics(
    entries: tuple[ValueTestCoverageEntry, ...],
    locations: Mapping[CoverageIdentity, SourceSpan | None],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for entry in entries:
        if entry.status not in {"authored_unplanned", "backend_unsupported"}:
            continue
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="TSL-VALUE-TEST-UNSUPPORTED-CASE",
                message=(
                    f"no {entry.backend_id} value-test plan for case {entry.case_name!r} "
                    f"of primitive {entry.primitive_name!r} in profile {entry.profile_name!r}: "
                    f"{entry.reason}{_case_kind_suffix(entry)}"
                ),
                span=locations.get(coverage_identity(entry)),
            )
        )
    return tuple(diagnostics)


def coverage_identity(entry: ValueTestCoverageEntry) -> CoverageIdentity:
    return (entry.backend_id, entry.profile_name, entry.primitive_name, entry.case_name)


def coverage_key(entry: ValueTestCoverageEntry) -> tuple[str, str, str, str, str]:
    return (
        entry.backend_id,
        entry.profile_name,
        entry.primitive_name,
        entry.case_name or "",
        entry.status,
    )


def parity_key(entry: ValueTestParityEntry) -> tuple[str, str, str]:
    return (entry.profile_name, entry.primitive_name, entry.case_name or "")


def _case_kinds(cases: tuple[ValueTestCasePlan, ...]) -> str | None:
    kinds = sorted({case.kind for case in cases})
    return ",".join(kinds) if kinds else None


def _case_kind_suffix(entry: ValueTestCoverageEntry) -> str:
    return f" ({entry.case_kind})" if entry.case_kind else ""


__all__ = (
    "BLOCKING_COVERAGE_STATUSES",
    "CoverageIdentity",
    "ParityIdentity",
    "SUCCESS_COVERAGE_STATUSES",
    "ValueTestCaseDrop",
    "ValueTestCaseDropCause",
    "case_coverage",
    "coverage_diagnostics",
    "coverage_identity",
    "coverage_key",
    "dropped_fuzz_coverage",
    "merge_coverage",
    "parity_gaps",
    "parity_inventory",
    "parity_key",
)
