"""Shared protocols and base classes for value-test patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
)


@dataclass(frozen=True, slots=True)
class ValueTestCaseContext:
    backend: ValueTestBackendSupport
    emitted_name: str
    index: int
    case: TestCase
    specs: tuple[LoweredSpecialization, ...]
    catalog: Catalog
    harness: HarnessPrimitiveNames


@dataclass(frozen=True, slots=True)
class ValueTestFuzzContext:
    backend: ValueTestBackendSupport
    emitted_name: str
    specs: tuple[LoweredSpecialization, ...]
    catalog: Catalog
    harness: HarnessPrimitiveNames
    iterations: int


class CasePlanBuilder(Protocol):
    def __call__(
        self,
        name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
    ) -> ValueTestCasePlan | None:
        ...


class PointerLayoutCasePlanBuilder(Protocol):
    def __call__(
        self,
        name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
        primitive: Primitive,
    ) -> ValueTestCasePlan | None:
        ...


class ValueTestPattern(Protocol):
    """A typed test-shape planner."""

    def matches(self, specs: tuple[LoweredSpecialization, ...]) -> bool:
        ...

    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        ...

    def plan_case(self, context: ValueTestCaseContext) -> tuple[ValueTestCasePlan, ...]:
        ...


class _BasePattern:
    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        return catalog.primitive(source_name, unmasked=True)

    def unplanned_reason(self, context: ValueTestCaseContext) -> str | None:
        del context
        return None


def unplanned_case_reason(
    pattern: ValueTestPattern | None,
    planned: tuple[ValueTestCasePlan, ...],
    context: ValueTestCaseContext,
) -> str | None:
    if pattern is None or planned:
        return None
    reason_builder = getattr(pattern, "unplanned_reason", None)
    return reason_builder(context) if reason_builder is not None else None


__all__ = (
    "CasePlanBuilder",
    "PointerLayoutCasePlanBuilder",
    "ValueTestCaseContext",
    "ValueTestFuzzContext",
    "ValueTestPattern",
    "_BasePattern",
    "unplanned_case_reason",
)
