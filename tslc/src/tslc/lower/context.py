"""Mutable lowering context threaded through region and query handlers.

Holds the selected extension/type and the backend translation facts, plus the
two side channels handlers need: a diagnostics sink and the "this body needs
``unsafe``" flag. Keeping this in one object means handlers stay pure-ish
strategy classes that read context and append diagnostics, rather than each
carrying their own bespoke state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Extension
from tslc.diagnostics import Diagnostic


@dataclass(slots=True)
class LoweringContext:
    extension: Extension
    type_tag: str
    translation: BackendTranslation
    diagnostics: list[Diagnostic] = field(default_factory=list)
    requires_unsafe: bool = False

    def error(self, code: str, message: str) -> None:
        self.diagnostics.append(Diagnostic(severity="error", code=code, message=message))

    def mark_unsafe(self) -> None:
        self.requires_unsafe = True

    @property
    def has_errors(self) -> bool:
        return any(diagnostic.severity == "error" for diagnostic in self.diagnostics)
