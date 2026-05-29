"""Exact backend intrinsic request-island discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    ImplementationBody,
    RawStringToken,
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

_INTRINSIC_HEADS: tuple[BackendIntrinsicKind, ...] = ("intrin_compose", "intrin")
_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


def discover_backend_intrinsic_requests(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> BackendIntrinsicDiscoveryLoweringResult:
    """Discover exact backend intrinsic islands in raw body-token text."""

    del context

    segments: list[BackendIntrinsicDiscoverySegment] = []
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
        return BackendIntrinsicDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_intrinsic_diagnostic(body.source),),
        )

    if pending_opaque_tokens:
        segments.append(
            BackendIntrinsicOpaqueTokenSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
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
    raw_run: list[RawStringToken],
    segments: list[BackendIntrinsicDiscoverySegment],
    pending_opaque_tokens: list[BodyToken],
) -> BackendIntrinsicDiscoveryLoweringResult | None:
    if not raw_run:
        return None

    text, source_map = _raw_run_text_and_source_map(raw_run)
    text_result = _discover_backend_intrinsic_requests_in_text(
        text,
        raw_run[0].source,
        source_at_offset=lambda offset: _source_from_raw_run(
            raw_run[0].source,
            text,
            source_map,
            offset,
        ),
    )
    if _has_malformed_intrinsic_diagnostic(text_result):
        return text_result
    if text_result.discovery is None:
        pending_opaque_tokens.extend(raw_run)
        return None

    if pending_opaque_tokens:
        segments.append(
            BackendIntrinsicOpaqueTokenSegment(
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


def discover_backend_intrinsic_requests_in_text(
    text: str,
    source: SourceLocation,
) -> BackendIntrinsicDiscoveryLoweringResult:
    """Discover exact backend intrinsic request islands in one text fragment."""

    return _discover_backend_intrinsic_requests_in_text(
        text,
        source,
        source_at_offset=lambda offset: _source_at_offset(source, text, offset),
    )


def _discover_backend_intrinsic_requests_in_text(
    text: str,
    source: SourceLocation,
    *,
    source_at_offset,
) -> BackendIntrinsicDiscoveryLoweringResult:
    segments: list[BackendIntrinsicOpaqueTextSegment | BackendIntrinsicRequestSegment]
    segments = []
    index = 0
    found_intrinsic = False

    while index < len(text):
        match = _find_next_intrinsic_head(text, index)
        if match is None:
            break

        start, intrinsic_kind = match
        open_angle_index = start + len(intrinsic_kind)
        close_angle_index = _matching_close(text, open_angle_index, "<", ">")
        if close_angle_index is None:
            return _malformed_intrinsic_result(source_at_offset(start))

        open_argument_index = close_angle_index + 1
        if (
            open_argument_index >= len(text)
            or text[open_argument_index] != "("
        ):
            return _malformed_intrinsic_result(source_at_offset(start))

        close_argument_index = _matching_close(
            text,
            open_argument_index,
            "(",
            ")",
        )
        if close_argument_index is None:
            return _malformed_intrinsic_result(source_at_offset(start))

        angle_payload_start = open_angle_index + 1
        if not text[angle_payload_start:close_angle_index].strip():
            return _malformed_intrinsic_result(source_at_offset(start))

        if start > index:
            segments.append(
                BackendIntrinsicOpaqueTextSegment(
                    text=text[index:start],
                    source=source_at_offset(index),
                )
            )

        argument_start = open_argument_index + 1
        request = BackendIntrinsicRequest(
            intrinsic_kind=intrinsic_kind,
            angle_payload_text=text[angle_payload_start:close_angle_index],
            angle_payload_source=source_at_offset(angle_payload_start),
            argument_text=text[argument_start:close_argument_index],
            argument_source=source_at_offset(argument_start),
            source_text=text[start : close_argument_index + 1],
            source=source_at_offset(start),
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
        segments.append(
            BackendIntrinsicOpaqueTextSegment(
                text=text[index:],
                source=source_at_offset(index),
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
            if _has_identifier_boundary_before(text, index):
                return (index, intrinsic_kind)
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


def _has_malformed_intrinsic_diagnostic(
    result: BackendIntrinsicDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-BACKEND-INTRINSIC"
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


def _malformed_intrinsic_result(source: SourceLocation) -> BackendIntrinsicDiscoveryLoweringResult:
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
