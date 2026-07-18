"""Bounded, binding-aware parsing for PIVOT residual target expressions.

The parser deliberately preserves target spelling and trivia.  It recognizes
only enough C++ and Rust structure to distinguish lexical binding uses from
names that must stay target-language text, and to retain delimiter and typed
PIVOT-call nesting for deterministic inlining.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tslc.diagnostics import SourceSpan
from tslc_pivot.body_ir import (
    PivotBinding,
    PivotBindingId,
    PivotBody,
    PivotCall,
    PivotExpression,
    PivotFixedCall,
    PivotLocal,
    PivotResidualStatementSequence,
    PivotResidualText,
)
from tslc_pivot.model import PivotLanguage


class PivotTokenKind(str, Enum):
    TRIVIA = "trivia"
    IDENTIFIER = "identifier"
    RAW_IDENTIFIER = "raw_identifier"
    NUMBER = "number"
    OPERATOR = "operator"
    PUNCTUATION = "punctuation"


class PivotNameRole(str, Enum):
    UNQUALIFIED = "unqualified"
    QUALIFIED = "qualified"
    MEMBER = "member"
    CALLABLE = "callable"
    RAW_IDENTIFIER = "raw_identifier"


@dataclass(frozen=True, slots=True)
class PivotToken:
    text: str
    kind: PivotTokenKind


@dataclass(frozen=True, slots=True)
class PivotTargetName:
    text: str
    role: PivotNameRole


@dataclass(frozen=True, slots=True)
class PivotBindingReference:
    binding: PivotBinding


@dataclass(frozen=True, slots=True)
class PivotParsedCall:
    call: PivotCall
    arguments: tuple[PivotParsedExpression, ...]


@dataclass(frozen=True, slots=True)
class PivotParsedFixedCall:
    call: PivotFixedCall
    arguments: tuple[PivotParsedExpression, ...]


@dataclass(frozen=True, slots=True)
class PivotDelimiterGroup:
    opening: str
    items: tuple[PivotExpressionNode, ...]
    closing: str


type PivotExpressionNode = (
    PivotToken
    | PivotTargetName
    | PivotBindingReference
    | PivotParsedCall
    | PivotParsedFixedCall
    | PivotDelimiterGroup
)


@dataclass(frozen=True, slots=True)
class PivotParsedExpression:
    items: tuple[PivotExpressionNode, ...]
    source: SourceSpan | None


@dataclass(frozen=True, slots=True)
class PivotParsedLocal:
    binding: PivotBinding
    initializer: PivotParsedExpression
    mutable: bool
    source: SourceSpan | None


@dataclass(frozen=True, slots=True)
class PivotParsedBody:
    language: PivotLanguage
    parameters: tuple[PivotBinding, ...]
    statements: tuple[PivotParsedLocal, ...]
    result: PivotParsedExpression
    requires_unsafe: bool
    source: SourceSpan | None


class PivotTargetParseError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        source: SourceSpan | None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source = source


@dataclass(frozen=True, slots=True)
class _CallPiece:
    call: PivotCall | PivotFixedCall


@dataclass(frozen=True, slots=True)
class _LexicalGroup:
    opening: str
    items: tuple[_LexicalItem, ...]
    closing: str


type _LexicalItem = PivotToken | _CallPiece | _LexicalGroup


_CONTROL_WORDS = {
    PivotLanguage.CPP: frozenset(
        {
            "if",
            "else",
            "for",
            "while",
            "do",
            "switch",
            "case",
            "default",
            "goto",
            "try",
            "catch",
            "throw",
            "co_await",
            "co_yield",
        }
    ),
    PivotLanguage.RUST: frozenset(
        {
            "if",
            "else",
            "for",
            "while",
            "loop",
            "match",
            "break",
            "continue",
        }
    ),
}
_CPP_NAMED_CASTS = frozenset(
    {"static_cast", "reinterpret_cast", "const_cast", "dynamic_cast"}
)
_MULTI_CHAR_OPERATORS = tuple(
    sorted(
        {
            "::",
            "->",
            "<<=",
            ">>=",
            "<<",
            ">>",
            "<=",
            ">=",
            "==",
            "!=",
            "&&",
            "||",
            "++",
            "--",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "&=",
            "|=",
            "^=",
            "=>",
        },
        key=len,
        reverse=True,
    )
)
_SINGLE_OPERATORS = frozenset("+-*/%&|^~!=<>.")
_PUNCTUATION = frozenset(",:")
_DELIMITERS = {"(": ")", "[": "]"}


def parse_pivot_body(body: PivotBody) -> PivotParsedBody:
    """Parse one retained PIVOT body with lexical binding scope."""

    bindings = {binding.authored_name: binding for binding in body.parameters}
    known_binding_names = frozenset(
        (
            *(binding.authored_name for binding in body.parameters),
            *(
                statement.binding.authored_name
                for statement in body.statements
                if isinstance(statement, PivotLocal)
            ),
        )
    )
    parsed_locals: list[PivotParsedLocal] = []
    for statement in body.statements:
        if isinstance(statement, PivotResidualStatementSequence):
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-STATEMENT-SEQUENCE",
                "PIVOT body contains residual top-level target statements",
                statement.source or body.source,
            )
        if not isinstance(statement, PivotLocal):
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-STATEMENT",
                "PIVOT body contains an unknown typed statement",
                body.source,
            )
        initializer = parse_pivot_expression(
            body.language,
            statement.initializer,
            bindings,
            known_binding_names=known_binding_names,
        )
        parsed_locals.append(
            PivotParsedLocal(
                statement.binding,
                initializer,
                statement.mutable,
                statement.source,
            )
        )
        # The initializer sees the prior lexical scope.  The new identity is
        # visible only to subsequent statements and the final result.
        bindings[statement.binding.authored_name] = statement.binding

    result = parse_pivot_expression(
        body.language,
        body.result.value,
        bindings,
        known_binding_names=known_binding_names,
    )
    return PivotParsedBody(
        language=body.language,
        parameters=body.parameters,
        statements=tuple(parsed_locals),
        result=result,
        requires_unsafe=body.requires_unsafe,
        source=body.source,
    )


def parse_pivot_expression(
    language: PivotLanguage,
    expression: PivotExpression,
    bindings: dict[str, PivotBinding],
    *,
    known_binding_names: frozenset[str] | None = None,
) -> PivotParsedExpression:
    lexical: list[PivotToken | _CallPiece] = []
    for piece in expression.pieces:
        if isinstance(piece, PivotResidualText):
            lexical.extend(_tokenize(language, piece.text, piece.source or expression.source))
        elif isinstance(piece, (PivotCall, PivotFixedCall)):
            lexical.append(_CallPiece(piece))
        else:
            raise PivotTargetParseError(
                "TSL-PIVOT-UNKNOWN-EXPRESSION-PIECE",
                "PIVOT expression contains an unknown retained value",
                expression.source,
            )
    grouped, cursor = _parse_groups(tuple(lexical), 0, None, expression.source)
    if cursor != len(lexical):
        raise PivotTargetParseError(
            "TSL-PIVOT-MALFORMED-DELIMITERS",
            "PIVOT expression has malformed delimiters",
            expression.source,
        )
    items = _classify(
        language,
        grouped,
        bindings,
        known_binding_names or frozenset(bindings),
        expression.source,
    )
    if not any(not _is_trivia(item) for item in items):
        raise PivotTargetParseError(
            "TSL-PIVOT-EMPTY-EXPRESSION",
            "PIVOT expression is empty",
            expression.source,
        )
    _reject_casts(language, items, expression.source)
    _reject_unresolved_constructs(language, items, expression.source)
    return PivotParsedExpression(items, expression.source)


def normalize_target_text(value: str) -> str:
    """Collapse target trivia at the final formatting boundary."""

    result: list[str] = []
    pending_space = False
    for char in value:
        if char.isspace():
            pending_space = bool(result)
            continue
        if pending_space:
            result.append(" ")
            pending_space = False
        result.append(char)
    return "".join(result)


def is_simple_target_value(value: str) -> bool:
    """Match the legacy no-parentheses cases without reparsing an expression."""

    text = value.strip()
    if not text:
        return False
    if _is_identifier_start(text[0]):
        return all(_is_identifier_continue(char) for char in text[1:])
    cursor = 0
    if text[0] in "+-":
        cursor = 1
    if cursor == len(text):
        return False
    saw_digit = False
    saw_dot = False
    for char in text[cursor:]:
        if char.isdigit():
            saw_digit = True
        elif char == "." and not saw_dot:
            saw_dot = True
        else:
            return False
    return saw_digit


def _tokenize(
    language: PivotLanguage,
    text: str,
    source: SourceSpan | None,
) -> tuple[PivotToken, ...]:
    tokens: list[PivotToken] = []
    cursor = 0
    while cursor < len(text):
        char = text[cursor]
        if char.isspace():
            end = cursor + 1
            while end < len(text) and text[end].isspace():
                end += 1
            tokens.append(PivotToken(text[cursor:end], PivotTokenKind.TRIVIA))
            cursor = end
            continue
        if text.startswith("//", cursor) or text.startswith("/*", cursor):
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-COMMENT",
                "PIVOT expression contains a comment",
                source,
            )
        if char in {'"', "'"}:
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-LITERAL",
                "PIVOT expression contains a string or character literal",
                source,
            )
        if char == "#":
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-PRAGMA",
                "PIVOT expression contains a pragma or attribute",
                source,
            )
        if char in "{}":
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-BLOCK",
                "PIVOT expression contains a residual block",
                source,
            )
        if char == "?":
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-CONDITIONAL",
                "PIVOT expression contains a conditional expression",
                source,
            )
        if char == ";":
            raise PivotTargetParseError(
                "TSL-PIVOT-UNSUPPORTED-STATEMENT",
                "PIVOT expression contains a statement delimiter",
                source,
            )
        if (
            language is PivotLanguage.RUST
            and text.startswith("r#", cursor)
            and cursor + 2 < len(text)
            and _is_identifier_start(text[cursor + 2])
        ):
            end = cursor + 3
            while end < len(text) and _is_identifier_continue(text[end]):
                end += 1
            tokens.append(PivotToken(text[cursor:end], PivotTokenKind.RAW_IDENTIFIER))
            cursor = end
            continue
        if _is_identifier_start(char):
            end = cursor + 1
            while end < len(text) and _is_identifier_continue(text[end]):
                end += 1
            word = text[cursor:end]
            if word in _CONTROL_WORDS[language] or (
                language is PivotLanguage.RUST
                and word == "return"
            ):
                raise PivotTargetParseError(
                    "TSL-PIVOT-UNSUPPORTED-CONTROL-FLOW",
                    "PIVOT body contains residual control flow",
                    source,
                )
            tokens.append(PivotToken(word, PivotTokenKind.IDENTIFIER))
            cursor = end
            continue
        if char.isdigit() or (
            char == "." and cursor + 1 < len(text) and text[cursor + 1].isdigit()
        ):
            end = _number_end(text, cursor)
            tokens.append(PivotToken(text[cursor:end], PivotTokenKind.NUMBER))
            cursor = end
            continue
        operator = next(
            (item for item in _MULTI_CHAR_OPERATORS if text.startswith(item, cursor)),
            None,
        )
        if operator is not None:
            tokens.append(PivotToken(operator, PivotTokenKind.OPERATOR))
            cursor += len(operator)
            continue
        if char in _SINGLE_OPERATORS:
            tokens.append(PivotToken(char, PivotTokenKind.OPERATOR))
            cursor += 1
            continue
        if char in _PUNCTUATION or char in "()[]":
            tokens.append(PivotToken(char, PivotTokenKind.PUNCTUATION))
            cursor += 1
            continue
        raise PivotTargetParseError(
            "TSL-PIVOT-UNSUPPORTED-TOKEN",
            f"PIVOT expression contains unsupported token {char!r}",
            source,
        )
    return tuple(tokens)


def _number_end(text: str, start: int) -> int:
    cursor = start
    while cursor < len(text):
        char = text[cursor]
        if char.isalnum() or char in "._'":
            cursor += 1
            continue
        if char in "+-" and cursor > start and text[cursor - 1] in "eEpP":
            cursor += 1
            continue
        break
    return cursor


def _parse_groups(
    items: tuple[PivotToken | _CallPiece, ...],
    cursor: int,
    closing: str | None,
    source: SourceSpan | None,
) -> tuple[tuple[_LexicalItem, ...], int]:
    result: list[_LexicalItem] = []
    while cursor < len(items):
        item = items[cursor]
        if isinstance(item, _CallPiece):
            result.append(item)
            cursor += 1
            continue
        if item.text in _DELIMITERS:
            expected = _DELIMITERS[item.text]
            nested, cursor = _parse_groups(items, cursor + 1, expected, source)
            result.append(_LexicalGroup(item.text, nested, expected))
            continue
        if item.text in ")]":
            if closing != item.text:
                raise PivotTargetParseError(
                    "TSL-PIVOT-MALFORMED-DELIMITERS",
                    "PIVOT expression has unbalanced delimiters",
                    source,
                )
            return tuple(result), cursor + 1
        result.append(item)
        cursor += 1
    if closing is not None:
        raise PivotTargetParseError(
            "TSL-PIVOT-MALFORMED-DELIMITERS",
            "PIVOT expression has unbalanced delimiters",
            source,
        )
    return tuple(result), cursor


def _classify(
    language: PivotLanguage,
    items: tuple[_LexicalItem, ...],
    bindings: dict[str, PivotBinding],
    known_binding_names: frozenset[str],
    source: SourceSpan | None,
) -> tuple[PivotExpressionNode, ...]:
    result: list[PivotExpressionNode] = []
    for index, item in enumerate(items):
        if isinstance(item, _LexicalGroup):
            result.append(
                PivotDelimiterGroup(
                    item.opening,
                    _classify(
                        language,
                        item.items,
                        bindings,
                        known_binding_names,
                        source,
                    ),
                    item.closing,
                )
            )
            continue
        if isinstance(item, _CallPiece):
            arguments = tuple(
                parse_pivot_expression(
                    language,
                    argument,
                    bindings,
                    known_binding_names=known_binding_names,
                )
                for argument in item.call.arguments
            )
            if isinstance(item.call, PivotCall):
                result.append(PivotParsedCall(item.call, arguments))
            else:
                result.append(PivotParsedFixedCall(item.call, arguments))
            continue
        if item.kind not in {
            PivotTokenKind.IDENTIFIER,
            PivotTokenKind.RAW_IDENTIFIER,
        }:
            result.append(item)
            continue

        previous = _previous_significant(items, index)
        following = _next_significant(items, index)
        following_pair = _following_significant(items, index, 2)
        if item.kind is PivotTokenKind.RAW_IDENTIFIER:
            result.append(PivotTargetName(item.text, PivotNameRole.RAW_IDENTIFIER))
            continue
        if _is_operator(previous, "::") or _is_operator(following, "::"):
            role = PivotNameRole.QUALIFIED
        elif _is_operator(previous, ".") or _is_operator(previous, "->"):
            role = PivotNameRole.MEMBER
        elif isinstance(following, _LexicalGroup) and following.opening == "(":
            role = PivotNameRole.CALLABLE
        elif (
            language is PivotLanguage.RUST
            and len(following_pair) == 2
            and _is_operator(following_pair[0], "!")
            and isinstance(following_pair[1], _LexicalGroup)
            and following_pair[1].opening == "("
        ):
            role = PivotNameRole.CALLABLE
        else:
            binding = bindings.get(item.text)
            if binding is not None:
                result.append(PivotBindingReference(binding))
                continue
            if item.text in known_binding_names:
                raise PivotTargetParseError(
                    "TSL-PIVOT-UNBOUND-IDENTITY",
                    f"PIVOT binding {item.text!r} is used before its declaration",
                    source,
                )
            role = PivotNameRole.UNQUALIFIED
        result.append(PivotTargetName(item.text, role))
    return tuple(result)


def _reject_casts(
    language: PivotLanguage,
    items: tuple[PivotExpressionNode, ...],
    source: SourceSpan | None,
) -> None:
    for index, item in enumerate(items):
        if isinstance(item, PivotTargetName):
            if language is PivotLanguage.CPP and item.text in _CPP_NAMED_CASTS:
                raise PivotTargetParseError(
                    "TSL-PIVOT-UNSUPPORTED-CAST",
                    "PIVOT body contains a cast",
                    source,
                )
            if language is PivotLanguage.RUST and item.text == "as":
                raise PivotTargetParseError(
                    "TSL-PIVOT-UNSUPPORTED-CAST",
                    "PIVOT body contains a cast",
                    source,
                )
        elif isinstance(item, PivotDelimiterGroup):
            _reject_casts(language, item.items, source)
            if (
                language is PivotLanguage.CPP
                and _type_like_group(item)
                and _starts_cast_operand(_next_expression_node(items, index))
            ):
                raise PivotTargetParseError(
                    "TSL-PIVOT-UNSUPPORTED-CAST",
                    "PIVOT body contains a cast",
                    source,
                )
        elif isinstance(item, (PivotParsedCall, PivotParsedFixedCall)):
            for argument in item.arguments:
                _reject_casts(language, argument.items, argument.source or source)


def _type_like_group(group: PivotDelimiterGroup) -> bool:
    if group.opening != "(":
        return False
    significant = tuple(item for item in group.items if not _is_trivia(item))
    return bool(significant) and any(
        isinstance(item, PivotTargetName) for item in significant
    ) and all(
        isinstance(item, PivotTargetName)
        or (
            isinstance(item, PivotToken)
            and (
                item.kind is PivotTokenKind.NUMBER
                or item.text in {"::", "*", "&", "<", ">", ","}
            )
        )
        or (
            isinstance(item, PivotDelimiterGroup)
            and item.opening == "["
        )
        for item in significant
    )


def _starts_cast_operand(item: PivotExpressionNode | None) -> bool:
    return isinstance(
        item,
        (
            PivotBindingReference,
            PivotTargetName,
            PivotParsedCall,
            PivotParsedFixedCall,
            PivotDelimiterGroup,
        ),
    ) or (
        isinstance(item, PivotToken) and item.kind is PivotTokenKind.NUMBER
    )


def _next_expression_node(
    items: tuple[PivotExpressionNode, ...], index: int
) -> PivotExpressionNode | None:
    return next((item for item in items[index + 1 :] if not _is_trivia(item)), None)


def _reject_unresolved_constructs(
    language: PivotLanguage,
    items: tuple[PivotExpressionNode, ...],
    source: SourceSpan | None,
) -> None:
    spellings = tuple(_node_spelling(item) for item in items if not _is_trivia(item))
    unresolved = False
    if language is PivotLanguage.CPP:
        unresolved = (
            any(
                spellings[index : index + 3] == ("::", "tsl", "::")
                for index in range(max(0, len(spellings) - 2))
            )
            or "LANES" in spellings
            or any(
                spellings[index : index + 3] == ("typename", "Vec", "::")
                for index in range(max(0, len(spellings) - 2))
            )
        )
    else:
        unresolved = any(
            spellings[index] in {"Self", "crate", "super"}
            and spellings[index + 1] == "::"
            for index in range(max(0, len(spellings) - 1))
        )
    if unresolved:
        raise PivotTargetParseError(
            "TSL-PIVOT-UNRESOLVED-GENERATED-CONSTRUCT",
            "PIVOT body contains an unresolved generated-library construct",
            source,
        )
    for item in items:
        if isinstance(item, PivotDelimiterGroup):
            _reject_unresolved_constructs(language, item.items, source)
        elif isinstance(item, (PivotParsedCall, PivotParsedFixedCall)):
            for argument in item.arguments:
                _reject_unresolved_constructs(
                    language,
                    argument.items,
                    argument.source or source,
                )


def _node_spelling(item: PivotExpressionNode) -> str:
    if isinstance(item, PivotToken):
        return item.text
    if isinstance(item, PivotTargetName):
        return item.text
    if isinstance(item, PivotBindingReference):
        return item.binding.authored_name
    return "<structured>"


def _previous_significant(
    items: tuple[_LexicalItem, ...], index: int
) -> _LexicalItem | None:
    for candidate in reversed(items[:index]):
        if not (
            isinstance(candidate, PivotToken)
            and candidate.kind is PivotTokenKind.TRIVIA
        ):
            return candidate
    return None


def _next_significant(
    items: tuple[_LexicalItem, ...], index: int
) -> _LexicalItem | None:
    for candidate in items[index + 1 :]:
        if not (
            isinstance(candidate, PivotToken)
            and candidate.kind is PivotTokenKind.TRIVIA
        ):
            return candidate
    return None


def _following_significant(
    items: tuple[_LexicalItem, ...],
    index: int,
    count: int,
) -> tuple[_LexicalItem, ...]:
    return tuple(
        candidate
        for candidate in items[index + 1 :]
        if not (
            isinstance(candidate, PivotToken)
            and candidate.kind is PivotTokenKind.TRIVIA
        )
    )[:count]


def _is_operator(item: _LexicalItem | None, spelling: str) -> bool:
    return isinstance(item, PivotToken) and item.text == spelling


def _is_trivia(item: PivotExpressionNode) -> bool:
    return isinstance(item, PivotToken) and item.kind is PivotTokenKind.TRIVIA


def _is_identifier_start(char: str) -> bool:
    return char == "_" or char.isalpha()


def _is_identifier_continue(char: str) -> bool:
    return char == "_" or char.isalnum()


def binding_ids(body: PivotParsedBody) -> tuple[PivotBindingId, ...]:
    """Expose parsed identity order for focused parser/inliner assertions."""

    return tuple(binding.identity for binding in body.parameters) + tuple(
        statement.binding.identity for statement in body.statements
    )


__all__ = (
    "PivotBindingReference",
    "PivotDelimiterGroup",
    "PivotExpressionNode",
    "PivotNameRole",
    "PivotParsedBody",
    "PivotParsedCall",
    "PivotParsedExpression",
    "PivotParsedFixedCall",
    "PivotParsedLocal",
    "PivotTargetName",
    "PivotTargetParseError",
    "PivotToken",
    "PivotTokenKind",
    "binding_ids",
    "is_simple_target_value",
    "normalize_target_text",
    "parse_pivot_body",
    "parse_pivot_expression",
)
