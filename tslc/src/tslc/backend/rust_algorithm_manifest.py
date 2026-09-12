"""Compiler-owned public names reserved by the static Rust algorithm facade."""

from __future__ import annotations

from tslc.backend.algorithm_surface import (
    ALGORITHM_CHECKED_NAMES,
    ALGORITHM_ORDINARY_NAMES,
    ALGORITHM_RAW_NAMES,
    ALGORITHM_SCALED_CHECKED_NAMES,
    ALGORITHM_SCALED_RAW_NAMES,
)


RUST_ALGORITHM_RESERVED_NAMES = frozenset(
    ALGORITHM_ORDINARY_NAMES
    | ALGORITHM_RAW_NAMES
    | ALGORITHM_CHECKED_NAMES
    | ALGORITHM_SCALED_RAW_NAMES
    | ALGORITHM_SCALED_CHECKED_NAMES
)


__all__ = ("RUST_ALGORITHM_RESERVED_NAMES",)
