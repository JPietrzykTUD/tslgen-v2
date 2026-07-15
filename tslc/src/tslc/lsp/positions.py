"""UTF-16/LSP and compiler source-position conversion."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from lsprotocol import types

from tslc.diagnostics import SourceSpan


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


def span_to_range(span: SourceSpan, text: str) -> types.Range:
    lines = text.splitlines(keepends=True)
    return types.Range(
        start=types.Position(
            line=max(span.line - 1, 0),
            character=_utf16_column(lines, span.line, span.column),
        ),
        end=types.Position(
            line=max(span.end_line - 1, 0),
            character=_utf16_column(lines, span.end_line, span.end_column),
        ),
    )


def _utf16_column(lines: list[str], one_based_line: int, one_based_column: int) -> int:
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
    "path_to_uri",
    "position_offset",
    "source_position",
    "span_to_range",
    "uri_to_path",
)
