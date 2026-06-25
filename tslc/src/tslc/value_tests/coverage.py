"""Coverage accounting for generated value-test plans."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.value_tests.model import (
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestCoverageEntry,
    ValueTestParityEntry,
)

CoverageIdentity = tuple[str, str, str, str | None]
ParityIdentity = tuple[str, str, str | None]

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
) -> ValueTestCoverageEntry:
    if supported:
        status = (
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
            reason="planned case kind is not supported by this backend renderer",
            case_kind=_case_kinds(planned),
        )
    return ValueTestCoverageEntry(
        backend_id=backend.backend_id,
        profile_name=profile_name,
        primitive_name=primitive_name,
        case_name=case_name,
        status="authored_unplanned",
        reason="no value-test pattern accepted the authored case shape",
    )


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
    locations: Mapping[CoverageIdentity, SourceLocation | None],
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
                location=locations.get(coverage_identity(entry)),
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
    "case_coverage",
    "coverage_diagnostics",
    "coverage_identity",
    "coverage_key",
    "merge_coverage",
    "parity_gaps",
    "parity_inventory",
    "parity_key",
)
