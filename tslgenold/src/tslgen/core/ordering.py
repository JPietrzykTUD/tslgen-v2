from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import TypeVar


T = TypeVar("T")
K = TypeVar("K")


def stable_sort_key(value: object) -> tuple[object, ...]:
    """Return a deterministic key for common pipeline value types."""

    if value is None:
        return (0,)
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, int):
        return (2, value)
    if isinstance(value, float):
        return (3, repr(value))
    if isinstance(value, str):
        return (4, value)
    if isinstance(value, Path):
        return (5, value.as_posix())
    if isinstance(value, bytes):
        return (6, value.hex())
    if isinstance(value, tuple):
        return (7, tuple(stable_sort_key(item) for item in value))
    if isinstance(value, list):
        return (8, tuple(stable_sort_key(item) for item in value))
    if isinstance(value, (frozenset, set)):
        return (9, tuple(sorted((stable_sort_key(item) for item in value))))
    if isinstance(value, Mapping):
        return (
            10,
            tuple(
                sorted(
                    (stable_sort_key(key), stable_sort_key(item))
                    for key, item in value.items()
                )
            ),
        )

    value_type = type(value)
    raise TypeError(
        "unsupported stable sort key type: "
        f"{value_type.__module__}.{value_type.__qualname__}"
    )


def stable_sorted(
    values: Iterable[T],
    *,
    key: Callable[[T], K] | None = None,
) -> tuple[T, ...]:
    """Sort values through ``stable_sort_key`` and return an immutable tuple."""

    if key is None:
        return tuple(sorted(values, key=stable_sort_key))
    return tuple(sorted(values, key=lambda value: stable_sort_key(key(value))))
