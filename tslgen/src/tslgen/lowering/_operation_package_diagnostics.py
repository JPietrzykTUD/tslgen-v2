from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation


def source_location_from_entries(
    entries: tuple[object, ...],
) -> SourceLocation | None:
    for entry in entries:
        location = source_location_from_object(entry)
        if location is not None:
            return location
    return None


def source_location_from_object(source: object) -> SourceLocation | None:
    location = getattr(source, "source_location", None)
    if isinstance(location, SourceLocation):
        return location
    return None


def source_location_key(location: SourceLocation | None) -> tuple[object, ...]:
    if location is None:
        return ("none",)
    return ("source_location", *location.sort_key())


def operation_package_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def operation_package_missing_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-VALUE-MISSING",
        detail,
        location=location,
    )


def operation_package_duplicate_value_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-VALUE-MULTIPLE",
        detail,
        location=location,
    )


def operation_package_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-MALFORMED",
        detail,
        location=location,
    )


def operation_package_source_family_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-FAMILY-MISMATCH",
        detail,
        location=location,
    )


def operation_package_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def operation_package_source_location_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-LOCATION-MISMATCH",
        detail,
        location=location,
    )


def operation_package_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def operation_package_dependency_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-DEPENDENCY-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def operation_package_source_ambiguous_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-OPERATION-PACKAGE-SOURCE-AMBIGUOUS",
        detail,
        location=location,
    )
