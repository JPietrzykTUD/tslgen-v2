"""Exact backend intrinsic request-island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
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
    BackendIntrinsicDiscovery,
    BackendIntrinsicDiscoveryLoweringResult,
    BackendIntrinsicDiscoverySegment,
    BackendIntrinsicKind,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicOpaqueTokenSegment,
    BackendIntrinsicRequest,
    BackendIntrinsicRequestSegment,
    SelectedImplementationLoweringContext,
)
from tslgen.syntax.source_body_fragments import SourceBodyFragmentSequence

_INTRINSIC_HEADS: tuple[BackendIntrinsicKind, ...] = ("intrin_compose", "intrin")


def discover_backend_intrinsic_requests(
    context: SelectedImplementationLoweringContext,
) -> BackendIntrinsicDiscoveryLoweringResult:
    """Discover exact backend intrinsic islands in raw body-token text."""

    if context.implementation.source_body_fragments is not None:
        return discover_backend_intrinsic_requests_in_fragments(
            context,
            context.implementation.source_body_fragments,
        )

    body = context.implementation.body
    segments: list[BackendIntrinsicDiscoverySegment] = []
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
        return BackendIntrinsicDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_intrinsic_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendIntrinsicOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return BackendIntrinsicDiscoveryLoweringResult(
        discovery=BackendIntrinsicDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def _flush_raw_run(
    raw_run: JoinedRawStringRun | None,
    segments: list[BackendIntrinsicDiscoverySegment],
    pending_opaque_tokens: OpaqueTokenBuffer,
) -> BackendIntrinsicDiscoveryLoweringResult | None:
    if raw_run is None:
        return None

    text_result = _discover_backend_intrinsic_requests_in_source_text(
        raw_run.source_text,
    )
    if _has_malformed_intrinsic_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run.tokens)
        return None

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendIntrinsicOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )
    segments.extend(text_result.discovery.segments)
    return None


def discover_backend_intrinsic_requests_in_text(
    text: str,
    source: SourceLocation,
) -> BackendIntrinsicDiscoveryLoweringResult:
    """Discover exact backend intrinsic request islands in one text fragment."""

    return _discover_backend_intrinsic_requests_in_source_text(
        source_text_from_text(text, source),
    )


def discover_backend_intrinsic_requests_in_fragments(
    context: SelectedImplementationLoweringContext,
    sequence: SourceBodyFragmentSequence,
) -> BackendIntrinsicDiscoveryLoweringResult:
    """Discover backend intrinsic requests from recursive source-body fragments."""

    del context

    return _discover_backend_intrinsic_requests_in_source_text(
        source_text_from_text(
            sequence.source_text.text,
            sequence.source_text.source_at(0),
        )
    )


def _discover_backend_intrinsic_requests_in_source_text(
    source_text: SourceMappedText,
) -> BackendIntrinsicDiscoveryLoweringResult:
    segments: list[BackendIntrinsicOpaqueTextSegment | BackendIntrinsicRequestSegment]
    segments = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_intrinsic = False

    while index < len(text):
        match = _find_next_intrinsic_head(text, index)
        if match is None:
            break

        start, intrinsic_kind = match
        open_angle_index = start + len(intrinsic_kind)
        close_angle_index = matching_delimiter_close(text, open_angle_index, "<", ">")
        if close_angle_index is None:
            return _malformed_intrinsic_result(source_text.source_at(start))

        open_argument_index = close_angle_index + 1
        if (
            open_argument_index >= len(text)
            or text[open_argument_index] != "("
        ):
            return _malformed_intrinsic_result(source_text.source_at(start))

        close_argument_index = matching_delimiter_close(
            text,
            open_argument_index,
            "(",
            ")",
        )
        if close_argument_index is None:
            return _malformed_intrinsic_result(source_text.source_at(start))

        angle_payload_start = open_angle_index + 1
        if not text[angle_payload_start:close_angle_index].strip():
            return _malformed_intrinsic_result(source_text.source_at(start))

        if start > index:
            opaque_span = source_text.span(index, start)
            segments.append(
                BackendIntrinsicOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        argument_start = open_argument_index + 1
        request = BackendIntrinsicRequest(
            intrinsic_kind=intrinsic_kind,
            angle_payload_text=text[angle_payload_start:close_angle_index],
            angle_payload_source=source_text.source_at(angle_payload_start),
            argument_text=text[argument_start:close_argument_index],
            argument_source=source_text.source_at(argument_start),
            source_text=text[start : close_argument_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            BackendIntrinsicRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_intrinsic = True
        index = close_argument_index + 1

    if not found_intrinsic:
        return BackendIntrinsicDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_intrinsic_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            BackendIntrinsicOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return BackendIntrinsicDiscoveryLoweringResult(
        discovery=BackendIntrinsicDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


def _find_next_intrinsic_head(
    text: str,
    start: int,
) -> tuple[int, BackendIntrinsicKind] | None:
    for index in range(max(0, start), len(text)):
        for intrinsic_kind in _INTRINSIC_HEADS:
            if not text.startswith(f"{intrinsic_kind}<", index):
                continue
            if has_identifier_boundary_before(text, index):
                return (index, intrinsic_kind)
    return None


def _has_malformed_intrinsic_diagnostic(
    result: BackendIntrinsicDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-BACKEND-INTRINSIC"
        for diagnostic in result.diagnostics
    )


def _malformed_intrinsic_result(
    source: SourceLocation,
) -> BackendIntrinsicDiscoveryLoweringResult:
    return BackendIntrinsicDiscoveryLoweringResult(
        discovery=None,
        diagnostics=(_malformed_intrinsic_diagnostic(source),),
    )


def _malformed_intrinsic_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-INTRINSIC",
        message=(
            "backend intrinsic discovery found an intrin<...>(...) or "
            "intrin_compose<...>(...) island with an unbalanced or incomplete "
            "outer shape"
        ),
        location=source,
    )


def _no_intrinsic_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-BACKEND-INTRINSIC",
        message=(
            "backend intrinsic discovery found no exact intrin<...>(...) or "
            "intrin_compose<...>(...) island"
        ),
        location=source,
    )
