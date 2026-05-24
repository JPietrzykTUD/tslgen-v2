"""Backend protocol and result values."""

from dataclasses import dataclass
from typing import Protocol

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact


@dataclass(frozen=True, slots=True)
class BackendEmitResult:
    artifact: Artifact | None
    diagnostics: tuple[Diagnostic, ...]


class Backend(Protocol):
    backend_id: str

    def emit(self, selected: SelectedImplementation) -> BackendEmitResult:
        """Emit an artifact for a selected implementation."""
