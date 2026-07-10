"""Catalog and parsed-source validation.

The builder promotes parsed source into immutable domain objects. This package
is the next boundary: it checks that the promoted catalog is coherent enough for
selection/lowering, while using the parsed tree for diagnostics that would be
lost after promotion (duplicates, unknown fields, malformed ``requires`` maps).
"""

from __future__ import annotations

from collections.abc import Iterable

from tslc.catalog.model import Catalog
from tslc.catalog.validation.body_validation import validate_body_regions
from tslc.catalog.validation.invariants import (
    validate_backend_type_spellings,
    validate_extension_inheritance,
    validate_generic_param_base_constraints,
    validate_primitive_signatures,
    validate_required_backends,
    validate_scalable_runtime_lane_counts,
)
from tslc.catalog.validation.schema_validation import validate_parsed_documents
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.syntax.ast import OuterTslParseResult

__all__ = ("validate_catalog",)


def validate_catalog(
    catalog: Catalog,
    parsed: OuterTslParseResult | None = None,
    *,
    required_backends: Iterable[str] | None = None,
    supported_backends: Iterable[str] | None = None,
) -> tuple[Diagnostic, ...]:
    """Validate parsed/catalog data and return structured diagnostics."""

    diagnostics: list[Diagnostic] = []
    backends = tuple(
        dict.fromkeys(
            sorted(catalog.type_spellings)
            if required_backends is None
            else required_backends
        )
    )
    supported = tuple(
        dict.fromkeys(backends if supported_backends is None else supported_backends)
    )
    validate_required_backends(catalog, backends, supported, diagnostics)
    validate_primitive_signatures(catalog, diagnostics)
    validate_generic_param_base_constraints(catalog, diagnostics)
    validate_extension_inheritance(catalog, diagnostics, parsed)
    validate_backend_type_spellings(
        catalog,
        backends,
        supported,
        diagnostics,
        parsed,
    )
    validate_scalable_runtime_lane_counts(catalog, backends, diagnostics, parsed)
    if parsed is not None:
        validate_parsed_documents(parsed, diagnostics, catalog.target_families)
        validate_body_regions(parsed, diagnostics)
    return sort_diagnostics(diagnostics)
