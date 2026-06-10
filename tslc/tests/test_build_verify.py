"""The generated per-profile projects actually compile (C++ and Rust).

Skips a backend whose toolchain is unavailable; fails on any build error.
"""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors


def test_generated_profiles_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd"],
        # Include a hyphenated, exotic-flag profile so identifier-sanitization and
        # feature-flag-spelling regressions are caught by the build, not just inspection.
        profiles=["scalar", "sse2", "avx", "avx2", "skylake", "icelake-rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None

    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    # configure+build for 4 C++ profiles (8) + cargo test for 4 Rust profiles (4).
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_scalar_mask_comparison_family_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # m-result comparisons + unequal_zero (call<primitive> + closure) on scalar:
    # bool masks, complete call closure -> builds end-to-end in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "equal",
            "nequal",
            "less_than",
            "greater_than",
            "less_than_or_equal",
            "greater_than_or_equal",
            "unequal_zero",
        ],
        profiles=["scalar"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
