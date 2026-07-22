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
    overload_inference_placeholders: int = 0
    isolated_case_kinds: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("value-test renderer capability requires backend_id")
        if not self.case_renderers:
            raise ValueError(
                f"value-test renderer capability {self.backend_id!r} "
                "requires at least one case renderer"
            )
        if self.overload_inference_placeholders < 0:
            raise ValueError(
                "value-test overload inference placeholders must be non-negative"
            )
        normalized = {
            kind: renderer
            for kind, renderer in sorted(self.case_renderers.items())
        }
        isolated = frozenset(self.isolated_case_kinds)
        if not all(isolated):
            raise ValueError(
                f"value-test renderer capability {self.backend_id!r} "
                "contains an empty isolated case kind"
            )
        overlap = set(normalized) & isolated
        if overlap:
            names = ", ".join(repr(kind) for kind in sorted(overlap))
            raise ValueError(
                f"value-test renderer capability {self.backend_id!r} declares "
                f"case kind(s) as both runner and isolated: {names}"
            )
        for kind in normalized:
            if not kind:
                raise ValueError(
                    f"value-test renderer capability {self.backend_id!r} "
                    "contains an empty case kind"
                )
        unknown_kinds = (
            set(normalized) | set(isolated)
        ) - DEFAULT_VALUE_TEST_CASE_KINDS
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
        object.__setattr__(self, "isolated_case_kinds", isolated)

    @property
    def case_kinds(self) -> frozenset[str]:
        return frozenset(self.case_renderers) | self.isolated_case_kinds

    def backend_support(self) -> ValueTestBackendSupport:
        return ValueTestBackendSupport(
            backend_id=self.backend_id,
            case_kinds=self.case_kinds,
            supports_differential=self.supports_differential,
            overload_inference_placeholders=self.overload_inference_placeholders,
        )

    def render_case(self, case: ValueTestCasePlan) -> str:
        renderer = self.case_renderers.get(case.kind)
        if renderer is None:
            raise ValueError(
                f"unsupported {self.backend_id} value-test case kind {case.kind!r}"
            )
        return renderer(case)


__all__ = ["ValueTestCaseRenderer", "ValueTestRendererCapability"]
