"""The complete PIVOT export is stable across interpreter hash seeds."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sys


_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE = Path(__file__).parent / "baselines" / "full_export.json"
_FULL_EXPORT_DIGEST_SCRIPT = """
from hashlib import sha256
from pathlib import Path

from tslc_pivot.baseline import (
    build_full_export_manifest,
    canonical_full_export,
    render_full_export_manifest,
)
from tslc_pivot.exporter import export_pivot

repository_root = Path.cwd()
run = canonical_full_export(repository_root)
result = export_pivot(run.request)
assert result.diagnostics == ()
manifest = build_full_export_manifest(run, result)
rendered = render_full_export_manifest(manifest).encode("utf-8")
print(sha256(rendered).hexdigest())
"""


def test_full_export_manifest_is_identical_across_hash_seeds() -> None:
    expected_digest = sha256(_BASELINE.read_bytes()).hexdigest()
    digests: list[str] = []
    for hash_seed in ("0", "12345"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hash_seed
        env["PYTHONPATH"] = os.pathsep.join(
            path
            for path in (
                str(_REPO_ROOT / "tools" / "pivot" / "src"),
                str(_REPO_ROOT / "tslc" / "src"),
                env.get("PYTHONPATH"),
            )
            if path
        )
        completed = subprocess.run(
            (
                sys.executable,
                "-c",
                _FULL_EXPORT_DIGEST_SCRIPT,
            ),
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr + completed.stdout
        assert completed.stderr == ""
        digests.append(completed.stdout.strip())

    assert digests == [expected_digest, expected_digest]
