"""Exact TSIL primitive-call island classification for raw body tokens."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    LowerableDirective,
    RawStringToken,
)

_CALL_PREFIX = "call<primitive="


@dataclass(frozen=True, slots=True)
class _PrimitiveCallMatch:
    selector: str
    payload: str
    start: int
    end: int


def classify_tsil_primitive_call_tokens(
    tokens: tuple[BodyToken, ...],
) -> tuple[BodyToken, ...]:
    """Classify exact primitive-call islands in contiguous raw-token runs."""

    classified: list[BodyToken] = []
    raw_run: list[RawStringToken] = []

    for token in tokens:
        if isinstance(token, RawStringToken):
            raw_run.append(token)
            continue

        classified.extend(_classify_raw_run(tuple(raw_run)))
        raw_run = []
        classified.append(token)

    classified.extend(_classify_raw_run(tuple(raw_run)))
    return tuple(classified)


def _classify_raw_run(tokens: tuple[RawStringToken, ...]) -> tuple[BodyToken, ...]:
    if not tokens:
        return ()

    joined = _JoinedRawTokens.from_tokens(tokens)
    if _CALL_PREFIX not in joined.text:
        return tokens

    classified: list[BodyToken] = []
    position = 0
    while position < len(joined.text):
        start = _find_call_prefix(joined.text, position)
        if start == -1:
            classified.extend(_raw_token(joined, position, len(joined.text)))
            break

        match = _match_primitive_call(joined.text, start)
        if match is None:
            classified.extend(_raw_token(joined, position, len(joined.text)))
            break

        classified.extend(_raw_token(joined, position, match.start))
        classified.append(
            LowerableDirective(
                name="call",
                arguments=("primitive", match.selector, match.payload),
                source=joined.source_at(match.start),
            )
        )
        position = match.end

    return tuple(classified)


def _find_call_prefix(text: str, start: int) -> int:
    index = text.find(_CALL_PREFIX, start)
    while index != -1:
        if _has_keyword_boundary(text, index):
            return index
        index = text.find(_CALL_PREFIX, index + 1)
    return -1


def _has_keyword_boundary(text: str, index: int) -> bool:
    if index == 0:
        return True
    previous = text[index - 1]
    return not (previous.isalnum() or previous in "_:.")


def _match_primitive_call(text: str, start: int) -> _PrimitiveCallMatch | None:
    if not text.startswith(_CALL_PREFIX, start):
        return None

    selector_start = start + len(_CALL_PREFIX)
    selector_end = _matching_call_selector_end(text, selector_start)
    if selector_end is None:
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

    return _PrimitiveCallMatch(
        selector=selector,
        payload=text[open_index + 1 : close_index],
        start=start,
        end=close_index + 1,
    )


def _matching_call_selector_end(text: str, start: int) -> int | None:
    bracket_depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == ">" and bracket_depth == 0:
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


def _raw_token(
    joined: "_JoinedRawTokens",
    start: int,
    end: int,
) -> tuple[RawStringToken, ...]:
    if start >= end:
        return ()
    return (
        RawStringToken(
            text=joined.text[start:end],
            source=joined.source_at(start),
        ),
    )


@dataclass(frozen=True, slots=True)
class _JoinedRawTokens:
    text: str
    sources: tuple[SourceLocation, ...]

    @classmethod
    def from_tokens(
        cls,
        tokens: tuple[RawStringToken, ...],
    ) -> "_JoinedRawTokens":
        text_parts: list[str] = []
        sources: list[SourceLocation] = []

        previous: RawStringToken | None = None
        for token in tokens:
            if previous is not None:
                text_parts.append("\n")
                sources.append(_source_after_text(previous.source, previous.text))

            text_parts.append(token.text)
            sources.extend(_sources_for_text(token.source, token.text))
            previous = token

        return cls(text="".join(text_parts), sources=tuple(sources))

    def source_at(self, index: int) -> SourceLocation:
        return self.sources[index]


def _sources_for_text(
    source: SourceLocation,
    text: str,
) -> tuple[SourceLocation, ...]:
    locations: list[SourceLocation] = []
    line = source.line
    column = source.column
    for char in text:
        locations.append(SourceLocation(source.path, line, column))
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return tuple(locations)


def _source_after_text(source: SourceLocation, text: str) -> SourceLocation:
    line = source.line
    column = source.column
    for char in text:
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return SourceLocation(source.path, line, column)
