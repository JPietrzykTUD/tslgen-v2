"""Catalog-owned facts about scalar TSL type tags."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ScalarTypeInfo:
    tag: str
    bit_width: int
    signed: bool
    floating: bool
    spelling_key: str
    documentation_short_label: str
    documentation_label: str
    documentation_sort_order: int


_SCALAR_TYPE_INFOS: tuple[ScalarTypeInfo, ...] = (
    ScalarTypeInfo("si8", 8, True, False, "s8", "i8", "signed int8", 0),
    ScalarTypeInfo("si16", 16, True, False, "s16", "i16", "signed int16", 1),
    ScalarTypeInfo("si32", 32, True, False, "s32", "i32", "signed int32", 2),
    ScalarTypeInfo("si64", 64, True, False, "s64", "i64", "signed int64", 3),
    ScalarTypeInfo("ui8", 8, False, False, "u8", "u8", "unsigned int8", 4),
    ScalarTypeInfo("ui16", 16, False, False, "u16", "u16", "unsigned int16", 5),
    ScalarTypeInfo("ui32", 32, False, False, "u32", "u32", "unsigned int32", 6),
    ScalarTypeInfo("ui64", 64, False, False, "u64", "u64", "unsigned int64", 7),
    ScalarTypeInfo("f32", 32, True, True, "f32", "f32", "float", 8),
    ScalarTypeInfo("f64", 64, True, True, "f64", "f64", "double", 9),
)

SCALAR_TYPE_INFOS = {info.tag: info for info in _SCALAR_TYPE_INFOS}
DEFAULT_SCALAR_TYPE_TAGS = tuple(info.tag for info in _SCALAR_TYPE_INFOS)
KNOWN_SCALAR_TYPE_TAGS = frozenset(SCALAR_TYPE_INFOS)
SCALAR_TYPE_ORDER = MappingProxyType(
    {tag: index for index, tag in enumerate(DEFAULT_SCALAR_TYPE_TAGS)}
)


def scalar_type_info(type_tag: str) -> ScalarTypeInfo | None:
    return SCALAR_TYPE_INFOS.get(type_tag)


def is_type_tag(text: str) -> bool:
    return text in SCALAR_TYPE_INFOS


def scalar_bit_width(type_tag: str) -> int | None:
    info = scalar_type_info(type_tag)
    return info.bit_width if info is not None else None


def scalar_bit_width_or_default(type_tag: str, default: int = 8) -> int:
    return scalar_bit_width(type_tag) or default


def scalar_byte_width(type_tag: str) -> int | None:
    width = scalar_bit_width(type_tag)
    return None if width is None else max(1, width // 8)


def scalar_byte_width_or_default(type_tag: str, default: int = 1) -> int:
    return scalar_byte_width(type_tag) or default


def same_scalar_width(left: str, right: str) -> bool:
    left_width = scalar_bit_width(left)
    right_width = scalar_bit_width(right)
    return left_width is not None and left_width == right_width


def signed_of(type_tag: str) -> str:
    info = scalar_type_info(type_tag)
    if info is None or (info.signed and not info.floating):
        return type_tag
    return f"si{info.bit_width}"


def unsigned_of(type_tag: str) -> str:
    info = scalar_type_info(type_tag)
    if info is None or (not info.signed and not info.floating):
        return type_tag
    return f"ui{info.bit_width}"


def is_signed(type_tag: str) -> bool:
    info = scalar_type_info(type_tag)
    return info.signed if info is not None else False


def normalize_scalar_tag(type_tag: str) -> str:
    info = scalar_type_info(type_tag)
    return info.spelling_key if info is not None else type_tag


__all__ = (
    "DEFAULT_SCALAR_TYPE_TAGS",
    "KNOWN_SCALAR_TYPE_TAGS",
    "SCALAR_TYPE_INFOS",
    "SCALAR_TYPE_ORDER",
    "ScalarTypeInfo",
    "is_signed",
    "is_type_tag",
    "normalize_scalar_tag",
    "same_scalar_width",
    "scalar_bit_width",
    "scalar_bit_width_or_default",
    "scalar_byte_width",
    "scalar_byte_width_or_default",
    "scalar_type_info",
    "signed_of",
    "unsigned_of",
)
