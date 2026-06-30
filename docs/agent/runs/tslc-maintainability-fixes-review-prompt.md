# TSLc Maintainability Fixes Review Prompt

## Accepted State

The active codebase is `tslc/`. The preceding run applied the maintainability
fixes from the TSLc design review: explicit backend support, extension metadata
promotion, shared TSIL region descriptors, value-test case-kind capabilities,
verifier scratch-path cleanup, scalar type-order centralization, and the raw-text
backend constraint documentation.

## Read First

- `AGENTS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `tslc/CHARTER.md`

## Review Scope

Review only the maintainability-fix batch in `tslc/`, `tsldata/` if touched,
and the workflow docs updated for this handoff.

Focus on:

- Backend support is explicit and inherited support still works.
- Extension metadata is typed and schema validation reports backend metadata
  typos without turning inert metadata into compiler semantics.
- TSIL keyword descriptors are a single neutral source for scan/lower/validation
  registration.
- Value-test case-kind registration prevents renderer dispatch from inventing
  unknown case kinds.
- Build verification no longer writes verifier-owned Zig caches under `/tmp`.
- Scalar type default ordering is catalog-owned.
- Raw-text backend limitations are documented accurately.

## Out Of Scope

- Do not add new primitive semantics, backend semantics, TSIL syntax, or value
  test case kinds.
- Do not rework renderer architecture beyond reviewing this batch.
- Do not touch `tslgen/`, `tslgenold/`, or `frozen/`.

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

Return a review verdict: `Accept`, `Accept With Follow-Ups`, `Needs Revision`,
`Return To Planner`, or `Reject`.

Lead with findings ordered by severity and include file/line references. If
accepted, identify the next concrete prompt to create. If revision is needed,
name the exact blocking issues and files in scope.

## Stop Rule

This is a read-only review prompt. Do not implement fixes unless a later prompt
explicitly assigns a focused revision task.
