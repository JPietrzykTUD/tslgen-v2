"""Typed lane-count values shared by lowering and backend dialects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LaneCount:
    """A fixed count or a scaled symbolic count before backend spelling."""

    value: int | None = None
    symbol: str | None = None
    multiplier: int = 1
    divisor: int = 1

    def __post_init__(self) -> None:
        if (self.value is None) == (self.symbol is None):
            raise ValueError("lane count requires exactly one fixed value or symbol")
        if self.value is not None:
            if self.value <= 0:
                raise ValueError("fixed lane count must be positive")
            if self.multiplier != 1 or self.divisor != 1:
                raise ValueError("fixed lane count cannot carry a symbolic scale")
            return
        if not self.symbol:
            raise ValueError("symbolic lane count requires a non-empty name")
        if self.multiplier <= 0 or self.divisor <= 0:
            raise ValueError("symbolic lane-count scale must be positive")

    @classmethod
    def fixed(cls, value: int) -> LaneCount:
        return cls(value=value)

    @classmethod
    def symbolic(
        cls,
        symbol: str,
        *,
        multiplier: int = 1,
        divisor: int = 1,
    ) -> LaneCount:
        return cls(symbol=symbol, multiplier=multiplier, divisor=divisor)

    def is_plain_symbol(self, symbol: str) -> bool:
        return (
            self.symbol == symbol
            and self.multiplier == 1
            and self.divisor == 1
        )

    @property
    def is_scaled(self) -> bool:
        return self.multiplier != 1 or self.divisor != 1


__all__ = ["LaneCount"]
