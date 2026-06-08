"""The generated C++ and Rust projects actually compile.

Skips a backend whose toolchain is unavailable; fails on any build error.
"""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors


def test_generated_projects_build(data_root: Path, tmp_path: Path) -> None:
    result = generate_project(
        [data_root], primitives=["add", "sub"], extensions=["scalar", "avx2"]
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None

    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    # At least one toolchain should have run on this dev container.
    assert report.commands, f"nothing verified; skipped={report.skipped}"
