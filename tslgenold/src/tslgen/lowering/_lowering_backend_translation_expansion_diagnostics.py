from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation


def _translation_expansion_diagnostic(
    suffix: str,
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        f"TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-{suffix}",
        detail,
        location=location,
    )


def _translation_expansion_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("SOURCE-UNSUPPORTED", detail, location)


def _translation_expansion_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("VALUE-MISSING", detail, location)


def _translation_expansion_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("VALUE-MULTIPLE", detail, location)


def _translation_expansion_conflicting_rule_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("RULE-CONFLICT", detail, location)


def _translation_expansion_rule_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("RULE-MISSING", detail, location)


def _translation_expansion_rule_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("RULE-MISMATCH", detail, location)


def _translation_expansion_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("MALFORMED", detail, location)


def _translation_expansion_request_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("REQUEST-UNSUPPORTED", detail, location)


def _translation_expansion_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("CONTEXT-MISMATCH", detail, location)


def _translation_expansion_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic(
        "SOURCE-LOCATION-MISMATCH",
        detail,
        location,
    )


def _translation_expansion_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return _translation_expansion_diagnostic("PROVENANCE-MISMATCH", detail, location)
