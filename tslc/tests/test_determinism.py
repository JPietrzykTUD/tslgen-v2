"""Generation is deterministic: same input -> identical artifacts."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project


def test_artifacts_are_byte_identical_across_runs(data_root: Path) -> None:
    first = generate_project(
        [data_root], primitives=["add", "sub"], extensions=["scalar", "avx2"]
    )
    second = generate_project(
        [data_root], primitives=["add", "sub"], extensions=["scalar", "avx2"]
    )
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
