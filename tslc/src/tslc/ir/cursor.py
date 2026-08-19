"""Tolerant TSIL cursor projection for compiler-owned authoring features."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tslc.ir.lexical import (
    IDENT_START as _IDENT_START,
    boundary_before as _boundary_before,
    match_bracket as _match_bracket,
    matches_keyword as _matches_keyword,
    read_ident as _read_ident,
    skip_opaque as _skip_opaque,
    skip_ws as _skip_ws,
)
from tslc.ir.region_registry import (
    RegionBodyShape,
    TSIL_REGION_KEYWORDS,
    region_body_shape,
)

KEYWORDS = TSIL_REGION_KEYWORDS
TsilCursorKind = Literal["region-boundary", "region-shell", "raw"]


@dataclass(frozen=True, slots=True)
class TsilCursorContext:
    """Lexical TSIL context at one body-relative cursor offset."""

    kind: TsilCursorKind
    replacement_start: int
    replacement_end: int
    prefix: str = ""
    keyword: str | None = None
    selector_start: int | None = None
    selector_prefix: str | None = None
    region_path: tuple[str, ...] = ()
    argument_keyword: str | None = None
    argument_selector: str | None = None
    argument_start: int | None = None
    argument_prefix: str | None = None
    in_opaque_text: bool = False


def tsil_cursor_context(text: str, offset: int) -> TsilCursorContext:
    """Classify a TSIL body cursor using the recursive scanner's lexical rules.

    The scan deliberately sees only the prefix through the cursor. A balanced
    region in the source therefore becomes an unfinished selector, payload, or
    block when the cursor is inside it, which gives completion a tolerant view
    without repairing malformed text or parsing raw target-language fragments.
    """

    bounded = min(max(offset, 0), len(text))
    return _tsil_cursor_in_prefix(text[:bounded], 0, ())


def _tsil_cursor_in_prefix(
    prefix: str,
    base_offset: int,
    region_path: tuple[str, ...],
) -> TsilCursorContext:
    n = len(prefix)
    index = 0
    while index < n:
        opaque_end = _skip_opaque(prefix, index)
        if opaque_end is not None:
            if opaque_end >= n:
                return _raw_cursor(
                    base_offset + n,
                    region_path,
                    in_opaque_text=True,
                )
            index = opaque_end
            continue

        character = prefix[index]
        if character in _IDENT_START and _boundary_before(prefix, index):
            word, after_word = _read_ident(prefix, index)
            if after_word == n:
                if any(keyword.startswith(word) for keyword in KEYWORDS):
                    return TsilCursorContext(
                        "region-boundary",
                        base_offset + index,
                        base_offset + n,
                        prefix=word,
                        region_path=region_path,
                    )
                return _raw_cursor(base_offset + n, region_path)
            if word in KEYWORDS:
                context, end = _tsil_region_cursor(
                    prefix,
                    index,
                    word,
                    after_word,
                    base_offset,
                    region_path,
                )
                if context is not None:
                    return context
                if end is not None:
                    index = end
                    continue
            index = after_word
            continue
        index += 1

    if _is_region_boundary(prefix):
        return TsilCursorContext(
            "region-boundary",
            base_offset + n,
            base_offset + n,
            region_path=region_path,
        )
    return _raw_cursor(base_offset + n, region_path)


def _tsil_region_cursor(
    prefix: str,
    start: int,
    keyword: str,
    after_keyword: int,
    base_offset: int,
    region_path: tuple[str, ...],
) -> tuple[TsilCursorContext | None, int | None]:
    del start
    position = _skip_ws(prefix, after_keyword)
    selector_text = ""
    if position < len(prefix) and prefix[position] == "<":
        selector_start = position + 1
        close = _match_bracket(prefix, position, "<", ">")
        if close is None:
            return (
                TsilCursorContext(
                    "region-shell",
                    base_offset + selector_start,
                    base_offset + len(prefix),
                    keyword=keyword,
                    selector_start=base_offset + selector_start,
                    selector_prefix=prefix[selector_start:],
                    region_path=region_path,
                ),
                None,
            )
        selector_text = prefix[selector_start:close]
        position = _skip_ws(prefix, close + 1)

    if position >= len(prefix) or prefix[position] != "(":
        return None, None
    close = _match_bracket(prefix, position, "(", ")")
    if close is None:
        argument_start = position + 1
        context = _tsil_cursor_in_prefix(
            prefix[argument_start:],
            base_offset + argument_start,
            (*region_path, keyword),
        )
        if context.kind != "region-shell" and context.argument_keyword is None:
            context = replace(
                context,
                argument_keyword=keyword,
                argument_selector=selector_text,
                argument_start=base_offset + argument_start,
                argument_prefix=prefix[argument_start:],
            )
        return context, None

    end = close + 1
    shape = region_body_shape(keyword)
    if shape == "call":
        return None, end
    return _structural_region_cursor(
        prefix,
        keyword,
        shape,
        end,
        base_offset,
        region_path,
    )


def _structural_region_cursor(
    prefix: str,
    keyword: str,
    shape: RegionBodyShape,
    after_payload: int,
    base_offset: int,
    region_path: tuple[str, ...],
) -> tuple[TsilCursorContext | None, int | None]:
    block_start = _skip_ws(prefix, after_payload)
    if block_start >= len(prefix) or prefix[block_start] != "{":
        return None, None
    block_close = _match_bracket(prefix, block_start, "{", "}")
    if block_close is None:
        inner = prefix[block_start + 1 :]
        if shape == "switch_block":
            nested_start = _last_unmatched_brace(inner)
            if nested_start is None:
                return (
                    _raw_cursor(
                        base_offset + len(prefix),
                        (*region_path, keyword),
                    ),
                    None,
                )
            return (
                _tsil_cursor_in_prefix(
                    inner[nested_start + 1 :],
                    base_offset + block_start + nested_start + 2,
                    (*region_path, keyword),
                ),
                None,
            )
        return (
            _tsil_cursor_in_prefix(
                inner,
                base_offset + block_start + 1,
                (*region_path, keyword),
            ),
            None,
        )

    end = block_close + 1
    if shape != "if_block":
        return None, end

    else_start = _skip_ws(prefix, end)
    if not _matches_keyword(prefix, else_start, "else"):
        return None, end
    position = _skip_ws(prefix, else_start + len("else"))
    if position < len(prefix) and prefix[position] == "<":
        selector_start = position + 1
        selector_close = _match_bracket(prefix, position, "<", ">")
        if selector_close is None:
            return (
                TsilCursorContext(
                    "region-shell",
                    base_offset + selector_start,
                    base_offset + len(prefix),
                    keyword=keyword,
                    selector_start=base_offset + selector_start,
                    selector_prefix=prefix[selector_start:],
                    region_path=region_path,
                ),
                None,
            )
        position = _skip_ws(prefix, selector_close + 1)
    if position < len(prefix) and prefix[position] == "{":
        else_close = _match_bracket(prefix, position, "{", "}")
        if else_close is None:
            return (
                _tsil_cursor_in_prefix(
                    prefix[position + 1 :],
                    base_offset + position + 1,
                    (*region_path, keyword),
                ),
                None,
            )
        return None, else_close + 1
    if _matches_keyword(prefix, position, "if"):
        return _tsil_region_cursor(
            prefix,
            position,
            "if",
            position + len("if"),
            base_offset,
            (*region_path, keyword),
        )
    return None, end


def _last_unmatched_brace(text: str) -> int | None:
    opens: list[int] = []
    index = 0
    while index < len(text):
        opaque_end = _skip_opaque(text, index)
        if opaque_end is not None:
            index = opaque_end
            continue
        if text[index] == "{":
            opens.append(index)
        elif text[index] == "}" and opens:
            opens.pop()
        index += 1
    return opens[-1] if opens else None


def _is_region_boundary(prefix: str) -> bool:
    if not prefix:
        return True
    index = len(prefix) - 1
    saw_newline = False
    while index >= 0 and prefix[index].isspace():
        saw_newline = saw_newline or prefix[index] in "\r\n"
        index -= 1
    if saw_newline or index < 0:
        return True
    return prefix[index] in "([{,=:+-*/%!&|?;"


def _raw_cursor(
    offset: int,
    region_path: tuple[str, ...],
    *,
    in_opaque_text: bool = False,
) -> TsilCursorContext:
    return TsilCursorContext(
        "raw",
        offset,
        offset,
        region_path=region_path,
        in_opaque_text=in_opaque_text,
    )


__all__ = ("TsilCursorContext", "TsilCursorKind", "tsil_cursor_context")
