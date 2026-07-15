"""Backend presentation helpers derived from typed extension metadata."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.catalog.model import Extension

_CPP_X86_HELPER_WIDTHS = frozenset({128, 256, 512})
_BACKEND_FEATURE_SPELLINGS: Mapping[str, Mapping[str, str]] = {
    "cpp": {"rdrand": "rdrnd"},
}


def feature_spelling(
    feature: str,
    alternatives: Mapping[str, str],
    *,
    backend_id: str | None = None,
) -> str:
    """Return a compiler target-feature spelling from a source feature name."""

    if feature in alternatives:
        return alternatives[feature]
    backend_spelling = _BACKEND_FEATURE_SPELLINGS.get(backend_id or "", {}).get(feature)
    if backend_spelling is not None:
        return backend_spelling
    if feature.startswith("sse4_"):
        return "sse4." + feature[len("sse4_") :]
    if feature.startswith("avx512_"):
        return "avx512" + feature[len("avx512_") :]
    return feature


def is_x86_register_extension(extension: Extension | None) -> bool:
    return x86_register_bits(extension) is not None


def x86_register_bits(extension: Extension | None) -> int | None:
    if (
        extension is None
        or extension.family != "x86"
        or extension.vector_bits_kind != "fixed"
        or extension.vector_bits <= 0
    ):
        return None
    return extension.vector_bits


def cpp_x86_register_helper(extension: Extension | None) -> str | None:
    bits = x86_register_bits(extension)
    if bits not in _CPP_X86_HELPER_WIDTHS:
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
    "cpp_x86_register_helper",
    "feature_spelling",
    "is_x86_register_extension",
    "rust_arch_module",
    "rust_extension_tag",
    "x86_register_bits",
]
