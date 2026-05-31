"""Exact backend/output source-island request discovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import BodyToken, ImplementationBody, RawStringToken
from tslgen.lowering._source_islands import (
    JoinedRawStringRun,
    OpaqueTokenBuffer,
    RawStringRunBuffer,
    SourceMappedText,
    has_identifier_boundary_before,
    matching_delimiter_close,
    source_text_from_text,
)
from tslgen.lowering.model import SelectedImplementationLoweringContext

_FAILURE_CODE = "TSL-LOWER-MALFORMED-BACKEND-OUTPUT-SOURCE-ISLAND"


class BackendOutputRequestKind(Enum):
    ASSUME_ALIGNED = "assume_aligned"
    ARRAY_TYPE = "array_type"
    PACK = "pack"


@dataclass(frozen=True, slots=True)
class BackendOutputRequest:
    kind: BackendOutputRequestKind
    angle_payload_text: str
    angle_payload_source: SourceLocation
    source_text: str
    source: SourceLocation
    argument_text: str | None = None
    argument_source: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class BackendOutputOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendOutputOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendOutputRequestSegment:
    request: BackendOutputRequest
    source: SourceLocation


BackendOutputDiscoverySegment = (
    BackendOutputOpaqueTextSegment
    | BackendOutputOpaqueTokenSegment
    | BackendOutputRequestSegment
)


@dataclass(frozen=True, slots=True)
class BackendOutputDiscovery:
    segments: tuple[BackendOutputDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendOutputDiscoveryLoweringResult:
    discovery: BackendOutputDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


_HEADS: tuple[BackendOutputRequestKind, ...] = (
    BackendOutputRequestKind.ASSUME_ALIGNED,
    BackendOutputRequestKind.ARRAY_TYPE,
    BackendOutputRequestKind.PACK,
)
_CALL_SHAPED_KINDS = frozenset(
    (
        BackendOutputRequestKind.ASSUME_ALIGNED,
        BackendOutputRequestKind.PACK,
    )
)


def discover_backend_output_requests(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> BackendOutputDiscoveryLoweringResult:
    """Discover exact backend/output islands in raw body-token text."""

    del context

    segments: list[BackendOutputDiscoverySegment] = []
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
        return BackendOutputDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_backend_output_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendOutputOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return BackendOutputDiscoveryLoweringResult(
        discovery=BackendOutputDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_backend_output_requests_in_text(
    text: str,
    source: SourceLocation,
) -> BackendOutputDiscoveryLoweringResult:
    """Discover exact backend/output request islands in one text fragment."""

    return _discover_backend_output_requests_in_source_text(
        source_text_from_text(text, source),
    )


def _flush_raw_run(
    raw_run: JoinedRawStringRun | None,
    segments: list[BackendOutputDiscoverySegment],
    pending_opaque_tokens: OpaqueTokenBuffer,
) -> BackendOutputDiscoveryLoweringResult | None:
    if raw_run is None:
        return None

    text_result = _discover_backend_output_requests_in_source_text(
        raw_run.source_text,
    )
    if _has_malformed_backend_output_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run.tokens)
        return None

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendOutputOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )
    segments.extend(text_result.discovery.segments)
    return None


def _discover_backend_output_requests_in_source_text(
    source_text: SourceMappedText,
) -> BackendOutputDiscoveryLoweringResult:
    segments: list[BackendOutputOpaqueTextSegment | BackendOutputRequestSegment] = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_backend_output = False

    while index < len(text):
        match = _find_next_backend_output_head(text, index)
        if match is None:
            break

        start, kind = match
        parsed = _parse_backend_output_request(source_text, start, kind)
        if parsed.diagnostic is not None:
            return BackendOutputDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(parsed.diagnostic,),
            )

        request = parsed.request
        if request is None:
            break

        if start > index:
            opaque_span = source_text.span(index, start)
            segments.append(
                BackendOutputOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        segments.append(
            BackendOutputRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_backend_output = True
        index = parsed.end_index

    if not found_backend_output:
        return BackendOutputDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_backend_output_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            BackendOutputOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return BackendOutputDiscoveryLoweringResult(
        discovery=BackendOutputDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _ParsedBackendOutputRequest:
    request: BackendOutputRequest | None
    end_index: int
    diagnostic: Diagnostic | None = None


def _parse_backend_output_request(
    source_text: SourceMappedText,
    start: int,
    kind: BackendOutputRequestKind,
) -> _ParsedBackendOutputRequest:
    text = source_text.text
    open_angle_index = start + len(kind.value)
    close_angle_index = matching_delimiter_close(text, open_angle_index, "<", ">")
    if close_angle_index is None:
        return _parsed_malformed_result(
            source_text.source_at(start),
            "missing or mismatched angle delimiters",
        )

    angle_payload_start = open_angle_index + 1
    angle_payload_text = text[angle_payload_start:close_angle_index]
    if not angle_payload_text.strip():
        return _parsed_malformed_result(
            source_text.source_at(start),
            "empty angle payload",
        )

    argument_text: str | None = None
    argument_source: SourceLocation | None = None

    if kind in _CALL_SHAPED_KINDS:
        open_argument_index = close_angle_index + 1
        if open_argument_index >= len(text) or text[open_argument_index] != "(":
            return _parsed_malformed_result(
                source_text.source_at(start),
                "missing argument delimiters",
            )

        close_argument_index = matching_delimiter_close(
            text,
            open_argument_index,
            "(",
            ")",
        )
        if close_argument_index is None:
            return _parsed_malformed_result(
                source_text.source_at(start),
                "missing or mismatched argument delimiters",
            )

        argument_start = open_argument_index + 1
        argument_text = text[argument_start:close_argument_index]
        argument_source = source_text.source_at(argument_start)
        end_index = close_argument_index + 1
    else:
        end_index = close_angle_index + 1
        if end_index < len(text) and text[end_index] == "(":
            return _parsed_malformed_result(
                source_text.source_at(start),
                "unexpected call delimiters for angle-only array_type<...>",
            )

    request = BackendOutputRequest(
        kind=kind,
        angle_payload_text=angle_payload_text,
        angle_payload_source=source_text.source_at(angle_payload_start),
        argument_text=argument_text,
        argument_source=argument_source,
        source_text=text[start:end_index],
        source=source_text.source_at(start),
    )
    return _ParsedBackendOutputRequest(request=request, end_index=end_index)


def _find_next_backend_output_head(
    text: str,
    start: int,
) -> tuple[int, BackendOutputRequestKind] | None:
    for index in range(max(0, start), len(text)):
        for kind in _HEADS:
            if not text.startswith(f"{kind.value}<", index):
                continue
            if has_identifier_boundary_before(text, index):
                return (index, kind)
    return None


def _has_malformed_backend_output_diagnostic(
    result: BackendOutputDiscoveryLoweringResult,
) -> bool:
    return any(diagnostic.code == _FAILURE_CODE for diagnostic in result.diagnostics)


def _parsed_malformed_result(
    source: SourceLocation,
    reason: str,
) -> _ParsedBackendOutputRequest:
    return _ParsedBackendOutputRequest(
        request=None,
        end_index=0,
        diagnostic=_malformed_backend_output_diagnostic(source, reason),
    )


def _malformed_backend_output_diagnostic(
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_FAILURE_CODE,
        message=(
            "backend/output source-island discovery found an "
            "assume_aligned<...>(...), array_type<...>, or pack<...>(...) "
            f"island with an invalid outer shape: {reason}"
        ),
        location=source,
    )


def _no_backend_output_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-BACKEND-OUTPUT-SOURCE-ISLAND",
        message=(
            "backend/output source-island discovery found no exact "
            "assume_aligned<...>(...), array_type<...>, or pack<...>(...) island"
        ),
        location=source,
    )
