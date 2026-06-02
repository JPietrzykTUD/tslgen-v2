"""C++ body-token rendering by substituting rendered backend intrinsic islands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.backends.intrinsic_invocations import BackendIntrinsicInvocationImmediate
from tslgen.backends.cpp.intrinsic_calls import CppRenderedIntrinsicCall
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.lowering.model import (
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicOpaqueTokenSegment,
)

CppBodyText = NewType("CppBodyText", str)


@dataclass(frozen=True, slots=True)
class CppRenderedBodyTokens:
    handoff: BackendIntrinsicHandoff
    text: CppBodyText
    calls: tuple[CppRenderedIntrinsicCall, ...]
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CppBodyTokenRenderResult:
    body: CppRenderedBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_cpp_body_tokens_from_intrinsic_handoff(
    handoff: BackendIntrinsicHandoff,
    rendered_calls: tuple[CppRenderedIntrinsicCall, ...],
) -> CppBodyTokenRenderResult:
    """Render a body token stream by replacing intrinsic request segments."""

    diagnostics: list[Diagnostic] = []
    request_segments = tuple(_request_segments(handoff))
    required_request_ids = {id(segment.request): segment for segment in request_segments}
    rendered_by_request_id: dict[int, CppRenderedIntrinsicCall] = {}

    for segment in handoff.segments:
        if isinstance(segment, BackendIntrinsicOpaqueTokenSegment):
            diagnostics.append(_unsupported_opaque_token_segment_diagnostic(segment))

    for call in rendered_calls:
        request = _call_request(call)
        request_id = id(request)

        if str(call.invocation.backend) != "cpp":
            diagnostics.append(_backend_mismatch_diagnostic(call))
            continue

        if request_id not in required_request_ids:
            diagnostics.append(_extra_call_diagnostic(call))
            continue

        if request_id in rendered_by_request_id:
            diagnostics.append(_duplicate_call_diagnostic(call))
            continue

        rendered_by_request_id[request_id] = call

    for segment in request_segments:
        if id(segment.request) not in rendered_by_request_id:
            diagnostics.append(_missing_call_diagnostic(segment))

    if diagnostics:
        return CppBodyTokenRenderResult(body=None, diagnostics=tuple(diagnostics))

    pieces: list[str] = []
    ordered_calls: list[CppRenderedIntrinsicCall] = []
    for segment in handoff.segments:
        if isinstance(segment, BackendIntrinsicOpaqueTextSegment):
            pieces.append(segment.text)
            continue

        if isinstance(segment, BackendIntrinsicHandoffRequestSegment):
            call = rendered_by_request_id[id(segment.request)]
            pieces.append(str(call.call_text))
            ordered_calls.append(call)

    return CppBodyTokenRenderResult(
        body=CppRenderedBodyTokens(
            handoff=handoff,
            text=CppBodyText("".join(pieces)),
            calls=tuple(ordered_calls),
            immediates=tuple(
                immediate for call in ordered_calls for immediate in call.immediates
            ),
            source=handoff.source,
        ),
        diagnostics=(),
    )


def _request_segments(
    handoff: BackendIntrinsicHandoff,
) -> tuple[BackendIntrinsicHandoffRequestSegment, ...]:
    return tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    )


def _call_request(call: CppRenderedIntrinsicCall) -> BackendIntrinsicHandoffRequest:
    return call.invocation.request


def _missing_call_diagnostic(
    segment: BackendIntrinsicHandoffRequestSegment,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-BODY-TOKENS-MISSING-INTRINSIC-CALL",
        message=(
            "C++ body token rendering needs a rendered intrinsic call for each "
            "backend intrinsic request segment"
        ),
        location=segment.source,
    )


def _extra_call_diagnostic(call: CppRenderedIntrinsicCall) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-BODY-TOKENS-EXTRA-INTRINSIC-CALL",
        message=(
            "C++ body token rendering received a rendered intrinsic call whose "
            "request is not present in the handoff stream"
        ),
        location=call.source,
    )


def _duplicate_call_diagnostic(call: CppRenderedIntrinsicCall) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-BODY-TOKENS-DUPLICATE-INTRINSIC-CALL",
        message=(
            "C++ body token rendering received more than one rendered intrinsic "
            "call for the same handoff request segment"
        ),
        location=call.source,
    )


def _backend_mismatch_diagnostic(call: CppRenderedIntrinsicCall) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-BODY-TOKENS-BACKEND-MISMATCH",
        message=(
            "C++ body token rendering accepts only rendered intrinsic calls for "
            f"backend 'cpp'; got {str(call.invocation.backend)!r}"
        ),
        location=call.source,
    )


def _unsupported_opaque_token_segment_diagnostic(
    segment: BackendIntrinsicOpaqueTokenSegment,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-BODY-TOKENS-UNSUPPORTED-OPAQUE-TOKEN-SEGMENT",
        message=(
            "C++ body token rendering cannot stringify opaque non-text body "
            "tokens; lower or render those tokens before body substitution"
        ),
        location=segment.source,
    )
