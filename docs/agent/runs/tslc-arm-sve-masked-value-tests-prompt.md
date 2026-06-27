# Prompt: Add C++ SVE Masked Value Tests

Implement the next narrow C++ SVE value-test slice after
`scalable_golden`.

## Context

Accepted so far:

- C++ `simd<T, sve>` is selected, lowered, rendered, built, and executed
  through QEMU.
- The first native scalable value-test case kind, `scalable_golden`, covers
  authored all-vector value-result cases such as unmasked `add`.
- SVE runtime lane counts are extension-owned through `test_runtime_lanes`,
  currently `cpp "svcntb() / sizeof({base_type})"`.
- `scalable_golden` initializes runtime-sized buffers, uses
  `tsl::load<Vec, false>` / `tsl::store<Vec, false>`, and avoids
  `array_for<simd<T, sve>>`.
- Review accepted the boundary after replacing the planner's hard-coded
  `backend_id == "cpp"` check with a backend case-kind capability check.
- Rust SVE remains unsupported.

Remaining gap:

For masked all-vector primitives and mask-result primitives, generated value
tests still prove only generic/fixed-size behavior. They do not yet create
native `tsl::simd<..., tsl::sve>` value checks for SVE predicates.

## Goal

Add the smallest honest C++ SVE value-test support for native predicate cases:

1. masked all-vector value-result cases, e.g. `add[mask=zero]` and
   `add[mask=pass_through]`;
2. if it fits the same typed boundary, mask-result all-vector cases such as
   comparisons;
3. otherwise leave mask-result cases as an explicit next prompt.

The implementation must remain primitive- and extension-agnostic: no production
branches on names like `add`, `equal`, or `sve`.

## Design Constraints

- Use typed facts: signature kinds, mask policy, parameter kinds,
  `Extension.mask_policy.kind`, `test_runtime_lanes`, and render-ready case
  plan fields.
- Do not use `array_for<simd<T, sve>>` or fixed `vector::length`.
- Do not inspect the catalog from renderers.
- Prefer source-owned helpers. If mask construction/extraction needs a helper,
  discover it by typed signature or add source-owned metadata; do not hard-code
  primitive names.
- Keep backend support capability-driven through `ValueTestBackendSupport`.
- Keep Rust SVE unsupported.

## Likely Implementation Shape

- Add one or two new case kinds, for example `scalable_masked` and maybe
  `scalable_mask_result`.
- Extend value-test planning from `_MaskedPattern` and/or `_GenericGoldenPattern`
  using scalable extension metadata, not extension names.
- For masked value-result cases, initialize runtime-sized input/expected
  buffers like `scalable_golden`; build a native predicate mask from authored
  mask bits without assuming a packed integral mask representation.
- Candidate SVE predicate construction strategy:
  - use ACLE predicates like `svwhilelt_b*` / lane-index comparisons only if
    the expression is source-owned or lives in a typed test helper fact;
  - avoid converting `svbool_t` to an integer unless the source declares a
    safe typed primitive for it.
- For mask-result cases, prefer storing/comparing masks through typed
  source-owned mask helpers. If that boundary is not ready, produce a planning
  diagnostic/follow-up instead of renderer-side guessing.

## Evidence Commands

Start by inspecting current behavior:

```bash
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-masked-before ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask|svadd_s32_[mz]|svbool_t|tsl::simd<.*tsl::sve>' /tmp/tslc-sve-masked-before/cpp/tests/values_sve.cpp
```

After implementation, prove native masked SVE value cases exist and run:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-masked ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_.*mask|svadd_s32_[mz]|svbool_t|tsl::simd<.*tsl::sve>' /tmp/tslc-sve-masked/cpp/tests/values_sve.cpp
./dev.sh ratchet
git diff --check
```

If mask-result cases are included, add a focused primitive such as a comparison
to the generated test command and assert that native SVE mask-result value
checks appear in the generated values file.

## Expected Output

- Native C++ SVE value cases for masked all-vector operations.
- Optional native C++ SVE value cases for mask-result operations, only if the
  typed predicate comparison boundary is clean.
- Clear typed diagnostics or a next prompt for scalable mask shapes still not
  covered.
- Updated docs/current-state with validation results and the next prompt.
