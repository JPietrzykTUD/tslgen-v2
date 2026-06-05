"""Exact TSIL primitive-call island classification for raw body tokens."""

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    LowerableDirective,
    RawStringToken,
)
from tslgen.lowering.primitive_call_fragments import (
    ExactPrimitiveCallFragment,
    PrimitiveCallFragmentAdaptationResult,
    PrimitiveCallFragmentText,
    adapt_exact_primitive_call_fragment,
)
from tslgen.syntax.tsil_lexical import (
    BRACKET_DELIMITER,
    PAREN_DELIMITER,
    find_top_level_char,
    matching_close,
)

_CALL_PREFIX = "call<primitive="


@dataclass(frozen=True, slots=True)
class _PrimitiveCallMatch:
    selector_payload: str
    payload: str
    start: int
    selector_payload_start: int
    argument_payload_start: int
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

        adaptation = _adapt_match(joined, match)
        if adaptation.directive is None:
            classified.extend(_raw_token(joined, position, len(joined.text)))
            break

        classified.extend(_raw_token(joined, position, match.start))
        classified.append(adaptation.directive)
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

    selector_payload_start = start + len("call<")
    selector_end = _matching_call_selector_end(text, selector_payload_start)
    if selector_end is None:
        return None

    open_index = selector_end + 1
    if open_index >= len(text) or text[open_index] != "(":
        return None

    close_index = matching_close(text, open_index, PAREN_DELIMITER)
    if close_index is None:
        return None

    return _PrimitiveCallMatch(
        selector_payload=text[selector_payload_start:selector_end],
        payload=text[open_index + 1 : close_index],
        start=start,
        selector_payload_start=selector_payload_start,
        argument_payload_start=open_index + 1,
        end=close_index + 1,
    )


def _matching_call_selector_end(text: str, start: int) -> int | None:
    return find_top_level_char(
        text,
        ">",
        start=start,
        delimiters=(BRACKET_DELIMITER,),
    )


def _adapt_match(
    joined: "_JoinedRawTokens",
    match: _PrimitiveCallMatch,
) -> PrimitiveCallFragmentAdaptationResult:
    return adapt_exact_primitive_call_fragment(
        ExactPrimitiveCallFragment(
            source=joined.source_at(match.start),
            selector_payload=PrimitiveCallFragmentText.from_source(
                match.selector_payload,
                joined.source_at(match.selector_payload_start),
            ),
            argument_payload=PrimitiveCallFragmentText.from_source(
                match.payload,
                joined.source_at(match.argument_payload_start),
            ),
        )
    )


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
