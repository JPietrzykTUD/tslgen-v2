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


class PivotDifferentialKind(str, Enum):
    DIRECT_MISMATCH = "direct_mismatch"
    LEGACY_ONLY_DEFINITION = "legacy_only_definition"
    STRUCTURED_ONLY_DEFINITION = "structured_only_definition"
    DOCUMENT_ORDER = "document_order"
    YAML_ARTIFACT = "yaml_artifact"
    SKIP_SOURCE_MISMATCH = "skip_source_mismatch"
    SKIP_REASON_MISMATCH = "skip_reason_mismatch"
    LEGACY_ONLY_SKIP = "legacy_only_skip"
    STRUCTURED_ONLY_SKIP = "structured_only_skip"


@dataclass(frozen=True, slots=True)
class PivotDifferentialDifference:
    kind: PivotDifferentialKind
    document: str | None
    detail: str
    legacy_definition: PivotDefinition | None = None
    structured_definition: PivotDefinition | None = None
    legacy_skip: PivotSkip | None = None
    structured_skip: PivotSkip | None = None


@dataclass(frozen=True, slots=True)
class PivotDifferentialReport:
    language: PivotLanguage
    structured_documents: tuple[PivotDocument, ...]
    structured_skipped: tuple[PivotSkip, ...]
    legacy_definition_count: int
    structured_definition_count: int
    exact_shared_definition_count: int
    direct_mismatch_count: int
    legacy_only_definition_count: int
    structured_only_definition_count: int
    exact_shared_skip_count: int
    skip_source_mismatch_count: int
    skip_reason_mismatch_count: int
    legacy_only_skip_count: int
    structured_only_skip_count: int
    document_order_equal: bool
    yaml_artifacts_equal: bool
    differences: tuple[PivotDifferentialDifference, ...]

    def __post_init__(self) -> None:
        counts = (
            self.legacy_definition_count,
            self.structured_definition_count,
            self.exact_shared_definition_count,
            self.direct_mismatch_count,
            self.legacy_only_definition_count,
            self.structured_only_definition_count,
            self.exact_shared_skip_count,
            self.skip_source_mismatch_count,
            self.skip_reason_mismatch_count,
            self.legacy_only_skip_count,
            self.structured_only_skip_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("PIVOT differential counts cannot be negative")
        if self.legacy_definition_count != (
            self.exact_shared_definition_count
            + self.direct_mismatch_count
            + self.legacy_only_definition_count
        ):
            raise ValueError(
                "PIVOT differential does not account for legacy definitions"
            )
        if self.structured_definition_count != (
            self.exact_shared_definition_count
            + self.direct_mismatch_count
            + self.structured_only_definition_count
        ):
            raise ValueError(
                "PIVOT differential does not account for structured definitions"
            )
        if len(self.structured_skipped) != (
            self.exact_shared_skip_count
            + self.skip_source_mismatch_count
            + self.skip_reason_mismatch_count
            + self.structured_only_skip_count
        ):
            raise ValueError("PIVOT differential does not account for structured skips")

    @property
    def shared_definitions_are_exact(self) -> bool:
        return self.direct_mismatch_count == 0


@dataclass(frozen=True, slots=True)
class PivotExportResult:
    artifacts: ArtifactSet
    projections: tuple[PivotProjection, ...]
    diagnostics: tuple[Diagnostic, ...]
    shadow_censuses: tuple[PivotShadowCensus, ...] = ()
    differentials: tuple[PivotDifferentialReport, ...] = ()

    @property
    def skipped(self) -> tuple[PivotSkip, ...]:
        return tuple(
            skip for projection in self.projections for skip in projection.skipped
        )


__all__ = (
    "PivotDefinition",
    "PivotDifferentialDifference",
    "PivotDifferentialKind",
    "PivotDifferentialReport",
    "PivotDocument",
    "PivotExportResult",
    "PivotLanguage",
    "PivotProjection",
    "PivotSkip",
)
