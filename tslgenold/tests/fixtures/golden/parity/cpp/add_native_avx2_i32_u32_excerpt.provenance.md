# Add Native AVX2 I32/U32 Excerpt Provenance

- Fixture: `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_i32_u32_excerpt.hpp`
- Source evidence:
  - `frozen/out/tsl/tsl_native.hpp`
  - `tsldata/primitives/arithmetic/fundamental.tsl`
  - `tsldata/detail/lang/types/types_cpp.tsl`
  - `tsldata/detail/lang/translate_cpp.tsl`
- Evidence ranges:
  - `frozen/out/tsl/tsl_native.hpp:24460-24477` for
    `add_binary<simd<int32_t, avx2>>` and `_mm256_add_epi32(left, right)`.
  - `frozen/out/tsl/tsl_native.hpp:24712-24729` for
    `add_binary<simd<uint32_t, avx2>>` and `_mm256_add_epi32(left, right)`.
  - `tsldata/primitives/arithmetic/fundamental.tsl:65-75` for the active
    `avx2/?i?` `intrin_compose<add, suffix=value<backend>(...)>` source.
  - `tsldata/detail/lang/types/types_cpp.tsl:4` for selected `s32` to
    `int32_t` spelling and `:8` for selected `u32` to `uint32_t` spelling.
  - `tsldata/detail/lang/translate_cpp.tsl:4-8` for backend type trait
    translation-map context; M47 does not evaluate those templates.
- Capture method: redesign-owned golden text derived from selected frozen and
  current-corpus evidence, with suffix and type spellings supplied by typed
  M45/M46 translation outputs.
- Capture date: 2026-05-04.
- Parity level: semantic parity with redesign-owned exact golden output.
- Runtime dependency on `frozen/`: none.
- Known limitations: no broad native rendering, no renderer-local suffix or
  type lookup, no AVX/SSE/AVX512 matrix generation, masks, generic loop-backed
  add, generated tests, CMake sidecars, compiler invocation, or full-header
  byte-for-byte parity.
