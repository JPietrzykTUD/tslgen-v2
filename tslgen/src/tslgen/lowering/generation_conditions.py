"""Typed generation-time boolean condition lowering."""

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog
from tslgen.lowering.generation_values import (
    lower_generation_expression,
    lower_generation_value_query,
)
from tslgen.lowering.model import (
    GenerationValueQueryLoweringResult,
    LoweredGenerationValue,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
)

_VALUE_QUERY_PREFIX = "value<generation>("
_COMPARISON_OPERATORS = ("==", "!=", "<=", ">=", "<", ">")
_RAW_ARITHMETIC_OPERATORS = ("+", "-", "*", "/", "%")
_KNOWN_ANGLE_TAGS = ("<generation>", "<backend>")


def lower_generation_condition(
    context: SelectedImplementationLoweringContext,
    condition: str,
    source: SourceLocation,
    *,
    catalog: Catalog | None = None,
    environment: SelectedTypeEnvironment | None = None,
) -> GenerationValueQueryLoweringResult:
    """Lower the exact generation-control condition grammar."""

    return _GenerationConditionParser(
        context,
        condition,
        source,
        catalog=catalog,
        environment=environment,
    ).parse()


class _GenerationConditionParser:
    def __init__(
        self,
        context: SelectedImplementationLoweringContext,
        condition: str,
        source: SourceLocation,
        *,
        catalog: Catalog | None,
        environment: SelectedTypeEnvironment | None,
    ) -> None:
        self._context = context
        self._condition = condition
        self._source = source
        self._catalog = catalog
        self._environment = environment
        self._position = 0

    def parse(self) -> GenerationValueQueryLoweringResult:
        result = self._parse_or()
        if result.value is None:
            return result

        self._skip_whitespace()
        if self._position != len(self._condition):
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _malformed_condition_diagnostic(
                        self._condition,
                        self._source,
                        "unexpected trailing condition text",
                    ),
                ),
            )
        return result

    def _parse_or(self) -> GenerationValueQueryLoweringResult:
        start = self._position
        left = self._parse_and()
        if left.value is None:
            return left

        while True:
            self._skip_whitespace()
            if not self._match("||"):
                return left
            right = self._parse_and()
            if right.value is None:
                return right
            left = self._combine_boolean(start, left.value, right.value, "||")

    def _parse_and(self) -> GenerationValueQueryLoweringResult:
        start = self._position
        left = self._parse_not()
        if left.value is None:
            return left

        while True:
            self._skip_whitespace()
            if not self._match("&&"):
                return left
            right = self._parse_not()
            if right.value is None:
                return right
            left = self._combine_boolean(start, left.value, right.value, "&&")

    def _parse_not(self) -> GenerationValueQueryLoweringResult:
        self._skip_whitespace()
        start = self._position
        if not self._match("!"):
            return self._parse_primary()

        operand = self._parse_not()
        if operand.value is None:
            return operand
        if type(operand.value.value) is not bool:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _nonboolean_condition_diagnostic(
                        operand.value.source_text,
                        self._source,
                    ),
                ),
            )

        return GenerationValueQueryLoweringResult(
            value=LoweredGenerationValue(
                kind="generation.boolean_condition",
                value=not operand.value.value,
                source_text=self._condition[start : self._position].strip(),
                source=self._source,
            ),
            diagnostics=(),
        )

    def _parse_primary(self) -> GenerationValueQueryLoweringResult:
        self._skip_whitespace()
        start = self._position
        if self._position >= len(self._condition):
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _malformed_condition_diagnostic(
                        self._condition,
                        self._source,
                        "expected a generation condition predicate",
                    ),
                ),
            )

        if self._match("("):
            inner = self._parse_or()
            if inner.value is None:
                return inner
            self._skip_whitespace()
            if not self._match(")"):
                return GenerationValueQueryLoweringResult(
                    value=None,
                    diagnostics=(
                        _malformed_condition_diagnostic(
                            self._condition,
                            self._source,
                            "expected closing ')' for generation condition group",
                        ),
                    ),
                )
            return GenerationValueQueryLoweringResult(
                value=LoweredGenerationValue(
                    kind="generation.boolean_condition",
                    value=inner.value.value,
                    source_text=self._condition[start : self._position].strip(),
                    source=self._source,
                ),
                diagnostics=(),
            )

        return self._parse_predicate()

    def _parse_predicate(self) -> GenerationValueQueryLoweringResult:
        start = self._position
        end = _predicate_end(self._condition, start)
        self._position = end
        predicate = self._condition[start:end].strip()
        if not predicate:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _malformed_condition_diagnostic(
                        self._condition,
                        self._source,
                        "expected a generation condition predicate",
                    ),
                ),
            )

        comparison = _split_top_level_comparison(predicate)
        if comparison is not None:
            left_text, operator, right_text = comparison
            return self._lower_integer_comparison(
                predicate,
                left_text,
                operator,
                right_text,
            )

        if _contains_top_level_raw_arithmetic(predicate):
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _unsupported_condition_diagnostic(
                        predicate,
                        self._source,
                        "raw arithmetic operator text is not supported",
                    ),
                ),
            )

        value_result = self._lower_generation_value(predicate)
        if value_result.value is None:
            return value_result
        if type(value_result.value.value) is not bool:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _nonboolean_condition_diagnostic(
                        value_result.value.source_text,
                        self._source,
                    ),
                ),
            )
        return value_result

    def _lower_integer_comparison(
        self,
        predicate: str,
        left_text: str,
        operator: str,
        right_text: str,
    ) -> GenerationValueQueryLoweringResult:
        left_result = self._lower_generation_value(left_text)
        if left_result.value is None:
            return left_result

        if type(left_result.value.value) is not int:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _noninteger_condition_diagnostic(
                        left_result.value.source_text,
                        self._source,
                    ),
                ),
            )

        if _split_top_level_comparison(right_text) is not None:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _malformed_condition_diagnostic(
                        predicate,
                        self._source,
                        "expected exactly one top-level comparison operator",
                    ),
                ),
            )

        if _contains_top_level_raw_arithmetic(right_text):
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _unsupported_condition_diagnostic(
                        predicate,
                        self._source,
                        "raw arithmetic operator text is not supported",
                    ),
                ),
            )

        if not _is_base_10_integer_literal(right_text):
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _malformed_condition_diagnostic(
                        predicate,
                        self._source,
                        "expected a base-10 integer literal on the right side",
                    ),
                ),
            )

        return GenerationValueQueryLoweringResult(
            value=LoweredGenerationValue(
                kind="generation.integer_comparison",
                value=_evaluate_integer_comparison(
                    left_result.value.value,
                    operator,
                    int(right_text),
                ),
                source_text=predicate,
                source=self._source,
            ),
            diagnostics=(),
        )

    def _lower_generation_value(
        self,
        expression: str,
    ) -> GenerationValueQueryLoweringResult:
        if expression.startswith(_VALUE_QUERY_PREFIX):
            return lower_generation_value_query(
                self._context,
                expression,
                self._source,
                catalog=self._catalog,
                environment=self._environment,
            )
        return lower_generation_expression(
            self._context,
            expression,
            self._source,
            catalog=self._catalog,
            environment=self._environment,
        )

    def _combine_boolean(
        self,
        start: int,
        left: LoweredGenerationValue,
        right: LoweredGenerationValue,
        operator: str,
    ) -> GenerationValueQueryLoweringResult:
        if type(left.value) is not bool:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _nonboolean_condition_diagnostic(
                        left.source_text,
                        self._source,
                    ),
                ),
            )
        if type(right.value) is not bool:
            return GenerationValueQueryLoweringResult(
                value=None,
                diagnostics=(
                    _nonboolean_condition_diagnostic(
                        right.source_text,
                        self._source,
                    ),
                ),
            )

        if operator == "&&":
            value = left.value and right.value
        elif operator == "||":
            value = left.value or right.value
        else:
            raise AssertionError(f"unsupported generation boolean operator {operator!r}")

        return GenerationValueQueryLoweringResult(
            value=LoweredGenerationValue(
                kind="generation.boolean_condition",
                value=value,
                source_text=self._condition[start : self._position].strip(),
                source=self._source,
            ),
            diagnostics=(),
        )

    def _match(self, token: str) -> bool:
        if not self._condition.startswith(token, self._position):
            return False
        self._position += len(token)
        return True

    def _skip_whitespace(self) -> None:
        while (
            self._position < len(self._condition)
            and self._condition[self._position].isspace()
        ):
            self._position += 1


