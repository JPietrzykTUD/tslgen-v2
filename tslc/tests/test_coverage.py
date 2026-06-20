"""The coverage report tracks emitted vs skipped behavior with reasons."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.coverage import coverage_by_primitive, format_coverage_report
from tslc.diagnostics import has_errors


def _result(data_root: Path, machine_profiles_path: Path):
    return generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd", "to_integral"],
        profiles=["scalar", "avx2"],
    )


def test_coverage_separates_emitted_and_skipped(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = _result(data_root, machine_profiles_path)
    by = {row.primitive: row for row in coverage_by_primitive(result)}

    # add lowers everywhere it is selected; it now also emits masked variants (`add_mask`/
    # `add_maskz`). Integer masked specs lower; the *float* masked specs on sse/avx2 prune
    # cleanly (their `mov[mask=zero]` float delegate isn't generated there), and the generic
    # `<LANES>` masked loop is deferred — so `add` shows some skips.
    assert by["add"].emitted > 0
    assert by["add"].emitted > by["add"].skipped

    # hadd now lowers fully: SIMD bodies plus the loop fallback (to_array + loop<range> +
    # details::arith_add); hmax/hmin likewise lower fully now that runtime `if` translates.
    assert by["hadd"].emitted == by["hadd"].attempted > 0
    assert by["hadd"].skipped == 0

    # to_integral now lowers on scalar + the x86 ISAs (the integral-mask type `im` /
    # `vector::imask` + the `movemask` bodies), but the generic bit-loop body still skips
    # (it uses the unimplemented `type::size_bytes` / `details::mask_test`), so it shows
    # both columns.
    assert by["to_integral"].emitted > 0
    assert by["to_integral"].skipped > 0

    # skips carry an actionable reason, and they are NOT surfaced as errors/warnings.
    assert result.skipped
    assert all(entry.reason for entry in result.skipped)
    assert not any(d.severity in ("warning", "error") for d in result.diagnostics)


def test_report_text_is_actionable(data_root: Path, machine_profiles_path: Path) -> None:
    report = format_coverage_report(_result(data_root, machine_profiles_path))
    assert "add" in report and "emitted" in report
    assert "skipped because" in report
    # the report names the construct blocking the remaining bodies (here: the cast type).
    assert any(token in report for token in ("cast", "region", "kind", "signature", "if"))


def test_strict_generation_reports_support_gaps_as_errors(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_integral"],
        profiles=["scalar", "avx2"],
        generation_mode="strict",
    )

    assert result.skipped
    assert has_errors(result.diagnostics)
    assert result.rendered is None
    assert result.artifacts.artifacts == ()
    assert any(
        diagnostic.severity == "error" and diagnostic.code.startswith("TSL-LOWER-")
        for diagnostic in result.diagnostics
    )
