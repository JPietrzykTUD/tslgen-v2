"""Rust const-generic wrapper types shared by validation and emission."""

from __future__ import annotations

from types import MappingProxyType

RUST_CONST_ARG_WRAPPERS = MappingProxyType(
    {
        "bool": "BoolArg",
        "i8": "I8Arg",
        "i16": "I16Arg",
        "i32": "I32Arg",
        "i64": "I64Arg",
        "isize": "ISizeArg",
        "u8": "U8Arg",
        "u16": "U16Arg",
        "u32": "U32Arg",
        "u64": "U64Arg",
        "usize": "USizeArg",
    }
)

__all__ = ("RUST_CONST_ARG_WRAPPERS",)
