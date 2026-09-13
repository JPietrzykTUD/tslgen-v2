"""Typed configuration for complete generated-project rendering."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeVar


class BackendRenderInput:
    """One backend-owned typed input used only while rendering its project."""

    __slots__ = ()


_BackendRenderInputT = TypeVar(
    "_BackendRenderInputT", bound=BackendRenderInput
)


@dataclass(frozen=True, slots=True)
class ProjectRenderConfig:
    """Frozen backend-keyed render inputs for one generation request."""

    values: Mapping[str, BackendRenderInput] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(
            not isinstance(backend_id, str) or not backend_id
            for backend_id in self.values
        ):
            raise ValueError("backend render inputs require non-empty backend IDs")
        invalid_values = tuple(
            sorted(
                backend_id
                for backend_id, value in self.values.items()
                if not isinstance(value, BackendRenderInput)
            )
        )
        if invalid_values:
            raise TypeError(
                "backend render inputs require typed values for: "
                + ", ".join(invalid_values)
            )
        object.__setattr__(
            self,
            "values",
            MappingProxyType(dict(sorted(self.values.items()))),
        )

    @classmethod
    def create(
        cls, entries: Iterable[tuple[str, BackendRenderInput]]
    ) -> "ProjectRenderConfig":
        values: dict[str, BackendRenderInput] = {}
        for backend_id, value in entries:
            if backend_id in values:
                raise ValueError(
                    f"duplicate backend render input {backend_id!r}"
                )
            values[backend_id] = value
        return cls(values)

    def get(
        self,
        backend_id: str,
        expected_type: type[_BackendRenderInputT],
    ) -> _BackendRenderInputT | None:
        value = self.values.get(backend_id)
        if value is None:
            return None
        if not isinstance(value, expected_type):
            raise TypeError(
                f"backend {backend_id!r} render input must be "
                f"{expected_type.__name__}, got {type(value).__name__}"
            )
        return value

    def require(
        self,
        backend_id: str,
        expected_type: type[_BackendRenderInputT],
    ) -> _BackendRenderInputT:
        value = self.get(backend_id, expected_type)
        if value is None:
            raise ValueError(
                f"backend {backend_id!r} requires a "
                f"{expected_type.__name__} render input"
            )
        return value


DEFAULT_PROJECT_RENDER_CONFIG = ProjectRenderConfig()
BackendRenderInputs = ProjectRenderConfig


__all__ = (
    "BackendRenderInput",
    "BackendRenderInputs",
    "DEFAULT_PROJECT_RENDER_CONFIG",
    "ProjectRenderConfig",
)
