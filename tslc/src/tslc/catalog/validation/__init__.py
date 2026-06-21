"""Catalog and parsed-source validation.

The builder promotes parsed source into immutable domain objects. This package
is the next boundary: it checks that the promoted catalog is coherent enough for
selection/lowering, while using the parsed tree for diagnostics that would be
lost after promotion (duplicates, unknown fields, malformed ``requires`` maps).
"""

from __future__ import annotations

from collections.abc import Iterable

from tslc.catalog.model import Catalog
from tslc.catalog.validation.invariants import (
    validate_backend_type_spellings,
    validate_extension_inheritance,
    validate_required_backends,
)
from tslc.catalog.validation.schema_validation import validate_parsed_documents
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.syntax.ast import OuterTslParseResult

__all__ = ("validate_catalog",)


def validate_catalog(
    catalog: Catalog,
    parsed: OuterTslParseResult | None = None,
    *,
    required_backends: Iterable[str] = ("cpp", "rust"),
) -> tuple[Diagnostic, ...]:
    """Validate parsed/catalog data and return structured diagnostics."""

    diagnostics: list[Diagnostic] = []
    backends = tuple(dict.fromkeys(required_backends))
    validate_required_backends(catalog, backends, diagnostics)
    validate_extension_inheritance(catalog, diagnostics, parsed)
    validate_backend_type_spellings(catalog, backends, diagnostics, parsed)
    if parsed is not None:
        validate_parsed_documents(parsed, diagnostics)
    return sort_diagnostics(diagnostics)
