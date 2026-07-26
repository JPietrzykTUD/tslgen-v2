"""Shared Rust backend naming rules."""

from __future__ import annotations

from tslc.names import identifier_slug


def rust_primitive_trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def rust_primitive_tag_name(primitive_name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in primitive_name.split("_"))


def rust_profile_module_name(profile_name: str) -> str:
    return f"tsl_{identifier_slug(profile_name)}"


__all__ = [
    "rust_primitive_tag_name",
    "rust_primitive_trait_name",
    "rust_profile_module_name",
]
