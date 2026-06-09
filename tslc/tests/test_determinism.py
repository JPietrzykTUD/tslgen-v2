"""Generation is deterministic: same input -> identical artifacts."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project


def _run(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd"],
        profiles=["scalar", "sse2", "avx", "avx2"],
    )


def test_artifacts_are_byte_identical_across_runs(
    data_root: Path, machine_profiles_path: Path
) -> None:
    first = _run(data_root, machine_profiles_path)
    second = _run(data_root, machine_profiles_path)
    assert first.artifacts.digest_manifest() == second.artifacts.digest_manifest()
