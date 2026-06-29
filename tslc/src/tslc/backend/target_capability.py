"""Typed compiler-owned target/backend presentation capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class X86RegisterCapability:
    """Backend-owned x86 register facts shared by lowering and renderers."""

    extension_name: str
    register_bits: int
    cpp_register_helper: str


@dataclass(frozen=True, slots=True)
class RustExtensionTagCapability:
    """Rust type-level tag spelling for an emitted TSL extension tag."""

    extension_name: str
    tag: str


@dataclass(frozen=True, slots=True)
class RustArchModuleCapability:
    """Rust ``core::arch`` module selected by extension family."""

    extension_family: str
    module: str


X86_REGISTER_CAPABILITIES: tuple[X86RegisterCapability, ...] = (
    X86RegisterCapability("sse", 128, "reg128"),
    X86RegisterCapability("avx2", 256, "reg256"),
    X86RegisterCapability("avx512", 512, "reg512"),
)

RUST_EXTENSION_TAG_CAPABILITIES: tuple[RustExtensionTagCapability, ...] = (
    RustExtensionTagCapability("scalar", "Scalar"),
    RustExtensionTagCapability("sse", "Sse"),
    RustExtensionTagCapability("avx2", "Avx2"),
    RustExtensionTagCapability("avx512", "Avx512"),
)

RUST_ARCH_MODULE_CAPABILITIES: tuple[RustArchModuleCapability, ...] = (
    RustArchModuleCapability("x86", "x86_64"),
    RustArchModuleCapability("arm", "aarch64"),
)


def _map_by_extension(
    entries: tuple[X86RegisterCapability, ...],
) -> Mapping[str, X86RegisterCapability]:
    result: dict[str, X86RegisterCapability] = {}
    for entry in entries:
        if entry.extension_name in result:
            raise ValueError(f"duplicate x86 register capability {entry.extension_name!r}")
        result[entry.extension_name] = entry
    return MappingProxyType(result)


def _tag_map(
    entries: tuple[RustExtensionTagCapability, ...],
) -> Mapping[str, str]:
    result: dict[str, str] = {}
    for entry in entries:
        if entry.extension_name in result:
            raise ValueError(f"duplicate Rust extension tag {entry.extension_name!r}")
        result[entry.extension_name] = entry.tag
    return MappingProxyType(result)


def _arch_module_map(
    entries: tuple[RustArchModuleCapability, ...],
) -> Mapping[str, str]:
    result: dict[str, str] = {}
    for entry in entries:
        if entry.extension_family in result:
            raise ValueError(f"duplicate Rust arch module {entry.extension_family!r}")
        result[entry.extension_family] = entry.module
    return MappingProxyType(result)


_X86_BY_EXTENSION = _map_by_extension(X86_REGISTER_CAPABILITIES)
X86_REGISTER_BITS: Mapping[str, int] = MappingProxyType(
    {
        entry.extension_name: entry.register_bits
        for entry in X86_REGISTER_CAPABILITIES
    }
)
_RUST_EXTENSION_TAGS = _tag_map(RUST_EXTENSION_TAG_CAPABILITIES)
_RUST_ARCH_MODULES = _arch_module_map(RUST_ARCH_MODULE_CAPABILITIES)


def x86_register_capability(extension_name: str) -> X86RegisterCapability | None:
    return _X86_BY_EXTENSION.get(extension_name)


def is_x86_register_extension(extension_name: str) -> bool:
    return extension_name in _X86_BY_EXTENSION


def x86_register_bits(extension_name: str) -> int | None:
    capability = x86_register_capability(extension_name)
    return None if capability is None else capability.register_bits


def cpp_x86_register_helper(extension_name: str) -> str | None:
    capability = x86_register_capability(extension_name)
    return None if capability is None else capability.cpp_register_helper


def rust_arch_module(extension_family: str) -> str | None:
    return _RUST_ARCH_MODULES.get(extension_family)


def rust_extension_tag(extension_name: str | None) -> str:
    if extension_name is None:
        return "Generic<1>"
    tag = _RUST_EXTENSION_TAGS.get(extension_name)
    if tag is not None:
        return tag
    return "".join(
        part[:1].upper() + part[1:]
        for part in extension_name.split("_")
        if part
    )


def rust_register_type(
    extension_name: str,
    base_spelling: str,
    *,
    uses_sized_vector: bool = False,
    lane_parameter: str | None = None,
) -> str:
    if uses_sized_vector:
        return f"array_type<{base_spelling}, {lane_parameter}>"
    bits = x86_register_bits(extension_name)
    if bits is None:
        return base_spelling
    if base_spelling == "f32":
        return f"core::arch::x86_64::__m{bits}"
    if base_spelling == "f64":
        return f"core::arch::x86_64::__m{bits}d"
    return f"core::arch::x86_64::__m{bits}i"


__all__ = [
    "RUST_ARCH_MODULE_CAPABILITIES",
    "RUST_EXTENSION_TAG_CAPABILITIES",
    "RustArchModuleCapability",
    "RustExtensionTagCapability",
    "X86_REGISTER_BITS",
    "X86_REGISTER_CAPABILITIES",
    "X86RegisterCapability",
    "cpp_x86_register_helper",
    "is_x86_register_extension",
    "rust_arch_module",
    "rust_extension_tag",
    "rust_register_type",
    "x86_register_bits",
    "x86_register_capability",
]
