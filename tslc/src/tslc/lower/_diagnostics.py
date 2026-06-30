"""Shared source and diagnostic helpers for lowering."""

from __future__ import annotations

from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.select.selector import SelectedImplementation


def primitive_signature_source(selected: SelectedImplementation) -> SourceSpan | None:
    return (
        selected.primitive.signature_source
        or selected.primitive.header_source
        or selected.primitive.source
    )


def implementation_source(selected: SelectedImplementation) -> SourceSpan | None:
    return (
        selected.implementation.selector_source
        or selected.implementation.body_source
        or selected.implementation.source
        or selected.primitive.source
    )


def implementation_body_source(selected: SelectedImplementation) -> SourceSpan | None:
    return (
        selected.implementation.body_source
        or selected.implementation.source
        or selected.implementation.selector_source
        or selected.primitive.source
    )


def lowering_error_diagnostic(
    code: str, message: str, *, source: SourceSpan | None = None
) -> Diagnostic:
    return diagnostic_at(
        severity="error",
        code=code,
        message=message,
        source=source,
    )


def lowering_skip_diagnostic(
    code: str, message: str, *, source: SourceSpan | None = None
) -> Diagnostic:
    """A not-yet-lowerable specialization diagnostic, reported as a coverage gap."""

    return diagnostic_at(
        severity="info",
        code=code,
        message=message,
        source=source,
    )
