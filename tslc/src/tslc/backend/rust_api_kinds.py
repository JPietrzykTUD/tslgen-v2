"""Shared enum vocabulary for the finalized ordinary Rust facade."""

from __future__ import annotations

from enum import StrEnum


class RustFacadeReceiverKind(StrEnum):
    VECTOR = "vector"
    MASK = "mask"
    FREE = "free"


class RustFacadeTraitRhsKind(StrEnum):
    SAME_TYPE = "same_type"
    SCALAR = "scalar"


class RustFacadeParameterPlacement(StrEnum):
    RECEIVER = "receiver"
    ARGUMENT = "argument"
    CONST_GENERIC = "const_generic"


class RustFacadeTypeParameterRole(StrEnum):
    RESULT_ELEMENT = "result_element"


class RustFacadeConstParameterSource(StrEnum):
    ATTRIBUTE = "attribute"
    IMMEDIATE = "immediate"
    GENERIC = "generic"


class RustFacadeCoverageStatus(StrEnum):
    ADMITTED = "admitted"
    EXCLUDED = "excluded"


class RustCuratedMethodKind(StrEnum):
    NUMERIC_CAST = "numeric_cast"
    COMPARISON = "comparison"
    SELECTION = "selection"


class RustFacadeBitConversionDirection(StrEnum):
    TO_BITS = "to_bits"
    FROM_BITS = "from_bits"


__all__ = (
    "RustCuratedMethodKind",
    "RustFacadeBitConversionDirection",
    "RustFacadeConstParameterSource",
    "RustFacadeCoverageStatus",
    "RustFacadeParameterPlacement",
    "RustFacadeReceiverKind",
    "RustFacadeTraitRhsKind",
    "RustFacadeTypeParameterRole",
)
