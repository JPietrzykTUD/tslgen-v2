"""Small text utilities shared by TSIL scanning, validation, and lowering."""

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
    """Split ``text`` on ``separator`` at bracket/string depth zero."""

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


def split_selector_terms(text: str) -> list[str]:
    """Split selector text on commas outside nested syntax and strings."""

    terms: list[str] = []
    round_depth = 0
    angle_depth = 0
    square_depth = 0
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch == "(":
            round_depth += 1
        elif ch == ")" and round_depth:
            round_depth -= 1
        elif ch == "<":
            angle_depth += 1
        elif ch == ">" and angle_depth:
            angle_depth -= 1
        elif ch == "[":
            square_depth += 1
        elif ch == "]" and square_depth:
            square_depth -= 1
        elif (
            round_depth == 0
            and angle_depth == 0
            and square_depth == 0
            and ch == ","
        ):
            if start < i:
                terms.append(text[start:i])
            start = i + 1
        i += 1
    if start < n:
        terms.append(text[start:])
    return [term.strip() for term in terms if term.strip()]


def split_head_arg(text: str) -> tuple[str, str] | None:
    """Split a balanced ``head(arg)`` form into its head and argument."""

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


__all__ = ("skip_string", "split_head_arg", "split_selector_terms", "split_top_level")
