"""Clean restart package surface for the TSL generator."""

from tslgen.api import generate_from_paths, write_artifacts
from tslgen.analysis.selection import Target
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.io.artifact_writer import (
    ArtifactWriteRecord,
    ArtifactWriteReport,
    ArtifactWriter,
)
from tslgen.io.artifacts import Artifact, ArtifactSet
from tslgen.pipeline.generator import GenerationResult, Generator, TslProject

__all__ = [
    "Artifact",
    "ArtifactSet",
    "ArtifactWriteRecord",
    "ArtifactWriteReport",
    "ArtifactWriter",
    "Diagnostic",
    "GenerationResult",
    "Generator",
    "SourceLocation",
    "Target",
    "TslProject",
    "generate_from_paths",
    "write_artifacts",
]
