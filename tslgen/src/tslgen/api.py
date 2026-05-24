"""Public API helpers for the clean restart slice."""

from collections.abc import Iterable
from pathlib import Path

from tslgen.analysis.selection import Target
from tslgen.pipeline.generator import GenerationResult, Generator, TslProject


def generate_from_paths(
    source_paths: Iterable[Path | str],
    targets: Iterable[Target],
) -> GenerationResult:
    """Load explicit TSL source paths and generate in-memory artifacts."""

    project = TslProject(
        source_paths=tuple(Path(path) for path in source_paths),
        targets=tuple(targets),
    )
    return Generator().generate(project)
