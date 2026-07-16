"""UTF-16/LSP and compiler source-position conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from lsprotocol import types

from tslc.diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class SourceTextMap:
    """One request-local source map for repeated UTF-16 range conversion."""

    lines: tuple[str, ...]

    @classmethod
    def from_text(cls, text: str) -> "SourceTextMap":
        return cls(tuple(text.splitlines(keepends=True)))

    def range(self, span: SourceSpan) -> types.Range:
        return types.Range(
            start=types.Position(
                line=max(span.line - 1, 0),
                character=_utf16_column(self.lines, span.line, span.column),
            ),
            end=types.Position(
                line=max(span.end_line - 1, 0),
                character=_utf16_column(
                    self.lines,
                    span.end_line,
                    span.end_column,
                ),
            ),
        )


def path_to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"TSL language server supports only file URIs, got {uri!r}")
    value = unquote(parsed.path)
    if parsed.netloc:
        value = f"//{parsed.netloc}{value}"
    return Path(value).resolve()


def source_position(text: str, position: types.Position) -> tuple[int, int]:
    """Convert zero-based UTF-16 LSP coordinates to one-based codepoint coordinates."""

    lines = text.splitlines(keepends=True)
    if not lines:
        return 1, 1
    line_index = min(max(position.line, 0), len(lines) - 1)
    line = lines[line_index].rstrip("\r\n")
    codepoints = _codepoints_for_utf16(line, max(position.character, 0))
    return line_index + 1, codepoints + 1


def position_offset(text: str, position: types.Position) -> int:
    """Return a Python codepoint offset for one LSP UTF-16 position."""

    lines = text.splitlines(keepends=True)
    if not lines:
        return 0
    line_index = min(max(position.line, 0), len(lines) - 1)
    prefix = sum(len(line) for line in lines[:line_index])
    content = lines[line_index].rstrip("\r\n")
    return prefix + _codepoints_for_utf16(content, max(position.character, 0))


def offset_position(text: str, offset: int) -> types.Position:
    """Return a zero-based UTF-16 LSP position for a Python codepoint offset."""

    bounded = min(max(offset, 0), len(text))
    line_start = text.rfind("\n", 0, bounded) + 1
    line = text.count("\n", 0, line_start)
    prefix = text[line_start:bounded]
    return types.Position(
        line=line,
        character=len(prefix.encode("utf-16-le")) // 2,
    )


def span_to_range(span: SourceSpan, text: str) -> types.Range:
    return SourceTextMap.from_text(text).range(span)


def _utf16_column(
    lines: tuple[str, ...], one_based_line: int, one_based_column: int
) -> int:
    if one_based_line < 1 or one_based_line > len(lines):
        return max(one_based_column - 1, 0)
    prefix = lines[one_based_line - 1][: max(one_based_column - 1, 0)]
    return len(prefix.encode("utf-16-le")) // 2


def _codepoints_for_utf16(text: str, units: int) -> int:
    consumed = 0
    for index, character in enumerate(text):
        width = len(character.encode("utf-16-le")) // 2
        if consumed + width > units:
            return index
        consumed += width
        if consumed == units:
            return index + 1
    return len(text)


__all__ = (
    "SourceTextMap",
    "offset_position",
    "path_to_uri",
    "position_offset",
    "source_position",
    "span_to_range",
    "uri_to_path",
)
