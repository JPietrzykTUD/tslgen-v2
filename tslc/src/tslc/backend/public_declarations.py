"""Small shared vocabulary for backend-owned public declaration records."""

from __future__ import annotations

from enum import StrEnum


class PublicDeclarationStability(StrEnum):
    """Compatibility treatment of one emitted declaration."""

    STABLE = "stable"
    UNSTABLE = "unstable"
    IMPLEMENTATION_DETAIL = "implementation_detail"


class PublicDeclarationKind(StrEnum):
    """Language-neutral item categories used only by manifest tooling."""

    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    FIELD = "field"
    TYPE = "type"
    TYPE_ALIAS = "type_alias"
    TRAIT = "trait"
    CONSTANT = "constant"
    MODULE = "module"
    MACRO = "macro"
    REEXPORT = "reexport"
    OVERLOAD_SET = "overload_set"


class PublicDeclarationClassificationScope(StrEnum):
    """Whether a record is exact or defaults otherwise-unrecorded descendants."""

    EXACT = "exact"
    DESCENDANTS = "descendants"


__all__ = (
    "PublicDeclarationClassificationScope",
    "PublicDeclarationKind",
    "PublicDeclarationStability",
)
