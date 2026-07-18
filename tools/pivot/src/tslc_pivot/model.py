"""Typed values produced by the isolated PIVOT export path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.output.artifacts import ArtifactSet

if TYPE_CHECKING:
    from tslc_pivot.body_ir import PivotShadowCensus


class PivotLanguage(str, Enum):
    CPP = "cpp"
    RUST = "rust"


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
    language: PivotLanguage
    profile: str
    primitive: str
    extension: str
    type_tag: str
    reason: str
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class PivotProjection:
    language: PivotLanguage
    documents: tuple[PivotDocument, ...]
    skipped: tuple[PivotSkip, ...]


@dataclass(frozen=True, slots=True)
class PivotExportResult:
    artifacts: ArtifactSet
    projections: tuple[PivotProjection, ...]
    diagnostics: tuple[Diagnostic, ...]
    shadow_censuses: tuple[PivotShadowCensus, ...] = ()

    @property
    def skipped(self) -> tuple[PivotSkip, ...]:
        return tuple(
            skip for projection in self.projections for skip in projection.skipped
        )


__all__ = (
    "PivotDefinition",
    "PivotDocument",
    "PivotExportResult",
    "PivotLanguage",
    "PivotProjection",
    "PivotSkip",
)
