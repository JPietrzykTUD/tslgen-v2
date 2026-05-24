"""Filesystem and artifact boundaries for the clean restart generator."""

from tslgen.io.artifact_writer import (
    ArtifactWriteRecord,
    ArtifactWriteReport,
    ArtifactWriter,
    write_artifacts,
)
from tslgen.io.artifacts import Artifact, ArtifactMetadata, ArtifactSet
from tslgen.io.sources import SourceDocument, SourceLoader, SourceLoadResult

__all__ = [
    "Artifact",
    "ArtifactMetadata",
    "ArtifactSet",
    "ArtifactWriteRecord",
    "ArtifactWriteReport",
    "ArtifactWriter",
    "SourceDocument",
    "SourceLoadResult",
    "SourceLoader",
    "write_artifacts",
]
