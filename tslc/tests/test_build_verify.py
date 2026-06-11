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


def test_blend_select_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Mask consumers + cross-extension delegation. `blend`/`mov` select on a mask (native
    # blendv/mask_blend, or the generic mask<test> loop); `min`/`max` are blend(less_than(...)),
    # so this is the first build of x86 min/max. `mul`'s si64 fallback delegates through the
    # generic vector via vector::as_extension(generic) -> simd<i64, generic<4>> (the lane count
    # is generation-time known), round-tripping to_array -> @self -> from_array.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul", "blend", "mov", "min", "max"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    blob = "\n".join(a.content for a in result.artifacts.artifacts)
    assert "tsl::generic<4>" in blob, "mul si64 cross-extension delegation not emitted"
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_generic_masks_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The generic vector's emulated mask: comparisons build a bitset mask via `let<type>(MaskT,
    # vector::mask)` + `var<typed>` + `mask<zero>`/`mask<set:1>` (the `mask<*>` ops lowered per
    # the lane-bitmask representation), and the mask/bitwise primitives (pulled by le/ge)
    # combine them with `mask<test>`/`mask<set>`. Builds in both backends; the native
    # comparison bodies are unaffected.
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
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    blob = "\n".join(a.content for a in result.artifacts.artifacts)
    assert "equal_impl<tsl::simd<int32_t, tsl::generic<LANES>>>" in blob, "generic mask not emitted"
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_generic_extension_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The `generic` portable vector emitted standalone: `simd<T, generic<LANES>>` with the lane
    # count a template param (C++) / const generic (Rust), its register an array, and its bodies
    # delegating per-lane to scalar (`result[i] = @self[vector::as_extension(scalar)](...)`).
    # `add`/`sub` build in both backends; the C++ smoke instantiates `generic<8>`, the Rust
    # impl is type-checked generically over `LANES`. The closure pulls scalar `add`/`sub`.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "sub"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    # The generic vector is actually emitted (not merely skipped-clean).
    blob = "\n".join(a.content for a in result.artifacts.artifacts)
    assert "tsl::generic<LANES>" in blob and "Generic<LANES>" in blob, "generic not emitted"

    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_elementwise_bitwise_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The core elementwise arithmetic + bitwise families. `add` was already build-verified;
    # this is the first compile of `sub`/`mul`/`div`/`binary_{and,andnot,or,xor}` in either
    # backend (they lowered but had never been built). Their integer/float intrinsic paths
    # plus the byte/word scalar-loop fallback (details::arith_mul) compile on scalar + SIMD;
    # cluster-gated variants (float bitwise via reinterpret, si64 mul via delegation) stay
    # skipped and are simply absent from the emitted set.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "add",
            "sub",
            "mul",
            "div",
            "binary_and",
            "binary_andnot",
            "binary_or",
            "binary_xor",
        ],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_reductions_build(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # Horizontal reductions: `hadd` (loop fallback via to_array + loop<range> +
    # details::arith_add) and `hmax`/`hmin` (intrinsic reduce_*/extracti128 bodies plus the
    # generic var<infer> + runtime-`if` loop for byte/word). Exercises native loop and
    # runtime-conditional translation end-to-end in C++ and Rust across scalar + SIMD; the
    # closure pulls in `to_array`/`load`/`store`.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["hadd", "hmax", "hmin"],
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
