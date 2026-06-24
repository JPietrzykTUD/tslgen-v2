"""Coverage accounting for generated value-test plans."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.value_tests.model import (
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestCoverageEntry,
)

CoverageIdentity = tuple[str, str, str, str | None]

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
        )
    if planned:
        return ValueTestCoverageEntry(
            backend_id=backend.backend_id,
            profile_name=profile_name,
            primitive_name=primitive_name,
            case_name=case_name,
            status="backend_unsupported",
            reason="planned case kind is not supported by this backend renderer",
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
                    f"{entry.reason}"
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


__all__ = (
    "CoverageIdentity",
    "case_coverage",
    "coverage_diagnostics",
    "coverage_identity",
    "coverage_key",
    "merge_coverage",
)
