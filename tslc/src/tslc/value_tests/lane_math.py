"""Shared lane-count, tiling, and seed-mix invariants for value tests and benchmarks.

Generated value tests and benchmarks both derive lane counts from register widths,
replicate one authored fixed-length pattern across a target lane count, refuse that
replication for cross-lane primitives, and decorrelate derived random seeds. Those
invariants must agree between the two planners — and, for scalable targets, with the
runtime tiling loops the C++ renderers emit — so they live here once. This module owns
only the shared facts; benchmark-only policy stays in ``tslc.benchmark``.
"""

from __future__ import annotations

from tslc.catalog.model import Primitive
from tslc.catalog.scalar_types import scalar_bit_width

# 64-bit golden-ratio constant (2**64 / phi, rounded to odd). Mixed into seeds derived
# from stable identities (function names, scenario ids) so related identities do not
# produce correlated random streams.
SEED_MIX_64 = 0x9E3779B97F4A7C15


def whole_lanes(vector_bits: int, type_tag: str) -> int | None:
    """Complete scalar lanes a fixed-width register holds for one type, or None.

    None when the scalar width is unknown or the register does not hold a positive
    whole number of lanes of the type.
    """

    bits = scalar_bit_width(type_tag)
    if bits is None or bits <= 0 or vector_bits < bits or vector_bits % bits:
        return None
    return vector_bits // bits


def tile(values: tuple[str, ...], lanes: int) -> tuple[str, ...]:
    """Replicate an authored fixed-length pattern across ``lanes`` (index modulo pattern)."""

    if not values:
        return ()
    return tuple(values[index % len(values)] for index in range(lanes))


def runtime_tile_index(index_expr: str, authored_lanes: int) -> str:
    """The C++ index expression matching :func:`tile` when lanes are only known at runtime."""

    return f"{index_expr} % {authored_lanes}"


def tiling_preserves_lane_semantics(primitive: Primitive | None) -> bool:
    """Whether tiling an authored pattern lane-by-lane keeps the primitive's meaning.

    Tiling with ``index % authored_lanes`` is sound only when output lane i depends
    solely on input lane i. The corpus-declared ``Primitive.cross_lane`` fact decides:
    the elementwise common case leaves it False (tiling-safe), and a cross-lane op
    (reduce, shuffle, compress, conflict, iota) declares it True so it is never tiled.
    An unresolved primitive is conservatively unsafe.
    """

    return primitive is not None and not primitive.cross_lane


__all__ = (
    "SEED_MIX_64",
    "runtime_tile_index",
    "tile",
    "tiling_preserves_lane_semantics",
    "whole_lanes",
)