def _predicate_end(text: str, start: int) -> int:
    paren_depth = 0
    bracket_depth = 0
    index = start

    while index < len(text):
        skipped = _skip_known_angle_tag(text, index)
        if skipped != index:
            index = skipped
            continue

        if paren_depth == 0 and bracket_depth == 0:
            if text.startswith("&&", index) or text.startswith("||", index):
                break
            if text[index] == ")":
                break

        char = text[index]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            if paren_depth > 0:
                paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth > 0:
            bracket_depth -= 1
        index += 1

    return index


def _split_top_level_comparison(text: str) -> tuple[str, str, str] | None:
    index = 0
    paren_depth = 0
    bracket_depth = 0

    while index < len(text):
        skipped = _skip_known_angle_tag(text, index)
        if skipped != index:
            index = skipped
            continue

        char = text[index]
        if char == "(":
            paren_depth += 1
            index += 1
            continue
        if char == ")":
            if paren_depth > 0:
                paren_depth -= 1
            index += 1
            continue
        if char == "[":
            bracket_depth += 1
            index += 1
            continue
        if char == "]":
            if bracket_depth > 0:
                bracket_depth -= 1
            index += 1
            continue

        if paren_depth == 0 and bracket_depth == 0:
            for operator in _COMPARISON_OPERATORS:
                if text.startswith(operator, index):
                    left_text = text[:index].strip()
                    right_text = text[index + len(operator) :].strip()
                    if not left_text or not right_text:
                        return None
                    return left_text, operator, right_text

        index += 1

    return None


def _contains_top_level_raw_arithmetic(text: str) -> bool:
    index = 0
    paren_depth = 0
    bracket_depth = 0

    while index < len(text):
        skipped = _skip_known_angle_tag(text, index)
        if skipped != index:
            index = skipped
            continue

        char = text[index]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            if paren_depth > 0:
                paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif (
            paren_depth == 0
            and bracket_depth == 0
            and char in _RAW_ARITHMETIC_OPERATORS
        ):
            return True
        index += 1

    return False


def _skip_known_angle_tag(text: str, index: int) -> int:
    for tag in _KNOWN_ANGLE_TAGS:
        if text.startswith(tag, index):
            return index + len(tag)
    return index


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


def _nonboolean_condition_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONBOOLEAN-GENERATION-CONTROL-CONDITION",
        message=(
            "generation-control condition must lower to a boolean generation "
            f"value; got {expression!r}"
        ),
        location=source,
    )


def _noninteger_condition_diagnostic(
    expression: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-NONINTEGER-GENERATION-CONTROL-CONDITION",
        message=(
            "generation-control integer comparison must compare an integer "
            f"generation value; got {expression!r}"
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
            "generation-control condition is malformed; "
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
            "generation-control condition is outside the typed generation "
            f"boolean condition boundary; {reason}; got {condition!r}"
        ),
        location=source,
    )
