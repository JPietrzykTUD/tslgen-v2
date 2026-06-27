# Prompt: Add C++ SVE Mask-Constant Value Tests

Implement the next narrow C++ SVE value-test slice after
`scalable_mask_logic`.

## Context

Accepted so far:

- C++ `simd<T, sve>` is selected, lowered, rendered, built, and executed
  through QEMU.
- `scalable_golden` covers authored all-vector value-result cases.
- `scalable_masked` covers native predicate inputs for masked value-result
  cases.
- `scalable_mask_result` covers unmasked all-vector predicate-result cases.
- `scalable_masked_mask_result` covers masked comparison cases.
- `scalable_mask_logic` covers all-mask predicate operations such as
  `mask_binary_and`.
- SVE runtime lane counts, predicate construction, and predicate checks are
  source-owned through `Extension.test_runtime_lanes`,
  `Extension.test_mask_from_bits`, and `Extension.test_mask_check`.
- Rust SVE remains unsupported.

Remaining gap:

Mask constants such as `mask_false` and `mask_true` have shape `m:=()`. They
lower and compile for SVE, but native scalable value tests need to check the
resulting `svbool_t` predicate directly without fixed `array_for<Vec>` or a
packed integral mask representation.

## Goal

Add the smallest honest C++ SVE value-test support for mask-constant cases.

The implementation must remain primitive- and extension-agnostic: no
production branches on names like `mask_true`, `mask_false`, `sve`, or `cpp`.

## Design Constraints

- Use typed facts: result kind `m`, no parameters, scalable extension metadata,
  runtime lane counts, and backend case-kind support.
- Reuse the existing extension-owned predicate-check metadata.
- Do not use `array_for<simd<T, sve>>` or fixed `vector::length`.
- Do not inspect the catalog from renderers.
- Keep Rust SVE unsupported.

## Likely Implementation Shape

- Add a case kind such as `scalable_mask_constant`.
- Extend the existing no-parameter mask-result pattern, or introduce a narrow
  scalable mask-constant pattern, for result kind `m` with no parameters.
- Render the primitive call and compare the result through `test_mask_check`.
- Add source-owned SVE-authored tests if the current mask-constant cases are
  extension-specific to another substrate.
- Prove the shape on `mask_true` and/or `mask_false` before broadening.

## Evidence Commands

Start by inspecting current behavior:

```bash
./dev.sh explain --primitive mask_true --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-constant-before ./dev.sh test --profiles sve --primitives mask_true,mask_false --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask_(true|false)|check_sve_mask_bits|svptrue|svpfalse' /tmp/tslc-sve-mask-constant-before/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-constant-before/cpp/include/tsl_sve.hpp
```

After implementation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-constant ./dev.sh test --profiles sve --primitives mask_true,mask_false --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask_(true|false)|check_sve_mask_bits|svptrue|svpfalse' /tmp/tslc-sve-mask-constant/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-constant/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

## Expected Output

- Native C++ SVE value cases for mask constants.
- Continued typed separation: predicate checking comes from extension-owned
  metadata and test helpers; renderers only format plans.
- Updated docs/current-state with validation results and the next prompt.
