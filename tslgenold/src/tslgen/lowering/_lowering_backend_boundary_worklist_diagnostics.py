from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation


def _worklist_diagnostic(
    suffix: str,
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        f"TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-{suffix}",
        detail,
        location=location,
    )


def _worklist_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("SOURCE-UNSUPPORTED", detail, location)


def _worklist_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("VALUE-MISSING", detail, location)


def _worklist_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("VALUE-MULTIPLE", detail, location)


def _worklist_conflicting_entry_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("ENTRY-CONFLICT", detail, location)


def _worklist_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("MALFORMED", detail, location)


def _worklist_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("CONTEXT-MISMATCH", detail, location)


def _worklist_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("SOURCE-LOCATION-MISMATCH", detail, location)


def _worklist_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _worklist_diagnostic("PROVENANCE-MISMATCH", detail, location)
