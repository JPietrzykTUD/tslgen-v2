"""Exact backend-control directive request discovery."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import BodyToken, ImplementationBody, LowerableDirective
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

_BACKEND_CONTROL_NAMES = frozenset(("if", "else", "switch"))
_SELECTED_BACKEND_CONTROL_SELECTOR = "compile"
_IGNORED_NON_BACKEND_CONTROL_SELECTORS = frozenset(("generation",))
_UNSUPPORTED_BACKEND_CONTROL_SELECTORS = frozenset(("runtime",))


def discover_backend_control_directives(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
) -> BackendControlDirectiveDiscoveryLoweringResult:
    """Discover exact backend-control directive requests in body-token streams."""

    del context

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
