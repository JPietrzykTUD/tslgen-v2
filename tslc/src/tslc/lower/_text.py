"""Small shared text utilities for TSIL selector/modifier parsing."""

from __future__ import annotations


def skip_string(text: str, index: int) -> int:
    """Return the index just past a double-quoted string starting at ``index``."""

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


def split_top_level(text: str, separator: str = ",") -> list[str]:
    """Split ``text`` on ``separator`` at bracket/string depth zero.

    Respects ``()`` and ``<>`` nesting and skips double-quoted strings, so a
    comma inside ``intrin::suffix("x,y")`` does not split it.
    """

    terms: list[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch in "(<":
            depth += 1
        elif ch in ")>":
            depth -= 1
        elif ch == separator and depth == 0:
            terms.append(text[start:i])
            start = i + 1
        i += 1
    terms.append(text[start:])
    return [term.strip() for term in terms if term.strip()]


def split_head_arg(text: str) -> tuple[str, str] | None:
    """Split a ``head(arg)`` form into ``(head, arg)`` with balanced parens.

    Returns ``None`` when ``text`` is not a single ``head(...)`` call (e.g. a
    bare leaf like ``base::in`` or a stray suffix after the closing paren).
    """

    text = text.strip()
    open_index = text.find("(")
    if open_index == -1 or not text.endswith(")"):
        return None
    depth = 0
    i = open_index
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                if i != n - 1:
                    return None
                return text[:open_index].strip(), text[open_index + 1 : i].strip()
        i += 1
    return None
