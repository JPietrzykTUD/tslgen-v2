"""Exact mask keyword request/selector boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import BodyToken, RawStringToken
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
from tslgen.syntax.source_body_fragments import SourceBodyFragmentSequence

_MASK_HEAD = "mask"
_MASK_PREFIX = f"{_MASK_HEAD}<"
_FAILURE_CODES = frozenset(
    (
        "TSL-LOWER-MALFORMED-MASK-KEYWORD",
        "TSL-LOWER-UNSUPPORTED-MASK-KEYWORD-SELECTOR",
    )
)


class MaskKeywordSelector(Enum):
    ZERO = "zero"
    TEST = "test"
    SET = "set"
    SET_ONE = "set:1"


@dataclass(frozen=True, slots=True)
class MaskKeywordRequest:
    selector: MaskKeywordSelector
    selector_source: SourceLocation
    argument_text: str
    argument_source: SourceLocation
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskKeywordOpaqueTextSegment:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskKeywordOpaqueTokenSegment:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskKeywordRequestSegment:
    request: MaskKeywordRequest
    source: SourceLocation


MaskKeywordDiscoverySegment = (
    MaskKeywordOpaqueTextSegment
    | MaskKeywordOpaqueTokenSegment
    | MaskKeywordRequestSegment
)


@dataclass(frozen=True, slots=True)
class MaskKeywordDiscovery:
    segments: tuple[MaskKeywordDiscoverySegment, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class MaskKeywordDiscoveryLoweringResult:
    discovery: MaskKeywordDiscovery | None
    diagnostics: tuple[Diagnostic, ...]


def discover_mask_keyword_requests(
    context: SelectedImplementationLoweringContext,
) -> MaskKeywordDiscoveryLoweringResult:
    """Discover exact mask<...>(...) islands in raw body-token text."""

    if context.implementation.source_body_fragments is not None:
        return discover_mask_keyword_requests_in_fragments(
            context,
            context.implementation.source_body_fragments,
        )

    body = context.implementation.body
    segments: list[MaskKeywordDiscoverySegment] = []
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
        return MaskKeywordDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_mask_keyword_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            MaskKeywordOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return MaskKeywordDiscoveryLoweringResult(
        discovery=MaskKeywordDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_mask_keyword_requests_in_text(
    text: str,
    source: SourceLocation,
) -> MaskKeywordDiscoveryLoweringResult:
    """Discover exact mask<...>(...) request islands in one text fragment."""

    return _discover_mask_keyword_requests_in_source_text(
        source_text_from_text(text, source),
    )


def discover_mask_keyword_requests_in_fragments(
    context: SelectedImplementationLoweringContext,
    sequence: SourceBodyFragmentSequence,
) -> MaskKeywordDiscoveryLoweringResult:
    """Discover mask keyword requests from recursive source-body fragments."""

    del context

    return _discover_mask_keyword_requests_in_source_text(
        source_text_from_text(
            sequence.source_text.text,
            sequence.source_text.source_at(0),
        )
    )


def _flush_raw_run(
    raw_run: JoinedRawStringRun | None,
    segments: list[MaskKeywordDiscoverySegment],
    pending_opaque_tokens: OpaqueTokenBuffer,
) -> MaskKeywordDiscoveryLoweringResult | None:
    if raw_run is None:
        return None

    text_result = _discover_mask_keyword_requests_in_source_text(raw_run.source_text)
    if _has_failure_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run.tokens)
        return None

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            MaskKeywordOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )
    segments.extend(text_result.discovery.segments)
    return None


def _discover_mask_keyword_requests_in_source_text(
    source_text: SourceMappedText,
) -> MaskKeywordDiscoveryLoweringResult:
    segments: list[MaskKeywordOpaqueTextSegment | MaskKeywordRequestSegment] = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_mask_keyword = False

    while index < len(text):
        start = _find_next_mask_keyword_head(text, index)
        if start is None:
            break

        open_angle_index = start + len(_MASK_HEAD)
        close_angle_index = matching_delimiter_close(text, open_angle_index, "<", ">")
        if close_angle_index is None:
            return _malformed_mask_keyword_result(source_text.source_at(start))

        open_argument_index = close_angle_index + 1
        if open_argument_index >= len(text) or text[open_argument_index] != "(":
            return _malformed_mask_keyword_result(source_text.source_at(start))

        close_argument_index = matching_delimiter_close(
            text,
            open_argument_index,
            "(",
            ")",
        )
        if close_argument_index is None:
            return _malformed_mask_keyword_result(source_text.source_at(start))

        selector_start = open_angle_index + 1
        selector_text = text[selector_start:close_angle_index]
        selector = _selector_for_text(selector_text)
        if selector is None:
            return _unsupported_selector_result(
                selector_text,
                source_text.source_at(selector_start),
            )

        if start > index:
            opaque_span = source_text.span(index, start)
            segments.append(
                MaskKeywordOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        argument_start = open_argument_index + 1
        request = MaskKeywordRequest(
            selector=selector,
            selector_source=source_text.source_at(selector_start),
            argument_text=text[argument_start:close_argument_index],
            argument_source=source_text.source_at(argument_start),
            source_text=text[start : close_argument_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            MaskKeywordRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_mask_keyword = True
        index = close_argument_index + 1

    if not found_mask_keyword:
        return MaskKeywordDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_mask_keyword_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            MaskKeywordOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return MaskKeywordDiscoveryLoweringResult(
        discovery=MaskKeywordDiscovery(
            segments=tuple(segments),
            source=source,
        ),
        diagnostics=(),
    )


def _find_next_mask_keyword_head(text: str, start: int) -> int | None:
    for index in range(max(0, start), len(text)):
        if not text.startswith(_MASK_PREFIX, index):
            continue
        if has_identifier_boundary_before(text, index):
            return index
    return None


def _selector_for_text(selector_text: str) -> MaskKeywordSelector | None:
    for selector in MaskKeywordSelector:
        if selector.value == selector_text:
            return selector
    return None


def _has_failure_diagnostic(result: MaskKeywordDiscoveryLoweringResult) -> bool:
    return any(diagnostic.code in _FAILURE_CODES for diagnostic in result.diagnostics)


def _malformed_mask_keyword_result(
    source: SourceLocation,
) -> MaskKeywordDiscoveryLoweringResult:
    return MaskKeywordDiscoveryLoweringResult(
        discovery=None,
        diagnostics=(_malformed_mask_keyword_diagnostic(source),),
    )


def _unsupported_selector_result(
    selector_text: str,
    source: SourceLocation,
) -> MaskKeywordDiscoveryLoweringResult:
    return MaskKeywordDiscoveryLoweringResult(
        discovery=None,
        diagnostics=(_unsupported_selector_diagnostic(selector_text, source),),
    )


def _malformed_mask_keyword_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-MASK-KEYWORD",
        message=(
            "mask keyword discovery found a mask<...>(...) island with an "
            "unbalanced or incomplete outer shape"
        ),
        location=source,
    )


def _unsupported_selector_diagnostic(
    selector_text: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-MASK-KEYWORD-SELECTOR",
        message=(
            "unsupported mask keyword selector "
            f"{_display_selector(selector_text)}; expected one of "
            "set, set:1, test, zero"
        ),
        location=source,
    )


def _no_mask_keyword_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-MASK-KEYWORD",
        message="mask keyword discovery found no exact mask<...>(...) island",
        location=source,
    )


def _display_selector(selector_text: str) -> str:
    if not selector_text:
        return "<empty>"
    return repr(selector_text)
