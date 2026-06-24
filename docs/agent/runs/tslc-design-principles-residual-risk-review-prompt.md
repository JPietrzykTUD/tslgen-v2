# TSLc Design-Principles Residual-Risk Review

You are reviewing a focused cleanup that addresses the findings and residual
risks from the latest TSLc design-principles review.

## Accepted State

The active implementation is `tslc/`. The previous design-principles review
returned `Accept With Follow-Ups` for three issues:

- dependency extraction used a concrete C++ backend dialect while computing
  backend-neutral primitive-call closure;
- scalar type facts were duplicated through ad-hoc digit parsing across
  support policy, lowering, validation, and value-test helpers;
- residual risks remained around `load_mask_repr` unpacked mask layout and
  dependency worklist determinism.

## Read First

- `PLANS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/design-decisions.md`
- `tslc/src/tslc/lower/dependencies.py`
- `tslc/src/tslc/catalog/scalar_types.py`
- `tslc/src/tslc/support_policy.py`
- `tslc/src/tslc/lower/queries.py`
- `tslc/src/tslc/pipeline.py`
- `tsldata/primitives/load_store/load.tsl`
- `tslc/tests/test_masks_and_calls.py`

## Scope

Review only this cleanup:

- `extract_call_dependencies_from_segments(...)` now resolves source query
  identities through a narrow semantic resolver instead of creating
  `create_backend_dialect(catalog, "cpp")`;
- scalar type facts live in `tslc.catalog.scalar_types`, with existing public
  helper names delegating to that typed table;
- the call-closure worklist adds discovered primitive names in sorted order;
- `load_mask_repr` `packed=false` now mirrors `store_mask_repr` by using
  unsigned lane-word layout instead of `vector::mask_underlying_t`;
- the Rust parity follow-up keeps generic unpacked `load_mask_repr` indexing on
  a reinterpreted unsigned lane-word pointer and reinterprets AVX2/SSE register
  comparison masks back to the current vector mask representation;
- focused tests cover backend-free dependency query resolution and the full
  generated C++/Rust build gate.

## Out Of Scope

- Do not add new primitive semantics beyond the reviewed source-body cleanup.
- Do not broaden TSIL expression parsing or repair malformed source bodies.
- Do not convert render-only backend-spelling formatting into semantic scalar
  rules.
- Do not split the remaining value-test C++ renderer or planner further unless
  the review finds a blocking issue in this cleanup.
- Do not start a new roadmap milestone.

## Review Questions

- Does dependency extraction now stay backend-neutral while preserving call
  closure for `type<...>(vector::as_extension(...))`, `vector::as_base(...)`,
  `vector::as(...)`, and source-local `let<type>` aliases?
- Is the scalar type table owned by the catalog/domain boundary and consumed
  by validation, support policy, query evaluation, immediate ranges, and
  value-test scalar-tag helpers without creating new runtime globals?
- Does the `load_mask_repr` unpacked path produce typed mask values from
  unsigned lane words for scalar/generic/x86 families and return the current
  vector's mask representation without relying on undocumented mask-underlying
  source spelling?
- Is dependency worklist ordering deterministic and free of set-order leakage?
- Are remaining digit parses clearly presentation-specific, such as emitted
  immediate type spellings or backend Rust/C++ base spellings?

## Suggested Validation

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_tsil_scan.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
python -m pytest -q tslc/tests/test_build_verify.py::test_masked_memory_build
python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds
./verify.sh
git diff --check
```

The generated C++/Rust build gates may need writable tool caches such as
`/root/.cache/zig`.

## Expected Verdict

Return `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To
Planner`, or `Reject`. Findings should cite concrete files/lines and separate
semantic-boundary issues from presentation-only formatting helpers.

If accepted, create the next concrete prompt from the active TSLc backlog and
update `docs/agent/current-redesign-state.md`. Do not start a new milestone in
this review run.
