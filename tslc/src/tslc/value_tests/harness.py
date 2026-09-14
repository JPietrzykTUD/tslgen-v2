"""Discover source-owned helpers used by generated value tests."""

from __future__ import annotations

from dataclasses import replace

from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.semantics import (
    CONTIGUOUS_VECTOR_LOAD_REQUIREMENT,
    CONTIGUOUS_VECTOR_STORE_REQUIREMENT,
    MASK_FROM_INTEGRAL_REQUIREMENT,
    MASK_TO_INTEGRAL_REQUIREMENT,
    VECTOR_FROM_ARRAY_REQUIREMENT,
    VECTOR_TO_ARRAY_REQUIREMENT,
    PrimitiveProviderRequirement,
)
from tslc.diagnostics import Diagnostic, Severity
from tslc.value_tests.model import HarnessPrimitiveNames


def discover_harness_primitives(catalog: Catalog) -> HarnessPrimitiveNames:
    """Resolve value-test harness helpers from source-owned semantic facts."""

    diagnostics: list[Diagnostic] = []
    from_array = _provider_name(
        catalog, VECTOR_FROM_ARRAY_REQUIREMENT, diagnostics
    )
    to_array = _provider_name(catalog, VECTOR_TO_ARRAY_REQUIREMENT, diagnostics)
    to_integral = _provider_name(
        catalog, MASK_TO_INTEGRAL_REQUIREMENT, diagnostics
    )
    to_mask = _provider_name(
        catalog, MASK_FROM_INTEGRAL_REQUIREMENT, diagnostics
    )
    load = _provider_name(
        catalog, CONTIGUOUS_VECTOR_LOAD_REQUIREMENT, diagnostics
    )
    store = _provider_name(
        catalog, CONTIGUOUS_VECTOR_STORE_REQUIREMENT, diagnostics
    )
    return HarnessPrimitiveNames(
        from_array=from_array,
        to_array=to_array,
        to_integral=to_integral,
        to_mask=to_mask,
        load=load,
        store=store,
        diagnostics=tuple(diagnostics),
    )


def _provider_name(
    catalog: Catalog,
    requirement: PrimitiveProviderRequirement,
    diagnostics: list[Diagnostic],
) -> str | None:
    result = catalog.resolve_primitive_provider(requirement)
    if isinstance(result, Primitive):
        return result.name
    severity: Severity
    if result.code == "TSL-CATALOG-MISSING-PRIMITIVE-PROVIDER":
        severity = "warning"
        code = "TSL-VALUE-TEST-HARNESS-MISSING"
    elif result.code == "TSL-CATALOG-AMBIGUOUS-PRIMITIVE-PROVIDER":
        severity = "error"
        code = "TSL-VALUE-TEST-HARNESS-AMBIGUOUS"
    else:
        raise ValueError(
            f"unsupported primitive-provider diagnostic {result.code!r}"
        )
    diagnostics.append(
        replace(
            result,
            severity=severity,
            code=code,
            message=f"value-test harness {result.message}",
        )
    )
    return None


__all__ = ("discover_harness_primitives",)
