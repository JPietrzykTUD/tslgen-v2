"""The coverage report tracks emitted vs skipped behavior deterministically."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.coverage import coverage_by_primitive, format_coverage_report
from tslc.diagnostics import has_errors


def _result(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd", "cast"],
        profiles=["scalar", "avx2"],
    )


def test_coverage_reports_full_emission_when_no_gaps_remain(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _result(data_root, machine_profiles_path)
    by = {row.primitive: row for row in coverage_by_primitive(result)}

    # These primitives used to provide representative support gaps. The current
    # primitive-finalization contract is stricter: selected corpus slots should
    # lower everywhere, so coverage rows are emitted == attempted.
    assert by["add"].emitted > 0
    assert by["add"].emitted == by["add"].attempted
    assert by["add"].skipped == 0

    assert by["hadd"].emitted == by["hadd"].attempted > 0
    assert by["hadd"].skipped == 0

    assert by["cast"].emitted == by["cast"].attempted > 0
    assert by["cast"].skipped == 0

    assert result.skipped == ()
    assert not any(d.severity in ("warning", "error") for d in result.diagnostics)


def test_report_text_is_actionable(data_root: Path, machine_profiles_path: Path) -> None:
    report = format_coverage_report(_result(data_root, machine_profiles_path))
    assert "add" in report and "emitted" in report
    assert "3464 emitted / 3464 attempted" in report
    assert "skipped because" not in report


def test_strict_generation_succeeds_when_no_support_gaps_remain(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["cast"],
        profiles=["scalar", "avx2"],
        generation_mode="strict",
    )

    assert result.skipped == ()
    assert not has_errors(result.diagnostics)
    assert result.rendered is not None
    assert result.artifacts.artifacts
