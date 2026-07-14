"""Canonical contextual type syntax in the primitive corpus."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_REDUNDANT_TYPE_WRAPPERS = {
    "cast type": re.compile(r"cast<[^>]+>\s*\(\s*type\s*\(", re.S),
    "let value": re.compile(r"let<type>\s*\([^,]+,\s*type\s*\(", re.S),
    "type comparison": re.compile(r"type::is_same\s*\(\s*type\s*\(", re.S),
    "typed variable": re.compile(
        r"var<(?:typed|const_typed|runtime_array)>\s*\(\s*type\s*\(", re.S
    ),
}


@pytest.mark.parametrize(
    ("description", "pattern"),
    _REDUNDANT_TYPE_WRAPPERS.items(),
)
def test_primitive_corpus_uses_contextual_type_arguments(
    data_root: Path,
    description: str,
    pattern: re.Pattern[str],
) -> None:
    offenders = [
        str(path.relative_to(data_root))
        for path in sorted((data_root / "primitives").rglob("*.tsl"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"redundant type(...) wrapper in {description}: {offenders}"
