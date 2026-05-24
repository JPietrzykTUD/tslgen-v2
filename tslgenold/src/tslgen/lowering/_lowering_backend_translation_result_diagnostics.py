from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation


def _translation_result_diagnostic(
    suffix: str,
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        f"TSL-LOWER-BACKEND-TRANSLATION-RESULT-{suffix}",
        detail,
        location=location,
    )


def _translation_result_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("SOURCE-UNSUPPORTED", detail, location)


def _translation_result_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("VALUE-MISSING", detail, location)


def _translation_result_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("VALUE-MULTIPLE", detail, location)


def _translation_result_conflicting_rule_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("RULE-CONFLICT", detail, location)


def _translation_result_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("MALFORMED", detail, location)


def _translation_result_backend_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("BACKEND-UNSUPPORTED", detail, location)


def _translation_result_request_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("REQUEST-UNSUPPORTED", detail, location)


def _translation_result_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("CONTEXT-MISMATCH", detail, location)


def _translation_result_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("SOURCE-LOCATION-MISMATCH", detail, location)


def _translation_result_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_result_diagnostic("PROVENANCE-MISMATCH", detail, location)
