# TSLc Maintainability Fixes Focused Re-Review Prompt

## Accepted State

The active codebase is `tslc/`. The previous maintainability-fixes review
returned `Needs Revision` for two issues:

- extension schema validation still hardcoded backend block names;
- TSIL shell-validator descriptor ids could silently drift from the validator
  implementation map.

The follow-up revision addressed both issues.

## Read First

- `AGENTS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/agent/runs/tslc-maintainability-fixes-review-prompt.md`

## Focused Review Scope

Review only the focused revision after commit `cea28e1`:

- `tslc/src/tslc/catalog/validation/_schema_extensions.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/tests/test_catalog_validation.py`
- `tslc/src/tslc/catalog/validation/body_validation.py`
- `tslc/tests/test_tsil_scan.py`
- this handoff update and prompt

Verify:

- extension top-level allowed fields are composed from source metadata fields
  plus the support policy's backend ids;
- future supported backend ids can be admitted without editing the extension
  field list;
- declared TSIL shell-validator ids are checked against the implementation map
  and cannot silently disable validation;
- the revision did not add backend semantics, primitive semantics, generated
  outputs, or legacy dependencies.

## Validation To Check

Confirm or rerun as needed:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog.py \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_tsil_scan.py \
  tslc/tests/test_value_test_planning.py \
  tslc/tests/test_build_verify_config.py \
  tslc/tests/test_pipeline_structure.py \
  tslc/tests/test_render_model.py \
  tslc/tests/test_select_and_lower.py \
  tslc/tests/test_generation_conditionals.py \
  tslc/tests/test_determinism.py \
  tslc/tests/test_safety_contract.py \
  tslc/tests/test_lower_text.py
git diff --check
```

## Expected Output

Return a focused re-review verdict: `Accept`, `Accept With Follow-Ups`,
`Needs Revision`, `Return To Planner`, or `Reject`.

Lead with any findings ordered by severity and include file/line references. If
accepted, identify the next concrete prompt to create.

## Stop Rule

This is a read-only focused re-review prompt. Do not implement fixes unless a
later prompt explicitly assigns a focused revision task.
