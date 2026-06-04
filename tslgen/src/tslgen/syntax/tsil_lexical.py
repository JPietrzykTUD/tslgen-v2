"""Shared lexical helpers for exact TSIL island boundaries.

The helpers in this module know only about characters, delimiter balance, and
top-level separators. Keyword-specific classifiers and lowerers still own all
TSIL semantics, diagnostics, and accepted source forms.
"""

from dataclasses import dataclass

DelimiterPair = tuple[str, str]

PAREN_DELIMITER: DelimiterPair = ("(", ")")
BRACKET_DELIMITER: DelimiterPair = ("[", "]")
ANGLE_DELIMITER: DelimiterPair = ("<", ">")
BRACE_DELIMITER: DelimiterPair = ("{", "}")


@dataclass(frozen=True, slots=True)
class LexicalPart:
    text: str
    start: int
    end: int


def matching_close(
    text: str,
    open_index: int,
    delimiter: DelimiterPair,
) -> int | None:
    """Return the matching close delimiter index for one balanced pair."""

    open_char, close_char = delimiter
    if open_index < 0 or open_index >= len(text) or text[open_index] != open_char:
        return None

    depth = 1
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def matching_close_lexical(
    text: str,
    open_index: int,
    delimiter: DelimiterPair,
) -> int | None:
    """Return the matching close delimiter while ignoring quoted text."""

    open_char, close_char = delimiter
    if open_index < 0 or open_index >= len(text) or text[open_index] != open_char:
        return None

    depth = 1
    index = open_index + 1

    while index < len(text):
        if starts_quoted_text(text, index):
            quote_close = matching_quote_close(text, index)
            if quote_close is None:
                return None
            index = quote_close + 1
            continue

        char = text[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1

    return None


def starts_quoted_text(text: str, index: int) -> bool:
    return _quote_marker_at(text, index) is not None


def matching_quote_close(text: str, quote_start: int) -> int | None:
    """Return the close quote index for raw or outer-string-escaped quotes."""

    marker = _quote_marker_at(text, quote_start)
    if marker is None:
        return None

    quote, escaped_marker, width = marker
    index = quote_start + width
    while index < len(text):
        if escaped_marker:
            if text[index] == "\\" and index + 1 < len(text) and text[index + 1] == quote:
                return index + 1
            index += 1
            continue

        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index
        index += 1

    return None


def find_top_level_char(
    text: str,
    target: str,
    *,
    start: int = 0,
    delimiters: tuple[DelimiterPair, ...] = (),
) -> int | None:
    """Find a character outside the supplied nested delimiter pairs."""

    if len(target) != 1:
        raise ValueError("target must be a single character")

    depths = [0] * len(delimiters)
    open_indexes = {pair[0]: index for index, pair in enumerate(delimiters)}
    close_indexes = {pair[1]: index for index, pair in enumerate(delimiters)}

    for index in range(max(0, start), len(text)):
        char = text[index]
        if char in open_indexes:
            depths[open_indexes[char]] += 1
            continue
        if char in close_indexes:
            depth_index = close_indexes[char]
            if depths[depth_index] == 0:
                return None
            depths[depth_index] -= 1
            continue
        if char == target and all(depth == 0 for depth in depths):
            return index

    return None


def split_top_level_parts(
    payload: str,
    *,
    separator: str = ",",
    delimiters: tuple[DelimiterPair, ...] = (
        PAREN_DELIMITER,
        BRACKET_DELIMITER,
    ),
    allow_empty_payload: bool = True,
) -> tuple[LexicalPart, ...] | None:
    """Split on a separator outside the supplied nested delimiter pairs."""

    if len(separator) != 1:
        raise ValueError("separator must be a single character")
    if not payload.strip():
        return () if allow_empty_payload else None

    parts: list[LexicalPart] = []
    part_start = 0
    depths = [0] * len(delimiters)
    open_indexes = {pair[0]: index for index, pair in enumerate(delimiters)}
    close_indexes = {pair[1]: index for index, pair in enumerate(delimiters)}

    for index, char in enumerate(payload):
        if char in open_indexes:
            depths[open_indexes[char]] += 1
        elif char in close_indexes:
            depth_index = close_indexes[char]
            if depths[depth_index] == 0:
                return None
            depths[depth_index] -= 1
        elif char == separator and all(depth == 0 for depth in depths):
            part = _trimmed_part(payload, part_start, index)
            if part is None:
                return None
            parts.append(part)
            part_start = index + 1

    if any(depth != 0 for depth in depths):
        return None

    part = _trimmed_part(payload, part_start, len(payload))
    if part is None:
        return None
    parts.append(part)
    return tuple(parts)


def raw_brace_depth_after(
    depth: int,
    text: str,
    *,
    clamp_underflow: bool = False,
) -> int:
    """Return raw brace depth after scanning text lexically."""

    for char in text:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if clamp_underflow and depth < 0:
                depth = 0
    return depth


def _trimmed_part(payload: str, start: int, end: int) -> LexicalPart | None:
    while start < end and payload[start].isspace():
        start += 1
    while end > start and payload[end - 1].isspace():
        end -= 1
    if start >= end:
        return None
    return LexicalPart(text=payload[start:end], start=start, end=end)


def is_escaped_at(text: str, index: int) -> bool:
    """Return whether the character at index is escaped by backslashes."""

    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _quote_marker_at(text: str, index: int) -> tuple[str, bool, int] | None:
    if index < 0 or index >= len(text):
        return None

    char = text[index]
    if char in {"'", '"'} and not is_escaped_at(text, index):
        return (char, False, 1)
    if char == "\\" and index + 1 < len(text) and text[index + 1] in {"'", '"'}:
        return (text[index + 1], True, 2)
    return None
