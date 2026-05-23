from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation


def _request_inventory_diagnostic(
    suffix: str,
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        f"TSL-LOWER-BACKEND-REQUEST-INVENTORY-{suffix}",
        detail,
        location=location,
    )


def _request_inventory_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("SOURCE-UNSUPPORTED", detail, location)


def _request_inventory_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("VALUE-MISSING", detail, location)


def _request_inventory_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("VALUE-MULTIPLE", detail, location)


def _request_inventory_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("MALFORMED", detail, location)


def _request_inventory_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("CONTEXT-MISMATCH", detail, location)


def _request_inventory_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("SOURCE-LOCATION-MISMATCH", detail, location)


def _request_inventory_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _request_inventory_diagnostic("PROVENANCE-MISMATCH", detail, location)
