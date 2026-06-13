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


def test_to_integral_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `to_integral` (result kind `im` = the integral-mask type) packs a mask into an
    # integer: the scalar `if`-return (imask = u64), the avx2/sse `movemask` bodies incl.
    # the avx2 `?i16` two-half pack (imask = a lane-sized uint via `lane_bitmask_int`),
    # and the avx512/_vl `emit_return(mask)` identity (imask = the native `__mmaskN`).
    # The `cast<static>(vector::imask, …)` resolves via the new `vector::imask` query.
    # Generic/neon/sve to_integral still skip (their bit-loop uses `type::size_bytes` /
    # `details::mask_test`, unimplemented), so they don't appear in the build.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_integral"],
        profiles=["scalar", "sse2", "avx", "avx2", "skylake", "icelake-rockerlake"],
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
    # `type<backend>(scalar::*)` / `cast<bitcast>` via `tsl_core::bit_cast`), the avx512
    # `maskz_set1`+`bit_cast` float paths, and the avx2/sse `emit_return(mask)` identity.
    # Both backends; avx2_vl/sse_vl native conversion (mov+mask::lane) skips cleanly.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["to_vector"],
        profiles=["scalar", "avx2", "skylake", "icelake-rockerlake"],
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
        profiles=["scalar", "avx2", "skylake", "icelake-rockerlake"],
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
    # stay the `shift_left` arg-trait; C++ keeps `shift_left_imm`. The x86 immediate body
    # forwards the const generic into the intrinsic — Rust `_mm256_slli_epi32::<shift>(data)`
    # (rust_const_match), C++ `_mm256_slli_epi32(data, shift)`. Both backends, scalar + sse +
    # avx2 (avx512's `u32`-immediate per-ISA type, generic/x86 fallback multi-arg call,
    # shift_right's `if<compile>`, float, and masked are deferred and skip cleanly).
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


def test_mask_binary_and_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `mask_binary_and` (the mask-algebra enabler for range comparisons): `binary_and` on the
    # lane-bitmask register (sse/avx2), raw `&` on the native `__mmaskN` (avx512), `bool & bool`
    # (scalar), and a `mask<test>`/`mask<set>` bit-loop (generic). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_binary_and"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake-rockerlake"],
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
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake-rockerlake"],
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
    # not-yet-built `mask::lane::all_true` lane value (deferred). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_binary_or", "mask_binary_xor", "mask_binary_not"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake-rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"


def test_mask_true_builds(data_root: Path, machine_profiles_path: Path, tmp_path: Path) -> None:
    # `mask_true` (`m:=()`) builds on all targets now that `mask::lane::all_true` resolves: native
    # `__mmaskN` all-ones (avx512), `set1(mask_lane_all_true<T>())` on the lane-bitmask ISAs
    # (sse/avx2 — the previously-pruned path), `true` (scalar), generic bit-loop. The lane value
    # comes from the `::tsl::mask_lane_all_true<T>()` / `<T as TslMaskLaneValue>::all_true()`
    # substrate (all-ones bytes → int all-ones / float all-ones-bit NaN). Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_true"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake-rockerlake"],
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
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake-rockerlake"],
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
    # `details::popcount` (C++ `__builtin_popcountll` / Rust `count_ones`, returning a u32
    # count), cast to the `usize` result (`std::size_t`/`usize` — a count, not a mask). The
    # generic path is a `size_t` count loop over `mask<test>`. Exercises the new `usize`
    # signature kind + the popcount substrate. Both backends.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mask_population_count"],
        profiles=["scalar", "sse2", "avx2", "skylake", "icelake-rockerlake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics
    report = verify_project(tmp_path, result.rendered.verify)
    assert report.diagnostics == (), report.diagnostics
    assert report.commands, f"nothing verified; skipped={report.skipped}"
