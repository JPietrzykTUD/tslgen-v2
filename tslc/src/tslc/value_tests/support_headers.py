"""Profile-specific C++ value-test support headers."""

from __future__ import annotations

from tslc.catalog.model import Catalog
from tslc.value_tests.model import ValueTestCasePlan


def support_headers_for_cases(
    cases: list[ValueTestCasePlan],
    catalog: Catalog,
    backend_id: str,
) -> tuple[str, ...]:
    headers: set[str] = set()
    for case in cases:
        if case.source_extension is None:
            continue
        extension = catalog.extensions.get(case.source_extension)
        if extension is None:
            continue
        headers.update(extension.test_support_headers.get(backend_id, ()))
    return tuple(sorted(headers))


__all__ = ("support_headers_for_cases",)
