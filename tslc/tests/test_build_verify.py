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


def test_simd_comparison_family_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The signed+unsigned+float comparison family as real SIMD in BOTH backends, across
    # both mask representations: lane-bitmask (sse2/avx2 — mask is the register) and
    # native-predicate (skylake — avx512/_vl `__mmaskN`, selected via `post=mask`).
    # Unsigned bodies resolve via if<generation> (avx2) or the `epu*` suffix (avx512);
    # the binary-op closure selects via extension-scoped/bracketed requires; declarations
    # precede all bodies; the emitted set is prune-clean.
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
        profiles=["sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_blend_native_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `blend` is the first mask-CONSUMING primitive (mask is a parameter). Its native
    # body `intrin_compose<mask_blend>(mask, left, right)` -> `_mm512_mask_blend_*`
    # build-verifies on skylake (native __mmaskN across sse/avx2/avx512) in C++ and
    # Rust. Scalar/generic blend (runtime if + raw return / loops) skip cleanly.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["blend"],
        profiles=["skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_to_from_array_roundtrip_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The vector<->array layer: `to_array` (result kind `s[]`, a `var<typed>` over the
    # `array_type` substrate + a defaulted-axis `store` call) and `from_array` (`s[]`
    # parameter, a `load attrs[aligned=false]` call / scalar `data[0]`). Exercises the new
    # generic constructs (`type<generation>`/`value<generation>` regions, `var<typed>` +
    # uninit array, calls into the axis'd/overloaded `store`/`load`) end-to-end in C++ and
    # Rust across scalar + SIMD; the closure pulls in `load`/`store`.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_array", "from_array"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_load_store_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `load`/`store` (the ptr/void kinds) across scalar + SIMD. `[aligned=*]` expands to
    # BOTH aligned/unaligned variants (a bool axis template/const-generic param); the
    # integer SIMD bodies use a register-pointer reinterpret cast (C++ reinterpret_cast /
    # Rust `as *mut`) and `assume_aligned` for the aligned branch. Builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["load", "store"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"
