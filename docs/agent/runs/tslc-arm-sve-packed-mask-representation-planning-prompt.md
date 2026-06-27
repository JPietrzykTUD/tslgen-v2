# Prompt: C++ SVE Packed Mask Representation Planning

Plan the next C++ SVE mask-representation slice after unpacked
`store_mask_repr packed=false` started passing through QEMU.

## Context

Current C++ SVE coverage includes scalable value, masked value, mask-result,
masked mask-result, mask-logic, mask-constant, mask-conversion, mask-to-vector,
and unpacked mask-store cases. Rust SVE remains unsupported because stable Rust
stdarch does not expose the required SVE API in this environment.

The latest completed slice:

- changed SVE `store_mask_repr packed=false` to compose
  `to_vector[MaskVec]` with `store[MaskVec]`;
- added `scalable_mask_store` planning and C++ rendering for unpacked storage;
- passed C++ SVE `store_mask_repr` value tests through QEMU;
- intentionally left `packed=true` unresolved.

Remaining evidence:

- `store_mask_repr packed=true` still uses fixed
  `value<generation>(vector::length)` and `mask<test>` on native predicates.
- `load_mask_repr packed=true` has the same fixed-lane/native-predicate
  tension.
- SVE declares `integral_mask_type_policy kind "same_as_mask_type"`, so
  `typename Vec::imask_type` is the native predicate type, not an ordinary
  scalar packed integer.

## Goal

Decide and implement the smallest honest next step for C++ SVE packed mask
representation memory.

The acceptable outcomes are:

- a typed source/compiler contract that makes packed SVE predicate load/store
  executable and value-testable through QEMU; or
- an explicit deferred-support diagnostic/coverage classification for packed
  SVE mask representation, with unpacked paths remaining green.

## Questions To Answer

- What should `packed=true` mean when a scalable extension declares
  `imask_type` as the same native predicate type as `mask_type`?
- Is there an SVE ACLE operation or source-owned helper shape that can load and
  store that predicate representation without fixed lanes or guessed byte
  layout?
- Should packed SVE mask representation be unsupported for now, while
  `packed=false` remains the source-owned interoperable representation?
- If support is added, what typed metadata belongs in `tsldata` and what
  render-ready values should the value-test planner carry?
- If support is deferred, where should the diagnostic or coverage reason live
  so it is visible and deterministic rather than a silent skip?

## Scope

- Work only on C++ SVE packed mask representation unless the evidence proves a
  tiny shared helper is needed.
- Keep renderers as formatters of `ValueTestCasePlan` values.
- Do not add compiler branches on primitive names such as `store_mask_repr` or
  `load_mask_repr`.
- Do not add extension-name branches for `sve`; use typed extension metadata
  and lowered facts.
- Do not manufacture a fixed lane count for scalable vectors.
- Do not assume `svbool_t` has a portable byte layout or pointer storage shape
  without source-owned evidence.

## Evidence Commands

Start with:

```bash
./dev.sh explain --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve
./dev.sh explain --primitive load_mask_repr --profile sve --type ui32 --backend cpp --extension sve
./dev.sh dump --stage segments --primitive store_mask_repr --profile sve --type ui32 --backend cpp --extension sve --format text
./dev.sh dump --stage segments --primitive load_mask_repr --profile sve --type ui32 --backend cpp --extension sve --format text
```

If you add executable support, validate with:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-packed-mask-repr ./dev.sh test --profiles sve --primitives store_mask_repr,load_mask_repr --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
./dev.sh ratchet
git diff --check
```

If you defer support, validate the diagnostic/coverage path with the narrowest
unit and CLI checks that prove the unsupported case is explicit and stable.

## Expected Output

- A concrete design decision for packed SVE mask representation.
- Either executable C++ SVE packed mask load/store coverage, or an explicit
  deterministic deferred-support classification.
- Updated ADR/current-state/handoff docs.
- A next-run prompt for the following ARM/SVE coverage slice.
