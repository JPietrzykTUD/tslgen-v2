"""Discover source-owned helpers used by generated value tests."""

from __future__ import annotations

from tslc.catalog.model import Catalog
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import Diagnostic
from tslc.value_tests.model import HarnessPrimitiveNames


def discover_harness_primitives(catalog: Catalog) -> HarnessPrimitiveNames:
    """Discover value-test harness helpers from unique source signatures."""

    diagnostics: list[Diagnostic] = []
    from_array = _unique_primitive_name(catalog, ("v", ("s[]",)), diagnostics)
    to_array = _unique_primitive_name(catalog, ("s[]", ("v",)), diagnostics)
    to_integral = _unique_primitive_name(catalog, ("im", ("m",)), diagnostics)
    load = _unique_primitive_name(catalog, ("v", ("cptr",)), diagnostics)
    store = _unique_primitive_name(catalog, ("void", ("ptr", "v")), diagnostics)
    return HarnessPrimitiveNames(
        from_array=from_array,
        to_array=to_array,
        to_integral=to_integral,
        load=load,
        store=store,
        diagnostics=tuple(diagnostics),
    )


def _unique_primitive_name(
    catalog: Catalog,
    shape_key: tuple[str, tuple[str, ...]],
    diagnostics: list[Diagnostic],
) -> str | None:
    matches: list[str] = []
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        if shape is None:
            continue
        if (shape.result_kind, tuple(shape.param_kinds)) == shape_key:
            matches.append(primitive.name)
    unique = tuple(sorted(set(matches)))
    if len(unique) == 1:
        return unique[0]
    result, params = shape_key
    spelling = f"{result}:=({', '.join(params)})"
    if not unique:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="TSL-VALUE-TEST-HARNESS-MISSING",
                message=f"no unique value-test harness primitive has signature {spelling}",
            )
        )
    else:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="TSL-VALUE-TEST-HARNESS-AMBIGUOUS",
                message=(
                    f"value-test harness signature {spelling} is ambiguous: "
                    f"{', '.join(unique)}"
                ),
            )
        )
    return None


__all__ = ("discover_harness_primitives",)
