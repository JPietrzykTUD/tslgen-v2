"""Exact selected-context generation-control region lowering."""

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
    GenerationControlRegionLoweringResult,
    LoweredGenerationControlBranch,
    LoweredGenerationControlRegion,
    LoweredGenerationValue,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)


_VALUE_QUERY_PREFIX = "value<generation>("
_COMPARISON_OPERATORS = ("==", "!=", "<=", ">=", "<", ">")
_RAW_ARITHMETIC_OPERATORS = ("+", "-", "*", "/", "%")


@dataclass(frozen=True, slots=True)
class _BranchBoundary:
    close_index: int
    next_index: int


@dataclass(frozen=True, slots=True)
class _ConditionLowering:
    condition: LoweredGenerationValue | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _BranchCloseSearch:
    boundary: _BranchBoundary | None
    diagnostic: Diagnostic | None


def lower_generation_control_region(
    context: SelectedImplementationLoweringContext,
    body: ImplementationBody,
    *,
    catalog: Catalog | None = None,
    environment: SelectedTypeEnvironment | None = None,
) -> GenerationControlRegionLoweringResult:
    tokens = body.tokens

    if not tokens:
        return _malformed_region_result(
            body.source,
            "expected if<generation>(...) { ... } else<generation> { ... }",
        )

    if_directive = tokens[0]
    if (
        not isinstance(if_directive, LowerableDirective)
        or if_directive.name != "if"
        or len(if_directive.arguments) != 2
        or if_directive.arguments[0] != "generation"
    ):
        return _malformed_region_result(
            _token_source(tokens[0]) if tokens else body.source,
            "expected leading if<generation>(Condition) directive",
        )

    if len(tokens) < 2:
        return _malformed_region_result(
            if_directive.source,
            "expected raw opening brace after if<generation>(...)",
        )

    if not _is_open_brace(tokens[1]):
        return _malformed_region_result(
            _token_source(tokens[1]),
            "expected raw opening brace after if<generation>(...)",
        )

    true_search = _find_branch_close(tokens, start=2)
    if true_search.diagnostic is not None:
        return GenerationControlRegionLoweringResult(
            region=None,
            diagnostics=(true_search.diagnostic,),
        )
    true_boundary = true_search.boundary
    if true_boundary is None:
        return _malformed_region_result(
            if_directive.source,
            "could not find matching close brace for true branch",
        )

    else_index = true_boundary.next_index
    if else_index >= len(tokens):
        return _malformed_region_result(
            if_directive.source,
            "expected else<generation> branch after true branch",
        )

    else_directive = tokens[else_index]
    if (
        not isinstance(else_directive, LowerableDirective)
        or else_directive.name != "else"
        or else_directive.arguments != ("generation",)
    ):
        return _malformed_region_result(
            _token_source(else_directive),
            "expected else<generation> directive after true branch",
        )

    else_open_index = else_index + 1
    if else_open_index >= len(tokens) or not _is_open_brace(tokens[else_open_index]):
        return _malformed_region_result(
            _token_source(else_directive),
            "expected raw opening brace after else<generation>",
        )

    false_start = else_open_index + 1
    false_search = _find_branch_close(tokens, start=false_start)
    if false_search.diagnostic is not None:
        return GenerationControlRegionLoweringResult(
            region=None,
            diagnostics=(false_search.diagnostic,),
        )
    false_boundary = false_search.boundary
    if false_boundary is None:
        return _malformed_region_result(
            else_directive.source,
            "could not find matching close brace for false branch",
        )
    if false_boundary.next_index != len(tokens):
        return _malformed_region_result(
            _token_source(tokens[false_boundary.next_index]),
            "unexpected tokens after generation-control region",
        )

    condition_result = _lower_generation_condition(
        context,
        if_directive.arguments[1],
        if_directive.source,
        catalog=catalog,
        environment=environment,
    )
    if condition_result.condition is None:
        return GenerationControlRegionLoweringResult(
            region=None,
            diagnostics=condition_result.diagnostics,
        )
    condition = condition_result.condition

    true_tokens = tokens[2:true_boundary.close_index]
    false_tokens = tokens[false_start:false_boundary.close_index]
    true_branch = LoweredGenerationControlBranch(
        tokens=true_tokens,
        source=_branch_source(true_tokens, if_directive.source),
    )
    false_branch = LoweredGenerationControlBranch(
        tokens=false_tokens,
        source=_branch_source(false_tokens, else_directive.source),
    )

    return GenerationControlRegionLoweringResult(
        region=LoweredGenerationControlRegion(
            condition=condition,
            selected_branch=true_branch if condition.value else false_branch,
            unselected_branch=false_branch if condition.value else true_branch,
            source=if_directive.source,
        ),
        diagnostics=(),
    )


