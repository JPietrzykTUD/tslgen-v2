"""Exact mask lane constant request-island discovery."""

from __future__ import annotations

from collections.abc import Callable

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import BodyToken, ImplementationBody, RawStringToken
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
        return MaskLaneConstantDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_mask_lane_constant_diagnostic(body.source),),
        )

    if pending_opaque_tokens:
        segments.append(
            MaskLaneConstantOpaqueTokenSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
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
    raw_run: list[RawStringToken],
    segments: list[MaskLaneConstantDiscoverySegment],
    pending_opaque_tokens: list[BodyToken],
) -> MaskLaneConstantDiscoveryLoweringResult | None:
    if not raw_run:
        return None

    text, source_map = _raw_run_text_and_source_map(raw_run)
    text_result = _discover_mask_lane_constant_requests_in_text(
        text,
        raw_run[0].source,
        source_at_offset=lambda offset: _source_from_raw_run(
            raw_run[0].source,
            text,
            source_map,
            offset,
        ),
    )
    if _has_failure_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run)
        return None

    if pending_opaque_tokens:
        segments.append(
            MaskLaneConstantOpaqueTokenSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
            )
        )
        pending_opaque_tokens.clear()
    segments.extend(text_result.discovery.segments)
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


def discover_mask_lane_constant_requests_in_text(
    text: str,
    source: SourceLocation,
) -> MaskLaneConstantDiscoveryLoweringResult:
    """Discover exact mask lane constant request islands in one text fragment."""

    return _discover_mask_lane_constant_requests_in_text(
        text,
        source,
        source_at_offset=lambda offset: _source_at_offset(source, text, offset),
    )


def _discover_mask_lane_constant_requests_in_text(
    text: str,
    source: SourceLocation,
    *,
    source_at_offset: Callable[[int], SourceLocation],
) -> MaskLaneConstantDiscoveryLoweringResult:
    segments: list[MaskLaneConstantOpaqueTextSegment | MaskLaneConstantRequestSegment]
    segments = []
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
        close_index = _matching_value_close(text, open_index)
        if close_index is None:
            return _malformed_mask_lane_constant_result(source_at_offset(start))

        payload_text = text[payload_start:close_index]
        lane_name = payload_text.removeprefix(_MASK_LANE_PREFIX)
        polarity = _polarity_for_lane_name(lane_name)
        if polarity is None:
            return _unknown_mask_lane_constant_result(
                lane_name,
                source_at_offset(payload_start + len(_MASK_LANE_PREFIX)),
            )

        if start > segment_start:
            segments.append(
                MaskLaneConstantOpaqueTextSegment(
                    text=text[segment_start:start],
                    source=source_at_offset(segment_start),
                )
            )

        request = MaskLaneConstantRequest(
            polarity=polarity,
            source_text=text[start : close_index + 1],
            source=source_at_offset(start),
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
        segments.append(
            MaskLaneConstantOpaqueTextSegment(
                text=text[segment_start:],
                source=source_at_offset(segment_start),
            )
        )

    return MaskLaneConstantDiscoveryLoweringResult(
        discovery=MaskLaneConstantDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


def _matching_value_close(text: str, open_index: int) -> int | None:
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
