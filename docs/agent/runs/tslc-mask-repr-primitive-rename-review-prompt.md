# TSLc Mask Representation Primitive Rename Review

You are reviewing a focused naming cleanup on top of the value-test
completeness and store-mask packed-layout slices.

## Scope

The source primitives formerly named `load_mask` and `store_mask` are now
`load_mask_repr` and `store_mask_repr`.

This is intentionally a source-data naming fix, not a generated-name policy
change. Emitted masked overload names such as `load_mask`, `load_maskz`, and
`store_mask` still come from the mask-policy suffix rules for ordinary
`load`/`store` overloads.

## Files To Review

- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/store.tsl`
- `tsldata/detail/templates.tsl`
- `tslc/tests/test_value_tests.py`
- `tslc/tests/test_build_verify.py`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/design-decisions.md`

## Review Questions

- Does the rename remove the source/emitted-name collision without changing
  emitted-name splitting semantics?
- Do tests and docs distinguish source primitives (`*_mask_repr`) from emitted
  masked overload names (`*_mask`, `*_maskz`) clearly?
- Did the change avoid touching unrelated local variables or implementation
  logic, especially the local `store_mask` variable in `pack_expand.tsl`?
- Are value-test expectations using derived source test names consistently?
- Does this preserve the design rule that renderers consume already-decided
  plan/source facts rather than repairing primitive names?

## Suggested Validation

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_value_tests.py
python -m pytest -q tslc/tests/test_build_verify.py::test_masked_memory_build
python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds
./verify.sh
```

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should cite concrete files/lines and separate
source-name collision concerns from ordinary emitted masked-overload names.
