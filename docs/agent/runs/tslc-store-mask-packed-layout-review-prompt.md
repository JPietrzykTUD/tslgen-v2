# TSLc Store-Mask Packed Layout Review Prompt

You are reviewing a focused follow-up to the value-test completeness slice in
`tslc/`. Use `docs/agent/review-checklist.md` and the main design principles
from `AGENTS.md`.

## Context

`store_mask_repr` carries a typed `packed` axis:

- `packed=true` stores the compact integral mask word;
- `packed=false` stores one unsigned lane word per vector lane.

The previous source/tests exercised only packed storage in the C++ AVX2 value
gate. This follow-up makes the unpacked layout explicit and testable.

## Files To Review

- `tsldata/primitives/load_store/store.tsl`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tslc/src/tslc/value_tests/case_helpers.py`
- `tslc/src/tslc/value_tests/render_cpp.py`
- `tslc/tests/test_value_tests.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Review Focus

Prioritize findings where:

- `store_mask_repr` semantics depend on primitive or extension names instead of
  typed signature/axis facts;
- `packed=false` layout is guessed in the renderer instead of carried by the
  typed value-test plan;
- the source body silently relies on the undocumented `vector::mask_underlying_t`
  spelling;
- the C++ renderer performs semantic classification instead of formatting
  `ValueTestCasePlan` fields;
- `packed=false` tests can disappear while the full-corpus coverage gate stays
  green;
- the narrow follow-up grows into broader naming-policy or overload rendering
  changes.

Also note the deliberate follow-up: `load_mask_repr` still contains the older
`vector::mask_underlying_t` source spelling and should be handled in a separate
typed layout cleanup.

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete
python -m pytest -q tslc/tests/test_value_tests.py
./verify.sh
```

Architecture scan:

```bash
rg -n 'primitive_name ==|source_primitive_name ==|case\\.call_name ==|_is_.*primitive|_is_.*case' tslc/src/tslc/value_tests tslc/src/tslc/render
```

Expected result: no new production value-test branches on source primitive or
extension identities. The `store_mask_repr` source name may appear in tests,
documentation, and source data.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should include concrete file/line references
and distinguish blocking design issues from acceptable prototype debt.
