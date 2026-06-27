# Prompt: Add C++ SVE Mask-To-Vector Coverage

Implement the next narrow C++ SVE mask slice after mask conversions.

## Context

Current C++ SVE value-test coverage includes scalable value, masked value,
mask-result, masked mask-result, mask-logic, mask-constant, and mask-conversion
cases. `to_integral` and `to_mask` are now identity conversions for SVE because
the extension declares `integral_mask_type_policy kind "same_as_mask_type"`.

Evidence collected during the mask-conversion slice:

- `./dev.sh explain --primitive to_vector --profile sve --type ui32 --backend cpp --extension sve`
  reports that `to_vector<sve, ui32>` is not selected because the primitive
  declares no implementation on the `sve` chain.
- `mov<sve, ui32> [mask=zero]` compiles and lowers through existing typed
  primitive calls.
- `set1<sve, ui32>` compiles and lowers to `svdup_n_u32(value)`.

## Goal

Add the smallest honest C++ SVE implementation and value-test support for
`to_vector` (`v:=m`) without adding primitive-name or extension-name compiler
branches.

## Expected Design Shape

- Prefer a source-owned SVE implementation that composes existing typed
  primitives, likely masked `mov` plus `set1` with
  `value<generation>(mask::lane::all_true)`.
- Add SVE-authored `to_vector` tests if existing tests are fixed-lane or do not
  target SVE.
- Add a scalable value-test case kind only if the existing planner cannot test
  `v:=m` through current scalable mask-input/value-result support.
- Reuse extension-owned `test_mask_from_bits` for native predicate input
  construction and runtime lane metadata for result checking.
- Keep Rust SVE unsupported.

## Evidence Commands

Start with:

```bash
./dev.sh explain --primitive to_vector --profile sve --type ui32 --backend cpp --extension sve
./dev.sh explain --primitive mov --profile sve --type ui32 --backend cpp --extension sve
./dev.sh explain --primitive set1 --profile sve --type ui32 --backend cpp --extension sve
./dev.sh dump --stage selection --primitive to_vector --profile sve --type ui32 --backend cpp --extension sve --format text
```

After implementation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
./dev.sh explain --primitive to_vector --profile sve --type ui32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-to-vector ./dev.sh test --profiles sve --primitives to_vector --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'test_scalable_sve_to_vector|sve_mask_from_bits|to_vector<Vec>|mov_maskz|svdup_n' /tmp/tslc-sve-mask-to-vector/cpp/tests/values_sve.cpp /tmp/tslc-sve-mask-to-vector/cpp/include/tsl_sve.hpp
./dev.sh ratchet
git diff --check
```

## Guardrails

- Do not add compiler-side branches on `to_vector`, `sve`, or `cpp`.
- Do not use `array_for<simd<T, sve>>` or fixed `vector::length`.
- Renderers must consume already-decided `ValueTestCasePlan` data only.
- If the source implementation requires a new typed TSIL capability, stop and
  document that as the next planning step instead of adding raw text repair.
