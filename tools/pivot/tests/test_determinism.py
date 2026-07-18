"""The complete PIVOT export is stable across interpreter hash seeds."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sys


_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE = Path(__file__).parent / "baselines" / "full_export.json"
_BODY_BASELINE = Path(__file__).parent / "baselines" / "body_census.json"
_FULL_EXPORT_DIGEST_SCRIPT = """
from hashlib import sha256
import json
from pathlib import Path

from tslc.diagnostics import SourceSpan
from tslc.target_text import LoweredBody
from tslc_pivot.baseline import (
    build_full_export_manifest,
    canonical_full_export,
    render_full_export_manifest,
)
from tslc_pivot.body_ir import pivot_body_census_digest
from tslc_pivot.exporter import export_pivot
from tslc_pivot.model import PivotLanguage
from tslc_pivot.body_builder import build_pivot_body
from tslc_pivot.lowering_capture import CAPTURE_CLOSE, CAPTURE_OPEN, PivotBodyCapture

repository_root = Path.cwd()
run = canonical_full_export(repository_root)
result = export_pivot(run.request)
assert result.diagnostics == ()
manifest = build_full_export_manifest(run, result)
rendered = render_full_export_manifest(manifest).encode("utf-8")
print(sha256(rendered).hexdigest())
print(
    pivot_body_census_digest(
        result.body_censuses,
        source_root=repository_root,
    )
)
source = SourceSpan(Path("determinism.tsl"), 1, 1, 1, 2)
unknown = f"{CAPTURE_OPEN}{'d' * 24}:complete:0{CAPTURE_CLOSE}"
failure = build_pivot_body(
    PivotLanguage.CPP,
    LoweredBody.from_text(unknown),
    PivotBodyCapture((), (), "a" * 24),
    source,
)
assert failure.body is None
assert len(failure.unsupported) == 1
reason = failure.unsupported[0]
print(
    json.dumps(
        [
            reason.code,
            reason.message,
            reason.phase,
            [
                reason.source.path.as_posix(),
                reason.source.line,
                reason.source.column,
                reason.source.end_line,
                reason.source.end_column,
            ],
        ],
        separators=(",", ":"),
    )
)
"""


def test_full_export_manifest_is_identical_across_hash_seeds() -> None:
    expected_digest = sha256(_BASELINE.read_bytes()).hexdigest()
    expected_body_digest = json.loads(
        _BODY_BASELINE.read_text(encoding="utf-8")
    )["digest"]
    digests: list[tuple[str, str, str]] = []
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
        lines = completed.stdout.splitlines()
        assert len(lines) == 3
        digests.append((lines[0], lines[1], lines[2]))

    assert digests[0] == digests[1]
    assert tuple(item[0] for item in digests) == (expected_digest, expected_digest)
    assert tuple(item[1] for item in digests) == (
        expected_body_digest,
        expected_body_digest,
    )
    expected_failure = (
        '["TSL-PIVOT-BODY-UNKNOWN-CAPTURE",'
        '"PIVOT render stream refers to an unknown capture token",'
        '"body_construction",["determinism.tsl",1,1,1,2]]'
    )
    assert tuple(item[2] for item in digests) == (
        expected_failure,
        expected_failure,
    )
