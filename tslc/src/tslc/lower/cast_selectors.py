"""Shared parsing for ``cast<...>`` TSIL selector terms."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.lower._text import split_selector_terms

CAST_TYPE_KINDS = frozenset({"value", "ptr", "const_ptr"})


@dataclass(frozen=True, slots=True)
class CastSelector:
    variant: str | None
    type_kind: str = "value"
    unsupported_terms: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.variant is not None and not self.unsupported_terms


def parse_cast_selector(text: str) -> CastSelector:
    terms = split_selector_terms(text)
    if not terms:
        return CastSelector(None)

    variant = terms[0].strip() or None
    type_kind = "value"
    unsupported: list[str] = []
    seen_type = False
    for term in terms[1:]:
        if term.startswith("type="):
            value = term[len("type=") :].strip()
            if seen_type or value not in CAST_TYPE_KINDS:
                unsupported.append(term)
            else:
                type_kind = value
                seen_type = True
            continue
        unsupported.append(term)
    return CastSelector(variant, type_kind, tuple(unsupported))


__all__ = ("CAST_TYPE_KINDS", "CastSelector", "parse_cast_selector")
