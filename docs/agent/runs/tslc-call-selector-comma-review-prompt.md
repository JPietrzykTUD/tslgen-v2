# TSLc Call Selector Comma Review

## Scope Under Review

Review the TSIL `call<...>` selector migration from whitespace-separated
attribute clauses to comma-separated clauses.

The intended final state:

- `call<primitive=NAME>(...)` remains unchanged.
- `call<primitive=NAME[TypeArgs...]>(...)` remains unchanged.
- `call<primitive=NAME, attrs[...]>(...)` is the accepted attribute form.
- `call<primitive=NAME[TypeArgs...], attrs[...]>(...)` is the accepted
  type-argument plus attribute form.
- The old `call<primitive=NAME attrs[...]>(...)` spelling is rejected.
- Primitive TSIL data under `tsldata/primitives` no longer uses the old
  whitespace-separated `attrs[...]` clause.

## Review Checklist

Use `docs/agent/review-checklist.md`. Pay special attention to:

- `parse_call_selector(...)` keeps syntax ownership only and does not take on
  dependency extraction, attribute evaluation, primitive selection, or rendering;
- bracketed type arguments remain attached to the primitive reference, not a
  separate selector clause;
- `attrs[...]` entries inside the bracket remain comma-separated and preserve
  raw values for later evaluation;
- the old whitespace-separated form is rejected by tests;
- the corpus migration is mechanical and does not alter call payloads or
  non-call TSIL body structure;
- dependency extraction and call lowering still consume the shared parser.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_tsil_scan.py
python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_masked_value_ops_build tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
git diff --check
env TSLC_VERIFY_WORKERS=1 ./verify.sh
```

Recommended source-boundary scan:

```bash
rg -n 'call<primitive=[^>,\n]*(\[[^\]]*\])?\s+attrs\[' tsldata/primitives tslc/tests
```

The scan should return no hits.

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
