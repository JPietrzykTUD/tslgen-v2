"""Structured, ranged diagnostics shared across compiler and authoring tools."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

Severity = Literal["error", "warning", "info"]
DIAGNOSTIC_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A one-based source position used by compiler-facing APIs."""

    path: Path
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """A one-based, end-exclusive source range."""

    path: Path
    line: int
    column: int
    end_line: int
    end_column: int

    @property
    def start(self) -> SourceLocation:
        return SourceLocation(self.path, self.line, self.column)

    @classmethod
    def point(cls, location: SourceLocation) -> "SourceSpan":
        return cls(
            path=location.path,
            line=location.line,
            column=location.column,
            end_line=location.line,
            end_column=location.column + 1,
        )


@dataclass(frozen=True, slots=True)
class RelatedLocation:
    message: str
    span: SourceSpan


@dataclass(frozen=True, slots=True, init=False)
class Diagnostic:
    """A compiler diagnostic with one canonical full source span.

    ``location=`` remains accepted while compiler producers migrate. It is
    immediately promoted to a one-character span and is never stored as a
    second source of truth.
    """

    severity: Severity
    code: str
    message: str
    span: SourceSpan | None
    related: tuple[RelatedLocation, ...]
    help: str | None

    def __init__(
        self,
        severity: Severity,
        code: str,
        message: str,
        span: SourceSpan | None = None,
        related: tuple[RelatedLocation, ...] = (),
        help: str | None = None,
        *,
        location: SourceLocation | None = None,
    ) -> None:
        if span is not None and location is not None:
            raise ValueError("diagnostic accepts either span or location, not both")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(
            self,
            "span",
            span or (SourceSpan.point(location) if location is not None else None),
        )
        object.__setattr__(self, "related", related)
        object.__setattr__(self, "help", help)

    @property
    def location(self) -> SourceLocation | None:
        """Compatibility view for callers that only need the start point."""

        return None if self.span is None else self.span.start


def source_location(source: SourceSpan | None) -> SourceLocation | None:
    return source.start if source is not None else None


def diagnostic_at(
    *,
    severity: Severity,
    code: str,
    message: str,
    source: SourceSpan | None,
    related: tuple[RelatedLocation, ...] = (),
    help: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        span=source,
        related=related,
        help=help,
    )


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    return any(diagnostic.severity == "error" for diagnostic in diagnostics)


def sort_diagnostics(diagnostics: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    """Order diagnostics deterministically by range, code, and message."""

    def key(diagnostic: Diagnostic) -> tuple[str, int, int, int, int, str, str]:
        span = diagnostic.span
        if span is None:
            return ("", 0, 0, 0, 0, diagnostic.code, diagnostic.message)
        return (
            span.path.as_posix(),
            span.line,
            span.column,
            span.end_line,
            span.end_column,
            diagnostic.code,
            diagnostic.message,
        )

    return tuple(sorted(diagnostics, key=key))


def diagnostic_json(diagnostic: Diagnostic) -> dict[str, object]:
    """Serialize one diagnostic with zero-based LSP-compatible coordinates."""

    span = diagnostic.span
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "path": None if span is None else str(span.path),
        "range": None if span is None else span_json(span),
        "related": [
            {
                "message": item.message,
                "path": str(item.span.path),
                "range": span_json(item.span),
            }
            for item in diagnostic.related
        ],
        "help": diagnostic.help,
    }


def diagnostics_json(
    diagnostics: Iterable[Diagnostic],
    *,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the versioned public diagnostic document."""

    payload: dict[str, object] = {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "diagnostics": [diagnostic_json(item) for item in sort_diagnostics(diagnostics)],
    }
    if extra:
        payload.update(extra)
    return payload


def span_json(span: SourceSpan) -> dict[str, object]:
    return {
        "start": {"line": span.line - 1, "character": span.column - 1},
        "end": {"line": span.end_line - 1, "character": span.end_column - 1},
    }


def format_diagnostic(
    diagnostic: Diagnostic,
    *,
    source_text: str | None = None,
    code_frame: bool = False,
) -> str:
    """Render stable human-readable text with optional source framing."""

    span = diagnostic.span
    prefix = f"{diagnostic.severity}[{diagnostic.code}]"
    if span is not None:
        prefix = f"{span.path}:{span.line}:{span.column}: {prefix}"
    lines = [f"{prefix}: {diagnostic.message}"]
    if code_frame and source_text is not None and span is not None:
        lines.extend(_code_frame(source_text, span))
    for item in diagnostic.related:
        related_span = item.span
        lines.append(
            f"related: {related_span.path}:{related_span.line}:"
            f"{related_span.column}: {item.message}"
        )
    if diagnostic.help:
        lines.append(f"help: {diagnostic.help}")
    return "\n".join(lines)


def format_diagnostics_json(
    diagnostics: Iterable[Diagnostic],
    *,
    extra: Mapping[str, object] | None = None,
) -> str:
    return json.dumps(diagnostics_json(diagnostics, extra=extra), indent=2, sort_keys=True)


def format_diagnostics(diagnostics: Iterable[Diagnostic]) -> str:
    """Render a deterministic sequence through the canonical text formatter."""

    return "\n".join(format_diagnostic(item) for item in sort_diagnostics(diagnostics))


def _code_frame(source_text: str, span: SourceSpan) -> tuple[str, ...]:
    source_lines = source_text.splitlines()
    if span.line < 1 or span.line > len(source_lines):
        return ()
    source_line = source_lines[span.line - 1]
    number = str(span.line)
    start = max(span.column - 1, 0)
    width = (
        max(span.end_column - span.column, 1)
        if span.end_line == span.line
        else max(len(source_line) - start, 1)
    )
    return (
        f"  {number} | {source_line}",
        f"  {' ' * len(number)} | {' ' * start}{'^' * width}",
    )


__all__ = (
    "DIAGNOSTIC_SCHEMA_VERSION",
    "Diagnostic",
    "RelatedLocation",
    "Severity",
    "SourceLocation",
    "SourceSpan",
    "diagnostic_at",
    "diagnostic_json",
    "diagnostics_json",
    "format_diagnostic",
    "format_diagnostics",
    "format_diagnostics_json",
    "has_errors",
    "sort_diagnostics",
    "source_location",
    "span_json",
)
