"""Typed values produced by the isolated PIVOT export path."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.output.artifacts import ArtifactSet


@dataclass(frozen=True, slots=True)
class PivotDefinition:
    isa: str
    dtype: str
    signature: tuple[tuple[str, str], ...]
    direct: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PivotDocument:
    name: str
    inputs: tuple[str, ...]
    output: str
    definitions: tuple[PivotDefinition, ...]


@dataclass(frozen=True, slots=True)
class PivotSkip:
    profile: str
    primitive: str
    extension: str
    type_tag: str
    reason: str
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class PivotExportResult:
    artifacts: ArtifactSet
    documents: tuple[PivotDocument, ...]
    skipped: tuple[PivotSkip, ...]
    diagnostics: tuple[Diagnostic, ...]


__all__ = (
    "PivotDefinition",
    "PivotDocument",
    "PivotExportResult",
    "PivotSkip",
)
