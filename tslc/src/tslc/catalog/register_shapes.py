"""Typed register multiplicity for concrete scalable conversions.

The ordinary TSL vector model names one target register.  A lane-preserving
conversion between differently sized scalar types can require a fractional
register or a small register group on a scalable ISA.  This module represents
that narrow fact without turning TSIL into a target-language type AST.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd


# Source syntax permits any canonical xN/dN value with N greater than one.
# These are the practical SIMD register groups/fractions worth suggesting to
# authors today.
REGISTER_MULTIPLICITY_COMPLETIONS = (
    "d8",
    "d4",
    "d2",
    "x2",
    "x3",
    "x4",
    "x8",
)


@dataclass(frozen=True, slots=True, order=True)
class RegisterMultiplicity:
    """Physical target-register capacity relative to one natural register."""

    numerator: int = 1
    denominator: int = 1

    def __post_init__(self) -> None:
        if self.numerator <= 0 or self.denominator <= 0:
            raise ValueError("register multiplicity terms must be positive")
        common = gcd(self.numerator, self.denominator)
        numerator = self.numerator // common
        denominator = self.denominator // common
        if numerator != 1 and denominator != 1:
            raise ValueError("register multiplicity must be a group or fraction")
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)

    @classmethod
    def parse(cls, text: str) -> RegisterMultiplicity | None:
        """Parse source keys ``xN`` (groups) and ``dN`` (fractions)."""

        if len(text) < 2 or not text[1:].isdigit():
            return None
        value = int(text[1:])
        if value <= 0 or text[1:] != str(value):
            return None
        if text[0] == "x":
            return cls(value, 1)
        if text[0] == "d":
            return cls(1, value)
        return None

    @property
    def source_token(self) -> str:
        if self.denominator == 1:
            return f"x{self.numerator}"
        if self.numerator == 1:
            return f"d{self.denominator}"
        raise AssertionError("noncanonical register multiplicity")

    @property
    def is_single(self) -> bool:
        return self.numerator == self.denominator


__all__ = ("REGISTER_MULTIPLICITY_COMPLETIONS", "RegisterMultiplicity")
