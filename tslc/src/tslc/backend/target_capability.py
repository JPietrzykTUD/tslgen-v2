"""Backend presentation helpers derived from typed extension metadata."""

from __future__ import annotations

from tslc.catalog.model import Extension

_CPP_WIDTH_INDEXED_HELPER_WIDTHS = frozenset({128, 256, 512})


def is_width_indexed_register_extension(extension: Extension | None) -> bool:
    return width_indexed_register_bits(extension) is not None


def width_indexed_register_bits(extension: Extension | None) -> int | None:
    if (
        extension is None
        or not extension.family_capability.width_indexed_registers
        or extension.vector_bits_kind != "fixed"
        or extension.vector_bits <= 0
    ):
        return None
    return extension.vector_bits


def cpp_width_indexed_register_helper(extension: Extension | None) -> str | None:
    bits = width_indexed_register_bits(extension)
    if bits not in _CPP_WIDTH_INDEXED_HELPER_WIDTHS:
        return None
    return f"reg{bits}"


def rust_arch_module(extension: Extension | None) -> str | None:
    if extension is None:
        return None
    metadata = extension.metadata.backend.get("rust")
    return None if metadata is None else metadata.arch_module


def rust_extension_tag(extension: Extension | str | None) -> str:
    if extension is None:
        return "Generic<1>"
    if isinstance(extension, str):
        return _rust_type_name_from_identifier(extension)
    metadata = extension.metadata.backend.get("rust")
    # Internal selection blocks such as avx2_vl are emitted under their public ISA tag
    # (`avx2`). Their source metadata still controls masks/registers, but not the public tag.
    if (
        extension.name == extension.isa_name
        and metadata is not None
        and metadata.type_name is not None
    ):
        return metadata.type_name
    return _rust_type_name_from_identifier(extension.isa_name)


def _rust_type_name_from_identifier(identifier: str) -> str:
    return "".join(
        part[:1].upper() + part[1:]
        for part in identifier.split("_")
        if part
    )


__all__ = [
    "cpp_width_indexed_register_helper",
    "is_width_indexed_register_extension",
    "rust_arch_module",
    "rust_extension_tag",
    "width_indexed_register_bits",
]
