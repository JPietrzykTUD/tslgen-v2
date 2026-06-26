# TSLc Const Pointer And Array Parameter Review

You are reviewing the latest `tslc` slice for const-correct pointer and
array/lane-list parameter handling.

## Scope To Review

- `tslc/src/tslc/support_policy.py`
- `tslc/src/tslc/catalog/signatures.py`
- `tslc/src/tslc/lower/context.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/lower/region_handlers/calls.py`
- `tslc/src/tslc/backend/cpp.py`
- `tslc/src/tslc/backend/rust.py`
- `tslc/src/tslc/backend/cpp_translation.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/backend/translation.py`
- `tslc/src/tslc/backend/assets/tsl_core.hpp`
- `tslc/src/tslc/backend/assets/tsl_core.rs`
- `tslc/src/tslc/output/verify.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/value_tests/*rust*`
- `tslc/src/tslc/value_tests/*memory*`
- `tsldata/primitives/load_store/*.tsl`
- `tsldata/primitives/memory/copy.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `verify.sh`
- focused tests under `tslc/tests`

## Design Intent

- `ptr` and `ptr+` are mutable pointer signature kinds.
- `cptr` and `cptr+` are read-only pointer signature kinds.
- `s[]` and `lanes<s>` parameters are read-only generated wrapper parameters.
- `s[]` results remain owned return values.
- Rust call lowering borrows array/lane-list call arguments from typed catalog
  signature positions, not from source-text guesses.
- TSIL source remains backend-neutral: source writes
  `call<primitive=from_array>(result)`, and lowering/rendering decide whether
  Rust needs `&result`.
- Lowering must not branch on `backend_id`; backend-specific borrowed argument
  spelling belongs to the syntax dialect.
- The official verifier should avoid shared or workspace-mounted generated
  build scratch that makes ambient `zig c++` fail nondeterministically.
- Renderers should not infer primitive semantics by name.

## Review Questions

1. Is pointer mutability consistently represented by typed signature kinds
   rather than ad hoc pointer casts or primitive names?
2. Do C++ and Rust distinguish parameter types from result/value types for
   array-like terms?
3. Does Rust call borrowing preserve nested render placeholders and unsafe
   framing without raw text rewrites?
4. Are read-only source buffers using `as_ptr()` and mutable outputs still
   using `data()`/`as_mut_ptr()`?
5. Did the change preserve existing value-test planning boundaries, with
   renderers formatting plans only?
6. Does build verification keep side effects in the verification boundary while
   avoiding shared cache/build-tree interference?
7. Are the docs and tests in line with the main design principles:
   primitive/extension agnostic, KISS, typed boundaries, DRY ownership,
   semantic logic before rendering, diagnostics over silent behavior,
   deterministic output, and maintainability?

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_lane_lists.py tslc/tests/test_generation_conditionals.py tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_generation_conditionals.py tslc/tests/test_lane_lists.py
python -m pytest -q --basetemp=/tmp/tslc-value-review tslc/tests/test_value_tests.py
python -m pytest -q --basetemp=/tmp/tslc-build-review tslc/tests/test_build_verify.py::test_to_from_array_roundtrip_builds tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_gather_scatter_builds tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_build_verify.py::test_masked_memory_build tslc/tests/test_build_verify.py::test_memory_cp_builds tslc/tests/test_build_verify.py::test_set_builds
./verify.sh
```

## Expected Verdict

Return `Accept` only if the typed boundary is coherent and the validation
passes. Return `Needs Revision` for any renderer-side semantic inference,
array-result borrow regression, stale mutable read pointer, or generated
C++/Rust compile failure.
