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
from tslgen.syntax.tsil_lexical import PAREN_DELIMITER, matching_close


_VALUE_QUERY_PREFIX = "value<generation>("
_COMPARISON_OPERATORS = ("==", "!=", "<=", ">=", "<", ">")
_RAW_ARITHMETIC_OPERATORS = ("+", "-", "*", "/", "%")


@dataclass(frozen=True, slots=True)
class _BranchBoundary:
    close_index: int
    next_index: int
    connector: str = "none"


@dataclass(frozen=True, slots=True)
class _GenerationControlArm:
    condition: str | None
    condition_source: SourceLocation
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class _GenerationControlShape:
    conditional_arms: tuple[_GenerationControlArm, ...]
    fallback_arm: _GenerationControlArm | None
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class _GenerationControlShapeParse:
    shape: _GenerationControlShape | None
    diagnostics: tuple[Diagnostic, ...]


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

    shape_result = _parse_generation_control_shape(tokens, body.source)
    if shape_result.shape is None:
        return GenerationControlRegionLoweringResult(
            region=None,
            diagnostics=shape_result.diagnostics,
        )
    shape = shape_result.shape

    selected_arm: _GenerationControlArm | None = None
    selected_condition: LoweredGenerationValue | None = None
    evaluated_conditions: list[LoweredGenerationValue] = []

    for arm in shape.conditional_arms:
        assert arm.condition is not None
        condition_result = _lower_generation_condition(
            context,
            arm.condition,
            arm.condition_source,
            catalog=catalog,
            environment=environment,
        )
        if condition_result.condition is None:
            return GenerationControlRegionLoweringResult(
                region=None,
                diagnostics=condition_result.diagnostics,
            )
        condition = condition_result.condition
        evaluated_conditions.append(condition)
        if condition.value:
            selected_arm = arm
            selected_condition = condition
            break

    if selected_arm is None:
        if shape.fallback_arm is None:
            return GenerationControlRegionLoweringResult(
                region=None,
                diagnostics=(
                    _no_matching_branch_diagnostic(
                        shape.conditional_arms[0].condition_source
                    ),
                ),
            )
        selected_arm = shape.fallback_arm
        selected_condition = evaluated_conditions[-1]

    selected_branch = LoweredGenerationControlBranch(
        tokens=selected_arm.tokens,
        source=selected_arm.source,
    )
    unselected_branch = _unselected_branch(shape, selected_arm)
    assert selected_condition is not None

    return GenerationControlRegionLoweringResult(
        region=LoweredGenerationControlRegion(
            condition=selected_condition,
            selected_branch=selected_branch,
            unselected_branch=unselected_branch,
            source=shape.source,
        ),
        diagnostics=(),
    )


def _parse_generation_control_shape(
    tokens: tuple[BodyToken, ...],
    body_source: SourceLocation,
) -> _GenerationControlShapeParse:
    if not tokens:
        return _malformed_shape_parse(
            body_source,
            "expected if<generation>(...) { ... } else<generation> { ... }",
        )

    if_directive = tokens[0]
    if (
        not isinstance(if_directive, LowerableDirective)
        or if_directive.name != "if"
        or len(if_directive.arguments) != 2
        or if_directive.arguments[0] != "generation"
    ):
        return _malformed_shape_parse(
            _token_source(tokens[0]) if tokens else body_source,
            "expected leading if<generation>(Condition) directive",
        )

    if len(tokens) < 2:
        return _malformed_shape_parse(
            if_directive.source,
            "expected raw opening brace after if<generation>(...)",
        )

    if not _is_open_brace(tokens[1]):
        return _malformed_shape_parse(
            _token_source(tokens[1]),
            "expected raw opening brace after if<generation>(...)",
        )

    arms: list[_GenerationControlArm] = []
    directive_index = 0

    while True:
        directive = tokens[directive_index]
        if (
            not isinstance(directive, LowerableDirective)
            or directive.name != "if"
            or len(directive.arguments) != 2
            or directive.arguments[0] != "generation"
        ):
            return _malformed_shape_parse(
                _token_source(directive),
                "expected if<generation>(Condition) branch",
            )

        open_index = directive_index + 1
        if open_index >= len(tokens) or not _is_open_brace(tokens[open_index]):
            return _malformed_shape_parse(
                directive.source,
                "expected raw opening brace after if<generation>(...)",
            )

        body_start = open_index + 1
        branch_search = _find_branch_close(tokens, start=body_start)
        if branch_search.diagnostic is not None:
            return _diagnostic_shape_parse(branch_search.diagnostic)
        boundary = branch_search.boundary
        if boundary is None:
            return _malformed_shape_parse(
                directive.source,
                "could not find matching close brace for generation branch",
            )

        branch_tokens = tokens[body_start:boundary.close_index]
        arms.append(
            _GenerationControlArm(
                condition=directive.arguments[1],
                condition_source=directive.source,
                tokens=branch_tokens,
                source=_branch_source(branch_tokens, directive.source),
            )
        )

        if boundary.connector == "else_if":
            directive_index = boundary.next_index
            continue

        next_index = boundary.next_index
        if next_index >= len(tokens):
            if len(arms) == 1:
                return _malformed_shape_parse(
                    if_directive.source,
                    "expected else<generation> branch after true branch",
                )
            return _shape_parse(
                _GenerationControlShape(
                    conditional_arms=tuple(arms),
                    fallback_arm=None,
                    source=if_directive.source,
                )
            )

        if _tokens_start_generation_else_if(tokens, next_index):
            directive_index = next_index + 1
            continue

        fallback_result = _parse_generation_fallback_arm(tokens, next_index)
        if fallback_result.shape is not None:
            return _shape_parse(
                _GenerationControlShape(
                    conditional_arms=tuple(arms),
                    fallback_arm=fallback_result.shape.fallback_arm,
                    source=if_directive.source,
                )
            )
        return fallback_result


