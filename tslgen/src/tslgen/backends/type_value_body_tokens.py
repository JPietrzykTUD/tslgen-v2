"""Shared backend type/value body-token substitution for backend renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NewType

from tslgen.backends.type_spelling import BackendTranslatedTypeSpelling
from tslgen.backends.value_translation import BackendTranslatedValue
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.lowering.model import (
    BackendTypeQueryHandoff,
    BackendTypeQueryHandoffRequestSegment,
    BackendTypeQueryOpaqueTextSegment,
    BackendTypeQueryOpaqueTokenSegment,
    BackendTypeSpellingRequest,
    BackendValueQueryHandoff,
    BackendValueQueryHandoffRequestSegment,
    BackendValueQueryOpaqueTextSegment,
    BackendValueQueryOpaqueTokenSegment,
    BackendValueRequest,
)

BodyTokenTypeValueText = NewType("BodyTokenTypeValueText", str)
BodyTokenRenderedTypeValueText = NewType("BodyTokenRenderedTypeValueText", str)
BodyTokenTypeValueKind = Literal["type", "value"]
BodyTokenTypeValueRequest = BackendTypeSpellingRequest | BackendValueRequest
BodyTokenTypeValueHandoff = BackendTypeQueryHandoff | BackendValueQueryHandoff
BodyTokenTranslatedTypeValue = BackendTranslatedTypeSpelling | BackendTranslatedValue


@dataclass(frozen=True, slots=True)
class BodyTokenRenderedTypeValue:
    kind: BodyTokenTypeValueKind
    backend: BackendId
    request: BodyTokenTypeValueRequest
    text: BodyTokenRenderedTypeValueText
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class TypeValueBodyTokenRenderPolicy:
    backend: BackendId
    backend_label: str
    diagnostic_code_prefix: str


@dataclass(frozen=True, slots=True)
class RenderedTypeValueBodyTokens:
    kind: BodyTokenTypeValueKind
    handoff: BodyTokenTypeValueHandoff
    text: BodyTokenTypeValueText
    values: tuple[BodyTokenRenderedTypeValue, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class TypeValueBodyTokenRenderResult:
    body: RenderedTypeValueBodyTokens | None
    diagnostics: tuple[Diagnostic, ...] = ()


def rendered_type_spelling_value(
    spelling: BackendTranslatedTypeSpelling,
) -> BodyTokenRenderedTypeValue:
    return BodyTokenRenderedTypeValue(
        kind="type",
        backend=spelling.backend,
        request=spelling.request,
        text=BodyTokenRenderedTypeValueText(str(spelling.spelling)),
        source=spelling.source,
    )


def rendered_backend_value(
    value: BackendTranslatedValue,
) -> BodyTokenRenderedTypeValue:
    return BodyTokenRenderedTypeValue(
        kind="value",
        backend=value.backend,
        request=value.request,
        text=BodyTokenRenderedTypeValueText(str(value.value)),
        source=value.source,
    )


def render_type_body_tokens_from_handoff(
    handoff: BackendTypeQueryHandoff,
    rendered_values: tuple[BodyTokenRenderedTypeValue, ...],
    policy: TypeValueBodyTokenRenderPolicy,
) -> TypeValueBodyTokenRenderResult:
    """Substitute backend type query request segments with rendered type text."""

    return _render_type_value_body_tokens(
        kind="type",
        handoff=handoff,
        rendered_values=rendered_values,
        policy=policy,
    )


def render_value_body_tokens_from_handoff(
    handoff: BackendValueQueryHandoff,
    rendered_values: tuple[BodyTokenRenderedTypeValue, ...],
    policy: TypeValueBodyTokenRenderPolicy,
) -> TypeValueBodyTokenRenderResult:
    """Substitute backend value query request segments with rendered value text."""

    return _render_type_value_body_tokens(
        kind="value",
        handoff=handoff,
        rendered_values=rendered_values,
        policy=policy,
    )


def _render_type_value_body_tokens(
    *,
    kind: BodyTokenTypeValueKind,
    handoff: BodyTokenTypeValueHandoff,
    rendered_values: tuple[BodyTokenRenderedTypeValue, ...],
    policy: TypeValueBodyTokenRenderPolicy,
) -> TypeValueBodyTokenRenderResult:
    diagnostics: list[Diagnostic] = []
    request_segments = tuple(_request_segments(kind, handoff))
    required_request_ids = {id(segment.request): segment for segment in request_segments}
    rendered_by_request_id: dict[int, BodyTokenRenderedTypeValue] = {}

    for segment in handoff.segments:
        if _is_opaque_token_segment(kind, segment):
            diagnostics.append(
                _unsupported_opaque_token_segment_diagnostic(segment.source, policy)
            )

    for value in rendered_values:
        request_id = id(value.request)

        if value.kind != kind:
            diagnostics.append(_kind_mismatch_diagnostic(value, kind, policy))
            continue

        if str(value.backend) != str(policy.backend):
            diagnostics.append(_backend_mismatch_diagnostic(value, policy))
            continue

        if request_id not in required_request_ids:
            diagnostics.append(_extra_value_diagnostic(value, policy))
            continue

        if request_id in rendered_by_request_id:
            diagnostics.append(_duplicate_value_diagnostic(value, policy))
            continue

        rendered_by_request_id[request_id] = value

    for segment in request_segments:
        if id(segment.request) not in rendered_by_request_id:
            diagnostics.append(_missing_value_diagnostic(segment.source, policy))

    if diagnostics:
        return TypeValueBodyTokenRenderResult(body=None, diagnostics=tuple(diagnostics))

    pieces: list[str] = []
    ordered_values: list[BodyTokenRenderedTypeValue] = []
    for segment in handoff.segments:
        if _is_opaque_text_segment(kind, segment):
            pieces.append(segment.text)
            continue

        if _is_request_segment(kind, segment):
            value = rendered_by_request_id[id(segment.request)]
            pieces.append(str(value.text))
            ordered_values.append(value)

    return TypeValueBodyTokenRenderResult(
        body=RenderedTypeValueBodyTokens(
            kind=kind,
            handoff=handoff,
            text=BodyTokenTypeValueText("".join(pieces)),
            values=tuple(ordered_values),
            source=handoff.source,
        ),
        diagnostics=(),
    )


def _request_segments(
    kind: BodyTokenTypeValueKind,
    handoff: BodyTokenTypeValueHandoff,
) -> tuple[BackendTypeQueryHandoffRequestSegment | BackendValueQueryHandoffRequestSegment, ...]:
    if kind == "type":
        assert isinstance(handoff, BackendTypeQueryHandoff)
        return tuple(
            segment
            for segment in handoff.segments
            if isinstance(segment, BackendTypeQueryHandoffRequestSegment)
        )

    assert isinstance(handoff, BackendValueQueryHandoff)
    return tuple(
        segment
        for segment in handoff.segments
        if isinstance(segment, BackendValueQueryHandoffRequestSegment)
    )


def _is_opaque_text_segment(
    kind: BodyTokenTypeValueKind,
    segment: object,
) -> bool:
    if kind == "type":
        return isinstance(segment, BackendTypeQueryOpaqueTextSegment)
    return isinstance(segment, BackendValueQueryOpaqueTextSegment)


def _is_opaque_token_segment(
    kind: BodyTokenTypeValueKind,
    segment: object,
) -> bool:
    if kind == "type":
        return isinstance(segment, BackendTypeQueryOpaqueTokenSegment)
    return isinstance(segment, BackendValueQueryOpaqueTokenSegment)


def _is_request_segment(
    kind: BodyTokenTypeValueKind,
    segment: object,
) -> bool:
    if kind == "type":
        return isinstance(segment, BackendTypeQueryHandoffRequestSegment)
    return isinstance(segment, BackendValueQueryHandoffRequestSegment)


def _diagnostic_code(policy: TypeValueBodyTokenRenderPolicy, suffix: str) -> str:
    return f"{policy.diagnostic_code_prefix}-{suffix}"


def _missing_value_diagnostic(
    source: SourceLocation,
    policy: TypeValueBodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "MISSING-RENDERED-VALUE"),
        message=(
            f"{policy.backend_label} type/value body token rendering needs a "
            "rendered backend value for each request segment"
        ),
        location=source,
    )


def _extra_value_diagnostic(
    value: BodyTokenRenderedTypeValue,
    policy: TypeValueBodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "EXTRA-RENDERED-VALUE"),
        message=(
            f"{policy.backend_label} type/value body token rendering received "
            "a rendered backend value whose request is not present in the "
            "handoff stream"
        ),
        location=value.source,
    )


def _duplicate_value_diagnostic(
    value: BodyTokenRenderedTypeValue,
    policy: TypeValueBodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "DUPLICATE-RENDERED-VALUE"),
        message=(
            f"{policy.backend_label} type/value body token rendering received "
            "more than one rendered backend value for the same request segment"
        ),
        location=value.source,
    )


def _backend_mismatch_diagnostic(
    value: BodyTokenRenderedTypeValue,
    policy: TypeValueBodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "BACKEND-MISMATCH"),
        message=(
            f"{policy.backend_label} type/value body token rendering accepts "
            f"only rendered backend values for backend {str(policy.backend)!r}; "
            f"got {str(value.backend)!r}"
        ),
        location=value.source,
    )


def _kind_mismatch_diagnostic(
    value: BodyTokenRenderedTypeValue,
    expected_kind: BodyTokenTypeValueKind,
    policy: TypeValueBodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "VALUE-KIND-MISMATCH"),
        message=(
            f"{policy.backend_label} type/value body token rendering expected "
            f"{expected_kind!r} rendered values; got {value.kind!r}"
        ),
        location=value.source,
    )


def _unsupported_opaque_token_segment_diagnostic(
    source: SourceLocation,
    policy: TypeValueBodyTokenRenderPolicy,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=_diagnostic_code(policy, "UNSUPPORTED-OPAQUE-TOKEN-SEGMENT"),
        message=(
            f"{policy.backend_label} type/value body token rendering cannot "
            "stringify opaque non-text body tokens; lower or render those "
            "tokens before body substitution"
        ),
        location=source,
    )
