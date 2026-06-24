# TSLc Param Types Layout Contract Review

You are reviewing a focused follow-up that makes `param_types` a consumed typed
value-test layout contract.

## Scope

`param_types:` entries are promoted into catalog `ParamTypeRule` values, schema
validated, and consumed by value-test pointer-layout planning for mask
representation load/store tests.

This slice deliberately does **not** change generated wrapper signatures,
overload rendering, or public backend ABI. Renderers still consume
`ValueTestCasePlan` storage fields; they do not inspect `param_types`.

## Files To Review

- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/value_tests/param_layouts.py`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tslc/src/tslc/value_tests/patterns.py`
- `tslc/src/tslc/value_tests/render_cpp.py`
- `tslc/tests/test_catalog_tests.py`
- `tslc/tests/test_value_test_planning.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`

## Review Questions

- Are `param_types` rules typed catalog facts rather than loose dictionaries or
  renderer-side string inspection?
- Does validation catch malformed conditions, unknown params/attrs, invalid
  values, duplicate rules, and empty type expressions?
- Does value-test planning actually consume the promoted rules, especially for
  `packed=false` mask representation storage?
- Is the resolver intentionally narrow, avoiding a broad type-expression engine
  or public ABI change?
- Do C++ renderers format only `ValueTestCasePlan.target_base_spelling` /
  `expected_type_tag` facts instead of rediscovering source layout?

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_tests.py
./verify.sh
```

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should cite concrete files/lines and separate
first-slice resolver limitations from actual boundary violations.