def _parse_generation_fallback_arm(
    tokens: tuple[BodyToken, ...],
    else_index: int,
) -> _GenerationControlShapeParse:
    else_directive = tokens[else_index]
    if (
        not isinstance(else_directive, LowerableDirective)
        or else_directive.name != "else"
        or else_directive.arguments != ("generation",)
    ):
        return _malformed_shape_parse(
            _token_source(else_directive),
            "expected else<generation> directive after generation branch",
        )

    else_open_index = else_index + 1
    if else_open_index >= len(tokens) or not _is_open_brace(tokens[else_open_index]):
        return _malformed_shape_parse(
            _token_source(else_directive),
            "expected raw opening brace after else<generation>",
        )

    fallback_start = else_open_index + 1
    fallback_search = _find_branch_close(
        tokens,
        start=fallback_start,
        allow_else_if_suffix=False,
    )
    if fallback_search.diagnostic is not None:
        return _diagnostic_shape_parse(fallback_search.diagnostic)
    fallback_boundary = fallback_search.boundary
    if fallback_boundary is None:
        return _malformed_shape_parse(
            else_directive.source,
            "could not find matching close brace for else<generation> branch",
        )
    if fallback_boundary.next_index != len(tokens):
        return _malformed_shape_parse(
            _token_source(tokens[fallback_boundary.next_index]),
            "unexpected tokens after generation-control region",
        )

    fallback_tokens = tokens[fallback_start:fallback_boundary.close_index]
    fallback_arm = _GenerationControlArm(
        condition=None,
        condition_source=else_directive.source,
        tokens=fallback_tokens,
        source=_branch_source(fallback_tokens, else_directive.source),
    )
    return _shape_parse(
        _GenerationControlShape(
            conditional_arms=(),
            fallback_arm=fallback_arm,
            source=else_directive.source,
        )
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
    close_index = matching_close(condition, open_index, PAREN_DELIMITER)
    if close_index is None:
        return None, condition

    return condition[: close_index + 1], condition[close_index + 1 :].strip()


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
    allow_else_if_suffix: bool = True,
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
                    if (
                        allow_else_if_suffix
                        and suffix.strip() == "else"
                        and _next_token_is_generation_if(tokens, index)
                    ):
                        return _BranchCloseSearch(
                            boundary=_BranchBoundary(
                                close_index=index,
                                next_index=index + 1,
                                connector="else_if",
                            ),
                            diagnostic=None,
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
                            connector="none",
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
    if stripped.startswith("else if<generation>"):
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
            message=(
                "generation-control branch-chain regions require classified "
                "else if<generation> directive tokens"
            ),
            location=tokens[close_index].source,
        )
    if stripped == "else" or stripped.startswith("else {"):
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-REGION",
            message=(
                "plain target-language else generation-control regions are "
                "not supported; expected else<generation>"
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


def _tokens_start_generation_else_if(
    tokens: tuple[BodyToken, ...],
    next_index: int,
) -> bool:
    if next_index + 1 >= len(tokens):
        return False
    prefix = tokens[next_index]
    directive = tokens[next_index + 1]
    return (
        isinstance(prefix, RawStringToken)
        and prefix.text.strip() == "else"
        and isinstance(directive, LowerableDirective)
        and directive.name == "if"
        and len(directive.arguments) == 2
        and directive.arguments[0] == "generation"
    )


def _branch_close_diagnostic(diagnostic: Diagnostic) -> _BranchCloseSearch:
    return _BranchCloseSearch(boundary=None, diagnostic=diagnostic)


def _shape_parse(
    shape: _GenerationControlShape,
) -> _GenerationControlShapeParse:
    return _GenerationControlShapeParse(shape=shape, diagnostics=())


def _diagnostic_shape_parse(
    diagnostic: Diagnostic,
) -> _GenerationControlShapeParse:
    return _GenerationControlShapeParse(shape=None, diagnostics=(diagnostic,))


def _malformed_shape_parse(
    source: SourceLocation,
    reason: str,
) -> _GenerationControlShapeParse:
    return _diagnostic_shape_parse(_malformed_region_diagnostic(source, reason))


def _unselected_branch(
    shape: _GenerationControlShape,
    selected_arm: _GenerationControlArm,
) -> LoweredGenerationControlBranch:
    arms = list(shape.conditional_arms)
    if shape.fallback_arm is not None:
        arms.append(shape.fallback_arm)
    unselected_arms = tuple(arm for arm in arms if arm is not selected_arm)
    if not unselected_arms:
        return LoweredGenerationControlBranch(tokens=(), source=selected_arm.source)

    tokens: list[BodyToken] = []
    for arm in unselected_arms:
        tokens.extend(arm.tokens)
    return LoweredGenerationControlBranch(
        tokens=tuple(tokens),
        source=unselected_arms[0].source,
    )


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


def _no_matching_branch_diagnostic(source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NO-MATCHING-GENERATION-CONTROL-BRANCH",
        message=(
            "generation-control branch chain cannot select a branch; no "
            "condition lowered to true and no final else<generation> fallback "
            "is present"
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
