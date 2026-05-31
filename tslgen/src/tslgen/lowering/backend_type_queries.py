"""Exact backend type query request-island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import ImplementationBody, RawStringToken
from tslgen.lowering._source_islands import (
    JoinedRawStringRun,
    OpaqueTokenBuffer,
    RawStringRunBuffer,
    SourceMappedText,
    has_identifier_boundary_before,
    matching_delimiter_close,
    source_text_from_text,
)
from tslgen.lowering.model import (
    BackendTypeQueryDiscovery,
    BackendTypeQueryDiscoveryLoweringResult,
    BackendTypeQueryDiscoverySegment,
    BackendTypeQueryHandoff,
    BackendTypeQueryHandoffLoweringResult,
    BackendTypeQueryHandoffRequestSegment,
    BackendTypeQueryHandoffSegment,
    BackendTypeQueryOpaqueTextSegment,
    BackendTypeQueryOpaqueTokenSegment,
    BackendTypeQueryRequestIsland,
    BackendTypeQueryRequestIslandSegment,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)
from tslgen.lowering.type_queries import lower_backend_type_query

_QUERY_PREFIX = "type<backend>("
_QUERY_HEAD = "type<backend>"


def discover_backend_type_queries(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> BackendTypeQueryDiscoveryLoweringResult:
    """Discover exact backend type query islands in raw body-token text."""

    del context

    segments: list[BackendTypeQueryDiscoverySegment] = []
    pending_opaque_tokens = OpaqueTokenBuffer()
    raw_run = RawStringRunBuffer()

    for token in body.tokens:
        if isinstance(token, RawStringToken):
            raw_run.append(token)
            continue

        flush_result = _flush_raw_run(raw_run.take(), segments, pending_opaque_tokens)
        if flush_result is not None:
            return flush_result
        pending_opaque_tokens.append(token)

    flush_result = _flush_raw_run(raw_run.take(), segments, pending_opaque_tokens)
    if flush_result is not None:
        return flush_result

    if not segments:
        return BackendTypeQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendTypeQueryOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return BackendTypeQueryDiscoveryLoweringResult(
        discovery=BackendTypeQueryDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_backend_type_queries_in_text(
    text: str,
    source: SourceLocation,
) -> BackendTypeQueryDiscoveryLoweringResult:
    """Discover exact backend type query islands in one source text fragment."""

    return _discover_backend_type_queries_in_source_text(
        source_text_from_text(text, source),
    )


def lower_backend_type_query_discovery(
    context: SelectedImplementationLoweringContext,
    discovery: BackendTypeQueryDiscovery,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> BackendTypeQueryHandoffLoweringResult:
    """Lower discovered backend type-query islands to spelling requests."""

    segments: list[BackendTypeQueryHandoffSegment] = []
    diagnostics: list[Diagnostic] = []

    for segment in discovery.segments:
        if isinstance(
            segment,
            BackendTypeQueryOpaqueTextSegment | BackendTypeQueryOpaqueTokenSegment,
        ):
            segments.append(segment)
            continue

        result = lower_backend_type_query(
            context,
            segment.request.source_text,
            segment.request.source,
            environment=environment,
        )
        diagnostics.extend(result.diagnostics)
        if result.request is None:
            continue
        segments.append(
            BackendTypeQueryHandoffRequestSegment(
                request=result.request,
                island=segment.request,
                source=segment.source,
            )
        )

    if diagnostics:
        return BackendTypeQueryHandoffLoweringResult(
            handoff=None,
            diagnostics=tuple(diagnostics),
        )

    return BackendTypeQueryHandoffLoweringResult(
        handoff=BackendTypeQueryHandoff(
            segments=tuple(segments),
            source=discovery.source,
        ),
        diagnostics=(),
    )


def _flush_raw_run(
    raw_run: JoinedRawStringRun | None,
    segments: list[BackendTypeQueryDiscoverySegment],
    pending_opaque_tokens: OpaqueTokenBuffer,
) -> BackendTypeQueryDiscoveryLoweringResult | None:
    if raw_run is None:
        return None

    text_result = _discover_backend_type_queries_in_source_text(raw_run.source_text)
    if _has_malformed_query_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run.tokens)
        return None

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendTypeQueryOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )
    segments.extend(text_result.discovery.segments)
    return None


def _discover_backend_type_queries_in_source_text(
    source_text: SourceMappedText,
) -> BackendTypeQueryDiscoveryLoweringResult:
    segments: list[
        BackendTypeQueryOpaqueTextSegment | BackendTypeQueryRequestIslandSegment
    ]
    segments = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_query = False

    while index < len(text):
        start = _find_next_query_start(text, index)
        if start is None:
            break

        open_index = start + len(_QUERY_HEAD)
        close_index = matching_delimiter_close(text, open_index, "(", ")")
        if close_index is None:
            return BackendTypeQueryDiscoveryLoweringResult(
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
                BackendTypeQueryOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        payload_start = open_index + 1
        request = BackendTypeQueryRequestIsland(
            payload_text=text[payload_start:close_index],
            payload_source=source_text.source_at(payload_start),
            source_text=text[start : close_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            BackendTypeQueryRequestIslandSegment(
                request=request,
                source=request.source,
            )
        )
        found_query = True
        index = close_index + 1

    if not found_query:
        return BackendTypeQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            BackendTypeQueryOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return BackendTypeQueryDiscoveryLoweringResult(
        discovery=BackendTypeQueryDiscovery(segments=tuple(segments), source=source),
        diagnostics=(),
    )


def _find_next_query_start(text: str, start: int) -> int | None:
    index = max(0, start)
    while index < len(text):
        found = text.find(_QUERY_PREFIX, index)
        if found == -1:
            return None
        if has_identifier_boundary_before(text, found):
            return found
        index = found + 1
    return None


def _has_malformed_query_diagnostic(
    result: BackendTypeQueryDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-BACKEND-TYPE-QUERY"
        for diagnostic in result.diagnostics
    )


def _malformed_query_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-TYPE-QUERY",
        message=(
            "backend type query discovery found a type<backend>(...) island "
            "with an unbalanced outer payload"
        ),
        location=source,
    )


def _no_query_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-BACKEND-TYPE-QUERY",
        message=(
            "backend type query discovery found no exact type<backend>(...) "
            "island"
        ),
        location=source,
    )
