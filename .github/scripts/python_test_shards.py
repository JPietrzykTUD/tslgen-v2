#!/usr/bin/env python3
"""Emit a balanced pytest file matrix for GitHub Actions."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = REPO_ROOT / "tslc" / "tests"

# Approximate per-file cost from pytest --durations in the Python-only CI lane.
# Unknown files use DEFAULT_WEIGHT and are still included automatically.
FILE_WEIGHTS = {
    "test_profile_rendering.py": 33.0,
    "test_specialization.py": 6.0,
    "test_generation_conditionals.py": 35.0,
    "test_explain.py": 30.0,
    "test_coverage.py": 17.0,
    "test_fuzz_value_tests.py": 16.0,
    "test_determinism.py": 11.0,
    "test_masks_and_calls.py": 10.0,
    "test_render_model.py": 6.0,
    "test_value_test_planning.py": 6.0,
    "test_build_verify_config.py": 3.0,
    "test_catalog_validation.py": 3.0,
    "test_select_and_lower.py": 3.0,
}
DEFAULT_WEIGHT = 1.0


@dataclass(frozen=True, slots=True)
class TestShard:
    index: int
    paths: tuple[Path, ...]
    weight: float

    @property
    def name(self) -> str:
        return f"python-{self.index}"

    def matrix_entry(self) -> dict[str, str]:
        return {
            "name": self.name,
            "paths_json": json.dumps(
                [_repo_relative(path) for path in sorted(self.paths)],
                separators=(",", ":"),
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=4, help="number of shards to emit")
    parser.add_argument(
        "--paths-json",
        help="JSON array of repository-relative test files; omit for the full suite",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    selected = None
    if args.paths_json is not None:
        values = json.loads(args.paths_json)
        if not isinstance(values, list) or not all(
            isinstance(value, str)
            for value in values
        ):
            raise SystemExit("--paths-json must contain a JSON string array")
        selected = tuple(values)
    shards = compute_shards(args.count, selected)
    kwargs = {"indent": 2} if args.pretty else {"separators": (",", ":")}
    print(json.dumps([shard.matrix_entry() for shard in shards], **kwargs))
    return 0


def compute_shards(
    count: int,
    selected: tuple[str, ...] | None = None,
) -> tuple[TestShard, ...]:
    if count < 1:
        raise SystemExit("--count must be positive")

    buckets: list[list[Path]] = [[] for _ in range(count)]
    weights = [0.0 for _ in range(count)]
    for path in _weighted_test_files(selected):
        index = min(range(count), key=lambda candidate: (weights[candidate], candidate))
        buckets[index].append(path)
        weights[index] += _weight(path)

    return tuple(
        TestShard(index=index, paths=tuple(paths), weight=weights[index])
        for index, paths in enumerate(buckets)
    )


def _weighted_test_files(selected: tuple[str, ...] | None) -> tuple[Path, ...]:
    files = (
        TEST_ROOT.glob("test_*.py")
        if selected is None
        else _selected_files(selected)
    )
    return tuple(sorted(files, key=lambda path: (-_weight(path), path.name)))


def _selected_files(selected: tuple[str, ...]) -> tuple[Path, ...]:
    paths: list[Path] = []
    for value in sorted(set(selected)):
        relative = Path(value)
        path = REPO_ROOT / relative
        if (
            relative.is_absolute()
            or path.parent != TEST_ROOT
            or not path.name.startswith("test_")
            or path.suffix != ".py"
            or not path.is_file()
        ):
            raise SystemExit(f"selected Python test is not a test file: {value}")
        paths.append(path)
    return tuple(paths)


def _weight(path: Path) -> float:
    return FILE_WEIGHTS.get(path.name, DEFAULT_WEIGHT)


def _repo_relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
