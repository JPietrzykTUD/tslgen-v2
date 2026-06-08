"""Exact backend value query island discovery and semantic handoff."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    RawStringToken,
)
from tslgen.lowering._source_islands import (
    OpaqueTokenBuffer,
    SourceMappedText,
    matching_delimiter_close,
    source_text_from_text,
)
from tslgen.lowering.model import (
    BackendConstantValueRequest,
    BackendIntrinsicPrefixValueRequest,
    BackendIntrinsicSuffixValueRequest,
    BackendUninitValueRequest,
    BackendValueQueryDiscovery,
    BackendValueQueryDiscoveryLoweringResult,
    BackendValueQueryDiscoverySegment,
    BackendValueQueryHandoff,
    BackendValueQueryHandoffLoweringResult,
    BackendValueQueryHandoffRequestSegment,
    BackendValueQueryHandoffSegment,
    BackendValueQueryOpaqueTextSegment,
    BackendValueQueryOpaqueTokenSegment,
    BackendValueQueryRequest,
    BackendValueQueryRequestSegment,
    BackendValueRequest,
    BackendValueStringLiteralOperand,
    BackendValueSymbolOperand,
    BackendValueTypeOperand,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)
from tslgen.lowering.type_queries import lower_type_expression
from tslgen.syntax.source_body_fragments import SourceBodyFragmentSequence

_QUERY_PREFIX = "value<backend>("
_QUERY_HEAD = "value<backend>"
_SUFFIX_HEAD = "intrin::suffix"
_PREFIX_PAYLOAD = "intrin::prefix"
_UNINIT_ARRAY_PAYLOAD = "uninit::array"
_UNINIT_SCALAR_PAYLOAD = "uninit::scalar"
_X86_MM_FROUND_TO_ZERO_PAYLOAD = "x86::mm_fround_to_zero"
_ACCEPTED_SUFFIX_STRING_LITERAL_TEXTS = frozenset({'"stream"'})
_BACKEND_SYMBOL_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_?]*(?:::[A-Za-z_][A-Za-z0-9_?]*)*"
)


def discover_backend_value_queries(
    context: SelectedImplementationLoweringContext,
) -> BackendValueQueryDiscoveryLoweringResult:
    """Discover exact backend value query islands in raw body-token text."""

    if context.implementation.source_body_fragments is not None:
        return discover_backend_value_queries_in_fragments(
            context,
            context.implementation.source_body_fragments,
        )

    body = context.implementation.body
    segments: list[BackendValueQueryDiscoverySegment] = []
    pending_opaque_tokens = OpaqueTokenBuffer()

    for token in body.tokens:
        if not isinstance(token, RawStringToken):
            pending_opaque_tokens.append(token)
            continue

        text_result = discover_backend_value_queries_in_text(
            token.text,
            token.source,
        )
        if _has_malformed_query_diagnostic(text_result):
            return text_result
        if text_result.discovery is None:
            pending_opaque_tokens.append(token)
            continue

        opaque_span = pending_opaque_tokens.take()
        if opaque_span is not None:
            segments.append(
                BackendValueQueryOpaqueTokenSegment(
                    tokens=opaque_span.tokens,
                    source=opaque_span.source,
                )
            )
        segments.extend(text_result.discovery.segments)

    if not segments:
        return BackendValueQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(body.source),),
        )

    opaque_span = pending_opaque_tokens.take()
    if opaque_span is not None:
        segments.append(
            BackendValueQueryOpaqueTokenSegment(
                tokens=opaque_span.tokens,
                source=opaque_span.source,
            )
        )

    return BackendValueQueryDiscoveryLoweringResult(
        discovery=BackendValueQueryDiscovery(
            segments=tuple(segments),
            source=body.source,
        ),
        diagnostics=(),
    )


def discover_backend_value_queries_in_text(
    text: str,
    source: SourceLocation,
) -> BackendValueQueryDiscoveryLoweringResult:
    """Discover exact backend value query islands in one source text fragment."""

    return _discover_backend_value_queries_in_source_text(
        source_text_from_text(text, source),
    )


def discover_backend_value_queries_in_fragments(
    context: SelectedImplementationLoweringContext,
    sequence: SourceBodyFragmentSequence,
) -> BackendValueQueryDiscoveryLoweringResult:
    """Discover backend value queries from recursive source-body fragments."""

    del context

    return _discover_backend_value_queries_in_source_text(
        source_text_from_text(
            sequence.source_text.text,
            sequence.source_text.source_at(0),
        )
    )


def lower_backend_value_query_discovery(
    context: SelectedImplementationLoweringContext,
    discovery: BackendValueQueryDiscovery,
    *,
    environment: SelectedTypeEnvironment | None = None,
) -> BackendValueQueryHandoffLoweringResult:
    """Lower discovered backend value-query islands to typed requests."""

    segments: list[BackendValueQueryHandoffSegment] = []
    diagnostics: list[Diagnostic] = []

    for segment in discovery.segments:
        if isinstance(
            segment,
            BackendValueQueryOpaqueTextSegment | BackendValueQueryOpaqueTokenSegment,
        ):
            segments.append(segment)
            continue

        result = _lower_backend_value_query_request(
            context,
            segment.request,
            environment=environment,
        )
        diagnostics.extend(result.diagnostics)
        if result.request is None:
            continue
        segments.append(
            BackendValueQueryHandoffRequestSegment(
                request=result.request,
                island=segment.request,
                source=segment.source,
            )
        )

    if diagnostics:
        return BackendValueQueryHandoffLoweringResult(
            handoff=None,
            diagnostics=tuple(diagnostics),
        )

    return BackendValueQueryHandoffLoweringResult(
        handoff=BackendValueQueryHandoff(
            segments=tuple(segments),
            source=discovery.source,
        ),
        diagnostics=(),
    )


def _discover_backend_value_queries_in_source_text(
    source_text: SourceMappedText,
) -> BackendValueQueryDiscoveryLoweringResult:
    segments: list[BackendValueQueryOpaqueTextSegment | BackendValueQueryRequestSegment]
    segments = []
    text = source_text.text
    source = source_text.source
    index = 0
    found_query = False

    while index < len(text):
        start = text.find(_QUERY_PREFIX, index)
        if start == -1:
            break

        open_index = start + len(_QUERY_HEAD)
        close_index = matching_delimiter_close(text, open_index, "(", ")")
        if close_index is None:
            return BackendValueQueryDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(
                    _malformed_query_diagnostic(
                        source_text.source_at(start),
                    ),
                ),
            )

        if start > index:
            opaque_span = source_text.span(index, start)
            segments.append(
                BackendValueQueryOpaqueTextSegment(
                    text=opaque_span.text,
                    source=opaque_span.source,
                )
            )

        query_start = open_index + 1
        query_text = text[query_start:close_index]
        request = BackendValueQueryRequest(
            query_text=query_text,
            query_source=source_text.source_at(query_start),
            source_text=text[start : close_index + 1],
            source=source_text.source_at(start),
        )
        segments.append(
            BackendValueQueryRequestSegment(
                request=request,
                source=request.source,
            )
        )
        found_query = True
        index = close_index + 1

    if not found_query:
        return BackendValueQueryDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_query_diagnostic(source),),
        )

    if index < len(text):
        opaque_span = source_text.span(index, len(text))
        segments.append(
            BackendValueQueryOpaqueTextSegment(
                text=opaque_span.text,
                source=opaque_span.source,
            )
        )

    return BackendValueQueryDiscoveryLoweringResult(
        discovery=BackendValueQueryDiscovery(segments=tuple(segments), source=source),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _BackendValueRequestLoweringResult:
    request: BackendValueRequest | None
    diagnostics: tuple[Diagnostic, ...]


def _lower_backend_value_query_request(
    context: SelectedImplementationLoweringContext,
    request: BackendValueQueryRequest,
    *,
    environment: SelectedTypeEnvironment | None,
) -> _BackendValueRequestLoweringResult:
    query_text = request.query_text
    if query_text != query_text.strip() or not query_text:
        return _unsupported_backend_value_query(request)

    arity_diagnostic = _malformed_selected_no_arg_payload(request)
    if arity_diagnostic is not None:
        return _BackendValueRequestLoweringResult(None, (arity_diagnostic,))

    if query_text == _PREFIX_PAYLOAD:
        return _request_result(
            BackendIntrinsicPrefixValueRequest(
                backend=context.backend,
                source_text=request.source_text,
                source=request.source,
            )
        )

    if query_text == _UNINIT_ARRAY_PAYLOAD:
        return _request_result(
            BackendUninitValueRequest(
                backend=context.backend,
                kind="array",
                source_text=request.source_text,
                source=request.source,
            )
        )

    if query_text == _UNINIT_SCALAR_PAYLOAD:
        return _request_result(
            BackendUninitValueRequest(
                backend=context.backend,
                kind="scalar",
                source_text=request.source_text,
                source=request.source,
            )
        )

    if query_text == _X86_MM_FROUND_TO_ZERO_PAYLOAD:
        return _request_result(
            BackendConstantValueRequest(
                backend=context.backend,
                name="x86::mm_fround_to_zero",
                source_text=request.source_text,
                source=request.source,
            )
        )

    suffix_payload = _suffix_argument_payload(request)
    if isinstance(suffix_payload, Diagnostic):
        return _BackendValueRequestLoweringResult(None, (suffix_payload,))
    if suffix_payload is not _NO_SUFFIX_MATCH:
        argument = None
        if suffix_payload is not None:
            argument_result = _lower_suffix_argument(
                context,
                suffix_payload,
                environment=environment,
            )
            if isinstance(argument_result, Diagnostic):
                return _BackendValueRequestLoweringResult(None, (argument_result,))
            argument = argument_result
        return _request_result(
            BackendIntrinsicSuffixValueRequest(
                backend=context.backend,
                argument=argument,
                source_text=request.source_text,
                source=request.source,
            )
        )

    return _unsupported_backend_value_query(request)


def _malformed_selected_no_arg_payload(
    request: BackendValueQueryRequest,
) -> Diagnostic | None:
    for payload in (
        _PREFIX_PAYLOAD,
        _UNINIT_ARRAY_PAYLOAD,
        _UNINIT_SCALAR_PAYLOAD,
        _X86_MM_FROUND_TO_ZERO_PAYLOAD,
    ):
        if request.query_text.startswith(f"{payload}("):
            return _malformed_payload_diagnostic(
                request.query_source,
                request.query_text,
                f"expected {payload} without arguments",
            )
    return None


def _request_result(
    request: BackendValueRequest,
) -> _BackendValueRequestLoweringResult:
    return _BackendValueRequestLoweringResult(request=request, diagnostics=())


@dataclass(frozen=True, slots=True)
class _SuffixArgumentPayload:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class _NoSuffixMatch:
    pass


_NO_SUFFIX_MATCH = _NoSuffixMatch()


def _suffix_argument_payload(
    request: BackendValueQueryRequest,
) -> _SuffixArgumentPayload | _NoSuffixMatch | Diagnostic | None:
    query_text = request.query_text
    if query_text == _SUFFIX_HEAD:
        return None
    if not query_text.startswith(f"{_SUFFIX_HEAD}("):
        return _NO_SUFFIX_MATCH

    open_index = len(_SUFFIX_HEAD)
    close_index = matching_delimiter_close(query_text, open_index, "(", ")")
    if close_index is None or close_index != len(query_text) - 1:
        return _malformed_payload_diagnostic(
            request.query_source,
            request.query_text,
            "expected intrin::suffix with exactly one balanced argument",
        )

    argument_text = query_text[open_index + 1 : close_index]
    if (
        not argument_text
        or argument_text != argument_text.strip()
        or _has_top_level_comma(argument_text)
    ):
        return _malformed_payload_diagnostic(
            request.query_source,
            request.query_text,
            "expected intrin::suffix with exactly one non-empty argument",
        )

    source_text = source_text_from_text(query_text, request.query_source)
    return _SuffixArgumentPayload(
        text=argument_text,
        source=source_text.source_at(open_index + 1),
    )


def _lower_suffix_argument(
    context: SelectedImplementationLoweringContext,
    argument: _SuffixArgumentPayload,
    *,
    environment: SelectedTypeEnvironment | None,
) -> (
    BackendValueTypeOperand
    | BackendValueStringLiteralOperand
    | BackendValueSymbolOperand
    | Diagnostic
):
    string_operand = _string_literal_operand(argument)
    if isinstance(string_operand, BackendValueStringLiteralOperand | Diagnostic):
        return string_operand

    type_result = lower_type_expression(
        context,
        argument.text,
        argument.source,
        environment=environment,
    )
    if type_result.value is not None:
        return BackendValueTypeOperand(
            value=type_result.value,
            source_text=argument.text,
            source=argument.source,
        )
    blocking_diagnostic = _selected_binding_diagnostic(type_result.diagnostics)
    if blocking_diagnostic is not None:
        return blocking_diagnostic

    if _BACKEND_SYMBOL_RE.fullmatch(argument.text) is not None:
        return BackendValueSymbolOperand(
            text=argument.text,
            source=argument.source,
        )

    return _unsupported_suffix_argument_diagnostic(argument)


def _selected_binding_diagnostic(
    diagnostics: tuple[Diagnostic, ...],
) -> Diagnostic | None:
    for diagnostic in diagnostics:
        if "SELECTED-SPECIALIZATION" in diagnostic.code:
            return diagnostic
    return None


def _string_literal_operand(
    argument: _SuffixArgumentPayload,
) -> BackendValueStringLiteralOperand | Diagnostic | None:
    if not (argument.text.startswith('"') or argument.text.endswith('"')):
        return None
    if not (argument.text.startswith('"') and argument.text.endswith('"')):
        return _malformed_payload_diagnostic(
            argument.source,
            argument.text,
            "expected a complete quoted string literal",
        )

    try:
        value = ast.literal_eval(argument.text)
    except (SyntaxError, ValueError):
        return _malformed_payload_diagnostic(
            argument.source,
            argument.text,
            "expected a valid quoted string literal",
        )
    if not isinstance(value, str):
        return _malformed_payload_diagnostic(
            argument.source,
            argument.text,
            "expected a quoted string literal",
        )
    if argument.text not in _ACCEPTED_SUFFIX_STRING_LITERAL_TEXTS:
        return _unsupported_suffix_argument_diagnostic(argument)
    return BackendValueStringLiteralOperand(
        value=value,
        source_text=argument.text,
        source=argument.source,
    )


def _has_top_level_comma(text: str) -> bool:
    depths = {"(": 0, "[": 0, "<": 0}
    open_to_close = {"(": ")", "[": "]", "<": ">"}
    close_to_open = {")": "(", "]": "[", ">": "<"}
    quote: str | None = None
    escaped = False

    for char in text:
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
        if char in open_to_close:
            depths[char] += 1
            continue
        if char in close_to_open:
            open_char = close_to_open[char]
            if depths[open_char] > 0:
                depths[open_char] -= 1
            continue
        if char == "," and all(depth == 0 for depth in depths.values()):
            return True

    return False


def _has_malformed_query_diagnostic(
    result: BackendValueQueryDiscoveryLoweringResult,
) -> bool:
    return any(
        diagnostic.code == "TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY"
        for diagnostic in result.diagnostics
    )


def _malformed_query_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY",
        message=(
            "backend value query discovery found a value<backend>(...) "
            "island with an unbalanced outer payload"
        ),
        location=source,
    )


def _unsupported_backend_value_query(
    request: BackendValueQueryRequest,
) -> _BackendValueRequestLoweringResult:
    return _BackendValueRequestLoweringResult(
        request=None,
        diagnostics=(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
                message=(
                    "unsupported backend value query payload "
                    f"{request.query_text!r}; expected one of "
                    "intrin::suffix, intrin::suffix(...), intrin::prefix, "
                    "uninit::array, uninit::scalar, or x86::mm_fround_to_zero"
                ),
                location=request.query_source,
            ),
        ),
    )


def _unsupported_suffix_argument_diagnostic(
    argument: _SuffixArgumentPayload,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-BACKEND-VALUE-QUERY",
        message=(
            "unsupported intrin::suffix backend value argument "
            f"{argument.text!r}; expected an accepted type expression, "
            'the observed quoted string literal "stream", or a backend-owned '
            "symbol/literal"
        ),
        location=argument.source,
    )


def _malformed_payload_diagnostic(
    source: SourceLocation,
    payload: str,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-BACKEND-VALUE-QUERY-PAYLOAD",
        message=f"malformed backend value query payload {payload!r}: {reason}",
        location=source,
    )


def _no_query_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-BACKEND-VALUE-QUERY",
        message=(
            "backend value query discovery found no exact "
            "value<backend>(...) island"
        ),
        location=source,
    )
