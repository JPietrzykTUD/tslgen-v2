# TSLc Value-Test Plan Boundary Review

## Accepted State

The active implementation line is `tslc/`. The prior `tslgen/` milestone
history is retained only as history. Read the active handoff before reviewing:

- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/review-checklist.md`

## Review Target

Review the completed value-test planning boundary slice. The implementation
should keep `tslc` primitive-agnostic by moving value-test shape classification
out of `tslc.render.tests_project` and into typed planning under
`tslc.value_tests`.

## Scope

- Verify `tslc.value_tests` owns catalog/lowered-shape classification and emits
  typed value-test plans.
- Verify C++ and Rust value-test renderers consume plans and do not inspect the
  catalog or classify primitives.
- Verify `source_primitive_name` preserves authored test lookup across emitted
  wrapper-name splits.
- Verify harness helper discovery is signature-driven rather than fixed to
  source primitive names.
- Verify diagnostics are surfaced through render/project results without making
  ordinary non-harness generation noisy.

## Out Of Scope

- Do not add new value-test shapes.
- Do not rewrite `tsldata` test metadata.
- Do not broaden Rust value-test parity.
- Do not split `tslc.value_tests.planner` unless a blocking review finding
  requires it; record it as a follow-up if it remains cohesive but near the
  size guardrail.

## Required Validation

Run or inspect results for:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_tests.py
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
python -m pytest -q tslc/tests/test_build_verify.py::test_generated_profiles_build
git diff --check
```

If the compiler preflight is blocked by sandbox cache permissions, rerun the
pytest command with approval rather than treating it as an implementation
failure.

## Expected Output

Return a review verdict: `Accept`, `Accept With Follow-Ups`, `Needs Revision`,
or `Return To Planner`.

Lead with findings ordered by severity and include file/line references. If
accepted, name any follow-ups. Do not implement changes during review.

## Stop Rule

Do not start another implementation milestone. The next action after this
review is either a focused revision prompt or the next concrete planning/review
prompt selected by the orchestrator.
