"""Shared catalog loading for repository maintenance projections."""

from __future__ import annotations

from tslc._pipeline_inputs import load_catalog_inputs
from tslc.catalog.model import Catalog
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.maintenance._repo_context import RepoContext
from tslc.sources import expand_source_paths


def load_repository_catalog(context: RepoContext, *, purpose: str) -> Catalog:
    """Load the repository corpus with both release backends required."""

    catalog_inputs, diagnostics = load_catalog_inputs(
        expand_source_paths((context.data_root,)),
        required_backends=("cpp", "rust"),
    )
    if catalog_inputs is None or has_errors(diagnostics):
        rendered = "\n".join(format_diagnostic(item) for item in diagnostics)
        raise RuntimeError(f"cannot build {purpose} catalog:\n{rendered}")
    return catalog_inputs.catalog


__all__ = ("load_repository_catalog",)
