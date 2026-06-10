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
class RequirementClause:
    """One `requires` clause: a feature-flag set, optionally scoped to an extension
    and/or a type-group.

    A simple ``requires [avx, avx2]`` is one clause with ``extension=None`` and
    ``type_group=None`` (applies to every extension and type). A nested ``requires:``
    map may key by extension name (``avx2 [avx, avx2]`` -> ``extension="avx2"``), by
    type-group (avx512's ``idqword [avx512f]`` -> ``type_group="idqword"``), or both
    (two-level ``avx512: idqword [...]`` -> ``extension="avx512", type_group="idqword"``).
    A clause applies to a body only when its extension scope matches the body's own
    extension (or is unscoped).
    """

    flags: frozenset[str]
    type_group: str | None = None
    extension: str | None = None


@dataclass(frozen=True, slots=True)
class Implementation:
    """One source-authored body for a (extension, type-group) selector path."""

    selector_path: tuple[str, ...]
    extension: str
    type_group: str
    body_text: str
    requirements: tuple[RequirementClause, ...] = ()
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

    name: str  # internal identity = TSL block name (e.g. "avx2_vl"); drives selection
    isa_name: str  # emitted tag = `extension_name` (e.g. "avx2"); `_vl` is internal only
    family: str  # "x86" | "arm" | "scalar" | … — picks the Rust core::arch module
    compose_prefix: dict[str, str]  # backend_id -> intrinsic prefix
    compose_suffix_by_type: dict[str, str]  # type tag -> suffix fragment
    inherits: str | None = None  # extension this one borrows impls/metadata from
    lscpu_flags: frozenset[str] = frozenset()  # features that make this extension available


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
            # `unmasked` excludes only the masked *variants* (`[mask=…]`); other
            # attributes (e.g. `[value=zero]` on set_zero) are ordinary primitives.
            if unmasked and "mask" in primitive.attribute_keys:
                continue
            return primitive
        return None

    def extension_chain(self, name: str) -> tuple[str, ...]:
        """An extension followed by its `inherits` ancestors (e.g. avx2_vl, avx2)."""

        chain: list[str] = []
        current: str | None = name
        seen: set[str] = set()
        while current is not None and current not in seen and current in self.extensions:
            seen.add(current)
            chain.append(current)
            current = self.extensions[current].inherits
        return tuple(chain)

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
