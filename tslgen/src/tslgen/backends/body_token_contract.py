"""Shared intrinsic body-token substitution contract for backend renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.backends.intrinsic_invocations import BackendIntrinsicInvocationImmediate
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.lowering.model import (
    BackendIntrinsicHandoff,
    BackendIntrinsicHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicOpaqueTextSegment,
    BackendIntrinsicOpaqueTokenSegment,
)

BodyTokenText = NewType("BodyTokenText", str)
BodyTokenRenderedIntrinsicCallText = NewType(
    "BodyTokenRenderedIntrinsicCallText",
    str,
)


@dataclass(frozen=True, slots=True)
class BodyTokenRenderedIntrinsicCall:
    backend: BackendId
    request: BackendIntrinsicHandoffRequest
    text: BodyTokenRenderedIntrinsicCallText
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BodyTokenRenderPolicy:
    backend: BackendId
    backend_label: str
    diagnostic_code_prefix: str


@dataclass(frozen=True, slots=True)
class RenderedIntrinsicBodyTokens:
    handoff: BackendIntrinsicHandoff
    text: BodyTokenText
    calls: tuple[BodyTokenRenderedIntrinsicCall, ...]
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BodyTokenRenderContractResult:
    body: RenderedIntrinsicBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_intrinsic_body_tokens_from_handoff(
    handoff: BackendIntrinsicHandoff,
    rendered_calls: tuple[BodyTokenRenderedIntrinsicCall, ...],
    policy: BodyTokenRenderPolicy,
) -> BodyTokenRenderContractResult:
    """Substitute intrinsic request segments with already-rendered call text."""

    diagnostics: list[Diagnostic] = []
    request_segments = tuple(_request_segments(handoff))
    required_request_ids = {id(segment.request): segment for segment in request_segments}
    rendered_by_request_id: dict[int, BodyTokenRenderedIntrinsicCall] = {}

    for segment in handoff.segments:
        if isinstance(segment, BackendIntrinsicOpaqueTokenSegment):
            diagnostics.append(
                _unsupported_opaque_token_segment_diagnostic(segment, policy)
            )

    for call in rendered_calls:
        request_id = id(call.request)

        if str(call.backend) != str(policy.backend):
            diagnostics.append(_backend_mismatch_diagnostic(call, policy))
            continue

        if request_id not in required_request_ids:
            diagnostics.append(_extra_call_diagnostic(call, policy))
            continue

        if request_id in rendered_by_request_id:
            diagnostics.append(_duplicate_call_diagnostic(call, policy))
            continue

        rendered_by_request_id[request_id] = call

    for segment in request_segments:
        if id(segment.request) not in rendered_by_request_id:
            diagnostics.append(_missing_call_diagnostic(segment, policy))

    if diagnostics:
        return BodyTokenRenderContractResult(body=None, diagnostics=tuple(diagnostics))

    pieces: list[str] = []
    ordered_calls: list[BodyTokenRenderedIntrinsicCall] = []
    for segment in handoff.segments:
        if isinstance(segment, BackendIntrinsicOpaqueTextSegment):
            pieces.append(segment.text)
            continue

        if isinstance(segment, BackendIntrinsicHandoffRequestSegment):
            call = rendered_by_request_id[id(segment.request)]
            pieces.append(str(call.text))
            ordered_calls.append(call)

    return BodyTokenRenderContractResult(
        body=RenderedIntrinsicBodyTokens(
            handoff=handoff,
            text=BodyTokenText("".join(pieces)),
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


def _diagnostic_code(policy: BodyTokenRenderPolicy, suffix: str) -> str:
    return f"{policy.diagnostic_code_prefix}-{suffix}"


def _missing_call_diagnostic(
    segment: BackendIntrinsicHandoffRequestSegment,
    policy: BodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "MISSING-INTRINSIC-CALL"),
        message=(
            f"{policy.backend_label} body token rendering needs a rendered "
            "intrinsic call for each backend intrinsic request segment"
        ),
        location=segment.source,
    )


def _extra_call_diagnostic(
    call: BodyTokenRenderedIntrinsicCall,
    policy: BodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "EXTRA-INTRINSIC-CALL"),
        message=(
            f"{policy.backend_label} body token rendering received a rendered "
            "intrinsic call whose request is not present in the handoff stream"
        ),
        location=call.source,
    )


def _duplicate_call_diagnostic(
    call: BodyTokenRenderedIntrinsicCall,
    policy: BodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "DUPLICATE-INTRINSIC-CALL"),
        message=(
            f"{policy.backend_label} body token rendering received more than "
            "one rendered intrinsic call for the same handoff request segment"
        ),
        location=call.source,
    )


def _backend_mismatch_diagnostic(
    call: BodyTokenRenderedIntrinsicCall,
    policy: BodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "BACKEND-MISMATCH"),
        message=(
            f"{policy.backend_label} body token rendering accepts only "
            f"rendered intrinsic calls for backend {str(policy.backend)!r}; "
            f"got {str(call.backend)!r}"
        ),
        location=call.source,
    )


def _unsupported_opaque_token_segment_diagnostic(
    segment: BackendIntrinsicOpaqueTokenSegment,
    policy: BodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "UNSUPPORTED-OPAQUE-TOKEN-SEGMENT"),
        message=(
            f"{policy.backend_label} body token rendering cannot stringify "
            "opaque non-text body tokens; lower or render those tokens before "
            "body substitution"
        ),
        location=segment.source,
    )
