"""The generated value-correctness tests build and pass (opt-in `run_value_tests`).

Separate from `test_build_verify` (which only compiles the substrate): value testing builds
and runs the extra `tsl_values` binary, so it is gated behind ``run_value_tests=True`` and kept
to a focused primitive/profile set to bound its cost.
"""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors


def test_golden_value_tests_build_and_pass(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Elementwise primitives whose golden cases run against the generic software reference.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "sub", "conflict"],
        profiles=["avx2"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify, run_value_tests=True)
    # No compile/configure errors, and (since the golden tests pass) no value-test warnings.
    assert report.diagnostics == (), report.diagnostics
    # The value tests actually ran (the ctest step is present), so a green result is meaningful
    # rather than vacuous.
    cpp_steps = {c.command.step for c in report.commands if c.command.backend_id == "cpp"}
    if cpp_steps:  # cpp toolchain available (else the backend was skipped)
        assert "test" in cpp_steps, cpp_steps
        assert "build-values" in cpp_steps, cpp_steps
