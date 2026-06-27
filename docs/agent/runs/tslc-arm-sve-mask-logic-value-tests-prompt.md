# Prompt: Add C++ SVE Mask-Logic Value Tests

Implement the next narrow C++ SVE value-test slice after
`scalable_masked_mask_result`.

## Context

Accepted so far:

- C++ `simd<T, sve>` is selected, lowered, rendered, built, and executed
  through QEMU.
- `scalable_golden` covers authored all-vector value-result cases.
- `scalable_masked` covers native predicate inputs for masked value-result
  cases.
- `scalable_mask_result` covers unmasked all-vector predicate-result cases.
- `scalable_masked_mask_result` covers masked comparison cases such as
  `equal[mask=zero]` with shape `m:=(m,v,v)`.
- SVE runtime lane counts, predicate construction, and predicate checks are
  source-owned through `Extension.test_runtime_lanes`,
  `Extension.test_mask_from_bits`, and `Extension.test_mask_check`.
- Rust SVE remains unsupported.

Remaining gap:

Mask-logic primitives such as `mask_binary_and` have shape `m:=(m,m)`. They
lower and compile for SVE, but native scalable value tests need to construct
multiple `svbool_t` input predicates and check the native predicate result
without using fixed `array_for<Vec>` or packed integral-mask assumptions.

## Goal

Add the smallest honest C++ SVE value-test support for mask-logic cases.

The implementation must remain primitive- and extension-agnostic: no
production branches on names like `mask_binary_and`, `sve`, or `cpp`.

## Design Constraints

- Use typed facts: result kind `m`, all-mask parameters, scalable extension
  metadata, runtime lane counts, and backend case-kind support.
- Reuse the existing extension-owned predicate construction/check metadata.
- Do not use `array_for<simd<T, sve>>` or fixed `vector::length`.
- Do not inspect the catalog from renderers.
- Keep Rust SVE unsupported.

## Likely Implementation Shape

- Add a case kind such as `scalable_mask_logic`.
- Extend the mask-logic pattern, or introduce a narrow scalable mask-logic
  pattern, for result kind `m` with all `m` parameters.
- Render each authored mask input through `test_mask_from_bits`, call the
  primitive, and compare the result through `test_mask_check`.
- Prove the shape on `mask_binary_and` before broadening.

## Evidence Commands

Start by inspecting current behavior:

```bash
./dev.sh explain --primitive mask_binary_and --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-logic-before ./dev.sh test --profiles sve --primitives mask_binary_and --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask_binary_and|check_sve_mask_bits|sve_mask_from_bits|mask_a & mask_b' /tmp/tslc-sve-mask-logic-before/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-logic-before/cpp/include/tsl_sve.hpp
```

After implementation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-logic ./dev.sh test --profiles sve --primitives mask_binary_and --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask_binary_and|check_sve_mask_bits|sve_mask_from_bits|mask_a & mask_b' /tmp/tslc-sve-mask-logic/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-logic/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

## Expected Output

- Native C++ SVE value cases for mask-logic operations.
- Continued typed separation: predicate construction/checking comes from
  extension-owned metadata and test helpers; renderers only format plans.
- Updated docs/current-state with validation results and the next prompt.
