# Add Scalar Excerpt Provenance

- Fixture: `tslgen/tests/fixtures/golden/parity/cpp/add_scalar_excerpt.hpp`
- Source evidence:
  - `frozen/out/tsl/tsl_native.hpp`
  - `frozen/generator_specs/wrapper_shapes.yaml`
  - `tsldata/primitives/arithmetic/fundamental.tsl`
- Evidence ranges:
  - `frozen/out/tsl/tsl_native.hpp:805-810` for the primary `detail::add_binary` declaration shape.
  - `frozen/out/tsl/tsl_native.hpp:19433-19452` for `add_binary<simd<int32_t, scalar>>`.
  - `frozen/out/tsl/tsl_native.hpp:19513-19532` for `add_binary<simd<uint32_t, scalar>>`.
  - `frozen/out/tsl/tsl_native.hpp:39071-39075` for public `add<Vec>` wrapper delegation.
  - `frozen/generator_specs/wrapper_shapes.yaml:47-56` for the C++ `binary` wrapper parameter/return shape.
  - `tsldata/primitives/arithmetic/fundamental.tsl:2` for `prim<v:=(v,v)> add(left, right)`.
  - `tsldata/primitives/arithmetic/fundamental.tsl:27-31` for scalar `emit_return(left + right);`.
- Capture method: redesign-owned golden text derived from selected frozen and current-corpus evidence.
- Capture date: 2026-05-01.
- Parity level: semantic parity with redesign-owned exact golden output.
- Runtime dependency on `frozen/`: none.
- Known limitations: no native SIMD intrinsics, masks, generic loop-backed add, combined binary templates, broad overload policy, CMake sidecars, or full-header byte-for-byte parity.
