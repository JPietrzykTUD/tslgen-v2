"""Structured diagnostics shared across the compiler."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: Path
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    location: SourceLocation | None = None


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    return any(diagnostic.severity == "error" for diagnostic in diagnostics)


def sort_diagnostics(diagnostics: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    """Order diagnostics deterministically by location then code."""

    def key(diagnostic: Diagnostic) -> tuple[str, int, int, str]:
        location = diagnostic.location
        if location is None:
            return ("", 0, 0, diagnostic.code)
        return (location.path.as_posix(), location.line, location.column, diagnostic.code)

    return tuple(sorted(diagnostics, key=key))
