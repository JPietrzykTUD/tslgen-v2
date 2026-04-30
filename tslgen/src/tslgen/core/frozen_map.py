from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Generic, Hashable, TypeVar

from tslgen.core.ordering import stable_sort_key


K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class FrozenMap(Mapping[K, V], Generic[K, V]):
    """An immutable mapping with deterministic key iteration."""

    __slots__ = ("_items",)

    _items: tuple[tuple[K, V], ...]

    def __init__(self, values: Mapping[K, V] | Iterable[tuple[K, V]] = ()) -> None:
        iterable: Iterable[tuple[K, V]]
        if isinstance(values, Mapping):
            iterable = values.items()
        else:
            iterable = values

        seen: set[K] = set()
        items: list[tuple[K, V]] = []
        for key, value in iterable:
            if key in seen:
                raise ValueError(f"duplicate FrozenMap key: {key!r}")
            seen.add(key)
            items.append((key, value))

        object.__setattr__(
            self,
            "_items",
            tuple(sorted(items, key=lambda item: stable_sort_key(item[0]))),
        )

    @classmethod
    def empty(cls) -> FrozenMap[K, V]:
        return cls()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("FrozenMap is immutable")

    def __getitem__(self, key: K) -> V:
        for item_key, item_value in self._items:
            if item_key == key:
                return item_value
        raise KeyError(key)

    def __iter__(self) -> Iterator[K]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        return any(item_key == key for item_key, _ in self._items)

    def __repr__(self) -> str:
        items = ", ".join(f"{key!r}: {value!r}" for key, value in self._items)
        return f"{type(self).__name__}({{{items}}})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self._items) == dict(other.items())
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._items)

    def to_dict(self) -> dict[K, V]:
        return dict(self._items)
