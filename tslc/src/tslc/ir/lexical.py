"""Shared lexical rules for TSIL scanning and cursor projection."""

from __future__ import annotations

IDENT_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
IDENT_CONT = IDENT_START | frozenset("0123456789")


def matches_keyword(text: str, index: int, keyword: str) -> bool:
    if not boundary_before(text, index):
        return False
    word, after = read_ident(text, index)
    return word == keyword and after > index


def match_bracket(
    text: str,
    open_index: int,
    open_ch: str,
    close_ch: str,
) -> int | None:
    depth = 0
    index = open_index
    while index < len(text):
        opaque_end = skip_opaque(text, index)
        if opaque_end is not None:
            index = opaque_end
            continue
        character = text[index]
        if character == open_ch:
            depth += 1
        elif character == close_ch:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def skip_opaque(text: str, index: int) -> int | None:
    """Skip target text whose contents cannot contain a TSIL region."""

    character = text[index]
    if character == '"':
        return _skip_string(text, index)
    if character != "/" or index + 1 >= len(text):
        return None
    next_character = text[index + 1]
    if next_character == "/":
        return _skip_line_comment(text, index)
    if next_character == "*":
        return _skip_block_comment(text, index)
    return None


def _skip_line_comment(text: str, index: int) -> int:
    newline = text.find("\n", index + 2)
    return len(text) if newline == -1 else newline


def _skip_block_comment(text: str, index: int) -> int:
    """Skip a C-like block comment, including Rust's nested block comments."""

    depth = 1
    position = index + 2
    while position < len(text):
        if text.startswith("/*", position):
            depth += 1
            position += 2
            continue
        if text.startswith("*/", position):
            depth -= 1
            position += 2
            if depth == 0:
                return position
            continue
        position += 1
    return len(text)


def _skip_string(text: str, index: int) -> int:
    position = index + 1
    while position < len(text):
        if text[position] == "\\":
            position += 2
            continue
        if text[position] == '"':
            return position + 1
        position += 1
    return len(text)


def read_ident(text: str, index: int) -> tuple[str, int]:
    position = index
    while position < len(text) and text[position] in IDENT_CONT:
        position += 1
    return text[index:position], position


def skip_ws(text: str, index: int) -> int:
    position = index
    while position < len(text) and text[position] in " \t\r\n":
        position += 1
    return position


def boundary_before(text: str, index: int) -> bool:
    """A keyword must not be the tail of a longer identifier."""

    return index == 0 or text[index - 1] not in IDENT_CONT


__all__ = (
    "IDENT_START",
    "boundary_before",
    "match_bracket",
    "matches_keyword",
    "read_ident",
    "skip_opaque",
    "skip_ws",
)
