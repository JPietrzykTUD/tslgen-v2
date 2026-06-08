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


@dataclass(frozen=True, slots=True)
class Primitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    attribute_keys: tuple[str, ...]  # e.g. () for unmasked, ("mask",) for masked
    implementations: tuple[Implementation, ...]


@dataclass(frozen=True, slots=True)
class Extension:
    """Hardware target metadata needed for backend translation."""

    name: str  # the extension's unique identity = its TSL block name (e.g. "avx2_vl")
    isa_name: str  # the shared ISA/family spelling from `extension_name` (e.g. "avx2")
    intrinsic_style: str  # "x86", "arm", "scalar", "generic"
    vector_bits: str  # kept as text ("256", "0", "sized")
    register_type_policy: str  # "explicit" | "base_type"
    # type-group name -> {backend_id: register type spelling}
    register_types: dict[str, dict[str, str]]
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

    def expand_type_group(self, name: str) -> tuple[str, ...]:
        return self.type_groups.get(name, ())

    def type_group_contains(self, type_group: str, type_tag: str) -> bool:
        members = self.type_groups.get(type_group)
        if members is None:
            return type_group == type_tag
        return type_tag in members
