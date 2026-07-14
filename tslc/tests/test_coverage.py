"""The coverage report tracks emitted vs skipped behavior deterministically."""

from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture(scope="module")
def representative_coverage_result(data_root: Path, machine_profiles_path: Path):
    return _result(data_root, machine_profiles_path)


def test_coverage_reports_full_emission_when_no_gaps_remain(
    representative_coverage_result,
) -> None:
    result = representative_coverage_result
    by = {row.primitive: row for row in coverage_by_primitive(result)}

    # Direct compiler-vector operations and reductions lower without a
    # hardware-width dependency, including profiles that have no matching
    # fixed-width hardware facade.
    assert by["add"].emitted > 0
    assert by["add"].emitted == by["add"].attempted
    assert by["add"].skipped == 0

    assert by["hadd"].emitted > 0
    assert by["hadd"].emitted == by["hadd"].attempted
    assert by["hadd"].skipped == 0

    assert by["cast"].emitted == by["cast"].attempted > 0
    assert by["cast"].skipped == 0

    assert result.skipped == ()
    assert not any(d.severity in ("warning", "error") for d in result.diagnostics)


def test_report_text_is_actionable(representative_coverage_result) -> None:
    report = format_coverage_report(representative_coverage_result)
    attempted = len(representative_coverage_result.coverage) + len(
        representative_coverage_result.skipped
    )
    assert "add" in report and "emitted" in report
    summary = (
        f"{len(representative_coverage_result.coverage)} emitted / "
        f"{attempted} attempted"
    )
    assert summary in report
    assert "compress_store" in report
    assert "gather_narrow" in report
    assert "mask_population_count" in report
    assert "mask_binary_and" in report
    assert "to_integral" in report
    assert "to_mask" in report
    assert "skipped because" not in report


def test_scalable_fixed_lane_signatures_are_policy_deferred(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["from_array", "to_array", "set"],
        profiles=["sve"],
        backends=["cpp"],
    )
    by = {row.primitive: row for row in coverage_by_primitive(result)}

    assert by["from_array"].emitted == 80
    assert by["from_array"].skipped == 0
    assert by["from_array"].policy_deferred == 10
    assert by["to_array"].emitted == 80
    assert by["to_array"].skipped == 0
    assert by["to_array"].policy_deferred == 10
    assert by["set"].emitted == 80
    assert by["set"].skipped == 0
    assert by["set"].policy_deferred == 10
    assert {entry.status for entry in result.skipped} == {"policy_deferred"}
    assert {
        diagnostic.code
        for entry in result.skipped
        for diagnostic in entry.diagnostics
    } == {"TSL-LOWER-POLICY-DEFERRED-SIGNATURE"}
    assert all(
        diagnostic.location is not None
        for entry in result.skipped
        for diagnostic in entry.diagnostics
    )

    report = format_coverage_report(result)
    # Compile/runtime branch-local type aliases no longer leak into the opposite arm's
    # dependency closure. Fixed/scalable reinterpret dependencies may regroup the same
    # register bits across lane widths, so those reachable target-base slots count too.
    assert "3272 emitted / 3272 attempted" in report
    assert "30 policy-deferred slots" in report
    assert "skipped because" not in report
    assert "policy-deferred because" in report


def test_strict_generation_allows_policy_deferred_scalable_signatures(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["from_array", "to_array", "set"],
        profiles=["sve"],
        backends=["cpp"],
        generation_mode="strict",
    )

    assert {entry.status for entry in result.skipped} == {"policy_deferred"}
    assert not has_errors(result.diagnostics)
    assert result.rendered is not None
    assert result.artifacts.artifacts


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


def test_clang_overlay_full_corpus_has_no_lowering_gaps(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        profiles=["icelake_rockerlake"],
        backends=["cpp"],
    )
    clang_extensions = {
        "clang_v128",
        "clang_v256",
        "clang_v512",
        "clang_v128_bool",
        "clang_v256_bool",
        "clang_v512_bool",
    }
    emitted = [
        entry for entry in result.coverage if entry.extension in clang_extensions
    ]
    skipped = [
        entry for entry in result.skipped if entry.extension in clang_extensions
    ]

    assert emitted
    assert skipped == []