def _lower_generation_condition(
    context: SelectedImplementationLoweringContext,
    condition: str,
    source: SourceLocation,
    *,
    catalog: Catalog | None,
    environment: SelectedTypeEnvironment | None,
) -> _ConditionLowering:
    left_query, suffix = _extract_leading_value_query(condition)
    if left_query is None:
        value_result = lower_generation_value_query(
            context,
            condition,
            source,
            catalog=catalog,
            environment=environment,
        )
        if value_result.value is None:
            return _ConditionLowering(
                condition=None,
                diagnostics=value_result.diagnostics,
            )
        if type(value_result.value.value) is not bool:
            return _ConditionLowering(
                condition=None,
                diagnostics=(
                    _nonboolean_condition_diagnostic(
                        value_result.value.source_text,
                        source,
                    ),
                ),
            )
        return _ConditionLowering(condition=value_result.value, diagnostics=())

    left_result = lower_generation_value_query(
        context,
        left_query,
        source,
        catalog=catalog,
        environment=environment,
    )
    if left_result.value is None:
        return _ConditionLowering(
            condition=None,
            diagnostics=left_result.diagnostics,
        )

    if not suffix:
        if type(left_result.value.value) is not bool:
            return _ConditionLowering(
                condition=None,
                diagnostics=(
                    _nonboolean_condition_diagnostic(
                        left_result.value.source_text,
                        source,
                    ),
                ),
            )
        return _ConditionLowering(condition=left_result.value, diagnostics=())

    if suffix.startswith(_RAW_ARITHMETIC_OPERATORS):
        return _ConditionLowering(
            condition=None,
            diagnostics=(
                _unsupported_condition_diagnostic(
                    condition,
                    source,
                    "raw arithmetic operator text is not supported",
                ),
            ),
        )

    comparison = _comparison_suffix(suffix)
    if comparison is None:
        return _ConditionLowering(
            condition=None,
            diagnostics=(
                _malformed_condition_diagnostic(
                    condition,
                    source,
                    "expected a comparison operator followed by an integer literal",
                ),
            ),
        )

    operator, right_text = comparison
    if type(left_result.value.value) is not int:
        return _ConditionLowering(
            condition=None,
            diagnostics=(
                _noninteger_condition_diagnostic(
                    left_result.value.source_text,
                    source,
                ),
            ),
        )
    if _contains_comparison_operator(right_text):
        return _ConditionLowering(
            condition=None,
            diagnostics=(
                _malformed_condition_diagnostic(
                    condition,
                    source,
                    "expected exactly one top-level comparison operator",
                ),
            ),
        )
    if _contains_raw_arithmetic_operator(right_text):
        return _ConditionLowering(
            condition=None,
            diagnostics=(
                _unsupported_condition_diagnostic(
                    condition,
                    source,
                    "raw arithmetic operator text is not supported",
                ),
            ),
        )
    if not _is_base_10_integer_literal(right_text):
        return _ConditionLowering(
            condition=None,
            diagnostics=(
                _malformed_condition_diagnostic(
                    condition,
                    source,
                    "expected a base-10 integer literal on the right side",
                ),
            ),
        )

    return _ConditionLowering(
        condition=LoweredGenerationValue(
            kind="generation.integer_comparison",
            value=_evaluate_integer_comparison(
                left_result.value.value,
                operator,
                int(right_text),
            ),
            source_text=condition,
            source=source,
        ),
        diagnostics=(),
    )


def _extract_leading_value_query(condition: str) -> tuple[str | None, str]:
    stripped = condition.strip()
    if stripped != condition or not condition.startswith(_VALUE_QUERY_PREFIX):
        return None, condition

    open_index = len(_VALUE_QUERY_PREFIX) - 1
    close_index = _matching_close_paren(condition, open_index)
    if close_index is None:
        return None, condition

    return condition[: close_index + 1], condition[close_index + 1 :].strip()


def _matching_close_paren(text: str, open_index: int) -> int | None:
    depth = 1
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _comparison_suffix(suffix: str) -> tuple[str, str] | None:
    for operator in _COMPARISON_OPERATORS:
        if suffix.startswith(operator):
            right_text = suffix[len(operator) :].strip()
            if not right_text:
                return None
            return operator, right_text
    return None


