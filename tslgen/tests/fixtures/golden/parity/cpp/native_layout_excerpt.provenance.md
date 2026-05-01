# Native Layout Excerpt Provenance

- Fixture: `tslgen/tests/fixtures/golden/parity/cpp/native_layout_excerpt.hpp`
- Source evidence: `frozen/out/tsl/tsl_native.hpp`
- Evidence ranges:
  - `frozen/out/tsl/tsl_native.hpp:1-30` for selected includes and support macros.
  - `frozen/out/tsl/tsl_native.hpp:147-167` for scalar/AVX2 extension tags and `simd` primary declaration evidence.
  - `frozen/out/tsl/tsl_native.hpp:720-725` for `detail::reg_param` evidence.
- Capture method: redesign-owned golden text derived from selected frozen evidence.
- Capture date: 2026-05-01.
- Parity level: semantic parity with redesign-owned exact golden output.
- Runtime dependency on `frozen/`: none.
- Known limitations: no scalar specializations, wrappers, intrinsic bodies, generic layout, CMake sidecars, or full-header byte-for-byte parity.
