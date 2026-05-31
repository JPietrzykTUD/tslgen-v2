"""Semantic handoff for discovered source-operation request islands."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic
from tslgen.lowering.model import (
    CastSourceOperationHandoffRequest,
    CastSourceOperationSelector,
    IoSourceOperationHandoffRequest,
    IoSourceOperationSelector,
    MemorySourceOperationHandoffRequest,
    MemorySourceOperationSelector,
    SelectedImplementationLoweringContext,
    SourceOperationDiscovery,
    SourceOperationHandoff,
    SourceOperationHandoffLoweringResult,
    SourceOperationHandoffRequest,
    SourceOperationHandoffRequestSegment,
    SourceOperationHandoffSegment,
    SourceOperationKind,
    SourceOperationOpaqueTextSegment,
    SourceOperationOpaqueTokenSegment,
    SourceOperationRequest,
)

_CAST_SELECTORS: dict[str, CastSourceOperationSelector] = {
    selector.value: selector for selector in CastSourceOperationSelector
}
_MEMORY_SELECTORS: dict[str, MemorySourceOperationSelector] = {
    selector.value: selector for selector in MemorySourceOperationSelector
}
_IO_SELECTORS: dict[str, IoSourceOperationSelector] = {
    selector.value: selector for selector in IoSourceOperationSelector
}


def lower_source_operation_discovery(
    context: SelectedImplementationLoweringContext,
    discovery: SourceOperationDiscovery,
) -> SourceOperationHandoffLoweringResult:
    """Lower discovered source-operation islands to typed selector facts."""

    del context

    segments: list[SourceOperationHandoffSegment] = []
    diagnostics: list[Diagnostic] = []

    for segment in discovery.segments:
        if isinstance(
            segment,
            SourceOperationOpaqueTextSegment | SourceOperationOpaqueTokenSegment,
        ):
            segments.append(segment)
            continue

        result = _lower_source_operation_request(segment.request)
        diagnostics.extend(result.diagnostics)
        if result.request is None:
            continue
        segments.append(
            SourceOperationHandoffRequestSegment(
                request=result.request,
                island=segment.request,
                source=segment.source,
            )
        )

    if diagnostics:
        return SourceOperationHandoffLoweringResult(
            handoff=None,
            diagnostics=tuple(diagnostics),
        )

    return SourceOperationHandoffLoweringResult(
        handoff=SourceOperationHandoff(
            segments=tuple(segments),
            source=discovery.source,
        ),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _SourceOperationRequestLoweringResult:
    request: SourceOperationHandoffRequest | None
    diagnostics: tuple[Diagnostic, ...]


def _lower_source_operation_request(
    request: SourceOperationRequest,
) -> _SourceOperationRequestLoweringResult:
    payload = request.angle_payload_text
    if request.operation_kind == "cast" and payload in _CAST_SELECTORS:
        return _SourceOperationRequestLoweringResult(
            request=CastSourceOperationHandoffRequest(
                selector=_CAST_SELECTORS[payload],
                source=request.angle_payload_source,
            ),
            diagnostics=(),
        )
    if request.operation_kind == "mem" and payload in _MEMORY_SELECTORS:
        return _SourceOperationRequestLoweringResult(
            request=MemorySourceOperationHandoffRequest(
                selector=_MEMORY_SELECTORS[payload],
                source=request.angle_payload_source,
            ),
            diagnostics=(),
        )
    if request.operation_kind == "io" and payload in _IO_SELECTORS:
        return _SourceOperationRequestLoweringResult(
            request=IoSourceOperationHandoffRequest(
                selector=_IO_SELECTORS[payload],
                source=request.angle_payload_source,
            ),
            diagnostics=(),
        )

    return _SourceOperationRequestLoweringResult(
        request=None,
        diagnostics=(_unsupported_selector_diagnostic(request),),
    )


def _unsupported_selector_diagnostic(request: SourceOperationRequest) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-SOURCE-OPERATION-SELECTOR",
        message=(
            f"unsupported {request.operation_kind} source-operation selector "
            f"{_display_payload(request.angle_payload_text)}; expected one of "
            f"{_expected_selectors(request.operation_kind)}"
        ),
        location=request.angle_payload_source,
    )


def _display_payload(payload: str) -> str:
    if not payload:
        return "<empty>"
    return repr(payload)


def _expected_selectors(operation_kind: SourceOperationKind) -> str:
    if operation_kind == "cast":
        return _format_expected(_CAST_SELECTORS)
    if operation_kind == "mem":
        return _format_expected(_MEMORY_SELECTORS)
    if operation_kind == "io":
        return _format_expected(_IO_SELECTORS)
    return "cast, mem, or io selector payloads"


def _format_expected(selectors: dict[str, object]) -> str:
    return ", ".join(sorted(selectors))
