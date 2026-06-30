"""Scan TSIL body text into a recursive segment sequence.

The scanner recognizes a configured set of TSIL keywords. A keyword island has
the shape ``keyword(<sel>)?(args)``; its ``<...>`` selector is captured as raw
text (modifiers are parsed later by the lowerer) and its ``(...)`` argument
payload is recursively scanned. Everything else is :class:`RawText` passed
through verbatim. String literals are skipped so keywords inside them are not
matched.

When a region is found in a statement stream and the source immediately
terminates that statement with ``;`` (allowing whitespace), the scanner consumes
the terminator and records it on the region. Nested argument payloads are
expression streams, so their punctuation stays owned by the surrounding source.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.diagnostics import SourceSpan
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS, region_body_shape
from tslc.ir.segments import RawText, Region, Segment

KEYWORDS: frozenset[str] = TSIL_REGION_KEYWORDS

_IDENT_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_CONT = _IDENT_START | frozenset("0123456789")


@dataclass(frozen=True, slots=True)
class MalformedRegion:
    keyword: str
    reason: str
    text: str
    source: SourceSpan | None = None


def scan(text: str, *, source: SourceSpan | None = None) -> tuple[Segment, ...]:
    return tuple(_scan(text, source, text, 0, statement_context=True))


def find_malformed_regions(
    text: str,
    *,
    source: SourceSpan | None = None,
) -> tuple[MalformedRegion, ...]:
    """Find TSIL keyword islands that look intentional but fail the shared shell shape.

    The scanner keeps raw target text pass-through by design; this companion pass lets catalog
    validation diagnose misspelled or incomplete TSIL shells before they disappear into RawText.
    """

    return tuple(_find_malformed_regions(text, source, text, 0))


def _find_malformed_regions(
    text: str,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> list[MalformedRegion]:
    malformed: list[MalformedRegion] = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == '"':
            i = _skip_string(text, i)
            continue
        if ch in _IDENT_START and _boundary_before(text, i):
            keyword, after = _read_ident(text, i)
            if keyword in KEYWORDS:
                region, end = _try_malformed_region(
                    text, i, keyword, after, source, root_text, base_offset
                )
                if region is not None:
                    malformed.append(region)
                    i = max(end, after)
                    continue
            i = after
            continue
        i += 1
    return malformed


def _scan(
    text: str,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
    *,
    statement_context: bool,
) -> list[Segment]:
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
                region, end = _try_region(
                    text, i, keyword, after, source, root_text, base_offset
                )
                if region is not None:
                    terminated = False
                    if statement_context:
                        end, terminated = _consume_statement_terminator(text, end)
                        if terminated:
                            region = Region(
                                keyword=region.keyword,
                                selector_text=region.selector_text,
                                body=region.body,
                                full_text=region.full_text,
                                source=region.source,
                                has_statement_terminator=True,
                                block=region.block,
                                else_block=region.else_block,
                                arms=region.arms,
                            )
                    if raw_start < i:
                        segments.append(
                            RawText(
                                text[raw_start:i],
                                source=_span_for(
                                    source,
                                    root_text,
                                    base_offset + raw_start,
                                    base_offset + i,
                                ),
                            )
                        )
                    segments.append(region)
                    i = end
                    raw_start = end
                    continue
            i = after
            continue
        i += 1
    if raw_start < n:
        segments.append(
            RawText(
                text[raw_start:n],
                source=_span_for(source, root_text, base_offset + raw_start, base_offset + n),
            )
        )
    return segments


def _try_region(
    text: str,
    start: int,
    keyword: str,
    after_keyword: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
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
    body = tuple(
        _scan(
            body_text,
            source,
            root_text,
            base_offset + pos + 1,
            statement_context=False,
        )
    )
    shape = region_body_shape(keyword)
    if shape == "if_block":
        # A block-bearing region: capture the `{ ... }` body (and any `else`) too.
        return _try_if_region(
            text,
            start,
            selector_text,
            body,
            close + 1,
            source,
            root_text,
            base_offset,
        )
    if shape == "loop_block":
        # `loop<backend>(…) { body }` and `loop<backend, unroll>(…) { body }`
        # capture their `{ ... }` block. The lowerer translates them to native loop constructs.
        return _try_loop_region(
            text,
            start,
            selector_text,
            body,
            close + 1,
            source,
            root_text,
            base_offset,
        )
    if shape == "switch_block":
        # `switch<compile>(sel) { label => { body } … }`: capture the arm blocks so the lowerer
        # can emit a compile-time multi-way selection over the selector.
        return _try_switch_region(
            text,
            start,
            selector_text,
            body,
            close + 1,
            source,
            root_text,
            base_offset,
        )
    region = Region(
        keyword=keyword,
        selector_text=selector_text,
        body=body,
        full_text=text[start : close + 1],
        source=_span_for(source, root_text, base_offset + start, base_offset + close + 1),
    )
    return region, close + 1


def _try_if_region(
    text: str,
    start: int,
    selector_text: str,
    condition: tuple[Segment, ...],
    after_condition: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[Region | None, int]:
    """Capture ``if<sel>(cond) { then } [else<sel> ({else} | if...)]`` from
    ``after_condition`` (just past the condition's ``)``). The taken-branch logic
    lives in the lowerer; here we only delimit the then/else blocks."""

    pos = _skip_ws(text, after_condition)
    if pos >= len(text) or text[pos] != "{":
        return None, start  # an `if` without a block is not a region we model
    close = _match_bracket(text, pos, "{", "}")
    if close is None:
        return None, start
    then_block = tuple(
        _scan(
            text[pos + 1 : close],
            source,
            root_text,
            base_offset + pos + 1,
            statement_context=True,
        )
    )
    end = close + 1

    else_block: tuple[Segment, ...] | None = None
    after_then = _skip_ws(text, end)
    if _matches_keyword(text, after_then, "else"):
        else_block, end = _scan_else(
            text, after_then + len("else"), source, root_text, base_offset
        )
        if else_block is None:
            return None, start

    region = Region(
        keyword="if",
        selector_text=selector_text,
        body=condition,
        full_text=text[start:end],
        source=_span_for(source, root_text, base_offset + start, base_offset + end),
        block=then_block,
        else_block=else_block,
    )
    return region, end


def _try_loop_region(
    text: str,
    start: int,
    selector_text: str,
    body: tuple[Segment, ...],
    after_body: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[Region | None, int]:
    """Capture ``loop<sel>(args) [{ block }]`` from ``after_body`` (just past the args'
    ``)``). A trailing ``{ ... }`` goes in ``Region.block``. The native-loop translation
    lives in the lowerer."""

    pos = _skip_ws(text, after_body)
    block: tuple[Segment, ...] | None = None
    end = after_body
    if pos < len(text) and text[pos] == "{":
        close = _match_bracket(text, pos, "{", "}")
        if close is None:
            return None, start
        block = tuple(
            _scan(
                text[pos + 1 : close],
                source,
                root_text,
                base_offset + pos + 1,
                statement_context=True,
            )
        )
        end = close + 1
    region = Region(
        keyword="loop",
        selector_text=selector_text,
        body=body,
        full_text=text[start:end],
        source=_span_for(source, root_text, base_offset + start, base_offset + end),
        block=block,
    )
    return region, end


def _try_switch_region(
    text: str,
    start: int,
    selector_text: str,
    selector: tuple[Segment, ...],
    after_selector: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[Region | None, int]:
    """Capture ``switch<sel>(selector) { label => { body } … }`` from ``after_selector`` (just
    past the selector's ``)``). Each arm is ``label => { block }``; ``label`` is a literal or
    ``_`` (default). The compile-time selection lives in the lowerer; here we only delimit arms."""

    pos = _skip_ws(text, after_selector)
    if pos >= len(text) or text[pos] != "{":
        return None, start  # a switch without a brace block is not a region we model
    outer_close = _match_bracket(text, pos, "{", "}")
    if outer_close is None:
        return None, start
    arms = _scan_switch_arms(
        text[pos + 1 : outer_close], source, root_text, base_offset + pos + 1
    )
    if arms is None:
        return None, start
    region = Region(
        keyword="switch",
        selector_text=selector_text,
        body=selector,
        full_text=text[start : outer_close + 1],
        source=_span_for(
            source, root_text, base_offset + start, base_offset + outer_close + 1
        ),
        arms=arms,
    )
    return region, outer_close + 1


def _try_malformed_region(
    text: str,
    start: int,
    keyword: str,
    after_keyword: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[MalformedRegion | None, int]:
    pos = _skip_ws(text, after_keyword)
    has_selector = False
    if pos < len(text) and text[pos] == "<":
        has_selector = True
        close = _match_bracket(text, pos, "<", ">")
        if close is None:
            return (
                _malformed_region(
                    text,
                    start,
                    len(text),
                    keyword,
                    "unterminated selector",
                    source,
                    root_text,
                    base_offset,
                ),
                len(text),
            )
        pos = _skip_ws(text, close + 1)

    if pos >= len(text) or text[pos] != "(":
        if has_selector:
            end = pos if pos > start else after_keyword
            return (
                _malformed_region(
                    text,
                    start,
                    end,
                    keyword,
                    "missing argument payload",
                    source,
                    root_text,
                    base_offset,
                ),
                max(end, after_keyword),
            )
        return None, after_keyword

    close = _match_bracket(text, pos, "(", ")")
    if close is None:
        return (
            _malformed_region(
                text,
                start,
                len(text),
                keyword,
                "unterminated argument payload",
                source,
                root_text,
                base_offset,
            ),
            len(text),
        )

    shape = region_body_shape(keyword)
    if shape == "if_block":
        return _try_malformed_if_region(
            text, start, keyword, close + 1, source, root_text, base_offset
        )
    if shape == "loop_block":
        return _try_malformed_loop_region(
            text, start, keyword, close + 1, source, root_text, base_offset
        )
    if shape == "switch_block":
        return _try_malformed_switch_region(
            text, start, keyword, close + 1, source, root_text, base_offset
        )
    return None, close + 1


def _try_malformed_if_region(
    text: str,
    start: int,
    keyword: str,
    after_condition: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[MalformedRegion | None, int]:
    pos = _skip_ws(text, after_condition)
    if pos >= len(text) or text[pos] != "{":
        return (
            _malformed_region(
                text,
                start,
                after_condition,
                keyword,
                "missing block",
                source,
                root_text,
                base_offset,
            ),
            after_condition,
        )
    close = _match_bracket(text, pos, "{", "}")
    if close is None:
        return (
            _malformed_region(
                text,
                start,
                len(text),
                keyword,
                "unterminated block",
                source,
                root_text,
                base_offset,
            ),
            len(text),
        )
    end = close + 1
    after_then = _skip_ws(text, end)
    if _matches_keyword(text, after_then, "else"):
        return _try_malformed_else_region(
            text, start, keyword, after_then + len("else"), source, root_text, base_offset
        )
    return None, end


def _try_malformed_else_region(
    text: str,
    start: int,
    keyword: str,
    after_else: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[MalformedRegion | None, int]:
    pos = _skip_ws(text, after_else)
    if pos < len(text) and text[pos] == "<":
        close = _match_bracket(text, pos, "<", ">")
        if close is None:
            return (
                _malformed_region(
                    text,
                    start,
                    len(text),
                    keyword,
                    "unterminated else selector",
                    source,
                    root_text,
                    base_offset,
                ),
                len(text),
            )
        pos = _skip_ws(text, close + 1)
    if pos >= len(text):
        return (
            _malformed_region(
                text,
                start,
                pos,
                keyword,
                "missing else block",
                source,
                root_text,
                base_offset,
            ),
            pos,
        )
    if text[pos] == "{":
        close = _match_bracket(text, pos, "{", "}")
        if close is None:
            return (
                _malformed_region(
                    text,
                    start,
                    len(text),
                    keyword,
                    "unterminated else block",
                    source,
                    root_text,
                    base_offset,
                ),
                len(text),
            )
        return None, close + 1
    if _matches_keyword(text, pos, "if"):
        nested_keyword, nested_after = _read_ident(text, pos)
        return _try_malformed_region(
            text,
            pos,
            nested_keyword,
            nested_after,
            source,
            root_text,
            base_offset,
        )
    return (
        _malformed_region(
            text,
            start,
            pos,
            keyword,
            "malformed else block",
            source,
            root_text,
            base_offset,
        ),
        pos,
    )


def _try_malformed_loop_region(
    text: str,
    start: int,
    keyword: str,
    after_body: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[MalformedRegion | None, int]:
    pos = _skip_ws(text, after_body)
    if pos < len(text) and text[pos] == "{":
        close = _match_bracket(text, pos, "{", "}")
        if close is None:
            return (
                _malformed_region(
                    text,
                    start,
                    len(text),
                    keyword,
                    "unterminated block",
                    source,
                    root_text,
                    base_offset,
                ),
                len(text),
            )
        return None, close + 1
    return None, after_body


def _try_malformed_switch_region(
    text: str,
    start: int,
    keyword: str,
    after_selector: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[MalformedRegion | None, int]:
    pos = _skip_ws(text, after_selector)
    if pos >= len(text) or text[pos] != "{":
        return (
            _malformed_region(
                text,
                start,
                after_selector,
                keyword,
                "missing switch block",
                source,
                root_text,
                base_offset,
            ),
            after_selector,
        )
    outer_close = _match_bracket(text, pos, "{", "}")
    if outer_close is None:
        return (
            _malformed_region(
                text,
                start,
                len(text),
                keyword,
                "unterminated switch block",
                source,
                root_text,
                base_offset,
            ),
            len(text),
        )
    arms = _scan_switch_arms(
        text[pos + 1 : outer_close], source, root_text, base_offset + pos + 1
    )
    if arms is None:
        return (
            _malformed_region(
                text,
                start,
                outer_close + 1,
                keyword,
                "malformed switch arms",
                source,
                root_text,
                base_offset,
            ),
            outer_close + 1,
        )
    return None, outer_close + 1


def _malformed_region(
    text: str,
    start: int,
    end: int,
    keyword: str,
    reason: str,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> MalformedRegion:
    bounded_end = min(len(text), max(start + len(keyword), end))
    return MalformedRegion(
        keyword=keyword,
        reason=reason,
        text=text[start:bounded_end],
        source=_span_for(
            source,
            root_text,
            base_offset + start,
            base_offset + bounded_end,
        ),
    )


def _scan_switch_arms(
    inner: str,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[tuple[str, tuple[Segment, ...]], ...] | None:
    """Parse ``label => { body } …`` arms from a switch block's inner text. Returns None if the
    shape doesn't hold (so the caller leaves the text as a non-region)."""

    arms: list[tuple[str, tuple[Segment, ...]]] = []
    i = 0
    while True:
        i = _skip_ws(inner, i)
        if i >= len(inner):
            break
        arrow = inner.find("=>", i)
        if arrow == -1:
            return None
        label = inner[i:arrow].strip()
        brace = _skip_ws(inner, arrow + 2)
        if brace >= len(inner) or inner[brace] != "{":
            return None
        close = _match_bracket(inner, brace, "{", "}")
        if close is None:
            return None
        arms.append(
            (
                label,
                tuple(
                    _scan(
                        inner[brace + 1 : close],
                        source,
                        root_text,
                        base_offset + brace + 1,
                        statement_context=True,
                    )
                ),
            )
        )
        i = close + 1
    return tuple(arms) if arms else None


def _scan_else(
    text: str,
    after_else: int,
    source: SourceSpan | None,
    root_text: str,
    base_offset: int,
) -> tuple[tuple[Segment, ...] | None, int]:
    """Parse the tail of ``else<sel> ( { ... } | if<sel>(...){...} )``.

    Returns ``(segments, end)``; ``segments`` is the else body (a brace block, or a
    one-element tuple holding the nested ``if`` region for an ``else if`` chain)."""

    pos = _skip_ws(text, after_else)
    if pos < len(text) and text[pos] == "<":  # consume the else<...> selector
        close = _match_bracket(text, pos, "<", ">")
        if close is None:
            return None, pos
        pos = _skip_ws(text, close + 1)
    if pos >= len(text):
        return None, pos
    if text[pos] == "{":
        close = _match_bracket(text, pos, "{", "}")
        if close is None:
            return None, pos
        return (
            tuple(
                _scan(
                    text[pos + 1 : close],
                    source,
                    root_text,
                    base_offset + pos + 1,
                    statement_context=True,
                )
            ),
            close + 1,
        )
    if _matches_keyword(text, pos, "if"):
        keyword, after = _read_ident(text, pos)
        region, end = _try_region(text, pos, keyword, after, source, root_text, base_offset)
        if region is None:
            return None, pos
        return (region,), end
    return None, pos


def _matches_keyword(text: str, index: int, keyword: str) -> bool:
    if not _boundary_before(text, index):
        return False
    word, after = _read_ident(text, index)
    return word == keyword and after > index


def _consume_statement_terminator(text: str, index: int) -> tuple[int, bool]:
    pos = _skip_ws(text, index)
    if pos < len(text) and text[pos] == ";":
        return pos + 1, True
    return index, False


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


def _span_for(
    source: SourceSpan | None,
    root_text: str,
    start: int,
    end: int,
) -> SourceSpan | None:
    if source is None:
        return None
    line, column = _line_column(source, root_text, start)
    end_line, end_column = _line_column(source, root_text, end)
    return SourceSpan(
        path=source.path,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
    )


def _line_column(source: SourceSpan, text: str, offset: int) -> tuple[int, int]:
    line = source.line
    column = source.column
    for character in text[:offset]:
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column


def _boundary_before(text: str, index: int) -> bool:
    """A keyword must not be the tail of a longer identifier (e.g. ``my_call``)."""

    if index == 0:
        return True
    return text[index - 1] not in _IDENT_CONT