def _contains_comparison_operator(text: str) -> bool:
    return any(operator in text for operator in _COMPARISON_OPERATORS)


def _contains_raw_arithmetic_operator(text: str) -> bool:
    return any(operator in text for operator in _RAW_ARITHMETIC_OPERATORS)


def _is_base_10_integer_literal(text: str) -> bool:
    if text == "0":
        return True
    return text.isdecimal() and not text.startswith("0")


def _evaluate_integer_comparison(
    left: int,
    operator: str,
    right: int,
) -> bool:
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    raise AssertionError(f"unsupported generation comparison operator {operator!r}")


def _find_branch_close(
    tokens: tuple[BodyToken, ...],
    *,
    start: int,
) -> _BranchCloseSearch:
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
                    if prefix.strip():
                        return _branch_close_diagnostic(
                            _malformed_region_diagnostic(
                                token.source,
                                "expected isolated raw close brace",
                            ),
                        )
                    unsupported = _unsupported_close_suffix_diagnostic(
                        suffix,
                        tokens,
                        index,
                    )
                    if unsupported is not None:
                        return _branch_close_diagnostic(unsupported)
                    if suffix.strip():
                        return _branch_close_diagnostic(
                            _malformed_region_diagnostic(
                                token.source,
                                "expected isolated raw close brace",
                            ),
                        )
                    return _BranchCloseSearch(
                        boundary=_BranchBoundary(
                            close_index=index,
                            next_index=index + 1,
                        ),
                        diagnostic=None,
                    )
                if depth < 0:
                    return _branch_close_diagnostic(
                        _malformed_region_diagnostic(
                            token.source,
                            "encountered extra close brace",
                        ),
                    )
    return _BranchCloseSearch(boundary=None, diagnostic=None)


def _unsupported_close_suffix_diagnostic(
    suffix: str,
    tokens: tuple[BodyToken, ...],
    close_index: int,
) -> Diagnostic | None:
    stripped = suffix.strip()
    if stripped.startswith("else if<generation>") or (
        stripped == "else"
        and _next_token_is_generation_if(tokens, close_index)
    ):
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
            message=(
                "generation-control branch-chain regions with "
                "else if<generation> are not supported by M156"
            ),
            location=tokens[close_index].source,
        )
    if stripped.startswith("else {"):
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
            message=(
                "plain else generation-control regions are not supported "
                "by M156; expected else<generation>"
            ),
            location=tokens[close_index].source,
        )
    return None


def _next_token_is_generation_if(
    tokens: tuple[BodyToken, ...],
    close_index: int,
) -> bool:
    next_index = close_index + 1
    if next_index >= len(tokens):
        return False
    token = tokens[next_index]
    return (
        isinstance(token, LowerableDirective)
        and token.name == "if"
        and len(token.arguments) == 2
        and token.arguments[0] == "generation"
    )


def _branch_close_diagnostic(diagnostic: Diagnostic) -> _BranchCloseSearch:
    return _BranchCloseSearch(boundary=None, diagnostic=diagnostic)


def _is_open_brace(token: BodyToken) -> bool:
    return isinstance(token, RawStringToken) and token.text.strip() == "{"


def _branch_source(
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
) -> GenerationControlRegionLoweringResult:
    return GenerationControlRegionLoweringResult(
        region=None,
        diagnostics=(_malformed_region_diagnostic(source, reason),),
    )


def _malformed_region_diagnostic(
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-CONTROL-REGION",
        message=(
            "generation-control region cannot be lowered; "
            f"{reason}"
        ),
        location=source,
    )


def _nonboolean_condition_diagnostic(
    condition: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONBOOLEAN-GENERATION-CONTROL-CONDITION",
        message=(
            "generation-control condition must lower to a boolean generation "
            f"value; got {condition!r}"
        ),
        location=source,
    )


def _noninteger_condition_diagnostic(
    condition: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONINTEGER-GENERATION-CONTROL-CONDITION",
        message=(
            "generation-control integer comparison left side must lower to an "
            f"integer generation value; got {condition!r}"
        ),
        location=source,
    )


def _malformed_condition_diagnostic(
    condition: str,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-GENERATION-CONTROL-CONDITION",
        message=(
            "generation-control condition cannot be lowered; "
            f"{reason}; got {condition!r}"
        ),
        location=source,
    )


def _unsupported_condition_diagnostic(
    condition: str,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-CONDITION",
        message=(
            "generation-control condition is outside the M158 comparison "
            f"boundary; {reason}; got {condition!r}"
        ),
        location=source,
    )
