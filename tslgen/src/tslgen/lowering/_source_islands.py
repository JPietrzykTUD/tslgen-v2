"""Private mechanics for source-owned request-island discovery.

This module intentionally knows only about characters, source locations, raw
body-token runs, and opaque token spans. Request-specific modules still own the
accepted head names, payload validation, diagnostics, and typed requests.
"""

from __future__ import annotations

from collections.abc import Container, Sequence
from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import BodyToken, RawStringToken

_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


@dataclass(frozen=True, slots=True)
class SourceTextSpan:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SourceMappedText:
    text: str
    source: SourceLocation
    _source_map: tuple[SourceLocation, ...] = ()

    def source_at(self, offset: int) -> SourceLocation:
        if 0 <= offset < len(self._source_map):
            return self._source_map[offset]
        return source_at_offset(self.source, self.text, offset)

    def span(self, start: int, end: int) -> SourceTextSpan:
        return SourceTextSpan(
            text=self.text[start:end],
            source=self.source_at(start),
        )


@dataclass(frozen=True, slots=True)
class JoinedRawStringRun:
    tokens: tuple[RawStringToken, ...]
    source_text: SourceMappedText


@dataclass(frozen=True, slots=True)
class OpaqueTokenSpan:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


class OpaqueTokenBuffer:
    """Preserve original opaque body-token identity until a request is found."""

    def __init__(self) -> None:
        self._tokens: list[BodyToken] = []

    def append(self, token: BodyToken) -> None:
        self._tokens.append(token)

    def extend(self, tokens: Sequence[BodyToken]) -> None:
        self._tokens.extend(tokens)

    def take(self) -> OpaqueTokenSpan | None:
        if not self._tokens:
            return None
        tokens = tuple(self._tokens)
        self._tokens.clear()
        return OpaqueTokenSpan(tokens=tokens, source=tokens[0].source)


class RawStringRunBuffer:
    """Collect contiguous raw body tokens and join them with source mapping."""

    def __init__(self) -> None:
        self._tokens: list[RawStringToken] = []

    def append(self, token: RawStringToken) -> None:
        self._tokens.append(token)

    def take(self) -> JoinedRawStringRun | None:
        if not self._tokens:
            return None
        tokens = tuple(self._tokens)
        self._tokens.clear()
        return JoinedRawStringRun(
            tokens=tokens,
            source_text=source_text_from_raw_tokens(tokens),
        )


def source_text_from_text(text: str, source: SourceLocation) -> SourceMappedText:
    return SourceMappedText(text=text, source=source)


def source_text_from_raw_tokens(
    raw_tokens: Sequence[RawStringToken],
) -> SourceMappedText:
    if not raw_tokens:
        raise ValueError("raw_tokens must not be empty")

    text_parts: list[str] = []
    source_map: list[SourceLocation] = []

    for token in raw_tokens:
        text_parts.append(token.text)
        line = token.source.line
        column = token.source.column
        for char in token.text:
            source_map.append(SourceLocation(token.source.path, line, column))
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1

    return SourceMappedText(
        text="".join(text_parts),
        source=raw_tokens[0].source,
        _source_map=tuple(source_map),
    )


def matching_delimiter_close(
    text: str,
    open_index: int,
    open_char: str,
    close_char: str,
) -> int | None:
    """Return the close delimiter index, ignoring delimiters inside quotes."""

    if open_index < 0 or open_index >= len(text) or text[open_index] != open_char:
        return None

    depth = 1
    quote: str | None = None
    escaped = False

    for index in range(open_index + 1, len(text)):
        char = text[index]

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
        if char == open_char:
            depth += 1
            continue
        if char == close_char:
            depth -= 1
            if depth == 0:
                return index

    return None


def has_identifier_boundary_before(
    text: str,
    start: int,
    *,
    identifier_chars: Container[str] = _IDENTIFIER_CHARS,
) -> bool:
    return start == 0 or text[start - 1] not in identifier_chars


def source_at_offset(
    source: SourceLocation,
    text: str,
    offset: int,
) -> SourceLocation:
    line = source.line
    column = source.column
    for char in text[:offset]:
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return SourceLocation(source.path, line, column)
