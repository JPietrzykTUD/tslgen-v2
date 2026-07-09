"""The generated per-profile projects actually compile (C++ and Rust).

Skips a backend whose toolchain is unavailable; fails on any build error.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import shlex
import subprocess
import textwrap

import pytest

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors

pytestmark = pytest.mark.generated_build


def _cmake_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ZIG_LOCAL_CACHE_DIR", str(tmp_path / "zig-local-cache"))
    env.setdefault("ZIG_GLOBAL_CACHE_DIR", str(tmp_path / "zig-global-cache"))
    _prefer_host_compiler_for_native_cmake(env)
    return env


def _prefer_host_compiler_for_native_cmake(env: dict[str, str]) -> None:
    if _compiler_basename(env.get("CXX", "")) == "zig":
        env["CXX"] = "c++"
    if _compiler_basename(env.get("CC", "")) == "zig":
        env["CC"] = "cc"


def _compiler_basename(command: str) -> str:
    parts = shlex.split(command)
    if not parts:
        return ""
    return Path(parts[0]).name


def test_generated_profiles_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "hadd"],
        # Include an exotic-flag profile so feature-flag-spelling regressions
        # are caught by the build, not just inspection.
        profiles=["scalar", "sse2", "avx", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None

    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    # configure+build for 4 C++ profiles (8) + cargo test for 4 Rust profiles (4).
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_cpp_fetch_content_consumer_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake not available")
    if shutil.which("c++") is None:
        pytest.skip("C++ compiler not available")

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar"],
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    write_report = write_artifacts(result.artifacts, tmp_path / "generated")
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "CMakeLists.txt").write_text(
        textwrap.dedent(
            f"""
            cmake_minimum_required(VERSION 3.20)
            project(tsl_consumer LANGUAGES CXX)

            include(FetchContent)
            set(TSL_PROFILE scalar CACHE STRING "TSL profile" FORCE)
            FetchContent_Declare(tsl SOURCE_DIR "{(tmp_path / "generated" / "cpp").as_posix()}")
            FetchContent_MakeAvailable(tsl)

            add_executable(consumer main.cpp)
            target_link_libraries(consumer PRIVATE tsl::tsl)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (consumer / "main.cpp").write_text(
        textwrap.dedent(
            """
            #include <cstdint>
            #include <tsl.hpp>

            int main() {
              using Vec = tsl::simd<std::int32_t, tsl::scalar>;
              return tsl::add<Vec>(1, 2) == 3 ? 0 : 1;
            }
            """
        ).lstrip(),
        encoding="utf-8",
    )
    build = tmp_path / "consumer-build"
    env = _cmake_env(tmp_path)
    configure = subprocess.run(
        ("cmake", "-S", str(consumer), "-B", str(build)),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert configure.returncode == 0, configure.stderr + configure.stdout
    built = subprocess.run(
        ("cmake", "--build", str(build), "--target", "consumer"),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert built.returncode == 0, built.stderr + built.stdout


def test_cpp_auto_profile_configures(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    if shutil.which("cmake") is None:
        pytest.skip("cmake not available")
    if shutil.which("c++") is None:
        pytest.skip("C++ compiler not available")

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar", "avx2"],
        backends=["cpp"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    write_report = write_artifacts(result.artifacts, tmp_path / "generated")
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    build = tmp_path / "auto-build"
    configured = subprocess.run(
        (
            "cmake",
            "-S",
            str(tmp_path / "generated" / "cpp"),
            "-B",
            str(build),
            "-DTSL_BUILD_TESTS=OFF",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=_cmake_env(tmp_path),
    )
    output = configured.stderr + configured.stdout
    assert configured.returncode == 0, output
    assert "TSL auto-detected profile =" in output


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
    # body `intrin<mask_blend, build>(mask, left, right)` -> `_mm512_mask_blend_*`
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
    # generic constructs (`type`/`value` regions, `var<typed>` +
    # uninit array, calls into the axis'd/overloaded `store`/`load`) end-to-end in C++ and
    # Rust across scalar + SIMD; the closure pulls in `load`/`store`. Including `avx`
    # guards the AVX-only 256-bit integer store/load fallback used by byte/word arrays.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_array", "from_array"],
        profiles=["scalar", "avx", "avx2", "skylake"],
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
    # vector::mask)` + `var<typed>` + `mask<zero>`/`mask<set>` (the `mask<*>` ops lowered per
    # the lane-bitmask representation), and the mask/bitwise primitives (pulled by le/ge)
    # combine them with `mask<test>`/`mask<set_to>`. Builds in both backends; the native
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
    # plus the byte/word scalar-loop fallback (`helper<arith_mul>`) compile on scalar + SIMD;
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
    # Horizontal reductions: `hadd` (loop fallback via to_array + loop<backend> +
    # `helper<arith_add>`) and `hmax`/`hmin` (intrinsic reduce_*/extracti128 bodies plus the
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


def test_convert_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # The width-changing conversion family (`return_type: base: ToBase`): `convert_up`/
    # `convert_down` (`v:=(v,sImm)`) select+widen/narrow a chunk; `load_convert_up` (`v:=cptr+`)
    # widens straight from memory. Their native bodies compose intrinsics from SPACE-separated
    # `intrin<..., build[...]>` modifiers + `infix`/`infix_sep`
    # (`<cvt, build[infix=epi8, infix_sep="", suffix=epi16]>`
    # -> `_mm256_cvtepi8_epi16`), dispatch the chunk via `switch<compile>(index)` (the `index`
    # const typed `si32` to match the i32 intrinsic const), and build the out/intermediate vectors
    # from `vector::as_base(ToBase)` / `as(ext, ToBase)`. Builds in C++ and
    # Rust; cluster-gated / not-yet-composable variants skip.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["convert_up", "convert_down", "load_convert_up"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_cast_reinterpret_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The representation-change `base`-dim primitives: `reinterpret` (same-width bit-reinterpret)
    # and `cast` (value conversion, possibly different lane count within the same register). Both
    # carry a `ToBase` second type axis; the selector resolves the `"=="` identity marker to the
    # source and drops the unenumerable `"*"` catch-all (else they'd leak as bogus target bases).
    # The same-width / bitcast / sse4.1-gated native bodies build; the space-separated-modifier
    # conversion bodies (`intrin<cvt, build[infix=…, suffix=…]>`) skip cleanly until Stage 2.
    # Builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["cast", "reinterpret"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_sequence_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `sequence` is nullary (`v:=()`, an iota generator) — its native bodies are
    # `intrin<set, build>(N-1, …, 0)` literal lists per width. Builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["sequence"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_extract_value_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `extract_value` (`s:=v[idx]`) extracts a lane. The `[idx]` is a decorative index annotation
    # the signature parser drops (it is NOT the array kind `s[]`); the real index is the `Index
    # {kind int}` generic_param, emitted as a compile-time const generic. The body reads
    # `to_array(a)[Index]`. Builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["extract_value"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_max_min_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `max`/`min` (`v:=(v,v)`) delegate to `blend(less_than(a,b), …)`. `blend` is a single-form
    # masked primitive (`[mask=pass_through]`) emitted *bare*, so the prune must match a bare
    # `blend` caller against the lone `pass_through` spec (single-form names normalize their policy
    # to None; only split `_mask`/`_maskz` names stay policy-aware). The scalar `blend` body uses
    # the `complete` form (not a raw `return`). Builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["max", "min"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_gather_scatter_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `gather`/`scatter` (the `vidx` index-vector kind + the free `IndicesType` SIMD type param +
    # an `N`/`scale` immediate). Two body shapes coexist: the portable fallback (a `to_array`
    # over `IndicesType` -> index loop with `idx_offset`/`ptr_add`, on scalar + types with no
    # native gather) and the native `switch<compile>(scale) { 1 => intrin… _ => fallback }` —
    # lowered to a C++ cascading `if constexpr` / Rust compile-time `match`, with the scale
    # forwarded via `immediate(N)=` (a C++ positional const arg / Rust turbofish const). The Rust
    # index register is pinned per-ISA so the native intrinsic's concrete `__m256i` type-checks.
    # Builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["gather", "scatter"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_to_integral_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `to_integral` (result kind `im` = the integral-mask type) packs a mask into an
    # integer: the scalar `if`-return (imask = u64), the avx2/sse `movemask` bodies incl.
    # the avx2 `?i16` two-half pack (imask = a lane-sized uint via `lane_bitmask_int`),
    # and the avx512/_vl `complete(mask)` identity (imask = the native `__mmaskN`).
    # The `cast<static>(vector::imask, …)` resolves via the new `vector::imask` query.
    # Generic/neon/sve to_integral still skip (their bit-loop uses `type::size_bytes` /
    # `detail::helpers::mask_test`, unimplemented), so they don't appear in the build.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_integral"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_to_mask_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `to_mask` is the inverse of `to_integral`: its parameter is the integral-mask scalar
    # (signature `m:=im`, the same `im` kind), spelled `Vec::imask_type` / `Self::ImaskType`.
    # The scalar `(mask & 1) != 0` body and the avx2 bodies that build a lane mask from the
    # integer build-verify in both backends; the heavier portable bodies skip cleanly.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_mask"],
        profiles=["scalar", "avx2"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_to_vector_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `to_vector` (mask -> vector) closes the mask triad. Exercises the reinterpret /
    # type-conversion cluster: the generic emulated body (`var<init_register>` + `if<compile>`
    # splicing the f32/f64 NaN branch + `mask<test>` loop + `base::unsigned_of` /
    # `type(scalar::*)` / `cast<bitcast>` via `tsl_core::bit_cast`), the avx512
    # `maskz_set1`+`bit_cast` float paths, and the avx2/sse `complete(mask)` identity.
    # Both backends; avx2_vl/sse_vl native conversion (mov+mask::lane) skips cleanly.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_vector"],
        profiles=["scalar", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_masked_value_ops_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Masked-variant generation (value-masking category): a dual name now emits its masked
    # variants alongside the unmasked one, split to `<name>_mask` (pass_through/merge) /
    # `<name>_maskz` (zero) — distinct names (Rust can't overload; the two policies share a
    # signature so C++ can't either). SIMD bodies delegate to the unmasked op + `blend`/`mov`
    # (which stay bare, masked-only; `mov` itself emits both `mov_mask`/`mov_maskz`); scalar uses
    # if/set_zero. Pruning is policy-aware, so float masked specs whose `mov_maskz` float delegate
    # is absent prune cleanly. Representative spread (`binary_and`, `add`, `inv`, `shift_left`,
    # `mul_imm`), both policies, both backends, scalar + sse2 + avx2 + skylake. (The generic
    # `<LANES>` masked loop and mask-producing comparisons / memory masked variants are deferred.)
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["binary_and", "add", "inv", "shift_left", "mul_imm"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_masked_comparisons_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Masked category B: mask-producing comparisons emit a `[mask=zero]` variant `m:=(m,v,v)`
    # (takes a mask, returns a mask), split to `<name>_maskz`. avx512(_vl) uses the native
    # masked compare (`intrin<…, build[post=mask]>` -> `_mm512_cmpeq_*_mask`); avx2/sse/scalar
    # fall back to `mask_binary_and(mask, <unmasked compare>)`; the generic `<LANES>` masked loop
    # is gated off. Both backends, scalar + sse2 + avx2 + skylake + icelake_rockerlake.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["equal", "less_than", "greater_than_or_equal", "between_inclusive"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_masked_load_store_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Masked category C (memory): `load` emits `load_maskz` (zero) + `load_mask` (pass_through);
    # `store` emits `store_mask` — each carrying the `aligned` const-generic (mask × aligned
    # compose orthogonally). avx512(_vl) uses native masked load/store (`maskz_loadu`/`mask_loadu`/
    # `mask_storeu`); avx2/sse fall back to `load`+`mov`/`blend`(+`store`) — the fallback forwards
    # the caller's `aligned` via `attrs[aligned=value(primitive::attribute(aligned))]`,
    # which the call lowerer now resolves. `void` store result types in both backends. scalar +
    # sse2 + avx2 + skylake. (gather/scatter masked are deferred on the `vidx` kind.)
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["load", "store"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_mul_imm_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `mul_imm` exercises the `sImm` compile-time immediate kind: the immediate `factor`
    # becomes a C++ non-type template parameter (`template <class Vec, uint32_t factor>`) and
    # a Rust const generic (`Mul_immImpl<const factor: u32>`), omitted from the runtime args
    # and used as a value in the body. Builds in both backends on scalar + generic + x86
    # (the C++ smoke instantiates the wrapper at `factor = 3`).
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul_imm"],
        profiles=["scalar", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_shift_left_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `shift_left` is the first MIXED overload set with an `sImm` member: in Rust the
    # immediate form splits out to `shift_left_imm` (const generic) while `(v,s)`/`(v,v)`
    # stay the `shift_left` arg-trait; C++ keeps `shift_left_imm`. The immediate's `params:`
    # block (`type ui32`, `value_range 0..base_bit_width(data)`, `dispatch rust: literal_match`)
    # drives the Rust forwarding: a literal match `match shift { 0 => _mm256_slli_epi32::<0>(data),
    # … }` whose arms re-type per intrinsic; C++ stays positional `_mm256_slli_epi32(data, shift)`.
    # Both backends, scalar + sse + avx2 (the generic/x86 fallback multi-arg call, shift_right's
    # `if<compile>`, float, and masked are deferred and skip cleanly).
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_shift_right_scalar_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Scalar `shift_right` is the `if<compile>` *second half* + `generic_params(PreserveSign)`.
    # Its `?i?` body splices on `if<generation>(is_signed)` (gen-known) and, on the signed arm,
    # emits a real compile-time branch over the *symbolic* `PreserveSign` template param —
    # C++ `if constexpr (!PreserveSign) { <unsigned-cast logical> } else { <arithmetic> }`,
    # Rust `if !PreserveSign { … } else { … }`. `PreserveSign` is a free `bool` template /
    # `const` generic (default `true` in C++; spelled at call sites otherwise). Unsigned scalars
    # splice the plain `else` (no `if constexpr`). The x86/generic/float forms are deferred and
    # skip cleanly. Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_right"],
        profiles=["scalar"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_shift_right_imask_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `shift_right_imask` (`im:=(im,usize)`) closes the mask subsystem: a logical right shift of
    # the integral mask. Its `if<compile>(is_signed(vector::imask) && !PreserveSign)` predicate
    # short-circuits — the imask is unsigned by construction, so `is_signed` folds `false`, the
    # `&&` collapses to `false`, and the generation splice takes the plain logical-shift `else`
    # arm (no `if constexpr` survives). Exercises the `&&` short-circuit fold + the
    # `type::is_signed` query + parenthesised-predicate handling. All profiles, both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_right_imask"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_shift_right_delegation_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The comma-separated `call` bracket: the `(v,s)`/`(v,v)` runtime `shift_right` forms with no
    # native intrinsic (e.g. avx2/sse `si64`, runtime vector shifts) delegate
    # `@self[GenericVec, PreserveSign]` -> generic -> `@self[as_extension(scalar), PreserveSign]`
    # -> scalar, forwarding the `PreserveSign` generic_param through the multi-entry `[...]` list
    # (entry 0 = target vector, entries 1.. = forwarded template args). The SIGNED x86 bodies build
    # via the `reinterpret` second type-axis (`srai` + the `!PreserveSign`
    # `reinterpret`->`srli`->`reinterpret` arm). The `(v,sImm)` IMMEDIATE-forwarding delegation also
    # builds: `@self[…, shift, PreserveSign]` targets the `_imm` split (`shift_right_imm`) with the
    # immediate forwarded as a const arg, chaining avx2/sse `si64` -> generic -> scalar. Scalar +
    # sse2 + avx2 (avx512 is covered by `test_shift_right_avx512_immediate_builds`; the float chain
    # is deferred and skips cleanly). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_right"],
        profiles=["scalar", "sse2", "avx2"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_shift_right_avx512_immediate_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # avx512's `_mm512_srli_epi32` etc. take their shift count as a `const u32`, while avx2's
    # take `i32` — a single shared trait const can't satisfy both, and stable Rust can't cast a
    # generic const in a turbofish. The `params:` `dispatch rust: literal_match` bridges it: the
    # immediate forwards through a literal match (`match shift { 0 => _mm512_srli_epi32::<0>(data),
    # … }`) whose literal arms re-type to whichever const each intrinsic wants (folds to one arm).
    # `value_range 0..base_bit_width(data)` sets the per-type arm count (16/32/64). This is the
    # case the wall blocked; skylake + icelake_rockerlake, both backends. (The si8/u8 avx512
    # `intrin::suffix(si?)` gap and the generic-vector reinterpret fallback skip cleanly.)
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_right"],
        profiles=["skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_set1_avx512_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `set1`'s avx512 `?i?` body previously hardcoded `intrin::suffix(si?)` — a type-group
    # wildcard, not a concrete type — so suffix resolution failed (16 skips on avx512) and any
    # primitive broadcasting a scalar via `call set1` pruned. Now it resolves the suffix from
    # the selected type like avx2/sse (`signed_of(base::in)` + a `cast<static>` to the signed
    # type; avx512 uses `_mm512_set1_epi64` directly). skylake, both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["set1"],
        profiles=["skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_shift_float_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Float shifts shift the *bit pattern*: reinterpret the float to a same-width int, shift,
    # reinterpret back. This needs same-width cross-domain `reinterpret` (`f32↔ui32`/`f64↔ui64`),
    # which the selector now enumerates (`_same_width`, was integer-only), plus `signed_of`
    # being float-aware (`f32→si32`) so the sign-preserving (`PreserveSign`) branch reinterprets
    # to the signed int rather than back to the float. `reinterpret`/`set1`/`from_array`/
    # `to_array` are pulled in as callees. scalar + sse2 + avx2 + skylake, both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left", "shift_right"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_reinterpret_integer_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `reinterpret` is the `base`-dimension of the target-vector second axis: `return_type: base:
    # ToBase` makes the result the source vector with its base type replaced. Delivered for
    # same-width integer targets (signedness flips `si32<->ui32`) — the corpus `?i?: ToBase: ?i?`
    # `bit_cast` branch. The backend emits a SECOND type param (C++ `reinterpret_impl<simd<i32,
    # avx2>, simd<u32,avx2>>` / Rust `ReinterpretImpl<ToVec>`); `register::generic(ToType)` resolves
    # the target register. Scalar + sse2 + avx2. Different-width / float / cross-domain reinterpret
    # and the generic (LANES-sized) vector are deferred. Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["reinterpret"],
        profiles=["scalar", "sse2", "avx2"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_extract_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `extract` is the `extension`-dimension of the same axis: `return_type: extension:
    # ToExtension` makes the result the source vector under a smaller extension (avx2->sse,
    # avx512->sse/avx2), via the single-intrinsic branches (`_mm256_extracti128_si256`,
    # `_mm512_extracti32x4_epi32`, the `f32`/`f64` variants) + an `sImm` lane-block index. Proves
    # the second axis on the *extension* dimension. The generic `where:`-clause body (`family
    # same_as`/`width smaller_than`) is deferred and skips cleanly. sse2 + avx2 + skylake, both
    # backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["extract"],
        profiles=["sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_insert_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `insert` is `extract`'s inverse on the `extension` axis: it writes the source vector into
    # a *larger* target (`return_type: extension: ToExtension`), so its `orig` operand is the
    # target (`ToVec`), not the source. That makes `orig` a `vt` (target-axis vector) param —
    # typed `ToVec::register_type` (C++) / `T::RegisterType` (Rust) while `data` stays the source
    # `Vec` — over `_mm256_inserti128_si256` / `_mm512_inserti32x4` / `_inserti64x4` + an `sImm`
    # lane-block index. Proves a parameter (not just the result) on the target type axis. sse2 +
    # avx2 + skylake, both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["insert"],
        profiles=["sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_mask_binary_and_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `mask_binary_and` (the mask-algebra enabler for range comparisons): `binary_and` on the
    # lane-bitmask register (sse/avx2), raw `&` on the native `__mmaskN` (avx512), `bool & bool`
    # (scalar), and a `mask<test>`/`mask<set>` bit-loop (generic). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_binary_and"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_range_comparisons_build(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # The four range predicates compose delivered primitives: scalar `(left <= x) && (x <= right)`,
    # and elsewhere `mask_binary_and(less_than[_or_equal](left, x), less_than[_or_equal](x, right))`.
    # The comparison family + `mask_binary_and` are pulled in as the call closure. Both backends,
    # scalar + sse + avx2 + avx512. (Masked `[mask=zero]` range variants are deferred.)
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "between_inclusive",
            "between_left_inclusive",
            "between_right_inclusive",
            "between_exclusive",
        ],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_mask_boolean_algebra_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The mask boolean ops, completing `mask_binary_and`: `or`/`xor` are `binary_or`/`binary_xor`
    # on the lane-bitmask register (sse/avx2), raw `|`/`^` on the native `__mmaskN` (avx512) /
    # `bool` (scalar), generic bit-loops. `not` is native `~`/`!` (avx512/scalar) + generic loop;
    # its avx2/sse path (`binary_xor(mask, mask_true())`) prunes cleanly — `mask_true` needs the
    # not-yet-built `mask<lane_true>()` lane value (deferred). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_binary_or", "mask_binary_xor", "mask_binary_not"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_mask_true_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `mask_true` (`m:=()`) builds on all targets now that `mask<lane_true>()` resolves: native
    # `__mmaskN` all-ones (avx512), `set1(mask_lane_all_true<T>())` on the lane-bitmask ISAs
    # (sse/avx2 — the previously-pruned path), `true` (scalar), generic bit-loop. The lane value
    # comes from the `::tsl::mask_lane_all_true<T>()` / `<T as TslMaskLaneValue>::all_true()`
    # substrate (all-ones bytes → int all-ones / float all-ones-bit NaN). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_true"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_imask_ops_build(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # The imask bit-manipulation ops, typed with the `im` (integral-mask) kind so they operate on
    # the integer mask, not the element type: `test_imask` `(mask >> position) & 1`, `insert_imask`
    # `a | (b << position)`, `extract_imask` `mask >> position` — all on `imask_type` (`__mmaskN` on
    # avx512, the lane-bitmask integer elsewhere), so float vectors shift by an integer (base-type
    # typing would shift by a float — illegal). Named `_imask` (not `_mask`) because they manipulate
    # the integral value, matching `shift_right_imask`/`lzc_imask`. Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["test_imask", "insert_imask", "extract_imask"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_mask_population_count_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `mask_population_count` (`usize:=m`) counts a mask's set lanes: `to_integral` then
    # `helper<popcount>` (C++ `__builtin_popcountll` / Rust `count_ones`, returning a u32
    # count), cast to the `usize` result (`std::size_t`/`usize` — a count, not a mask). The
    # generic path is a `size_t` count loop over `mask<test>`. Exercises the new `usize`
    # signature kind + the popcount substrate. Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_population_count"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_nullary_constants_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The `v:=()` / `m:=()` nullary constructors: `set_zero` (native `setzero`/`0`),
    # `set_undef` (native `undefined`/uninit), `mask_false` (`set_zero`-of-mask /
    # scalar `false`). No call closure of their own — they ARE the building blocks other
    # bodies call. Builds in C++ and Rust across scalar + SIMD.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["set_zero", "set_undef", "mask_false"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_simple_memory_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `load_scalar` (`s:=cptr`, a scalar dereference / masked-zero variant). Builds in both
    # backends across scalar + SIMD. (Deferred siblings: `memory_cp`'s `mem<copy>` directive
    # and `void`-pointer types aren't lowered for Rust yet; `compress_store`'s generic
    # fallback needs `detail::helpers::mask_test` — see test_masked_memory_build, skipped.)
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["load_scalar"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_modulo_build(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `mod` (`v:=(v,v)`) and `mod_imm` (`v:=(v,sImm)`, which calls `mod(x, set1(imm))`).
    # x86 has no integer-vector modulo intrinsic, so the SIMD bodies delegate to the
    # generic per-lane vector and the scalar `%` (the closure pulls `set1`/`to_array`/
    # `from_array`). Exercises cross-extension arithmetic delegation + an `sImm` forwarded
    # to a sibling call. Builds in C++ and Rust; scalar + avx2 + skylake.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mod", "mod_imm"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_blend_add_sequence_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `blend_add` (`v:=(m,v,v,v)`, the composite `mov[mask=pass_through](mask, add(left,
    # right))`-shaped masked add) and `custom_sequence` (`v:=(s,s)`, an iota from a start
    # + stepwidth built over to_array/from_array + scalar `helper<arith_add>`). The
    # closure pulls `mov`/`add` and the array layer. Builds in C++ and Rust across scalar
    # + SIMD.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["blend_add", "custom_sequence"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_conflict_counting_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `conflict` (`v:=v`, avx512cd native `_mm*_conflict_*` + the array-loop fallback),
    # `conflict_free` (`m:=(m,v)` = `mask_binary_and(mask, equal(conflict(data), zero))`),
    # and `count_matches` (`s:=(v,s)` = `mask_population_count(equal(data, set1(value)))`).
    # The closure pulls the comparison + mask-algebra families. avx2 + skylake (the
    # `type::size_bytes`-gated generic conflict bound-check path skips until Phase B1).
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["conflict", "conflict_free", "count_matches"],
        profiles=["avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_bit_reductions_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # `hand`/`hor` (`s:=v` horizontal AND/OR: native reduce + the extract/shuffle x86 path,
    # plus the `to_array` + `var<typed>` accumulator loop) and `popcnt` (`v:=v`, per-lane
    # population count on the AVX512 VPOPCNTDQ/BITALG native path — hence icelake_rockerlake —
    # plus the sse/avx2 intrinsic slots), and `tzc` (`usize:=m`, `helper<ctz>` of the integral
    # mask, cast to a size value). Both backends; the generic fallbacks use width-aware
    # helper functions and no longer depend on a `vector::offset_base` query.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["popcnt", "hand", "hor", "tzc"],
        profiles=["sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_leading_zeros_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Leading-zero counts: `lzc` (`v:=v`, the avx512cd `_mm*_lzcnt_epi32/64` native plus the
    # per-lane loop fallback that delegates to `lzc_scalar` over the scalar vector) and
    # `lzc_imask` (`usize:=m`, `helper<clz>` of the integral mask, cast to a size value). The
    # closure pulls `lzc_scalar` (`usize:=s`), whose integer body is `helper<clz>(data)` cast to
    # a size value — the `clz` helper is width-aware via `sizeof(T)` / Rust `leading_zeros`, so
    # no offset arg is needed. The float `lzc_scalar` bit-reinterpret path uses `mem<copy>` into
    # an unsigned carrier and the same width-aware helper. Both backends, scalar + sse2 + avx2 +
    # skylake.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["lzc", "lzc_imask", "lzc_scalar"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake_rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_masked_memory_build(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # The masked / sparse memory family: `load_mask_repr` (`m:=cptr`) / `store_mask_repr`
    # (`void:=(ptr,m)`), `masked_set1` (`v:=(m,v,s)`), `compress` (`v:=(m,v)`),
    # `expand_load` (`v:=(m,cptr)`). avx512 native mask_compress/mask_expandload plus the
    # generic/sse/avx2 per-lane fallbacks whose loop tests the mask with `mask<test>`. That
    # region now lowers per physical mask repr: the generic vector's integer bitset uses the
    # inline `(m>>i)&1` shift, while sse/avx2 register lane-masks route to the universal
    # `tsl::detail::helpers::mask_test<Vec>` / `Self::mask_lane_test` lane-extraction helper. sse2/avx2
    # exercise the register-mask loop fallback (the path the helper fixes); skylake exercises
    # the AVX-512 native paths plus the generic fallback for the vbmi2-gated i8/i16 `compress`
    # (Skylake-X lacks VBMI2, so those `compress` bodies skip and fall back to the loop).
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "load_mask_repr", "store_mask_repr", "masked_set1", "compress", "compress_store",
            "expand_load",
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


def test_memory_cp_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `memory_cp` (`void:=(ptr,cptr,s,s)`) copies raw bytes via the `mem<copy>` TSIL region:
    # `mem<copy>(cast<reinterpret>(void *, dst), cast<reinterpret>(void const *, src),
    # count_bytes)`. `mem` is a scanned keyword lowered by `MemLowerer` to the `mem_copy`
    # translate template — C++ `std::memcpy` over `void *` reinterprets, Rust
    # `crate::tsl_core::mem_copy` over `u8` byte pointers (the `void`-cast maps to `*const/*mut
    # u8`) with a `TslByteCount` normalization of the base-typed count. Same body for every
    # extension (no SIMD intrinsics), so it builds across scalar + SIMD in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["memory_cp"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_allocate_family_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # The memory-allocation family is non-vector (`allocate` ptr:=(usize), `allocate_aligned`
    # ptr:=(usize,usize), `deallocate` void:=(ptr)) — derived `is_free_function` from the
    # signature, so each emits a single plain `tsl::` free function (no simd<> template), not a
    # per-(type,ext) wrapper. Bodies lower mem<alloc|alloc_aligned|free> to std::malloc/
    # aligned_alloc/free (C++) and crate::tsl_core::mem_* (Rust). ISA-independent, so one slot
    # regardless of profile; builds in C++ and Rust across scalar + SIMD.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["allocate", "allocate_aligned", "deallocate"],
        profiles=["scalar", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_set_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `set` is authored as `v:=(lanes<s>)`: one named lane-list parameter whose length is the
    # selected vector's lane count. Fixed-width SIMD bodies expand lane accesses at generation
    # time; the generic <LANES> fallback copies from the same named lane-list parameter in an
    # emitted runtime loop. C++ and Rust both expose an array-like lane-list argument.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["set"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_to_ostream_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `to_ostream` (`o:=(o,v,s)`) writes a vector's lanes into a text buffer. The `o` (ostream)
    # kind renders as a string buffer (C++ std::string& / Rust &mut String); the body collapses
    # to_array -> io<format> -> complete(out), where io<format> calls the runtime
    # tsl::ostream_write helper (the per-lane base formatting + a TslBits as_u64 in Rust). No
    # scalar impl in the corpus, so it emits for generic + SIMD; builds in C++ and Rust.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_ostream"],
        profiles=["scalar", "sse2", "avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_full_corpus_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Compile EVERY primitive together in one project (vs the per-primitive-group tests
    # above, which prune incomplete callees). Compiling the whole corpus as one translation
    # unit catches latent cross-primitive type bugs the targeted tests cannot — e.g. a body
    # that passes a base_type where a callee wants the integral-mask type, which only fails
    # when both primitives are emitted together. avx2 covers scalar/sse/avx2/generic; skylake
    # adds avx512 + the native-mask (`__mmaskN`) bodies.
    from tslc.catalog.builder import CatalogBuilder
    from tslc.compiler_assets import load_default_tsl_grammar
    from tslc.sources import SourceLoader
    from tslc.syntax.parser import TslParser

    load = SourceLoader().load(tuple(sorted(data_root.rglob("*.tsl"))))
    catalog = CatalogBuilder().build(
        TslParser(load_default_tsl_grammar()).parse(load.documents)
    ).catalog
    assert catalog is not None
    names = sorted({primitive.name for primitive in catalog.primitives})

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=names,
        profiles=["avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"
