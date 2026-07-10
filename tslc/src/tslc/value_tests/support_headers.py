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
        for extension_name in (
            case.scalable.source_extension if case.scalable is not None else None,
            (
                case.representation.source_extension
                if case.representation is not None
                else None
            ),
            (
                case.representation.target_extension
                if case.representation is not None
                else None
            ),
            (
                case.differential.hardware_extension
                if case.differential is not None
                else None
            ),
        ):
            if extension_name is None:
                continue
            extension = catalog.extensions.get(extension_name)
            if extension is None:
                continue
            headers.update(extension.test_support_headers.get(backend_id, ()))
    return tuple(sorted(headers))


__all__ = ("support_headers_for_cases",)
