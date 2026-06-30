"""Typed value-test renderer capability declarations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from tslc.value_tests.model import (
    DEFAULT_VALUE_TEST_CASE_KINDS,
    ValueTestBackendSupport,
    ValueTestCasePlan,
)

ValueTestCaseRenderer = Callable[[ValueTestCasePlan], str]


@dataclass(frozen=True, slots=True)
class ValueTestRendererCapability:
    backend_id: str
    case_renderers: Mapping[str, ValueTestCaseRenderer]
    supports_differential: bool = False

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("value-test renderer capability requires backend_id")
        if not self.case_renderers:
            raise ValueError(
                f"value-test renderer capability {self.backend_id!r} "
                "requires at least one case renderer"
            )
        normalized = {
            kind: renderer
            for kind, renderer in sorted(self.case_renderers.items())
        }
        for kind in normalized:
            if not kind:
                raise ValueError(
                    f"value-test renderer capability {self.backend_id!r} "
                    "contains an empty case kind"
                )
        unknown_kinds = set(normalized) - DEFAULT_VALUE_TEST_CASE_KINDS
        if unknown_kinds:
            names = ", ".join(repr(kind) for kind in sorted(unknown_kinds))
            raise ValueError(
                f"value-test renderer capability {self.backend_id!r} "
                f"uses unregistered case kind(s) {names}"
            )
        object.__setattr__(
            self,
            "case_renderers",
            MappingProxyType(normalized),
        )

    @property
    def case_kinds(self) -> frozenset[str]:
        return frozenset(self.case_renderers)

    def backend_support(self) -> ValueTestBackendSupport:
        return ValueTestBackendSupport(
            backend_id=self.backend_id,
            case_kinds=self.case_kinds,
            supports_differential=self.supports_differential,
        )

    def render_case(self, case: ValueTestCasePlan) -> str:
        renderer = self.case_renderers.get(case.kind)
        if renderer is None:
            raise ValueError(
                f"unsupported {self.backend_id} value-test case kind {case.kind!r}"
            )
        return renderer(case)


__all__ = ["ValueTestCaseRenderer", "ValueTestRendererCapability"]
