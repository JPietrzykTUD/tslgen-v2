"""Explicit selection targets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Target:
    """A concrete request: emit ``primitive`` for one backend/extension/type."""

    backend: str  # "cpp" | "rust"
    primitive_name: str
    extension: str  # extension block name, e.g. "scalar", "avx2"
    type_tag: str  # concrete type tag, e.g. "si32", "f64"

    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.backend, self.extension, self.primitive_name, self.type_tag)
