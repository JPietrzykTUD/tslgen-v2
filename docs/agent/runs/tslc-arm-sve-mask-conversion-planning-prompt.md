# Prompt: Plan C++ SVE Mask Conversion Coverage

Plan the next narrow ARM/SVE value-test slice after C++ SVE mask constants.

## Context

Accepted C++ SVE value-test coverage now includes:

- `scalable_golden` for all-vector value-result cases;
- `scalable_masked` for masked value-result cases;
- `scalable_mask_result` for unmasked vector comparison results;
- `scalable_masked_mask_result` for masked comparison results;
- `scalable_mask_logic` for all-mask predicate operations;
- `scalable_mask_constant` for no-input mask constants.

SVE runtime lane counts, predicate construction, and predicate checks are
source-owned through `Extension.test_runtime_lanes`,
`Extension.test_mask_from_bits`, and `Extension.test_mask_check`. Rust SVE
remains unsupported.

The likely next mask gap is conversion between native predicates and scalar or
integral mask forms, for example `to_integral` / `to_mask`-style primitives.
Those may require source implementations before value tests can be planned, so
start with evidence instead of assuming a renderer-only change.

## Goal

Produce a concrete implementation plan for the next smallest SVE mask
conversion slice, preserving primitive- and extension-agnostic compiler
boundaries.

## Questions To Answer

- Which mask conversion primitives are selected, skipped, or absent for
  `profile=sve`, `backend=cpp`, and representative types such as `ui32`?
- Are the blockers missing source implementations, unsupported TSIL query
  shapes, missing extension test metadata, missing case-plan kinds, or C++
  renderer support gaps?
- Can the next slice be limited to value-test planning/rendering, or must it
  first add/repair `tsldata` SVE implementations?
- What typed facts should drive the shape: signatures, result/parameter kinds,
  runtime-lane metadata, mask construction/check metadata, and lowered
  specialization facts?
- What focused `dev.sh test` command would prove the next slice without
  broadening into all SVE mask semantics?

## Scope

- Use `./dev.sh explain` and `./dev.sh dump` as the primary evidence path.
- Do not add primitive-name, extension-name, or backend-name classifier
  branches to production compiler code.
- Do not invent packed SVE predicate representations in renderers.
- Keep C++ SVE as the target; Rust SVE remains out of scope.
- Keep the result as a plan unless the evidence shows a very small
  implementation-only follow-up is safe.

## Evidence Commands

Start with:

```bash
./dev.sh explain --primitive to_integral --profile sve --type ui32 --backend cpp --extension sve
./dev.sh explain --primitive to_mask --profile sve --type ui32 --backend cpp --extension sve
./dev.sh dump --stage selection --primitive to_integral --profile sve --type ui32 --backend cpp --extension sve --format text
./dev.sh dump --stage selection --primitive to_mask --profile sve --type ui32 --backend cpp --extension sve --format text
```

If one primitive is close enough to implement, validate the selected narrow
slice with:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_profile_rendering.py
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-mask-conversion ./dev.sh test --profiles sve --primitives CURRENT_ACTIVE_PRIMITIVE --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
./dev.sh ratchet
git diff --check
```

## Expected Output

- A concrete next implementation slice, with blockers categorized by typed
  source/compiler boundary.
- Updated current-state/handoff docs with evidence and a next execution prompt.
- No compiler-side source primitive or extension special cases.
