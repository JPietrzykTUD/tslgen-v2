from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics


T = TypeVar("T")
U = TypeVar("U")


class ResultError(RuntimeError):
    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        super().__init__("cannot unwrap a result with error diagnostics")
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    value: T | None
    diagnostics: tuple[Diagnostic, ...] = ()
    _has_value: bool = True

    def __post_init__(self) -> None:
        ordered = sort_diagnostics(tuple(self.diagnostics))
        object.__setattr__(self, "diagnostics", ordered)
        if not self._has_value and not has_errors(ordered):
            raise ValueError("failed results require at least one error diagnostic")
        if self._has_value and has_errors(ordered):
            raise ValueError("successful results cannot contain error diagnostics")

    @classmethod
    def ok(
        cls,
        value: T,
        diagnostics: Iterable[Diagnostic] = (),
    ) -> Result[T]:
        return cls(value=value, diagnostics=tuple(diagnostics), _has_value=True)

    @classmethod
    def failure(cls, diagnostics: Iterable[Diagnostic]) -> Result[T]:
        return cls(value=None, diagnostics=tuple(diagnostics), _has_value=False)

    @property
    def is_ok(self) -> bool:
        return self._has_value and not has_errors(self.diagnostics)

    @property
    def is_error(self) -> bool:
        return has_errors(self.diagnostics)

    @property
    def has_value(self) -> bool:
        return self._has_value

    def unwrap(self) -> T:
        if not self.is_ok:
            raise ResultError(self.diagnostics)
        return cast(T, self.value)

    def value_or(self, default: T) -> T:
        if self.is_ok:
            return cast(T, self.value)
        return default

    def map(self, transform: Callable[[T], U]) -> Result[U]:
        if not self.is_ok:
            return Result.failure(self.diagnostics)
        return Result.ok(transform(cast(T, self.value)), diagnostics=self.diagnostics)
