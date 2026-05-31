"""Exact cast/memory/I/O source-operation request-island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    ImplementationBody,
    RawStringToken,
)
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
    SelectedImplementationLoweringContext,
    SourceOperationDiscovery,
    SourceOperationDiscoveryLoweringResult,
    SourceOperationDiscoverySegment,
    SourceOperationKind,
    SourceOperationOpaqueTextSegment,
    SourceOperationOpaqueTokenSegment,
    SourceOperationRequest,
    SourceOperationRequestSegment,
)

_SOURCE_OPERATION_HEADS: tuple[SourceOperationKind, ...] = ("cast", "mem", "io")


def discover_source_operation_requests(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> SourceOperationDiscoveryLoweringResult:
    """Discover exact cast/memory/I/O islands in raw body-token text."""

    del context

    segments: list[SourceOperationDiscoverySegment] = []
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
        return SourceOperationDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_source_operation_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            SourceOperationOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return SourceOperationDiscoveryLoweringResult(
        discovery=SourceOperationDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_source_operation_requests_in_text(
    text: str,
    source: SourceLocation,
) -> SourceOperationDiscoveryLoweringResult:
    """Discover exact cast/memory/I/O request islands in one text fragment."""

    return _discover_source_operation_requests_in_source_text(
        source_text_from_text(text, source),
    )


def _flush_raw_run(
    raw_run: JoinedRawStringRun | None,
    segments: list[SourceOperationDiscoverySegment],
    pending_opaque_tokens: OpaqueTokenBuffer,
) -> SourceOperationDiscoveryLoweringResult | None:
    if raw_run is None:
        return None

    text_result = _discover_source_operation_requests_in_source_text(
        raw_run.source_text,
    )
    if _has_malformed_source_operation_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run.tokens)
        return None

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            SourceOperationOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )
    segments.extend(text_result.discovery.segments)
    return None


def _discover_source_operation_requests_in_source_text(
    source_text: SourceMappedText,
) -> SourceOperationDiscoveryLoweringResult:
    segments: list[SourceOperationOpaqueTextSegment | SourceOperationRequestSegment]
    segments = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_source_operation = False

    while index < len(text):
        match = _find_next_source_operation_head(text, index)
        if match is None:
            break

        start, operation_kind = match
        open_angle_index = start + len(operation_kind)
        close_angle_index = matching_delimiter_close(text, open_angle_index, "<", ">")
        if close_angle_index is None:
            return _malformed_source_operation_result(source_text.source_at(start))

        open_argument_index = close_angle_index + 1
        if (
            open_argument_index >= len(text)
            or text[open_argument_index] != "("
        ):
            return _malformed_source_operation_result(source_text.source_at(start))

        close_argument_index = matching_delimiter_close(
            text,
            open_argument_index,
            "(",
            ")",
        )
        if close_argument_index is None:
            return _malformed_source_operation_result(source_text.source_at(start))

        angle_payload_start = open_angle_index + 1
        if not text[angle_payload_start:close_angle_index].strip():
            return _malformed_source_operation_result(source_text.source_at(start))

        if start > index:
            opaque_span = source_text.span(index, start)
            segments.append(
                SourceOperationOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        argument_start = open_argument_index + 1
        request = SourceOperationRequest(
            operation_kind=operation_kind,
            angle_payload_text=text[angle_payload_start:close_angle_index],
            angle_payload_source=source_text.source_at(angle_payload_start),
            argument_text=text[argument_start:close_argument_index],
            argument_source=source_text.source_at(argument_start),
            source_text=text[start : close_argument_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            SourceOperationRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_source_operation = True
        index = close_argument_index + 1

    if not found_source_operation:
        return SourceOperationDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_source_operation_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            SourceOperationOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return SourceOperationDiscoveryLoweringResult(
        discovery=SourceOperationDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


def _find_next_source_operation_head(
    text: str,
    start: int,
) -> tuple[int, SourceOperationKind] | None:
    for index in range(max(0, start), len(text)):
        for operation_kind in _SOURCE_OPERATION_HEADS:
            if not text.startswith(f"{operation_kind}<", index):
                continue
            if has_identifier_boundary_before(text, index):
                return (index, operation_kind)
    return None


def _has_malformed_source_operation_diagnostic(
    result: SourceOperationDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-SOURCE-OPERATION"
        for diagnostic in result.diagnostics
    )


def _malformed_source_operation_result(
    source: SourceLocation,
) -> SourceOperationDiscoveryLoweringResult:
    return SourceOperationDiscoveryLoweringResult(
        discovery=None,
        diagnostics=(_malformed_source_operation_diagnostic(source),),
    )


def _malformed_source_operation_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-SOURCE-OPERATION",
        message=(
            "source-operation discovery found a cast<...>(...), mem<...>(...), "
            "or io<...>(...) island with an unbalanced or incomplete outer shape"
        ),
        location=source,
    )


def _no_source_operation_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-SOURCE-OPERATION",
        message=(
            "source-operation discovery found no exact cast<...>(...), "
            "mem<...>(...), or io<...>(...) island"
        ),
        location=source,
    )
