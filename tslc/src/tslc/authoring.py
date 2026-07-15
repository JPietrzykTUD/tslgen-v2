"""Public, side-effect-free authoring checks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tslc._pipeline_inputs import load_catalog_inputs
from tslc.api import _expand_sources
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic, sort_diagnostics


@dataclass(frozen=True, slots=True)
class CatalogCheckResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]
    source_paths: tuple[Path, ...]


def check_catalog(
    source_paths: Iterable[Path | str],
    *,
    backends: Iterable[str] = registered_backend_ids(),
) -> CatalogCheckResult:
    """Validate a complete corpus without profiles, selection, or rendering."""

    expanded = _expand_sources(source_paths)
    inputs, diagnostics = load_catalog_inputs(
        expanded,
        required_backends=tuple(backends),
    )
    return CatalogCheckResult(
        catalog=None if inputs is None else inputs.catalog,
        diagnostics=sort_diagnostics(diagnostics),
        source_paths=expanded,
    )


__all__ = ("CatalogCheckResult", "check_catalog")
