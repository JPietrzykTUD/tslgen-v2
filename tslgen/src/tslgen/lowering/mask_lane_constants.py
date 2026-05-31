"""Exact mask lane constant request-island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import ImplementationBody, RawStringToken
from tslgen.lowering._source_islands import (
    JoinedRawStringRun,
    OpaqueTokenBuffer,
    RawStringRunBuffer,
    SourceMappedText,
    matching_delimiter_close,
    source_text_from_text,
)
from tslgen.lowering.model import (
    MaskLaneConstantDiscovery,
    MaskLaneConstantDiscoveryLoweringResult,
    MaskLaneConstantDiscoverySegment,
    MaskLaneConstantOpaqueTextSegment,
    MaskLaneConstantOpaqueTokenSegment,
    MaskLaneConstantPolarity,
    MaskLaneConstantRequest,
    MaskLaneConstantRequestSegment,
    SelectedImplementationLoweringContext,
)

_VALUE_HEAD = "value<generation>"
_VALUE_PREFIX = f"{_VALUE_HEAD}("
_MASK_LANE_PREFIX = "mask::lane::"
_FAILURE_CODES = frozenset(
    (
        "TSL-LOWER-MALFORMED-MASK-LANE-CONSTANT",
        "TSL-LOWER-UNKNOWN-MASK-LANE-CONSTANT",
    )
)


def discover_mask_lane_constant_requests(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> MaskLaneConstantDiscoveryLoweringResult:
    """Discover exact mask lane constant islands in raw body-token text."""

    del context

    segments: list[MaskLaneConstantDiscoverySegment] = []
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
        return MaskLaneConstantDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_mask_lane_constant_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            MaskLaneConstantOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return MaskLaneConstantDiscoveryLoweringResult(
        discovery=MaskLaneConstantDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def _flush_raw_run(
    raw_run: JoinedRawStringRun | None,
    segments: list[MaskLaneConstantDiscoverySegment],
    pending_opaque_tokens: OpaqueTokenBuffer,
) -> MaskLaneConstantDiscoveryLoweringResult | None:
    if raw_run is None:
        return None

    text_result = _discover_mask_lane_constant_requests_in_source_text(
        raw_run.source_text,
    )
    if _has_failure_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run.tokens)
        return None

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            MaskLaneConstantOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )
    segments.extend(text_result.discovery.segments)
    return None


def discover_mask_lane_constant_requests_in_text(
    text: str,
    source: SourceLocation,
) -> MaskLaneConstantDiscoveryLoweringResult:
    """Discover exact mask lane constant request islands in one text fragment."""

    return _discover_mask_lane_constant_requests_in_source_text(
        source_text_from_text(text, source),
    )


def _discover_mask_lane_constant_requests_in_source_text(
    source_text: SourceMappedText,
) -> MaskLaneConstantDiscoveryLoweringResult:
    segments: list[MaskLaneConstantOpaqueTextSegment | MaskLaneConstantRequestSegment]
    segments = []
    text = source_text.text
    source = source_text.source
    search_index = 0
    segment_start = 0
    found_request = False

    while search_index < len(text):
        start = text.find(_VALUE_PREFIX, search_index)
        if start == -1:
            break

        payload_start = start + len(_VALUE_PREFIX)
        if not text.startswith(_MASK_LANE_PREFIX, payload_start):
            search_index = payload_start
            continue

        open_index = start + len(_VALUE_HEAD)
        close_index = matching_delimiter_close(text, open_index, "(", ")")
        if close_index is None:
            return _malformed_mask_lane_constant_result(source_text.source_at(start))

        payload_text = text[payload_start:close_index]
        lane_name = payload_text.removeprefix(_MASK_LANE_PREFIX)
        polarity = _polarity_for_lane_name(lane_name)
        if polarity is None:
            return _unknown_mask_lane_constant_result(
                lane_name,
                source_text.source_at(payload_start + len(_MASK_LANE_PREFIX)),
            )

        if start > segment_start:
            opaque_span = source_text.span(segment_start, start)
            segments.append(
                MaskLaneConstantOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        request = MaskLaneConstantRequest(
            polarity=polarity,
            source_text=text[start : close_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            MaskLaneConstantRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_request = True
        search_index = close_index + 1
        segment_start = close_index + 1

    if not found_request:
        return MaskLaneConstantDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_mask_lane_constant_diagnostic(source),),
        )

    if segment_start < len(text):
        opaque_span = source_text.span(segment_start, len(text))
        segments.append(
            MaskLaneConstantOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return MaskLaneConstantDiscoveryLoweringResult(
        discovery=MaskLaneConstantDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


def _polarity_for_lane_name(lane_name: str) -> MaskLaneConstantPolarity | None:
    if lane_name == "all_true":
        return "all_true"
    if lane_name == "all_false":
        return "all_false"
    return None


def _has_failure_diagnostic(
    result: MaskLaneConstantDiscoveryLoweringResult,
) -> bool:
    return any(diagnostic.code in _FAILURE_CODES for diagnostic in result.diagnostics)


def _malformed_mask_lane_constant_result(
    source: SourceLocation,
) -> MaskLaneConstantDiscoveryLoweringResult:
    return MaskLaneConstantDiscoveryLoweringResult(
        discovery=None,
        diagnostics=(_malformed_mask_lane_constant_diagnostic(source),),
    )


def _unknown_mask_lane_constant_result(
    lane_name: str,
    source: SourceLocation,
) -> MaskLaneConstantDiscoveryLoweringResult:
    return MaskLaneConstantDiscoveryLoweringResult(
        discovery=None,
        diagnostics=(_unknown_mask_lane_constant_diagnostic(lane_name, source),),
    )


def _malformed_mask_lane_constant_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-MASK-LANE-CONSTANT",
        message=(
            "mask lane constant discovery found a "
            "value<generation>(mask::lane::...) island with an unbalanced "
            "outer payload"
        ),
        location=source,
    )


def _unknown_mask_lane_constant_diagnostic(
    lane_name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNKNOWN-MASK-LANE-CONSTANT",
        message=(
            "mask lane constant discovery found unsupported mask lane "
            f"constant {lane_name!r}; expected one of: all_false, all_true"
        ),
        location=source,
    )


def _no_mask_lane_constant_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-MASK-LANE-CONSTANT",
        message=(
            "mask lane constant discovery found no exact "
            "value<generation>(mask::lane::all_true) or "
            "value<generation>(mask::lane::all_false) island"
        ),
        location=source,
    )
