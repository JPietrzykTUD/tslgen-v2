from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


DiagnosticSeverity = Literal["error", "warning", "info"]
SEVERITIES: tuple[DiagnosticSeverity, ...] = ("error", "warning", "info")


def severity_rank(severity: DiagnosticSeverity) -> int:
    return SEVERITIES.index(severity)


@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: Path
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        if self.line < 1:
            raise ValueError("source line must be one-based")
        if self.column < 1:
            raise ValueError("source column must be one-based")
        if self.end_line is not None and self.end_line < self.line:
            raise ValueError("source end_line must not precede line")
        if self.end_column is not None and self.end_column < 1:
            raise ValueError("source end_column must be one-based when present")
        if (
            self.end_line is not None
            and self.end_column is not None
            and self.end_line == self.line
            and self.end_column < self.column
        ):
            raise ValueError("source end_column must not precede column")

    def sort_key(self) -> tuple[object, ...]:
        end_line = self.end_line if self.end_line is not None else self.line
        end_column = self.end_column if self.end_column is not None else self.column
        return (self.path.as_posix(), self.line, self.column, end_line, end_column)


@dataclass(frozen=True, slots=True)
class SourceSpan:
    location: SourceLocation
    text: str | None = None


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    location: SourceLocation | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("diagnostic code must be non-empty")
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown diagnostic severity: {self.severity!r}")
        if not self.message:
            raise ValueError("diagnostic message must be non-empty")
        object.__setattr__(self, "notes", tuple(self.notes))

    @classmethod
    def error(
        cls,
        code: str,
        message: str,
        *,
        location: SourceLocation | None = None,
        notes: tuple[str, ...] = (),
    ) -> Diagnostic:
        return cls(
            code=code,
            severity="error",
            message=message,
            location=location,
            notes=notes,
        )

    @classmethod
    def warning(
        cls,
        code: str,
        message: str,
        *,
        location: SourceLocation | None = None,
        notes: tuple[str, ...] = (),
    ) -> Diagnostic:
        return cls(
            code=code,
            severity="warning",
            message=message,
            location=location,
            notes=notes,
        )

    @classmethod
    def info(
        cls,
        code: str,
        message: str,
        *,
        location: SourceLocation | None = None,
        notes: tuple[str, ...] = (),
    ) -> Diagnostic:
        return cls(code=code, severity="info", message=message, location=location, notes=notes)

    def sort_key(self) -> tuple[object, ...]:
        location_key: tuple[object, ...]
        if self.location is None:
            location_key = (1, "", 0, 0, 0, 0)
        else:
            location_key = (0, *self.location.sort_key())
        return (
            location_key,
            severity_rank(self.severity),
            self.code,
            self.message,
            self.notes,
        )

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


def diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[object, ...]:
    return diagnostic.sort_key()


def sort_diagnostics(diagnostics: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=diagnostic_sort_key))


def has_errors(diagnostics: Iterable[Diagnostic]) -> bool:
    return any(diagnostic.is_error for diagnostic in diagnostics)
