"""Lexical source-body region discovery for raw TSIL payload envelopes.

This module recognizes configured keyword-shaped regions by delimiter balance
only. It does not interpret TSIL keyword semantics, expression contents, branch
conditions, primitive calls, or backend behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.syntax.outer_ast import ParsedImplementationBodyEnvelope
from tslgen.syntax.tsil_lexical import (
    ANGLE_DELIMITER,
    BRACE_DELIMITER,
    PAREN_DELIMITER,
    DelimiterPair,
    matching_close_lexical,
    matching_quote_close,
    starts_quoted_text,
)

SourceBodyDelimitedSpanKind = Literal["angle", "brace", "paren"]

_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


@dataclass(frozen=True, slots=True)
class SourceBodyText:
    path: Path
    line: int
    column: int
    text: str

    @classmethod
    def from_envelope(
        cls,
        envelope: ParsedImplementationBodyEnvelope,
    ) -> "SourceBodyText":
        return cls(
            path=envelope.payload_source.path,
            line=envelope.payload_source.line,
            column=envelope.payload_source.column,
            text=envelope.payload_text,
        )

    @classmethod
    def from_span(cls, span: "SourceBodySpan") -> "SourceBodyText":
        return cls(
            path=span.path,
            line=span.line,
            column=span.column,
            text=span.text,
        )

    def source_at(self, offset: int) -> SourceLocation:
        if offset < 0 or offset > len(self.text):
            raise ValueError("offset is outside source body text")
        line, column = _line_column_after_offset(self.line, self.column, self.text, offset)
        return SourceLocation(self.path, line, column)

    def span(self, start_offset: int, end_offset: int) -> "SourceBodySpan":
        if start_offset < 0 or end_offset < start_offset or end_offset > len(self.text):
            raise ValueError("invalid source body span offsets")
        line, column = _line_column_after_offset(
            self.line,
            self.column,
            self.text,
            start_offset,
        )
        end_line, end_column = _line_column_after_offset(
            self.line,
            self.column,
            self.text,
            end_offset,
        )
        return SourceBodySpan(
            path=self.path,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            start_offset=start_offset,
            end_offset=end_offset,
            text=self.text[start_offset:end_offset],
        )


@dataclass(frozen=True, slots=True)
class SourceBodySpan:
    path: Path
    line: int
    column: int
    end_line: int
    end_column: int
    start_offset: int
    end_offset: int
    text: str

    @property
    def start(self) -> SourceLocation:
        return SourceLocation(self.path, self.line, self.column)


@dataclass(frozen=True, slots=True)
class SourceBodyDelimitedSpan:
    kind: SourceBodyDelimitedSpanKind
    delimiter: DelimiterPair
    full_span: SourceBodySpan
    payload_span: SourceBodySpan


class SourceBodyKeyword(Enum):
    INTRIN_COMPOSE = auto()
    EMIT_RETURN = auto()
    CALL = auto()
    TYPE = auto()
    VALUE = auto()
    VAR = auto()
    IF = auto()
    ELSE = auto()
    LOOP = auto()
    SWITCH = auto()
    CUSTOM = auto()


@dataclass(frozen=True, slots=True)
class SourceBodyRegionHead:
    keyword: SourceBodyKeyword
    spelling: str
    selector_text: str | None = None
    expects_selector: bool = False
    expects_payload: bool = True
    expects_body: bool = False

    @classmethod
    def custom(
        cls,
        spelling: str,
        *,
        selector_text: str | None = None,
        expects_selector: bool = False,
        expects_payload: bool = True,
        expects_body: bool = False,
    ) -> "SourceBodyRegionHead":
        return cls(
            keyword=SourceBodyKeyword.CUSTOM,
            spelling=spelling,
            selector_text=selector_text,
            expects_selector=expects_selector,
            expects_payload=expects_payload,
            expects_body=expects_body,
        )

    @property
    def name(self) -> str:
        return self.spelling


@dataclass(frozen=True, slots=True)
class SourceBodyRawSegment:
    source_order: int
    span: SourceBodySpan


@dataclass(frozen=True, slots=True)
class SourceBodyLexicalRegionCandidate:
    source_order: int
    head: SourceBodyRegionHead
    full_span: SourceBodySpan
    head_span: SourceBodySpan
    selector: SourceBodyDelimitedSpan | None = None
    payload: SourceBodyDelimitedSpan | None = None
    body: SourceBodyDelimitedSpan | None = None


SourceBodyLexicalItem = SourceBodyRawSegment | SourceBodyLexicalRegionCandidate


@dataclass(frozen=True, slots=True)
class SourceBodyLexicalScanResult:
    source_text: SourceBodyText
    items: tuple[SourceBodyLexicalItem, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def raw_segments(self) -> tuple[SourceBodyRawSegment, ...]:
        return tuple(
            item for item in self.items if isinstance(item, SourceBodyRawSegment)
        )

    @property
    def regions(self) -> tuple[SourceBodyLexicalRegionCandidate, ...]:
        return tuple(
            item
            for item in self.items
            if isinstance(item, SourceBodyLexicalRegionCandidate)
        )


DEFAULT_SOURCE_BODY_REGION_HEADS: tuple[SourceBodyRegionHead, ...] = (
    SourceBodyRegionHead(
        SourceBodyKeyword.INTRIN_COMPOSE,
        "intrin_compose",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.EMIT_RETURN,
        "emit_return",
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.CALL,
        "call",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.TYPE,
        "type",
        selector_text="backend",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.VALUE,
        "value",
        selector_text="generation",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.VAR,
        "var",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.IF,
        "if",
        expects_selector=True,
        expects_body=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.ELSE,
        "else",
        expects_selector=True,
        expects_payload=False,
        expects_body=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.LOOP,
        "loop",
        selector_text="unroll",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.LOOP,
        "loop",
        selector_text="range",
        expects_selector=True,
        expects_body=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.LOOP,
        "loop",
        expects_selector=True,
    ),
    SourceBodyRegionHead(
        SourceBodyKeyword.SWITCH,
        "switch",
        expects_selector=True,
        expects_body=True,
    ),
)


class SourceBodyLexicalRegionScanner:
    """Find configured balanced TSIL-looking regions in source-owned text."""

    def __init__(
        self,
        region_heads: tuple[SourceBodyRegionHead, ...] = DEFAULT_SOURCE_BODY_REGION_HEADS,
    ) -> None:
        self._region_heads = tuple(
            sorted(region_heads, key=lambda head: (-len(head.name), head.name))
        )

    def scan_envelope(
        self,
        envelope: ParsedImplementationBodyEnvelope,
    ) -> SourceBodyLexicalScanResult:
        return self.scan(SourceBodyText.from_envelope(envelope))

    def scan(self, source_text: SourceBodyText) -> SourceBodyLexicalScanResult:
        text = source_text.text
        items: list[SourceBodyLexicalItem] = []
        diagnostics: list[Diagnostic] = []
        index = 0
        raw_start = 0
        source_order = 0

        while index < len(text):
            if starts_quoted_text(text, index):
                quote_close = matching_quote_close(text, index)
                if quote_close is None:
                    break
                index = quote_close + 1
                continue

            matched = False
            for head in self._region_heads:
                if not _head_matches_at(text, index, head.name):
                    continue
                match = self._match_region(source_text, index, head)
                if match.candidate is not None:
                    if raw_start < index:
                        items.append(
                            SourceBodyRawSegment(
                                source_order=source_order,
                                span=source_text.span(raw_start, index),
                            )
                        )
                        source_order += 1
                    items.append(
                        SourceBodyLexicalRegionCandidate(
                            source_order=source_order,
                            head=match.candidate.head,
                            full_span=match.candidate.full_span,
                            head_span=match.candidate.head_span,
                            selector=match.candidate.selector,
                            payload=match.candidate.payload,
                            body=match.candidate.body,
                        )
                    )
                    source_order += 1
                    index = match.end_offset
                    raw_start = index
                    matched = True
                    break
                if match.error is not None:
                    diagnostics.append(match.error)
                    index = max(match.end_offset, index + len(head.name))
                    matched = True
                    break

            if not matched:
                index += 1

        if raw_start < len(text):
            items.append(
                SourceBodyRawSegment(
                    source_order=source_order,
                    span=source_text.span(raw_start, len(text)),
                )
            )

        return SourceBodyLexicalScanResult(
            source_text=source_text,
            items=tuple(items),
            diagnostics=tuple(diagnostics),
        )

    def _match_region(
        self,
        source_text: SourceBodyText,
        start_offset: int,
        head: SourceBodyRegionHead,
    ) -> "_SourceBodyRegionMatch":
        text = source_text.text
        cursor = start_offset + len(head.name)
        selector: SourceBodyDelimitedSpan | None = None
        payload: SourceBodyDelimitedSpan | None = None
        body: SourceBodyDelimitedSpan | None = None

        if head.expects_selector:
            if cursor >= len(text) or text[cursor] != "<":
                return _SourceBodyRegionMatch.no_match()
            close_index = matching_close_lexical(text, cursor, ANGLE_DELIMITER)
            if close_index is None:
                return _SourceBodyRegionMatch.diagnostic(
                    self._diagnostic(
                        "TSL-BODY-REGION-UNBALANCED-ANGLE",
                        f"TSIL source-body region {head.name!r} has no matching '>'",
                        source_text,
                        cursor,
                    ),
                    len(text),
                )
            selector = _delimited_span(
                source_text,
                "angle",
                ANGLE_DELIMITER,
                cursor,
                close_index,
            )
            if (
                head.selector_text is not None
                and selector.payload_span.text.strip() != head.selector_text
            ):
                return _SourceBodyRegionMatch.no_match()
            cursor = close_index + 1

        if head.expects_payload:
            cursor = _skip_whitespace(text, cursor)
            if cursor >= len(text) or text[cursor] != "(":
                return _SourceBodyRegionMatch.diagnostic(
                    self._diagnostic(
                        "TSL-BODY-REGION-MISSING-PAREN",
                        f"TSIL source-body region {head.name!r} is missing '('",
                        source_text,
                        cursor,
                    ),
                    len(text),
                )
            close_index = matching_close_lexical(text, cursor, PAREN_DELIMITER)
            if close_index is None:
                return _SourceBodyRegionMatch.diagnostic(
                    self._diagnostic(
                        "TSL-BODY-REGION-UNBALANCED-PAREN",
                        f"TSIL source-body region {head.name!r} has no matching ')'",
                        source_text,
                        cursor,
                    ),
                    len(text),
                )
            payload = _delimited_span(
                source_text,
                "paren",
                PAREN_DELIMITER,
                cursor,
                close_index,
            )
            cursor = close_index + 1

        if head.expects_body:
            cursor = _skip_whitespace(text, cursor)
            if cursor >= len(text) or text[cursor] != "{":
                return _SourceBodyRegionMatch.diagnostic(
                    self._diagnostic(
                        "TSL-BODY-REGION-MISSING-BRACE",
                        f"TSIL source-body region {head.name!r} is missing '{{'",
                        source_text,
                        cursor,
                    ),
                    len(text),
                )
            close_index = matching_close_lexical(text, cursor, BRACE_DELIMITER)
            if close_index is None:
                return _SourceBodyRegionMatch.diagnostic(
                    self._diagnostic(
                        "TSL-BODY-REGION-UNBALANCED-BRACE",
                        f"TSIL source-body region {head.name!r} has no matching '}}'",
                        source_text,
                        cursor,
                    ),
                    len(text),
                )
            body = _delimited_span(
                source_text,
                "brace",
                BRACE_DELIMITER,
                cursor,
                close_index,
            )
            cursor = close_index + 1

        return _SourceBodyRegionMatch.region(
            SourceBodyLexicalRegionCandidate(
                source_order=0,
                head=head,
                full_span=source_text.span(start_offset, cursor),
                head_span=source_text.span(start_offset, start_offset + len(head.name)),
                selector=selector,
                payload=payload,
                body=body,
            ),
            cursor,
        )

    def _diagnostic(
        self,
        code: str,
        message: str,
        source_text: SourceBodyText,
        offset: int,
    ) -> Diagnostic:
        return Diagnostic(
            severity="error",
            code=code,
            message=message,
            location=source_text.source_at(min(offset, len(source_text.text))),
        )


@dataclass(frozen=True, slots=True)
class _SourceBodyRegionMatch:
    candidate: SourceBodyLexicalRegionCandidate | None
    error: Diagnostic | None
    end_offset: int

    @classmethod
    def no_match(cls) -> "_SourceBodyRegionMatch":
        return cls(candidate=None, error=None, end_offset=0)

    @classmethod
    def diagnostic(
        cls,
        diagnostic: Diagnostic,
        end_offset: int,
    ) -> "_SourceBodyRegionMatch":
        return cls(candidate=None, error=diagnostic, end_offset=end_offset)

    @classmethod
    def region(
        cls,
        region: SourceBodyLexicalRegionCandidate,
        end_offset: int,
    ) -> "_SourceBodyRegionMatch":
        return cls(candidate=region, error=None, end_offset=end_offset)


def scan_source_body_envelope(
    envelope: ParsedImplementationBodyEnvelope,
    *,
    region_heads: tuple[SourceBodyRegionHead, ...] = DEFAULT_SOURCE_BODY_REGION_HEADS,
) -> SourceBodyLexicalScanResult:
    return SourceBodyLexicalRegionScanner(region_heads).scan_envelope(envelope)


def scan_source_body_text(
    source_text: SourceBodyText,
    *,
    region_heads: tuple[SourceBodyRegionHead, ...] = DEFAULT_SOURCE_BODY_REGION_HEADS,
) -> SourceBodyLexicalScanResult:
    return SourceBodyLexicalRegionScanner(region_heads).scan(source_text)


def _delimited_span(
    source_text: SourceBodyText,
    kind: SourceBodyDelimitedSpanKind,
    delimiter: DelimiterPair,
    open_offset: int,
    close_offset: int,
) -> SourceBodyDelimitedSpan:
    return SourceBodyDelimitedSpan(
        kind=kind,
        delimiter=delimiter,
        full_span=source_text.span(open_offset, close_offset + 1),
        payload_span=source_text.span(open_offset + 1, close_offset),
    )


def _head_matches_at(text: str, offset: int, head: str) -> bool:
    return (
        text.startswith(head, offset)
        and _has_identifier_boundary_before(text, offset)
        and _has_identifier_boundary_after(text, offset + len(head))
    )


def _has_identifier_boundary_before(text: str, offset: int) -> bool:
    return offset == 0 or text[offset - 1] not in _IDENTIFIER_CHARS


def _has_identifier_boundary_after(text: str, offset: int) -> bool:
    return offset >= len(text) or text[offset] not in _IDENTIFIER_CHARS


def _skip_whitespace(text: str, offset: int) -> int:
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _line_column_after_offset(
    line: int,
    column: int,
    text: str,
    offset: int,
) -> tuple[int, int]:
    for char in text[:offset]:
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column
