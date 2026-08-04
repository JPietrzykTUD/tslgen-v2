from __future__ import annotations

from pathlib import Path

from pipcost.records import (
    canonical_json,
    digest_file,
    digest_tree,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)


def test_json_writes_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    write_json(path, {"z": 1, "a": [2, 3]})
    first = digest_file(path)
    write_json(path, {"a": [2, 3], "z": 1})
    assert digest_file(path) == first
    assert read_json(path) == {"a": [2, 3], "z": 1}
    assert canonical_json({"z": 1, "a": 2}) == '{"a":2,"z":1}'


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    write_jsonl(path, [{"b": 2, "a": 1}, {"value": 3}])
    assert read_jsonl(path) == (
        {"a": 1, "b": 2},
        {"value": 3},
    )


def test_tree_digest_ignores_python_cache(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "source.pyc").write_bytes(b"ignored")
    (tmp_path / ".source.py.swp").write_bytes(b"ignored editor state")
    digest, entries = digest_tree(tmp_path)
    assert digest
    assert [entry[0] for entry in entries] == ["source.py"]
