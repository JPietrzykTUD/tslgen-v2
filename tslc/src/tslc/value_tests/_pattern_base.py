"""Shared protocols and base classes for value-test patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.catalog.signatures import parse_signature
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
    primitive: Primitive


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

    def unplanned_reason(self, context: ValueTestCaseContext) -> str | None:
        """An actionable reason when this pattern matched but planned nothing."""
        ...

    def fuzz_cases(self, context: ValueTestFuzzContext) -> tuple[ValueTestCasePlan, ...]:
        """Synthetic random-input cases independent of authored tests."""
        ...


class _BasePattern:
    def source_primitive(
        self,
        catalog: Catalog,
        source_name: str,
        spec: LoweredSpecialization,
    ) -> Primitive | None:
        for primitive in catalog.primitives_named(source_name, unmasked=True):
            shape = parse_signature(primitive.signature)
            if shape is None:
                continue
            if (
                shape.result_kind == spec.result_kind
                and shape.param_kinds == spec.param_kinds
            ):
                return primitive
        return None

    def unplanned_reason(self, context: ValueTestCaseContext) -> str | None:
        del context
        return None

    def fuzz_cases(self, context: ValueTestFuzzContext) -> tuple[ValueTestCasePlan, ...]:
        del context
        return ()


def unplanned_case_reason(
    pattern: ValueTestPattern | None,
    planned: tuple[ValueTestCasePlan, ...],
    context: ValueTestCaseContext,
) -> str | None:
    if pattern is None or planned:
        return None
    return pattern.unplanned_reason(context)


__all__ = (
    "CasePlanBuilder",
    "PointerLayoutCasePlanBuilder",
    "ValueTestCaseContext",
    "ValueTestFuzzContext",
    "ValueTestPattern",
    "_BasePattern",
    "unplanned_case_reason",
)
