# Prompt: Add C++ SVE Mask-Result Value Tests

Implement the next narrow C++ SVE value-test slice after `scalable_masked`.

## Context

Accepted so far:

- C++ `simd<T, sve>` is selected, lowered, rendered, built, and executed
  through QEMU.
- `scalable_golden` covers authored all-vector value-result cases.
- `scalable_masked` covers native SVE predicate inputs for masked value-result
  cases such as `add[mask=zero]` and `add[mask=pass_through]`.
- SVE runtime lane counts are source-owned through `Extension.test_runtime_lanes`.
- SVE authored mask-bit construction is source-owned through
  `Extension.test_mask_from_bits` and rendered as a plan field.
- Rust SVE remains unsupported.

Remaining gap:

Mask-result all-vector primitives, such as comparisons, still lack native SVE
value cases. Existing fixed-lane mask checks cannot directly inspect `svbool_t`
without a typed predicate extraction/comparison boundary.

## Goal

Add the smallest honest C++ SVE value-test support for mask-result all-vector
cases.

The implementation must remain primitive- and extension-agnostic: no
production branches on names like `equal`, `less_than`, `sve`, or `cpp`.

## Design Constraints

- Use typed facts: result kind `m`, all-vector parameter kinds, scalable
  extension metadata, runtime lane counts, and backend case-kind support.
- Do not use `array_for<simd<T, sve>>` or fixed `vector::length`.
- Do not inspect the catalog from renderers.
- Prefer source-owned or typed helper facts for predicate comparison/extraction.
- Do not convert `svbool_t` to an integer unless a safe typed helper boundary is
  explicitly introduced.
- Keep Rust SVE unsupported.

## Likely Implementation Shape

- Add a case kind such as `scalable_mask_result`.
- Extend the generic all-vector mask-result pattern to plan this case only for
  scalable extensions and supporting backends.
- Add extension-owned metadata or a typed test helper expression for comparing
  an `svbool_t` result to authored expected lane bits.
- Render runtime-sized buffers for vector inputs like `scalable_golden`, call
  the primitive under test, then compare the native predicate with expected
  runtime lane activity.
- If the clean boundary needs more design than this slice allows, leave a
  diagnostic/follow-up rather than renderer-side guessing.

## Evidence Commands

Start by inspecting a comparison primitive:

```bash
./dev.sh explain --primitive equal --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-result-before ./dev.sh test --profiles sve --primitives equal --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*equal|svcmpeq|svbool_t|tsl::simd<.*tsl::sve>' /tmp/tslc-sve-mask-result-before/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-result-before/cpp/include/tsl_sve.hpp
```

After implementation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-result ./dev.sh test --profiles sve --primitives equal --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*equal|svcmpeq|svbool_t|tsl::simd<.*tsl::sve>' /tmp/tslc-sve-mask-result/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-result/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

## Expected Output

- Native C++ SVE value cases for mask-result all-vector operations.
- A typed helper or extension-owned metadata boundary for comparing native SVE
  predicates against authored expected lane activity.
- Updated docs/current-state with validation results and the next prompt.
