"""Shared helpers for value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import (
    base_spelling as _base_spelling,
    effective_lanes as _effective_lanes,
)


def ordinary_base_spelling(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> str | None:
    if _effective_lanes(case) is None:
        return None
    return _base_spelling(specs, case.type_tag)


__all__ = ("ordinary_base_spelling",)
