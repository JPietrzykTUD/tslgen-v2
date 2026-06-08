"""Exact backend-control directive request discovery."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    LowerableDirective,
    RawStringToken,
)
from tslgen.lowering.model import (
    BackendControlDirectiveDiscovery,
    BackendControlDirectiveDiscoveryLoweringResult,
    BackendControlDirectiveDiscoverySegment,
    BackendControlDirectiveName,
    BackendControlDirectiveOpaqueSegment,
    BackendControlDirectiveRequest,
    BackendControlDirectiveRequestSegment,
    BackendControlDirectiveSelector,
    SelectedImplementationLoweringContext,
)
from tslgen.syntax.source_body_fragments import (
    KeywordRegionFragment,
    SourceBodyFragmentSequence,
)
from tslgen.syntax.source_body_regions import SourceBodyKeyword
from tslgen.syntax.source_body_regions import SourceBodyText

_BACKEND_CONTROL_NAMES = frozenset(("if", "else", "switch"))
_SELECTED_BACKEND_CONTROL_SELECTOR = "compile"
_IGNORED_NON_BACKEND_CONTROL_SELECTORS = frozenset(("generation",))
_UNSUPPORTED_BACKEND_CONTROL_SELECTORS = frozenset(("runtime",))


@dataclass(frozen=True, slots=True)
class _BackendControlFragmentRequest:
    fragment: KeywordRegionFragment
    request: BackendControlDirectiveRequest
    request_end_offset: int


def discover_backend_control_directives(
    context: SelectedImplementationLoweringContext,
) -> BackendControlDirectiveDiscoveryLoweringResult:
    """Discover exact backend-control directive requests in body-token streams."""

    if context.implementation.source_body_fragments is not None:
        return discover_backend_control_directives_in_fragments(
            context,
            context.implementation.source_body_fragments,
        )

    body = context.implementation.body
    segments: list[BackendControlDirectiveDiscoverySegment] = []
    pending_opaque_tokens: list[BodyToken] = []

    for token in body.tokens:
        lowered = _lower_backend_control_directive(token)
        if lowered is None:
            pending_opaque_tokens.append(token)
            continue
        if isinstance(lowered, Diagnostic):
            return BackendControlDirectiveDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(lowered,),
            )

        if pending_opaque_tokens:
            segments.append(
                BackendControlDirectiveOpaqueSegment(
                    tokens=tuple(pending_opaque_tokens),
                    source=pending_opaque_tokens[0].source,
                )
            )
            pending_opaque_tokens.clear()
        segments.append(
            BackendControlDirectiveRequestSegment(
                request=lowered,
                source=lowered.source,
            )
        )

    if not segments:
        return BackendControlDirectiveDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_backend_control_diagnostic(body.source),),
        )

    if pending_opaque_tokens:
        segments.append(
            BackendControlDirectiveOpaqueSegment(
                tokens=tuple(pending_opaque_tokens),
                source=pending_opaque_tokens[0].source,
            )
        )

    return BackendControlDirectiveDiscoveryLoweringResult(
        discovery=BackendControlDirectiveDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_backend_control_directives_in_fragments(
    context: SelectedImplementationLoweringContext,
    sequence: SourceBodyFragmentSequence,
) -> BackendControlDirectiveDiscoveryLoweringResult:
    """Discover backend-control directive requests from recursive fragments."""

    del context

    requests: list[_BackendControlFragmentRequest] = []
    diagnostics: list[Diagnostic] = []
    _collect_backend_control_requests(sequence, requests, diagnostics)
    if diagnostics:
        return BackendControlDirectiveDiscoveryLoweringResult(
            discovery=None,
            diagnostics=tuple(diagnostics),
        )
    if not requests:
        return BackendControlDirectiveDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_backend_control_diagnostic(sequence.source_text.source_at(0)),),
        )

    segments: list[BackendControlDirectiveDiscoverySegment] = []
    cursor = 0
    for item in sorted(
        requests,
        key=lambda request: (
            _root_start_offset(sequence.source_text, request.fragment),
            request.request.source_text,
        ),
    ):
        region = item.fragment.source_region
        request_start = _root_start_offset(sequence.source_text, item.fragment)
        if request_start < cursor:
            continue

        if cursor < request_start:
            segments.append(
                _opaque_text_segment_from_source_range(
                    sequence,
                    cursor,
                    request_start,
                )
            )
        segments.append(
            BackendControlDirectiveRequestSegment(
                request=item.request,
                source=item.request.source,
            )
        )
        cursor = request_start + (
            item.request_end_offset - region.full_span.start_offset
        )

    if cursor < len(sequence.source_text.text):
        segments.append(
            _opaque_text_segment_from_source_range(
                sequence,
                cursor,
                len(sequence.source_text.text),
            )
        )

    return BackendControlDirectiveDiscoveryLoweringResult(
        discovery=BackendControlDirectiveDiscovery(
            segments=tuple(segments),
            source=sequence.source_text.source_at(0),
        ),
        diagnostics=(),
    )


def _collect_backend_control_requests(
    sequence: SourceBodyFragmentSequence,
    requests: list[_BackendControlFragmentRequest],
    diagnostics: list[Diagnostic],
) -> None:
    for fragment in sequence.fragments:
        if not isinstance(fragment, KeywordRegionFragment):
            continue

        if fragment.keyword in {
            SourceBodyKeyword.IF,
            SourceBodyKeyword.ELSE,
            SourceBodyKeyword.SWITCH,
        }:
            lowered = _lower_backend_control_fragment(fragment)
            if isinstance(lowered, Diagnostic):
                diagnostics.append(lowered)
            elif lowered is not None:
                requests.append(lowered)

        for child_sequence in (
            fragment.selector_fragments,
            fragment.payload_fragments,
            fragment.body_fragments,
        ):
            if child_sequence is not None:
                _collect_backend_control_requests(
                    child_sequence,
                    requests,
                    diagnostics,
                )


def _lower_backend_control_fragment(
    fragment: KeywordRegionFragment,
) -> _BackendControlFragmentRequest | Diagnostic | None:
    region = fragment.source_region
    if region.selector is None:
        return None

    selector = region.selector.payload_span.text.strip()
    if fragment.keyword is SourceBodyKeyword.ELSE:
        directive = LowerableDirective(
            name="else",
            arguments=(selector,),
            source=region.full_span.start,
        )
        request_end_offset = region.selector.full_span.end_offset
    else:
        if region.payload is None:
            return _malformed_directive_diagnostic(
                LowerableDirective(
                    name=region.head.name,
                    arguments=(selector,),
                    source=region.full_span.start,
                ),
                f"{region.head.name}<compile> expected exactly one payload",
            )
        directive = LowerableDirective(
            name=region.head.name,
            arguments=(selector, region.payload.payload_span.text),
            source=region.full_span.start,
        )
        request_end_offset = region.payload.full_span.end_offset

    lowered = _lower_backend_control_directive(directive)
    if lowered is None or isinstance(lowered, Diagnostic):
        return lowered

    return _BackendControlFragmentRequest(
        fragment=fragment,
        request=lowered,
        request_end_offset=request_end_offset,
    )


def _opaque_text_segment_from_source_range(
    sequence: SourceBodyFragmentSequence,
    start_offset: int,
    end_offset: int,
) -> BackendControlDirectiveOpaqueSegment:
    span = sequence.source_text.span(start_offset, end_offset)
    return BackendControlDirectiveOpaqueSegment(
        tokens=(RawStringToken(text=span.text, source=span.start),),
        source=span.start,
    )


def _root_start_offset(
    source_text: SourceBodyText,
    fragment: KeywordRegionFragment,
) -> int:
    return _offset_for_location(source_text, fragment.source_region.full_span.start)


def _offset_for_location(
    source_text: SourceBodyText,
    location: SourceLocation,
) -> int:
    if location.path != source_text.path:
        raise ValueError("fragment location is outside the root source body")

    line = source_text.line
    column = source_text.column
    for offset, char in enumerate(source_text.text):
        if line == location.line and column == location.column:
            return offset
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1

    if line == location.line and column == location.column:
        return len(source_text.text)
    raise ValueError("fragment location is outside the root source body")


def _lower_backend_control_directive(
    token: BodyToken,
) -> BackendControlDirectiveRequest | Diagnostic | None:
    if not isinstance(token, LowerableDirective):
        return None
    if token.name not in _BACKEND_CONTROL_NAMES:
        return None
    if not token.arguments:
        return None

    selector = token.arguments[0]
    if selector in _IGNORED_NON_BACKEND_CONTROL_SELECTORS:
        return None
    if selector in _UNSUPPORTED_BACKEND_CONTROL_SELECTORS:
        return _unsupported_selector_diagnostic(token, selector)
    if selector != _SELECTED_BACKEND_CONTROL_SELECTOR:
        return _unsupported_selector_diagnostic(token, selector)

    if token.name in ("if", "switch"):
        return _lower_payload_directive(token)
    if token.name == "else":
        return _lower_else_directive(token)
    return None


def _lower_payload_directive(
    directive: LowerableDirective,
) -> BackendControlDirectiveRequest | Diagnostic:
    if len(directive.arguments) != 2:
        return _malformed_directive_diagnostic(
            directive,
            f"{directive.name}<compile> expected exactly one payload",
        )

    payload = directive.arguments[1]
    if not payload.strip():
        return _malformed_directive_diagnostic(
            directive,
            f"{directive.name}<compile> payload must not be empty",
        )

    selector = _typed_selector(directive.arguments[0])
    selector_source = _selector_source(directive)
    payload_source = _payload_source(directive, selector)
    source_text = f"{directive.name}<{selector}>({payload})"
    return BackendControlDirectiveRequest(
        directive_name=_typed_name(directive.name),
        selector=selector,
        selector_source=selector_source,
        payload_text=payload,
        payload_source=payload_source,
        source_text=source_text,
        source=directive.source,
    )


def _lower_else_directive(
    directive: LowerableDirective,
) -> BackendControlDirectiveRequest | Diagnostic:
    if len(directive.arguments) != 1:
        return _malformed_directive_diagnostic(
            directive,
            "else<compile> expected no payload",
        )

    selector = _typed_selector(directive.arguments[0])
    source_text = f"else<{selector}>"
    return BackendControlDirectiveRequest(
        directive_name="else",
        selector=selector,
        selector_source=_selector_source(directive),
        source_text=source_text,
        source=directive.source,
    )


def _typed_name(name: str) -> BackendControlDirectiveName:
    if name == "if":
        return "if"
    if name == "else":
        return "else"
    if name == "switch":
        return "switch"
    raise AssertionError(f"unsupported backend-control directive name {name!r}")


def _typed_selector(selector: str) -> BackendControlDirectiveSelector:
    if selector == "compile":
        return "compile"
    raise AssertionError(f"unsupported backend-control selector {selector!r}")


def _selector_source(directive: LowerableDirective) -> SourceLocation:
    return SourceLocation(
        directive.source.path,
        directive.source.line,
        directive.source.column + len(directive.name) + 1,
    )


def _payload_source(
    directive: LowerableDirective,
    selector: BackendControlDirectiveSelector,
) -> SourceLocation:
    return SourceLocation(
        directive.source.path,
        directive.source.line,
        directive.source.column + len(f"{directive.name}<{selector}>("),
    )


def _unsupported_selector_diagnostic(
    directive: LowerableDirective,
    selector: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-BACKEND-CONTROL-SELECTOR",
        message=(
            "backend-control directive selector is not supported by M165; "
            f"expected compile, got {selector!r}"
        ),
        location=_selector_source(directive),
    )


def _malformed_directive_diagnostic(
    directive: LowerableDirective,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-CONTROL-DIRECTIVE",
        message=(
            "backend-control directive cannot be recorded by M165; "
            f"{reason}"
        ),
        location=directive.source,
    )


def _no_backend_control_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-BACKEND-CONTROL-DIRECTIVE",
        message=(
            "backend-control directive discovery found no exact classified "
            "compile-control directive"
        ),
        location=source,
    )
