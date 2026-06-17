"""Shared parsing for ``call<...>`` selector metadata.

This module owns only selector syntax: the primitive reference, bracket entries, and raw
``attrs[...]`` pairs. It deliberately does not resolve ``@self``, evaluate queries, choose emitted
wrapper names, compute dependency identities, or render backend code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tslc.lower._text import skip_string, split_top_level

_CALL_NAME = re.compile(r"(@?[A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True, slots=True)
class ParsedCallSelector:
    primitive_ref: str
    type_args: tuple[str, ...] = ()
    attrs: tuple[tuple[str, str], ...] = ()


def parse_call_selector(selector_text: str) -> ParsedCallSelector | None:
    """Parse ``primitive=NAME[... ] attrs[...]`` selector metadata.

    Returns ``None`` for malformed or unsupported selector tails. Attribute values stay raw so
    callers can decide whether and how to evaluate them.
    """

    selector = selector_text.strip()
    if not selector.startswith("primitive="):
        return None
    rest = selector[len("primitive=") :].strip()
    match = _CALL_NAME.match(rest)
    if match is None:
        return None

    primitive_ref = match.group(1)
    rest = rest[match.end() :].strip()
    type_args: tuple[str, ...] = ()
    if rest.startswith("["):
        bracket = _take_bracket(rest)
        if bracket is None:
            return None
        type_text, rest = bracket
        type_args = tuple(split_top_level(type_text)) if type_text else ()
        rest = rest.strip()

    attrs: tuple[tuple[str, str], ...] = ()
    if rest.startswith("attrs"):
        bracket = _take_bracket(rest[len("attrs") :].lstrip())
        if bracket is None:
            return None
        attr_text, rest = bracket
        attrs = _parse_attrs(attr_text)
        if attrs is None:
            return None
        rest = rest.strip()

    if rest:
        return None
    return ParsedCallSelector(primitive_ref=primitive_ref, type_args=type_args, attrs=attrs)


def _parse_attrs(attr_text: str) -> tuple[tuple[str, str], ...] | None:
    attrs: list[tuple[str, str]] = []
    for term in split_top_level(attr_text):
        key, sep, value = term.partition("=")
        if not sep or not key.strip() or not value.strip():
            return None
        attrs.append((key.strip(), value.strip()))
    return tuple(attrs)


def _take_bracket(text: str) -> tuple[str, str] | None:
    if not text.startswith("["):
        return None
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[1:i], text[i + 1 :]
        i += 1
    return None
