"""Filesystem and artifact boundaries for the clean restart generator."""

from tslgen.io.artifact_writer import (
    ArtifactRemovalRecord,
    ArtifactWriteRecord,
    ArtifactWriteReport,
    ArtifactWriter,
    manifest_logical_path,
    write_artifacts,
)
from tslgen.io.artifacts import Artifact, ArtifactMetadata, ArtifactSet
from tslgen.io.sources import SourceDocument, SourceLoader, SourceLoadResult

__all__ = [
    "Artifact",
    "ArtifactMetadata",
    "ArtifactRemovalRecord",
    "ArtifactSet",
    "ArtifactWriteRecord",
    "ArtifactWriteReport",
    "ArtifactWriter",
    "SourceDocument",
    "SourceLoadResult",
    "SourceLoader",
    "manifest_logical_path",
    "write_artifacts",
]
