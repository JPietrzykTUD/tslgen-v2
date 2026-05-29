"""Exact TSIL directive-envelope classification for catalog body lines."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    LowerableDirective,
    RawStringToken,
)
from tslgen.syntax.ast import ParsedRawStringLine

_EMIT_RETURN_DIRECTIVE = "emit_return"
_EMIT_RETURN_PREFIX = f"{_EMIT_RETURN_DIRECTIVE}("
_CALL_SHAPED_DIRECTIVES = frozenset(("if", "let", "loop", "switch", "var"))
_SELECTOR_ONLY_DIRECTIVES = frozenset(("else",))


@dataclass(frozen=True, slots=True)
class _DirectiveMatch:
    name: str
    arguments: tuple[str, ...]
    start: int
    end: int
    prefix: str
    suffix: str


def classify_tsil_directive_line(
    line: ParsedRawStringLine,
) -> tuple[BodyToken, ...] | None:
    """Classify one exact selected directive envelope in a raw TSIL line."""

    leading_columns = len(line.text) - len(line.text.lstrip(" "))
    text = line.text[leading_columns:]
    base_column = line.source.column + leading_columns

    match = _match_emit_return(text) or _match_selected_directive(text)
    if match is None:
        return None

    segments: list[RawStringToken | LowerableDirective] = []
    if match.prefix:
        segments.append(
            RawStringToken(
                text=match.prefix,
                source=_source_at(line.source, base_column + match.start),
            )
        )

    directive_source = _source_at(
        line.source,
        base_column + match.start + len(match.prefix),
    )
    segments.append(
        LowerableDirective(
            name=match.name,
            arguments=match.arguments,
            source=directive_source,
        )
    )

    if match.suffix:
        segments.extend(
            _raw_suffix_tokens(
                match.suffix,
                _source_at(line.source, base_column + match.end),
            )
        )

    return tuple(segments)


def _match_emit_return(text: str) -> _DirectiveMatch | None:
    if not text.startswith(_EMIT_RETURN_PREFIX):
        return None

    payload_start = len(_EMIT_RETURN_PREFIX)
    close_index = _matching_close_paren(text, payload_start - 1)
    if close_index is None:
        return None

    payload = text[payload_start:close_index]
    if not payload:
        return None
    if text[close_index + 1 :].strip() != ";":
        return None

    return _DirectiveMatch(
        name=_EMIT_RETURN_DIRECTIVE,
        arguments=(payload,),
        start=0,
        end=close_index + 1,
        prefix="",
        suffix="",
    )


def _match_selected_directive(text: str) -> _DirectiveMatch | None:
    for name in sorted(_CALL_SHAPED_DIRECTIVES):
        match = _match_call_shaped_directive(text, name, 0, "")
        if match is not None:
            return match
    if text.startswith("else "):
        match = _match_call_shaped_directive(text, "if", len("else "), "else ")
        if match is not None and match.arguments[0] == "generation":
            return match
    prefix, start = _allowed_prefix(text)
    for name in sorted(_SELECTOR_ONLY_DIRECTIVES):
        match = _match_selector_only_directive(text, name, start, prefix)
        if match is not None:
            return match
    return None


def _allowed_prefix(text: str) -> tuple[str, int]:
    if text.startswith("}"):
        index = 1
        while index < len(text) and text[index] == " ":
            index += 1
        return (text[:index], index)
    return ("", 0)


def _match_call_shaped_directive(
    text: str,
    name: str,
    start: int,
    prefix: str,
) -> _DirectiveMatch | None:
    selector_start = start + len(name) + 1
    if not text.startswith(f"{name}<", start):
        return None

    selector_end = text.find(">", selector_start)
    if selector_end == -1:
        return None
    selector = text[selector_start:selector_end]
    if not selector:
        return None

    open_index = selector_end + 1
    if open_index >= len(text) or text[open_index] != "(":
        return None

    close_index = _matching_close_paren(text, open_index)
    if close_index is None:
        return None

    payload = text[open_index + 1 : close_index]
    if not payload:
        return None

    suffix = _accepted_call_suffix(name, selector, text[close_index + 1 :])
    if suffix is None:
        return None

    return _DirectiveMatch(
        name=name,
        arguments=(selector, payload),
        start=start - len(prefix),
        end=close_index + 1,
        prefix=prefix,
        suffix=suffix,
    )


def _match_selector_only_directive(
    text: str,
    name: str,
    start: int,
    prefix: str,
) -> _DirectiveMatch | None:
    selector_start = start + len(name) + 1
    if not text.startswith(f"{name}<", start):
        return None

    selector_end = text.find(">", selector_start)
    if selector_end == -1:
        return None
    selector = text[selector_start:selector_end]
    if not selector:
        return None

    suffix = _accepted_block_suffix(text[selector_end + 1 :])
    if suffix is None:
        return None

    return _DirectiveMatch(
        name=name,
        arguments=(selector,),
        start=start - len(prefix),
        end=selector_end + 1,
        prefix=prefix,
        suffix=suffix,
    )


def _accepted_call_suffix(name: str, selector: str, tail: str) -> str | None:
    stripped = tail.strip()
    if name in ("let", "var"):
        if stripped == "":
            return ""
        if stripped == ";":
            return tail
        return None
    if name == "if" and selector == "generation":
        generation_inline = _accepted_inline_generation_block_suffix(tail)
        if generation_inline is not None:
            return generation_inline
    return _accepted_block_suffix(tail)


def _accepted_inline_generation_block_suffix(tail: str) -> str | None:
    stripped = tail.strip()
    if not stripped.startswith("{"):
        return None
    close_index = _matching_close_brace(stripped, 0)
    if close_index is None or stripped[close_index + 1 :].strip():
        return None
    return tail


def _accepted_block_suffix(tail: str) -> str | None:
    stripped = tail.strip()
    if stripped == "":
        return ""
    if stripped == "{":
        return tail
    return None


def _raw_suffix_tokens(
    suffix: str,
    source: SourceLocation,
) -> tuple[RawStringToken, ...]:
    inline_block = _split_inline_block_suffix(suffix)
    if inline_block is None:
        return (RawStringToken(text=suffix, source=source),)

    open_text, body_text, close_text, body_offset, close_offset = inline_block
    tokens = [
        RawStringToken(text=open_text, source=source),
    ]
    if body_text:
        tokens.append(
            RawStringToken(
                text=body_text,
                source=_source_at(source, source.column + body_offset),
            )
        )
    tokens.append(
        RawStringToken(
            text=close_text,
            source=_source_at(source, source.column + close_offset),
        )
    )
    return tuple(tokens)


def _split_inline_block_suffix(
    suffix: str,
) -> tuple[str, str, str, int, int] | None:
    open_index = suffix.find("{")
    if open_index == -1 or suffix[:open_index].strip():
        return None
    close_index = _matching_close_brace(suffix, open_index)
    if close_index is None or suffix[close_index + 1 :].strip():
        return None
    body_text = suffix[open_index + 1 : close_index]
    if not body_text:
        return None
    return (
        suffix[: open_index + 1],
        body_text,
        suffix[close_index:],
        open_index + 1,
        close_index,
    )


def _matching_close_brace(text: str, open_index: int) -> int | None:
    depth = 1
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _matching_close_paren(text: str, open_index: int) -> int | None:
    depth = 1
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _source_at(source: SourceLocation, column: int) -> SourceLocation:
    return SourceLocation(source.path, source.line, column)
