# Review Prompt: TSLc Backend Loop Surface Cleanup

You are reviewing the completed `tslc` TSIL loop source cleanup.

## Scope

The slice harmonizes emitted loop syntax and removes the standalone unroll
directive from current primitive TSIL:

- `loop<range>(var, start, end, step) { ... }` becomes
  `loop<backend>(var, start, end, step) { ... }`;
- paired `loop<unroll>(count)` plus `loop<range>(...) { ... }` becomes
  `loop<backend, unroll>(...) { ... }`;
- `loop<generation>(...) { ... }` remains the generation-time expansion loop.

## Files To Review

- `tslc/src/tslc/lower/region_handlers/control.py`
- `tslc/src/tslc/ir/scan.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/detail/lang/translate_c17.tsl`
- `tsldata/primitives/**/*.tsl`
- `tslc/tests/test_lane_lists.py`
- `tslc/tests/test_tsil_scan.py`
- `tslc/tests/test_tsil_statement_terminators.py`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Review Questions

- Does `LoopLowerer` keep the semantic boundary simple: generation loops expand
  in the generator, backend loops render target loops, and unroll remains an
  attached optional hint?
- Does `loop<backend, unroll>` avoid making known trip count imply unroll intent
  for ordinary `loop<backend>` loops?
- Does symbolic-count unroll intent, such as sized-vector `LANES`, preserve the
  normal backend loop instead of dropping a specialization?
- Are old source spellings rejected or guarded without adding compatibility
  wrappers around poor abstractions?
- Are backend templates presentation-only (`loop_backend`,
  optional `loop_backend_unroll`) and free of TSIL parsing or semantic repair?
- Does the corpus migration preserve source intent and avoid accidental broad
  rewrites beyond loop spelling?
- Are tests proportionate: direct lowerer behavior, scanner shape, corpus guard,
  generated-build/value-test coverage?
- Do docs describe the current source surface without rewriting historical
  milestone evidence as if it had always been true?

## Validation Already Run

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_tsil_scan.py::test_backend_loop_unroll_selector_captures_block tslc/tests/test_tsil_statement_terminators.py::test_primitive_tsil_uses_backend_loop_surface
python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_masked_value_ops_build tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_cast_reinterpret_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
env TSLC_VERIFY_WORKERS=1 ./verify.sh
git diff --check
```

Results: focused loop tests passed with 17 tests; affected non-build tests
passed with 60 tests; generated-build/value tests passed with 6 tests; full
`verify.sh` passed with 178 non-build tests and 53 generated-build tests; final
diff check passed.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, or `Needs Revision`.

Treat any production use of `loop<range>`, standalone source `loop<unroll>`,
`loop_range`, or `loop_unroll` as a likely blocker unless it is intentional
negative-test or historical-documentation text.
