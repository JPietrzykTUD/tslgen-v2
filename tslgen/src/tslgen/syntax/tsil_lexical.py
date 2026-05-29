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
