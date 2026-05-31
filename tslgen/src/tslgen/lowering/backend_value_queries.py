"""Exact backend value query island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    ImplementationBody,
    RawStringToken,
)
from tslgen.lowering._source_islands import (
    OpaqueTokenBuffer,
    SourceMappedText,
    matching_delimiter_close,
    source_text_from_text,
)
from tslgen.lowering.model import (
    BackendValueQueryDiscovery,
    BackendValueQueryDiscoveryLoweringResult,
    BackendValueQueryDiscoverySegment,
    BackendValueQueryOpaqueTextSegment,
    BackendValueQueryOpaqueTokenSegment,
    BackendValueQueryRequest,
    BackendValueQueryRequestSegment,
    SelectedImplementationLoweringContext,
)

_QUERY_PREFIX = "value<backend>("
_QUERY_HEAD = "value<backend>"


def discover_backend_value_queries(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> BackendValueQueryDiscoveryLoweringResult:
    """Discover exact backend value query islands in raw body-token text."""

    del context

    segments: list[BackendValueQueryDiscoverySegment] = []
    pending_opaque_tokens = OpaqueTokenBuffer()

    for token in body.tokens:
        if not isinstance(token, RawStringToken):
            pending_opaque_tokens.append(token)
            continue

        text_result = discover_backend_value_queries_in_text(
            token.text,
            token.source,
        )
        if _has_malformed_query_diagnostic(text_result):
            return text_result
        if text_result.discovery is None:
            pending_opaque_tokens.append(token)
            continue

        opaque_span = pending_opaque_tokens.take()
        if opaque_span is not None:
            segments.append(
                BackendValueQueryOpaqueTokenSegment(
                    tokens=opaque_span.tokens,
                    source=opaque_span.source,
                )
            )
        segments.extend(text_result.discovery.segments)

    if not segments:
        return BackendValueQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendValueQueryOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return BackendValueQueryDiscoveryLoweringResult(
        discovery=BackendValueQueryDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_backend_value_queries_in_text(
    text: str,
    source: SourceLocation,
) -> BackendValueQueryDiscoveryLoweringResult:
    """Discover exact backend value query islands in one source text fragment."""

    return _discover_backend_value_queries_in_source_text(
        source_text_from_text(text, source),
    )


def _discover_backend_value_queries_in_source_text(
    source_text: SourceMappedText,
) -> BackendValueQueryDiscoveryLoweringResult:
    segments: list[BackendValueQueryOpaqueTextSegment | BackendValueQueryRequestSegment]
    segments = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_query = False

    while index < len(text):
        start = text.find(_QUERY_PREFIX, index)
        if start == -1:
            break

        open_index = start + len(_QUERY_HEAD)
        close_index = matching_delimiter_close(text, open_index, "(", ")")
        if close_index is None:
            return BackendValueQueryDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(
                    _malformed_query_diagnostic(
                        source_text.source_at(start),
                    ),
                ),
            )

        if start > index:
            opaque_span = source_text.span(index, start)
            segments.append(
                BackendValueQueryOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        query_start = open_index + 1
        query_text = text[query_start:close_index]
        request = BackendValueQueryRequest(
            query_text=query_text,
            query_source=source_text.source_at(query_start),
            source_text=text[start : close_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            BackendValueQueryRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_query = True
        index = close_index + 1

    if not found_query:
        return BackendValueQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            BackendValueQueryOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return BackendValueQueryDiscoveryLoweringResult(
        discovery=BackendValueQueryDiscovery(segments=tuple(segments), source=source),
        diagnostics=(),
    )


def _has_malformed_query_diagnostic(
    result: BackendValueQueryDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY"
        for diagnostic in result.diagnostics
    )


def _malformed_query_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY",
        message=(
            "backend value query discovery found a value<backend>(...) "
            "island with an unbalanced outer payload"
        ),
        location=source,
    )


def _no_query_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-BACKEND-VALUE-QUERY",
        message=(
            "backend value query discovery found no exact "
            "value<backend>(...) island"
        ),
        location=source,
    )
