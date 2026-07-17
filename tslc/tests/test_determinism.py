"""Generation is deterministic: same input -> identical artifacts."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

from tslc.api import generate_project

_REPO_ROOT = Path(__file__).resolve().parents[2]

# One small-scope generation dumped as the full snapshot-semantics document
# (diagnostics, coverage, skipped, verification, value tests, benchmarks) plus
# the artifact digest manifest.  Runs in a fresh interpreter so a differing
# PYTHONHASHSEED can surface hash-order bugs invisible to same-process reruns.
_HASH_SEED_PROBE = textwrap.dedent(
    """
    import json
    import sys
    from pathlib import Path

    from tslc.api import generate_project
    from tslc.maintenance._generation_snapshot_semantics import (
        serialize_generation_semantics,
    )

    repo_root = Path(sys.argv[1])
    result = generate_project(
        [repo_root / "tsldata"],
        machine_profiles_path=(
            repo_root / "supplementary" / "buildsystem" / "machine_profiles.json"
        ),
        primitives=["add", "hadd"],
        profiles=["scalar", "avx2"],
        backends=["cpp", "rust"],
    )
    document = {
        "semantics": serialize_generation_semantics(result, repo_root),
        "artifact_digests": list(result.artifacts.digest_manifest()),
    }
    Path(sys.argv[2]).write_bytes(
        json.dumps(document, indent=1, sort_keys=True).encode("utf-8")
    )
    """
)


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


def test_generation_semantics_are_identical_across_hash_seeds(
    tmp_path: Path,
) -> None:
    documents: list[bytes] = []
    for hash_seed in ("0", "12345"):
        output = tmp_path / f"semantics-{hash_seed}.json"
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hash_seed
        env["PYTHONPATH"] = os.pathsep.join(
            path
            for path in (str(_REPO_ROOT / "tslc" / "src"), env.get("PYTHONPATH"))
            if path
        )
        completed = subprocess.run(
            (sys.executable, "-c", _HASH_SEED_PROBE, str(_REPO_ROOT), str(output)),
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr + completed.stdout
        documents.append(output.read_bytes())

    assert documents[0] == documents[1]
