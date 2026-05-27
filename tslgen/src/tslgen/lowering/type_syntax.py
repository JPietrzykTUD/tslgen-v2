"""Tiny syntax nodes for exact TSIL type/query islands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

TypeQueryKind = Literal["backend", "generation", "generation_value"]


@dataclass(frozen=True, slots=True)
class TypeIdentifier:
    name: str
    source_text: str


@dataclass(frozen=True, slots=True)
class TypeCall:
    name: str
    arguments: tuple[TypeSyntax, ...]
    source_text: str


@dataclass(frozen=True, slots=True)
class TypeQuery:
    kind: TypeQueryKind
    expression: TypeSyntax
    source_text: str


TypeSyntax = TypeIdentifier | TypeCall | TypeQuery

_IDENTIFIER_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*"
)
_QUERY_PREFIXES: tuple[tuple[str, TypeQueryKind], ...] = (
    ("type<backend>(", "backend"),
    ("type<generation>(", "generation"),
    ("value<generation>(", "generation_value"),
)


def parse_type_syntax(expression: str) -> TypeSyntax | None:
    """Parse the exact type/query island syntax supported by lowering."""

    if expression != expression.strip() or not expression:
        return None

    query = _parse_query(expression)
    if query is not None:
        return query

    call = _parse_call(expression)
    if call is not None:
        return call

    if _IDENTIFIER_RE.fullmatch(expression) is not None:
        return TypeIdentifier(name=expression, source_text=expression)

    return None


def split_top_level_arguments(payload: str) -> tuple[str, ...] | None:
    if not payload.strip():
        return ()

    arguments: list[str] = []
    start = 0
    paren_depth = 0
    bracket_depth = 0
    for index, char in enumerate(payload):
        if char == "(":
            paren_depth += 1
        elif char == ")":
            if paren_depth == 0:
                return None
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            if bracket_depth == 0:
                return None
            bracket_depth -= 1
        elif char == "," and paren_depth == 0 and bracket_depth == 0:
            argument = payload[start:index].strip()
            if not argument:
                return None
            arguments.append(argument)
            start = index + 1

    if paren_depth != 0 or bracket_depth != 0:
        return None

    argument = payload[start:].strip()
    if not argument:
        return None
    arguments.append(argument)
    return tuple(arguments)


def _parse_query(expression: str) -> TypeQuery | None:
    for prefix, kind in _QUERY_PREFIXES:
        payload = _extract_query_payload(expression, prefix)
        if payload is None:
            continue
        parsed_payload = parse_type_syntax(payload)
        if parsed_payload is None:
            return None
        return TypeQuery(
            kind=kind,
            expression=parsed_payload,
            source_text=expression,
        )
    return None


def _parse_call(expression: str) -> TypeCall | None:
    open_index = expression.find("(")
    if open_index == -1 or not expression.endswith(")"):
        return None

    close_index = _matching_close_paren(expression, open_index)
    if close_index is None or close_index != len(expression) - 1:
        return None

    name = expression[:open_index].strip()
    if _IDENTIFIER_RE.fullmatch(name) is None:
        return None

    raw_arguments = split_top_level_arguments(
        expression[open_index + 1 : close_index]
    )
    if raw_arguments is None:
        return None

    arguments: list[TypeSyntax] = []
    for raw_argument in raw_arguments:
        parsed_argument = parse_type_syntax(raw_argument)
        if parsed_argument is None:
            return None
        arguments.append(parsed_argument)

    return TypeCall(
        name=name,
        arguments=tuple(arguments),
        source_text=expression,
    )


def _extract_query_payload(query: str, prefix: str) -> str | None:
    if not query.startswith(prefix):
        return None

    open_index = len(prefix) - 1
    close_index = _matching_close_paren(query, open_index)
    if close_index is None or close_index != len(query) - 1:
        return None

    expression = query[len(prefix) : close_index]
    if not expression or expression != expression.strip():
        return None
    return expression


def _matching_close_paren(text: str, open_index: int) -> int | None:
    if open_index >= len(text) or text[open_index] != "(":
        return None

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
