"""Exact selected-context generation loop-region lowering."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Catalog,
    ImplementationBody,
    LowerableDirective,
    RawStringToken,
)
from tslgen.lowering.generation_values import lower_generation_value_query
from tslgen.lowering.model import (
    GenerationLoopRegionLoweringResult,
    LoweredGenerationLoopBody,
    LoweredGenerationLoopRegion,
    LoweredGenerationValue,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)

_VALUE_QUERY_PREFIX = "value<generation>("


@dataclass(frozen=True, slots=True)
class _LoopBoundary:
    close_index: int
    next_index: int


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
    body: ImplementationBody,
    *,
    catalog: Catalog | None = None,
    environment: SelectedTypeEnvironment | None = None,
) -> GenerationLoopRegionLoweringResult:
    tokens = body.tokens
    if not tokens:
        return _malformed_region_result(
            body.source,
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
        loop_index = 1
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
    parts: list[str] = []
    start = 0
    paren_depth = 0
    bracket_depth = 0
    angle_depth = 0

    for index, char in enumerate(payload):
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth -= 1
        elif (
            char == ","
            and paren_depth == 0
            and bracket_depth == 0
            and angle_depth == 0
        ):
            part = payload[start:index].strip()
            if not part:
                return None
            parts.append(part)
            start = index + 1
        if paren_depth < 0 or bracket_depth < 0 or angle_depth < 0:
            return None

    if paren_depth != 0 or bracket_depth != 0 or angle_depth != 0:
        return None
    part = payload[start:].strip()
    if not part:
        return None
    parts.append(part)
    return tuple(parts)


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
