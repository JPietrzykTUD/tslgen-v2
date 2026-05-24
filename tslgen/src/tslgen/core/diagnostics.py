"""Structured diagnostics for the clean restart slice."""

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
