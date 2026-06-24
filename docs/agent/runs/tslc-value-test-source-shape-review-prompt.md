# TSLc Value-Test Source Shape Review Prompt

You are reviewing the `tslc` value-test source-shape cleanup.

## Required Reading

- `AGENTS.md`
- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/design-decisions.md` ADR-085

## Scope To Review

This slice changes authored primitive value tests under `tsldata/primitives`:

- source tests use required semantic `tags [...]`;
- source tests no longer use `test_name`, `lane_set`, or `lanes`;
- source `lane_count` remains only as an explicit escape hatch;
- catalog promotion derives `TestCase.name` and inferred `TestCase.lanes`;
- duplicate derived case names are catalog errors;
- value-test render function names no longer hide source duplicates behind an
  source-order index.

Primary files:

- `tslc/src/tslc/catalog/test_cases.py`
- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tslc/tests/test_catalog_tests.py`
- `tslc/tests/test_value_test_planning.py`
- `tsldata/primitives/**/*.tsl`

## Review Questions

- Does the new source shape stay primitive- and extension-agnostic?
- Are semantic facts owned once, or did naming/lane inference move duplication
  somewhere else?
- Is `lane_count` genuinely narrow, or does it preserve the old authored
  `lanes` habit under a new name?
- Are derived names deterministic, readable, and sufficiently tied to typed
  axes?
- Are duplicate derived names diagnosed before rendering?
- Is lane-count inference conservative for memory, mask-only, reduction,
  broadcast, and representation-change cases?
- Do renderers still consume typed plans rather than inferring source semantics?
- Are corpus tags semantic enough to support future coverage audits?

## Suggested Evidence Commands

```bash
rg -n 'test_name|lane_set|\\blanes\\s+[0-9]+' tsldata/primitives tslc/src/tslc tslc/tests
rg -n 'lane_count' tsldata/primitives
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
python -m pytest -q --basetemp=/tmp/tslc-pytest-value-build tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_build_verify.py
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_determinism.py
env TSLC_VERIFY_WORKERS=1 ./verify.sh
```

## Expected Output

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with findings, ordered by severity. Include exact file/line references and
say which design principle is at risk for each finding. If accepted, note any
follow-up coverage-audit work separately from blocking defects.
