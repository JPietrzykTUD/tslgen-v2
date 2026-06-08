"""Exact selected-context generation loop-region lowering."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Catalog,
    LowerableDirective,
    RawStringToken,
)
from tslgen.lowering.generation_values import lower_generation_value_query
from tslgen.lowering.model import (
    GenerationLoopDiscoveryLoweringResult,
    GenerationLoopRegionLoweringResult,
    LoweredGenerationLoopDiscovery,
    LoweredGenerationLoopBody,
    LoweredGenerationLoopOpaqueSegment,
    LoweredGenerationLoopRegion,
    LoweredGenerationLoopRegionSegment,
    LoweredGenerationValue,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)
from tslgen.lowering.source_body_fragments import (
    compatibility_body_token_result_from_fragment_sequence,
)
from tslgen.syntax.tsil_lexical import (
    ANGLE_DELIMITER,
    BRACKET_DELIMITER,
    PAREN_DELIMITER,
    raw_brace_depth_after,
    split_top_level_parts,
)

_VALUE_QUERY_PREFIX = "value<generation>("


@dataclass(frozen=True, slots=True)
class _LoopBoundary:
    close_index: int
    next_index: int


@dataclass(frozen=True, slots=True)
class _LoopRegionSlice:
    start_index: int
    end_index: int


@dataclass(frozen=True, slots=True)
class _LoopRegionSliceSearch:
    loop_slice: _LoopRegionSlice | None
    diagnostic: Diagnostic | None


@dataclass(frozen=True, slots=True)
class _LoopCloseSearch:
    boundary: _LoopBoundary | None
    diagnostic: Diagnostic | None


@dataclass(frozen=True, slots=True)
class _LoopPayload:
    index_name: str
    start: str
    end: str
    step: str


@dataclass(frozen=True, slots=True)
class _LoopIntegerValueLowering:
    value: LoweredGenerationValue | None
    diagnostics: tuple[Diagnostic, ...]


def lower_generation_loop_region(
    context: SelectedImplementationLoweringContext,
    *,
    catalog: Catalog | None = None,
    environment: SelectedTypeEnvironment | None = None,
) -> GenerationLoopRegionLoweringResult:
    if context.implementation.source_body_fragments is not None:
        token_result = compatibility_body_token_result_from_fragment_sequence(
            context.implementation.source_body_fragments,
        )
        if token_result.diagnostics:
            return GenerationLoopRegionLoweringResult(
                region=None,
                diagnostics=token_result.diagnostics,
            )
        return _lower_generation_loop_region_from_tokens(
            context,
            _strip_boundary_whitespace_tokens(token_result.tokens),
            context.implementation.source_body_fragments.source_text.source_at(0),
            catalog=catalog,
            environment=environment,
        )

    body = context.implementation.body
    return _lower_generation_loop_region_from_tokens(
        context,
        body.tokens,
        body.source,
        catalog=catalog,
        environment=environment,
    )


def _lower_generation_loop_region_from_tokens(
    context: SelectedImplementationLoweringContext,
    tokens: tuple[BodyToken, ...],
    body_source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> GenerationLoopRegionLoweringResult:
    if not tokens:
        return _malformed_region_result(
            body_source,
            "expected loop<range>(Index, Start, End, Step) region",
        )

    unroll_count: LoweredGenerationValue | None = None
    loop_index = 0
    first = tokens[0]
    if _is_loop_directive(first, "unroll"):
        assert isinstance(first, LowerableDirective)
        unroll_result = _lower_loop_integer_value(
            context,
            first.arguments[1],
            first.source,
            catalog=catalog,
            environment=environment,
        )
        if unroll_result.value is None:
            return GenerationLoopRegionLoweringResult(
                region=None,
                diagnostics=unroll_result.diagnostics,
            )
        unroll_count = unroll_result.value
        loop_index = _skip_whitespace_tokens(tokens, 1)
        if loop_index >= len(tokens):
            return _malformed_region_result(
                first.source,
                "expected loop<range>(...) region after loop<unroll>(...)",
            )

    loop = tokens[loop_index]
    if not isinstance(loop, LowerableDirective) or loop.name != "loop":
        return _malformed_region_result(
            _token_source(loop),
            "expected loop<range>(Index, Start, End, Step) directive",
        )
    if len(loop.arguments) != 2:
        return _malformed_region_result(
            loop.source,
            "expected loop directive with selector and payload",
        )
    if loop.arguments[0] != "range":
        return GenerationLoopRegionLoweringResult(
            region=None,
            diagnostics=(_unsupported_loop_selector_diagnostic(loop),),
        )

    payload = _parse_loop_range_payload(loop.arguments[1], loop.source)
    if isinstance(payload, Diagnostic):
        return GenerationLoopRegionLoweringResult(region=None, diagnostics=(payload,))

    value_results = (
        _lower_loop_integer_value(
            context,
            payload.start,
            loop.source,
            catalog=catalog,
            environment=environment,
        ),
        _lower_loop_integer_value(
            context,
            payload.end,
            loop.source,
            catalog=catalog,
            environment=environment,
        ),
        _lower_loop_integer_value(
            context,
            payload.step,
            loop.source,
            catalog=catalog,
            environment=environment,
        ),
    )
    diagnostics = tuple(
        diagnostic
        for result in value_results
        if result.value is None
        for diagnostic in result.diagnostics
    )
    if diagnostics:
        return GenerationLoopRegionLoweringResult(region=None, diagnostics=diagnostics)

    open_index = loop_index + 1
    if open_index >= len(tokens) or not _is_open_brace(tokens[open_index]):
        return _malformed_region_result(
            _token_source(tokens[open_index]) if open_index < len(tokens) else loop.source,
            "expected raw opening brace after loop<range>(...)",
        )

    body_start = open_index + 1
    close_search = _find_loop_close(tokens, start=body_start)
    if close_search.diagnostic is not None:
        return GenerationLoopRegionLoweringResult(
            region=None,
            diagnostics=(close_search.diagnostic,),
        )
    boundary = close_search.boundary
    if boundary is None:
        return _malformed_region_result(
            loop.source,
            "could not find matching close brace for generation loop",
        )
    if boundary.next_index != len(tokens):
        return _malformed_region_result(
            _token_source(tokens[boundary.next_index]),
            "unexpected tokens after generation loop region",
        )

    body_tokens = tokens[body_start:boundary.close_index]
    start, end, step = tuple(result.value for result in value_results)
    assert start is not None
    assert end is not None
    assert step is not None
    return GenerationLoopRegionLoweringResult(
        region=LoweredGenerationLoopRegion(
            index_name=payload.index_name,
            start=start,
            end=end,
            step=step,
            body=LoweredGenerationLoopBody(
                tokens=body_tokens,
                source=_body_source(body_tokens, loop.source),
            ),
            source=tokens[0].source,
            unroll_count=unroll_count,
        ),
        diagnostics=(),
    )


def discover_generation_loop_regions(
    context: SelectedImplementationLoweringContext,
    *,
    catalog: Catalog | None = None,
    environment: SelectedTypeEnvironment | None = None,
) -> GenerationLoopDiscoveryLoweringResult:
    if context.implementation.source_body_fragments is not None:
        token_result = compatibility_body_token_result_from_fragment_sequence(
            context.implementation.source_body_fragments,
        )
        if token_result.diagnostics:
            return GenerationLoopDiscoveryLoweringResult(
                discovery=None,
                diagnostics=token_result.diagnostics,
            )
        return _discover_generation_loop_regions_from_tokens(
            context,
            token_result.tokens,
            context.implementation.source_body_fragments.source_text.source_at(0),
            catalog=catalog,
            environment=environment,
        )

    body = context.implementation.body
    return _discover_generation_loop_regions_from_tokens(
        context,
        body.tokens,
        body.source,
        catalog=catalog,
        environment=environment,
    )


def _discover_generation_loop_regions_from_tokens(
    context: SelectedImplementationLoweringContext,
    tokens: tuple[BodyToken, ...],
    body_source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> GenerationLoopDiscoveryLoweringResult:
    segments: list[LoweredGenerationLoopOpaqueSegment | LoweredGenerationLoopRegionSegment] = []
    pending_opaque_start = 0
    index = 0
    raw_brace_depth = 0

    while index < len(tokens):
        token = tokens[index]
        if raw_brace_depth == 0 and _is_unsupported_loop_directive(token):
            assert isinstance(token, LowerableDirective)
            return GenerationLoopDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(_unsupported_loop_selector_diagnostic(token),),
            )

        slice_start = _loop_slice_start(tokens, index) if raw_brace_depth == 0 else None
        if slice_start is None:
            raw_brace_depth = _updated_raw_brace_depth(raw_brace_depth, token)
            index += 1
            continue

        slice_search = _find_embedded_loop_slice(tokens, start=slice_start)
        if slice_search.diagnostic is not None:
            return GenerationLoopDiscoveryLoweringResult(
                discovery=None,
                diagnostics=(slice_search.diagnostic,),
            )
        loop_slice = slice_search.loop_slice
        if loop_slice is None:
            index += 1
            continue

        loop_result = _lower_generation_loop_region_from_tokens(
            context,
            tokens[loop_slice.start_index:loop_slice.end_index],
            _token_source(tokens[loop_slice.start_index]),
            catalog=catalog,
            environment=environment,
        )
        if loop_result.region is None:
            return GenerationLoopDiscoveryLoweringResult(
                discovery=None,
                diagnostics=loop_result.diagnostics,
            )

        opaque_tokens = tokens[pending_opaque_start:loop_slice.start_index]
        if opaque_tokens:
            segments.append(
                LoweredGenerationLoopOpaqueSegment(
                    tokens=opaque_tokens,
                    source=_token_source(opaque_tokens[0]),
                )
            )
        segments.append(
            LoweredGenerationLoopRegionSegment(
                region=loop_result.region,
                source=loop_result.region.source,
            )
        )
        pending_opaque_start = loop_slice.end_index
        index = loop_slice.end_index

    if not segments:
        return GenerationLoopDiscoveryLoweringResult(
            discovery=None,
            diagnostics=(_no_loop_region_diagnostic(body_source),),
        )

    trailing_tokens = tokens[pending_opaque_start:]
    if trailing_tokens:
        segments.append(
            LoweredGenerationLoopOpaqueSegment(
                tokens=trailing_tokens,
                source=_token_source(trailing_tokens[0]),
            )
        )

    return GenerationLoopDiscoveryLoweringResult(
        discovery=LoweredGenerationLoopDiscovery(
            segments=tuple(segments),
            source=body_source,
        ),
        diagnostics=(),
    )


def _parse_loop_range_payload(
    payload: str,
    source: SourceLocation,
) -> _LoopPayload | Diagnostic:
    arguments = _split_top_level_arguments(payload)
    if arguments is None or len(arguments) != 4:
        return _malformed_loop_payload_diagnostic(
            payload,
            source,
            "expected exactly four arguments: Index, Start, End, Step",
        )

    index_name, start, end, step = arguments
    if not _is_identifier(index_name):
        return _malformed_loop_payload_diagnostic(
            payload,
            source,
            f"loop index must be an identifier, got {index_name!r}",
        )

    return _LoopPayload(index_name=index_name, start=start, end=end, step=step)


def _split_top_level_arguments(payload: str) -> tuple[str, ...] | None:
    parts = split_top_level_parts(
        payload,
        delimiters=(PAREN_DELIMITER, BRACKET_DELIMITER, ANGLE_DELIMITER),
        allow_empty_payload=False,
    )
    if parts is None:
        return None
    return tuple(part.text for part in parts)


def _lower_loop_integer_value(
    context: SelectedImplementationLoweringContext,
    expression: str,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> _LoopIntegerValueLowering:
    expression = expression.strip()
    if _is_base_10_integer_literal(expression):
        return _LoopIntegerValueLowering(
            value=_literal_generation_value(expression, source),
            diagnostics=(),
        )

    if not expression.startswith(_VALUE_QUERY_PREFIX):
        return _LoopIntegerValueLowering(
            value=None,
            diagnostics=(_unsupported_loop_bound_diagnostic(expression, source),),
        )

    result = lower_generation_value_query(
        context,
        expression,
        source,
        catalog=catalog,
        environment=environment,
    )
    if result.value is None:
        return _LoopIntegerValueLowering(value=None, diagnostics=result.diagnostics)
    if type(result.value.value) is not int:
        return _LoopIntegerValueLowering(
            value=None,
            diagnostics=(_noninteger_loop_bound_diagnostic(expression, source),),
        )
    return _LoopIntegerValueLowering(value=result.value, diagnostics=())


def _is_loop_directive(token: BodyToken, selector: str) -> bool:
    return (
        isinstance(token, LowerableDirective)
        and token.name == "loop"
        and token.arguments[:1] == (selector,)
        and len(token.arguments) == 2
    )


def _strip_boundary_whitespace_tokens(
    tokens: tuple[RawStringToken | LowerableDirective, ...],
) -> tuple[BodyToken, ...]:
    start = 0
    end = len(tokens)
    while start < end and _is_whitespace_raw_token(tokens[start]):
        start += 1
    while end > start and _is_whitespace_raw_token(tokens[end - 1]):
        end -= 1
    return tuple(tokens[start:end])


def _skip_whitespace_tokens(tokens: tuple[BodyToken, ...], index: int) -> int:
    while index < len(tokens) and _is_whitespace_raw_token(tokens[index]):
        index += 1
    return index


def _is_whitespace_raw_token(token: BodyToken) -> bool:
    return isinstance(token, RawStringToken) and token.text.strip() == ""


def _is_unsupported_loop_directive(token: BodyToken) -> bool:
    return (
        isinstance(token, LowerableDirective)
        and token.name == "loop"
        and len(token.arguments) >= 1
        and token.arguments[0] not in {"range", "unroll"}
    )


def _updated_raw_brace_depth(depth: int, token: BodyToken) -> int:
    if not isinstance(token, RawStringToken):
        return depth
    return raw_brace_depth_after(depth, token.text, clamp_underflow=True)


def _loop_slice_start(
    tokens: tuple[BodyToken, ...],
    index: int,
) -> int | None:
    token = tokens[index]
    if _is_loop_directive(token, "range"):
        return index
    if (
        _is_loop_directive(token, "unroll")
        and _next_non_whitespace_token_is_loop_range(tokens, index + 1)
    ):
        return index
    return None


def _find_embedded_loop_slice(
    tokens: tuple[BodyToken, ...],
    *,
    start: int,
) -> _LoopRegionSliceSearch:
    loop_index = (
        _skip_whitespace_tokens(tokens, start + 1)
        if _is_loop_directive(tokens[start], "unroll")
        else start
    )
    if loop_index >= len(tokens):
        return _loop_slice_diagnostic(
            _malformed_region_diagnostic(
                _token_source(tokens[start]),
                "expected loop<range>(...) region after loop<unroll>(...)",
            )
        )

    loop = tokens[loop_index]
    if not _is_loop_directive(loop, "range"):
        return _LoopRegionSliceSearch(loop_slice=None, diagnostic=None)

    open_index = loop_index + 1
    if open_index >= len(tokens) or not _is_open_brace(tokens[open_index]):
        return _loop_slice_diagnostic(
            _malformed_region_diagnostic(
                _token_source(tokens[open_index]) if open_index < len(tokens) else loop.source,
                "expected raw opening brace after loop<range>(...)",
            )
        )

    close_search = _find_loop_close(tokens, start=open_index + 1)
    if close_search.diagnostic is not None:
        return _loop_slice_diagnostic(close_search.diagnostic)
    if close_search.boundary is None:
        return _loop_slice_diagnostic(
            _malformed_region_diagnostic(
                loop.source,
                "could not find matching close brace for generation loop",
            )
        )

    return _LoopRegionSliceSearch(
        loop_slice=_LoopRegionSlice(
            start_index=start,
            end_index=close_search.boundary.next_index,
        ),
        diagnostic=None,
    )


def _next_non_whitespace_token_is_loop_range(
    tokens: tuple[BodyToken, ...],
    index: int,
) -> bool:
    next_index = _skip_whitespace_tokens(tokens, index)
    return next_index < len(tokens) and _is_loop_directive(tokens[next_index], "range")


def _loop_slice_diagnostic(diagnostic: Diagnostic) -> _LoopRegionSliceSearch:
    return _LoopRegionSliceSearch(loop_slice=None, diagnostic=diagnostic)


def _is_identifier(text: str) -> bool:
    if not text:
        return False
    if not (text[0].isalpha() or text[0] == "_"):
        return False
    return all(char.isalnum() or char == "_" for char in text[1:])


def _is_base_10_integer_literal(text: str) -> bool:
    if text == "0":
        return True
    return text.isdecimal() and not text.startswith("0")


def _literal_generation_value(
    text: str,
    source: SourceLocation,
) -> LoweredGenerationValue:
    return LoweredGenerationValue(
        kind="generation.integer_literal",
        value=int(text),
        source_text=text,
        source=source,
    )


def _find_loop_close(
    tokens: tuple[BodyToken, ...],
    *,
    start: int,
) -> _LoopCloseSearch:
    depth = 1
    for index in range(start, len(tokens)):
        token = tokens[index]
        if not isinstance(token, RawStringToken):
            continue
        for offset, char in enumerate(token.text):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    prefix = token.text[:offset]
                    suffix = token.text[offset + 1 :]
                    if prefix.strip() or suffix.strip():
                        return _loop_close_diagnostic(
                            _malformed_region_diagnostic(
                                token.source,
                                "expected isolated raw close brace",
                            ),
                        )
                    return _LoopCloseSearch(
                        boundary=_LoopBoundary(
                            close_index=index,
                            next_index=index + 1,
                        ),
                        diagnostic=None,
                    )
                if depth < 0:
                    return _loop_close_diagnostic(
                        _malformed_region_diagnostic(
                            token.source,
                            "encountered extra close brace",
                        ),
                    )
    return _LoopCloseSearch(boundary=None, diagnostic=None)


def _loop_close_diagnostic(diagnostic: Diagnostic) -> _LoopCloseSearch:
    return _LoopCloseSearch(boundary=None, diagnostic=diagnostic)


def _is_open_brace(token: BodyToken) -> bool:
    return isinstance(token, RawStringToken) and token.text.strip() == "{"


def _body_source(
    tokens: tuple[BodyToken, ...],
    fallback: SourceLocation,
) -> SourceLocation:
    if not tokens:
        return fallback
    return _token_source(tokens[0])


def _token_source(token: BodyToken) -> SourceLocation:
    return token.source


def _malformed_region_result(
    source: SourceLocation,
    reason: str,
) -> GenerationLoopRegionLoweringResult:
    return GenerationLoopRegionLoweringResult(
        region=None,
        diagnostics=(_malformed_region_diagnostic(source, reason),),
    )


def _malformed_region_diagnostic(
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-LOOP-REGION",
        message=(
            "generation loop region cannot be lowered; "
            f"{reason}"
        ),
        location=source,
    )


def _malformed_loop_payload_diagnostic(
    payload: str,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-LOOP-PAYLOAD",
        message=(
            "generation loop payload cannot be lowered; "
            f"{reason}; got {payload!r}"
        ),
        location=source,
    )


def _unsupported_loop_selector_diagnostic(
    directive: LowerableDirective,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-LOOP-SELECTOR",
        message=(
            "generation loop selector is not supported by M161; "
            f"expected 'range', got {directive.arguments[0]!r}"
        ),
        location=directive.source,
    )


def _unsupported_loop_bound_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-LOOP-BOUND",
        message=(
            "generation loop bound cannot be lowered by M161; expected a "
            "base-10 integer literal or accepted integer value<generation>(...) "
            f"query, got {expression!r}"
        ),
        location=source,
    )


def _noninteger_loop_bound_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONINTEGER-GENERATION-LOOP-BOUND",
        message=(
            "generation loop bound must lower to an integer generation value; "
            f"got {expression!r}"
        ),
        location=source,
    )


def _no_loop_region_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-GENERATION-LOOP-REGION",
        message=(
            "generation loop discovery found no exact top-level "
            "loop<range>(...) region"
        ),
        location=source,
    )
