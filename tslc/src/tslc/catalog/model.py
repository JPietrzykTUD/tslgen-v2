"""Typed, immutable domain model promoted from the parse tree.

This is intentionally a *rich vocabulary* (the charter encourages that): every
type here represents a real TSL concept the rest of the compiler reasons about.
What it is not is plumbing — there are no result/handoff wrappers here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

TypeTag = NewType("TypeTag", str)
BackendId = NewType("BackendId", str)
ExtensionName = NewType("ExtensionName", str)


@dataclass(frozen=True, slots=True)
class Implementation:
    """One source-authored body for a (extension, type-group) selector path."""

    selector_path: tuple[str, ...]
    extension: str
    type_group: str
    body_text: str
    # Hardware features this body needs. None means the requirement could not be
    # evaluated (e.g. avx512's nested per-type `requires:`), so the body is treated
    # as unavailable until that form is supported.
    required_flags: frozenset[str] | None = frozenset()
    source_order: int = 0  # tiebreak: earlier source wins


@dataclass(frozen=True, slots=True)
class Primitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    attribute_keys: tuple[str, ...]  # e.g. () for unmasked, ("mask",) for masked
    implementations: tuple[Implementation, ...]


@dataclass(frozen=True, slots=True)
class Extension:
    """Hardware target metadata needed for backend translation.

    Identity is the TSL block name (`avx2` and `avx2_vl` are distinct extensions
    even though they share an ISA spelling). Register types are *not* modeled here
    — the generated library's static `simd<>` core supplies them; this carries only
    what backend translation consumes (the intrinsic family and compose fragments).
    """

    name: str
    family: str  # "x86" | "arm" | "scalar" | … — picks the Rust core::arch module
    compose_prefix: dict[str, str]  # backend_id -> intrinsic prefix
    compose_suffix_by_type: dict[str, str]  # type tag -> suffix fragment


@dataclass(frozen=True, slots=True)
class Catalog:
    primitives: tuple[Primitive, ...]
    type_groups: dict[str, tuple[str, ...]]
    extensions: dict[str, Extension]
    # backend_id -> normalized scalar tag (s32/u32/f32) -> spelling
    type_spellings: dict[str, dict[str, str]]
    # backend_id -> translation-template key (e.g. "emit_return", "loop_range") -> template
    translations: dict[str, dict[str, str]]

    def primitive(self, name: str, *, unmasked: bool = True) -> Primitive | None:
        for primitive in self.primitives:
            if primitive.name != name:
                continue
            if unmasked and primitive.attribute_keys:
                continue
            return primitive
        return None

    def type_group_members(self, type_group: str) -> tuple[str, ...]:
        """Members of a selector's type-group.

        Handles named groups (``?i?``), bracketed type lists (``[si32, ui32]``),
        and bare concrete tags (``f64`` -> itself).
        """

        named = self.type_groups.get(type_group)
        if named is not None:
            return named
        text = type_group.strip()
        if text.startswith("[") and text.endswith("]"):
            return tuple(
                part.strip() for part in text[1:-1].split(",") if part.strip()
            )
        return (type_group,)

    def type_group_contains(self, type_group: str, type_tag: str) -> bool:
        return type_tag in self.type_group_members(type_group)

    def type_group_specificity(self, type_group: str) -> int:
        """Fewer members = more specific (used as the primary selection key)."""

        return len(self.type_group_members(type_group))
