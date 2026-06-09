"""Scan TSIL body text into a recursive segment sequence.

The scanner recognizes a configured set of TSIL keywords. A keyword island has
the shape ``keyword(<sel>)?(args)``; its ``<...>`` selector is captured as raw
text (modifiers are parsed later by the lowerer) and its ``(...)`` argument
payload is recursively scanned. Everything else is :class:`RawText` passed
through verbatim. String literals are skipped so keywords inside them are not
matched.
"""

from __future__ import annotations

from tslc.ir.segments import RawText, Region, Segment

# Keywords that introduce a region. Growth happens by adding entries here (and
# teaching the lowerer to translate them) — never by adding wrapper families.
KEYWORDS: frozenset[str] = frozenset(
    {
        "emit_return",
        "intrin_compose",
        "intrin",
        "call",
        "value",
        "type",
        "cast",
        "var",
        "let",
    }
)

_IDENT_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_CONT = _IDENT_START | frozenset("0123456789")


def scan(text: str) -> tuple[Segment, ...]:
    return tuple(_scan(text))


def _scan(text: str) -> list[Segment]:
    segments: list[Segment] = []
    n = len(text)
    i = 0
    raw_start = 0
    while i < n:
        ch = text[i]
        if ch == '"':
            i = _skip_string(text, i)
            continue
        if ch in _IDENT_START and _boundary_before(text, i):
            keyword, after = _read_ident(text, i)
            if keyword in KEYWORDS:
                region, end = _try_region(text, i, keyword, after)
                if region is not None:
                    if raw_start < i:
                        segments.append(RawText(text[raw_start:i]))
                    segments.append(region)
                    i = end
                    raw_start = end
                    continue
            i = after
            continue
        i += 1
    if raw_start < n:
        segments.append(RawText(text[raw_start:n]))
    return segments


def _try_region(
    text: str, start: int, keyword: str, after_keyword: int
) -> tuple[Region | None, int]:
    pos = _skip_ws(text, after_keyword)
    selector_text = ""
    if pos < len(text) and text[pos] == "<":
        close = _match_bracket(text, pos, "<", ">")
        if close is None:
            return None, start
        selector_text = text[pos + 1 : close]
        pos = _skip_ws(text, close + 1)
    if pos >= len(text) or text[pos] != "(":
        # Not a region shape (e.g. a bare identifier that matches a keyword name).
        return None, start
    close = _match_bracket(text, pos, "(", ")")
    if close is None:
        return None, start
    body_text = text[pos + 1 : close]
    region = Region(
        keyword=keyword,
        selector_text=selector_text,
        body=tuple(_scan(body_text)),
        full_text=text[start : close + 1],
    )
    return region, close + 1


def _match_bracket(text: str, open_index: int, open_ch: str, close_ch: str) -> int | None:
    depth = 0
    i = open_index
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = _skip_string(text, i)
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _skip_string(text: str, index: int) -> int:
    i = index + 1
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return n


def _read_ident(text: str, index: int) -> tuple[str, int]:
    i = index
    n = len(text)
    while i < n and text[i] in _IDENT_CONT:
        i += 1
    return text[index:i], i


def _skip_ws(text: str, index: int) -> int:
    i = index
    n = len(text)
    while i < n and text[i] in " \t\r\n":
        i += 1
    return i


def _boundary_before(text: str, index: int) -> bool:
    """A keyword must not be the tail of a longer identifier (e.g. ``my_call``)."""

    if index == 0:
        return True
    return text[index - 1] not in _IDENT_CONT
