"""Exact cast/memory/I/O source-operation request-island discovery."""

from __future__ import annotations

from collections.abc import Callable

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    ImplementationBody,
    RawStringToken,
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
_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


def discover_source_operation_requests(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> SourceOperationDiscoveryLoweringResult:
    """Discover exact cast/memory/I/O islands in raw body-token text."""

    del context

    segments: list[SourceOperationDiscoverySegment] = []
    pending_opaque_tokens: list[BodyToken] = []
    raw_run: list[RawStringToken] = []

    for token in body.tokens:
        if isinstance(token, RawStringToken):
            raw_run.append(token)
            continue

        flush_result = _flush_raw_run(raw_run, segments, pending_opaque_tokens)
        if flush_result is not None:
            return flush_result
        raw_run.clear()
        pending_opaque_tokens.append(token)

    flush_result = _flush_raw_run(raw_run, segments, pending_opaque_tokens)
    if flush_result is not None:
        return flush_result
    raw_run.clear()

    if not segments:
        return SourceOperationDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_source_operation_diagnostic(body.source),),
        )

    if pending_opaque_tokens:
        segments.append(
            SourceOperationOpaqueTokenSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
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

    return _discover_source_operation_requests_in_text(
        text,
        source,
        source_at_offset=lambda offset: _source_at_offset(source, text, offset),
    )


def _flush_raw_run(
    raw_run: list[RawStringToken],
    segments: list[SourceOperationDiscoverySegment],
    pending_opaque_tokens: list[BodyToken],
) -> SourceOperationDiscoveryLoweringResult | None:
    if not raw_run:
        return None

    text, source_map = _raw_run_text_and_source_map(raw_run)
    text_result = _discover_source_operation_requests_in_text(
        text,
        raw_run[0].source,
        source_at_offset=lambda offset: _source_from_raw_run(
            raw_run[0].source,
            text,
            source_map,
            offset,
        ),
    )
    if _has_malformed_source_operation_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run)
        return None

    if pending_opaque_tokens:
        segments.append(
            SourceOperationOpaqueTokenSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
            )
        )
        pending_opaque_tokens.clear()
    segments.extend(text_result.discovery.segments)
    return None


def _discover_source_operation_requests_in_text(
    text: str,
    source: SourceLocation,
    *,
    source_at_offset: Callable[[int], SourceLocation],
) -> SourceOperationDiscoveryLoweringResult:
    segments: list[SourceOperationOpaqueTextSegment | SourceOperationRequestSegment]
    segments = []
    index = 0
    found_source_operation = False

    while index < len(text):
        match = _find_next_source_operation_head(text, index)
        if match is None:
            break

        start, operation_kind = match
        open_angle_index = start + len(operation_kind)
        close_angle_index = _matching_close(text, open_angle_index, "<", ">")
        if close_angle_index is None:
            return _malformed_source_operation_result(source_at_offset(start))

        open_argument_index = close_angle_index + 1
        if (
            open_argument_index >= len(text)
            or text[open_argument_index] != "("
        ):
            return _malformed_source_operation_result(source_at_offset(start))

        close_argument_index = _matching_close(
            text,
            open_argument_index,
            "(",
            ")",
        )
        if close_argument_index is None:
            return _malformed_source_operation_result(source_at_offset(start))

        angle_payload_start = open_angle_index + 1
        if not text[angle_payload_start:close_angle_index].strip():
            return _malformed_source_operation_result(source_at_offset(start))

        if start > index:
            segments.append(
                SourceOperationOpaqueTextSegment(
                    text=text[index:start],
                    source=source_at_offset(index),
                )
            )

        argument_start = open_argument_index + 1
        request = SourceOperationRequest(
            operation_kind=operation_kind,
            angle_payload_text=text[angle_payload_start:close_angle_index],
            angle_payload_source=source_at_offset(angle_payload_start),
            argument_text=text[argument_start:close_argument_index],
            argument_source=source_at_offset(argument_start),
            source_text=text[start : close_argument_index + 1],
            source=source_at_offset(start),
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
        segments.append(
            SourceOperationOpaqueTextSegment(
                text=text[index:],
                source=source_at_offset(index),
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
            if _has_identifier_boundary_before(text, index):
                return (index, operation_kind)
    return None


def _has_identifier_boundary_before(text: str, start: int) -> bool:
    return start == 0 or text[start - 1] not in _IDENTIFIER_CHARS


def _matching_close(
    text: str,
    open_index: int,
    open_char: str,
    close_char: str,
) -> int | None:
    if open_index < 0 or open_index >= len(text) or text[open_index] != open_char:
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
        if char == open_char:
            depth += 1
            continue
        if char == close_char:
            depth -= 1
            if depth == 0:
                return index

    return None


def _raw_run_text_and_source_map(
    raw_run: list[RawStringToken],
) -> tuple[str, tuple[SourceLocation, ...]]:
    text_parts: list[str] = []
    source_map: list[SourceLocation] = []

    for token in raw_run:
        text_parts.append(token.text)
        line = token.source.line
        column = token.source.column
        for char in token.text:
            source_map.append(SourceLocation(token.source.path, line, column))
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1

    return "".join(text_parts), tuple(source_map)


def _source_from_raw_run(
    fallback_source: SourceLocation,
    text: str,
    source_map: tuple[SourceLocation, ...],
    offset: int,
) -> SourceLocation:
    if 0 <= offset < len(source_map):
        return source_map[offset]
    return _source_at_offset(fallback_source, text, offset)


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
