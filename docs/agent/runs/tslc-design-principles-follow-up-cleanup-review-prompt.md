# TSLc Design-Principles Follow-Up Cleanup Review

## Accepted State

The active implementation line is `tslc/`. The prior `tslgen/` milestone
history is retained only as historical evidence. Read first:

- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/review-checklist.md`
- `docs/agent/runs/tslc-design-principles-review-prompt.md`

## Review Target

Review the focused cleanup that addresses the actionable findings from the TSLc
design-principles review.

## Scope

The cleanup should only address:

- per-authored-case value-test diagnostics, so one unsupported `tests:` case is
  not hidden by a sibling case that plans successfully;
- explicit value-test warning visibility through `GenerationRequest`,
  `generate_project(...)`, and the CLI `--value-test-warnings` flag, without
  tying warnings to `test_harness`;
- a narrow lowerer maintainability split that moves raw TSIL text tokenization
  out of `lowerer.py` without changing lowering behavior.

## Files To Review

- `tslc/src/tslc/value_tests/planner.py`
- `tslc/src/tslc/pipeline.py`
- `tslc/src/tslc/api.py`
- `tslc/src/tslc/cli.py`
- `tslc/src/tslc/render/project.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/lower/raw_text.py`
- `tslc/tests/test_value_test_planning.py`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Review Questions

- Does `ValueTestPlanner` warn per unsupported authored case, including cases
  filtered out by backend-supported case kinds?
- Are value-test warnings surfaced only when explicitly requested, while
  duplicate-function errors remain visible regardless?
- Is `test_harness` still limited to dependency closure and harness discovery
  diagnostics, not used as a proxy for value-test warning visibility?
- Did the raw-text extraction preserve behavior and avoid creating a new
  lowering facade or semantic parser?
- Did the tests cover the regression without overfitting production behavior to
  fixture primitive names?

## Validation Already Run

```bash
python -m pytest -q tslc/tests/test_value_test_planning.py
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_tsil_scan.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
python -m pytest -q tslc/tests/test_catalog_validation.py tslc/tests/test_catalog_tests.py tslc/tests/test_value_tests.py tslc/tests/test_coverage.py
git diff --check
```

Results: focused value-test planning passed with 9 tests; the main review
slice passed with 75 tests; the catalog/value/coverage batch passed with 30
tests; compileall and diff check passed.

## Expected Output

Return a review verdict: `Accept`, `Accept With Follow-Ups`, `Needs Revision`,
or `Return To Planner`.

Lead with findings ordered by severity and include file/line references. If
accepted, name any follow-ups.

## Stop Rule

Do not start another implementation milestone. The next action after this
review is either a focused revision prompt or the next concrete planning/review
prompt selected by the orchestrator.
