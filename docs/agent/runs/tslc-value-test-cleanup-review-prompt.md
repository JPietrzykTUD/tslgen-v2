# TSLc Value-Test Cleanup Review

## Accepted State

The active implementation line is `tslc/`. The prior `tslgen/` milestone
history is retained only as history. Read the active handoff before reviewing:

- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/review-checklist.md`

## Review Target

Review the focused cleanup after the value-test planning boundary slice. The
cleanup should answer the two observed smells:

- C++ value-test rendering must not carry Rust literal-formatting logic.
- `tslc.value_tests.planner` must not be a new monolith.

## Scope

- Verify `tslc.value_tests.planner` is orchestration-only.
- Verify harness discovery lives in `tslc.value_tests.harness`.
- Verify typed pattern matching lives in `tslc.value_tests.patterns`.
- Verify render-ready case construction lives in `tslc.value_tests.case_plans`.
- Verify literal spelling lives in `tslc.value_tests.literals` and is imported
  by the C++/Rust renderers.
- Verify the plan-kind names used for vector-array and mask-vector cases are
  typed shape names, not source primitive names.
- Verify the added architecture guard would fail if Rust literal code returns
  to the C++ renderer or planner grows back past the current boundary.

## Out Of Scope

- Do not add new value-test shapes.
- Do not broaden Rust value-test parity.
- Do not change `tsldata` test metadata.
- Do not split `case_plans.py` unless review finds a concrete blocker; record
  it as the next cleanup if it remains only a size-risk follow-up.

## Required Validation

Run or inspect results for:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_tests.py
python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
python -m pytest -q tslc/tests/test_build_verify.py::test_generated_profiles_build
git diff --check
```

## Expected Output

Return a review verdict: `Accept`, `Accept With Follow-Ups`, `Needs Revision`,
or `Return To Planner`.

Lead with findings ordered by severity and include file/line references. If
accepted, name any follow-ups. Do not implement changes during review.

## Stop Rule

Do not start another implementation milestone. The next action after this
review is either a focused revision prompt or the next concrete planning/review
prompt selected by the orchestrator.
