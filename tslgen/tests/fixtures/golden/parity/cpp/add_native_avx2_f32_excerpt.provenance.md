# Add Native AVX2 F32 Excerpt Provenance

- Fixture: `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_f32_excerpt.hpp`
- Source evidence:
  - `frozen/out/tsl/tsl_native.hpp`
  - `tsldata/primitives/arithmetic/fundamental.tsl`
  - `tsldata/detail/lang/types/types_cpp.tsl`
- Evidence ranges:
  - `frozen/out/tsl/tsl_native.hpp:24337-24355` for `add_binary<simd<float, avx2>>` and `_mm256_add_ps(left, right)`.
  - `tsldata/primitives/arithmetic/fundamental.tsl:77-80` for the active `avx2/f?` `emit_return(intrin_compose<add>(left, right));` source.
  - `tsldata/detail/lang/types/types_cpp.tsl:10` for the selected local `f32` to `float` C++ spelling.
- Capture method: redesign-owned golden text derived from selected frozen and current-corpus evidence.
- Capture date: 2026-05-01.
- Parity level: semantic parity with redesign-owned exact golden output.
- Runtime dependency on `frozen/`: none.
- Known limitations: no broad translation-map evaluation, integer intrinsic suffix inference, AVX/SSE/AVX512 matrix generation, masks, generic loop-backed add, CMake sidecars, compiler invocation, or full-header byte-for-byte parity.
