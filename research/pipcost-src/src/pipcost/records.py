"""Deterministic JSON records and evidence digests."""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


def canonical_json(value: object, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(value, indent=2, sort_keys=True) + "\n"
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest_json(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def digest_tree(root: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {
            ".pyc",
            ".pyo",
            ".swp",
            ".swo",
        }:
            continue
        entries.append((relative.as_posix(), digest_file(path)))
    return digest_json(entries), tuple(entries)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(canonical_json(value, pretty=True), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, values: Iterable[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as output:
        for value in values:
            output.write(canonical_json(value))
            output.write("\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        records.append(value)
    return tuple(records)
