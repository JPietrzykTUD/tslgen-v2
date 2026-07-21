"""Typed semantic-overload declarations promoted from source data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class OverloadValueSpec:
    """One overload value and the signature kinds accepted at its operand."""

    name: str
    operand_kinds: tuple[str, ...]
    source: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class OverloadAxisSpec:
    """One closed semantic-overload axis."""

    name: str
    values: Mapping[str, OverloadValueSpec] = field(default_factory=dict)
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            MappingProxyType(dict(sorted(self.values.items()))),
        )


@dataclass(frozen=True, slots=True)
class OverloadRegistry:
    """Source-owned semantic-overload axes and compatibility rules."""

    axes: Mapping[str, OverloadAxisSpec] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "axes",
            MappingProxyType(dict(sorted(self.axes.items()))),
        )

    def axis(self, name: str) -> OverloadAxisSpec | None:
        return self.axes.get(name)

    def value(self, axis: str, value: str) -> OverloadValueSpec | None:
        axis_spec = self.axis(axis)
        return None if axis_spec is None else axis_spec.values.get(value)

    def accepts_operand_kind(self, axis: str, value: str, kind: str) -> bool:
        value_spec = self.value(axis, value)
        return value_spec is not None and kind in value_spec.operand_kinds


__all__ = (
    "OverloadAxisSpec",
    "OverloadRegistry",
    "OverloadValueSpec",
)
