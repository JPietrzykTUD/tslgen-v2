"""Shared protocols and base classes for value-test patterns."""

from __future__ import annotations

from typing import Protocol

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
)

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

    def plan_case(
        self,
        *,
        backend: ValueTestBackendSupport,
        emitted_name: str,
        index: int,
        case: TestCase,
        specs: tuple[LoweredSpecialization, ...],
        catalog: Catalog,
        harness: HarnessPrimitiveNames,
    ) -> tuple[ValueTestCasePlan, ...]:
        ...

class _BasePattern:
    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        return catalog.primitive(source_name, unmasked=True)

__all__ = (
    "CasePlanBuilder",
    "PointerLayoutCasePlanBuilder",
    "ValueTestPattern",
    "_BasePattern",
)
