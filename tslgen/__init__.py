"""Repo-root import shim for the clean restart package.

The implementation package lives in ``tslgen/src/tslgen``. This shim keeps
uninstalled repo-root validation imports pointed at that package surface
without adding generator behavior outside ``src``.
"""

from pathlib import Path

_SOURCE_PACKAGE = Path(__file__).resolve().parent / "src" / "tslgen"
__path__ = [str(_SOURCE_PACKAGE)]

from .api import generate_from_paths, write_artifacts
from .analysis.selection import Target
from .core.diagnostics import Diagnostic, SourceLocation
from .io.artifact_writer import (
    ArtifactWriteRecord,
    ArtifactWriteReport,
    ArtifactWriter,
)
from .io.artifacts import Artifact, ArtifactSet
from .pipeline.generator import GenerationResult, Generator, TslProject

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
