# Prompt: Add C++ SVE Masked Mask-Result Value Tests

Implement the next narrow C++ SVE value-test slice after
`scalable_mask_result`.

## Context

Accepted so far:

- C++ `simd<T, sve>` is selected, lowered, rendered, built, and executed
  through QEMU.
- `scalable_golden` covers authored all-vector value-result cases.
- `scalable_masked` covers native predicate inputs for masked value-result
  cases.
- `scalable_mask_result` covers unmasked all-vector predicate-result cases
  such as `equal`.
- SVE runtime lane counts, predicate construction, and predicate checks are
  source-owned through `Extension.test_runtime_lanes`,
  `Extension.test_mask_from_bits`, and `Extension.test_mask_check`.
- Rust SVE remains unsupported.

Remaining gap:

Masked comparison primitives, for example `equal[mask=zero]`, have shape
`m:=(m,v,v)`: they need both native predicate construction for the authored
input mask and native predicate checking for the result.

## Goal

Add the smallest honest C++ SVE value-test support for masked mask-result
cases.

The implementation must remain primitive- and extension-agnostic: no
production branches on names like `equal`, `less_than`, `sve`, or `cpp`.

## Design Constraints

- Use typed facts: result kind `m`, exactly one mask parameter, vector
  parameters, mask policy, scalable extension metadata, runtime lane counts,
  and backend case-kind support.
- Reuse the existing extension-owned predicate construction/check metadata.
- Do not use `array_for<simd<T, sve>>` or fixed `vector::length`.
- Do not inspect the catalog from renderers.
- Keep Rust SVE unsupported.

## Likely Implementation Shape

- Add a case kind such as `scalable_masked_mask_result`.
- Extend the masked pattern, or introduce a narrow pattern, for result kind
  `m` with parameter kinds like `m,v,v`.
- Render runtime-sized vector inputs, construct the native input predicate from
  authored mask bits, call the primitive, and compare the result through the
  render-ready mask-check expression.
- Prove the shape on `equal[mask=zero]` before broadening.

## Evidence Commands

Start by inspecting current behavior:

```bash
./dev.sh explain --primitive equal --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-masked-mask-result-before ./dev.sh test --profiles sve --primitives equal --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*equal_mask|check_sve_mask_bits|sve_mask_from_bits|svcmpeq_s32\\(mask' /tmp/tslc-sve-masked-mask-result-before/cpp/tests/values_sve.cpp /tmp/tslc-sve-masked-mask-result-before/cpp/include/tsl_sve.hpp
```

After implementation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-masked-mask-result ./dev.sh test --profiles sve --primitives equal --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*equal_mask|check_sve_mask_bits|sve_mask_from_bits|svcmpeq_s32\\(mask' /tmp/tslc-sve-masked-mask-result/cpp/tests/values_sve.cpp /tmp/tslc-sve-masked-mask-result/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

## Expected Output

- Native C++ SVE value cases for masked mask-result operations.
- Continued typed separation: predicate construction/checking comes from
  extension-owned metadata and test helpers, renderers only format plans.
- Updated docs/current-state with validation results and the next prompt.
