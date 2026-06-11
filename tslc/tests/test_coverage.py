"""The coverage report tracks emitted vs skipped behavior with reasons."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.coverage import coverage_by_primitive, format_coverage_report


def _result(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd", "hmax"],
        profiles=["scalar", "avx2"],
    )


def test_coverage_separates_emitted_and_skipped(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _result(data_root, machine_profiles_path)
    by = {row.primitive: row for row in coverage_by_primitive(result)}

    # add lowers everywhere it is selected (only scalar/x86-family extensions are
    # emitted, and add covers them).
    assert by["add"].skipped == 0
    assert by["add"].emitted == by["add"].attempted > 0

    # hadd now lowers fully: its SIMD bodies plus the loop fallback (to_array + loop<range>
    # + details::arith_add) that previously skipped before native-loop translation landed.
    assert by["hadd"].emitted == by["hadd"].attempted > 0
    assert by["hadd"].skipped == 0

    # hmax still skips the bodies that use a runtime `if` (only if<generation> is modeled).
    assert by["hmax"].emitted > 0
    assert by["hmax"].skipped > 0

    # skips carry an actionable reason, and they are NOT surfaced as errors/warnings.
    assert result.skipped
    assert all(entry.reason for entry in result.skipped)
    assert not any(d.severity in ("warning", "error") for d in result.diagnostics)


def test_report_text_is_actionable(data_root: Path, machine_profiles_path: Path) -> None:
    report = format_coverage_report(_result(data_root, machine_profiles_path))
    assert "add" in report and "emitted" in report
    assert "skipped because" in report
    # the report names the construct blocking the remaining bodies (here: the runtime `if`).
    assert any(token in report for token in ("if", "region", "kind", "signature"))
