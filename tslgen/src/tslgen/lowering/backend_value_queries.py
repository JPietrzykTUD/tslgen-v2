"""Exact backend value query island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    ImplementationBody,
    RawStringToken,
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
    pending_opaque_tokens: list[BodyToken] = []

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

        if pending_opaque_tokens:
            segments.append(
                BackendValueQueryOpaqueTokenSegment(
                    tokens=tuple(pending_opaque_tokens),
                    source=pending_opaque_tokens[0].source,
                )
            )
            pending_opaque_tokens.clear()
        segments.extend(text_result.discovery.segments)

    if not segments:
        return BackendValueQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(body.source),),
        )

    if pending_opaque_tokens:
        segments.append(
            BackendValueQueryOpaqueTokenSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
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

    segments: list[BackendValueQueryOpaqueTextSegment | BackendValueQueryRequestSegment]
    segments = []
    index = 0
    found_query = False

    while index < len(text):
        start = text.find(_QUERY_PREFIX, index)
        if start == -1:
            break

        open_index = start + len(_QUERY_HEAD)
        close_index = _matching_query_close(text, open_index)
        if close_index is None:
            return BackendValueQueryDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(
                    _malformed_query_diagnostic(
                        _source_at_offset(source, text, start),
                    ),
                ),
            )

        if start > index:
            segments.append(
                BackendValueQueryOpaqueTextSegment(
                    text=text[index:start],
                    source=_source_at_offset(source, text, index),
                )
            )

        query_start = open_index + 1
        query_text = text[query_start:close_index]
        request = BackendValueQueryRequest(
            query_text=query_text,
            query_source=_source_at_offset(source, text, query_start),
            source_text=text[start : close_index + 1],
            source=_source_at_offset(source, text, start),
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
        segments.append(
            BackendValueQueryOpaqueTextSegment(
                text=text[index:],
                source=_source_at_offset(source, text, index),
            )
        )

    return BackendValueQueryDiscoveryLoweringResult(
        discovery=BackendValueQueryDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


def _matching_query_close(text: str, open_index: int) -> int | None:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "(":
        return None

    depth = 1
    quote: str | None = None
    escaped = False

    for index in range(open_index + 1, len(text)):
        char = text[index]

        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index

    return None


def _has_malformed_query_diagnostic(
    result: BackendValueQueryDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY"
        for diagnostic in result.diagnostics
    )


def _source_at_offset(
    source: SourceLocation,
    text: str,
    offset: int,
) -> SourceLocation:
    line = source.line
    column = source.column
    for char in text[:offset]:
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return SourceLocation(source.path, line, column)


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
