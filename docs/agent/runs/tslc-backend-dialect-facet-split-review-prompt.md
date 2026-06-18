# TSLc Backend Dialect Facet Split Review Prompt

## Accepted State

This is an ad hoc `tslc/` worktree review prompt, not a numbered `tslgen/`
redesign milestone. The previously selected numbered redesign action
(`M254.91 ImplementationBody Full Deletion`) remains paused while this `tslc`
work is reviewed.

The implemented slice refactors the lowering-time backend boundary from the
old broad `BackendTranslator` protocol into `BackendDialect` with four facets:
`types`, `intrinsics`, `templates`, and `syntax`.

## Read First

- `AGENTS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `tslc/src/tslc/backend/translation.py`
- `tslc/src/tslc/backend/cpp_translation.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/lower/context.py`

## Scope

Review the backend dialect facet split and its mechanical migration through
lowering, query evaluation, dependency extraction, pipeline orchestration, and
tests.

Confirm that:

- `BackendTranslator` and `create_backend_translation(...)` are removed from
  source/tests.
- `LoweringEnv` carries explicit `catalog` and `backend` fields.
- query/dependency code reads catalog facts from `context.env.catalog`;
- backend-specific spelling/rendering goes through the appropriate facet:
  `backend.types`, `backend.intrinsics`, `backend.templates`, or
  `backend.syntax`;
- generated behavior remains unchanged for covered tests;
- no compatibility alias was added for the old factory/protocol names.

## Out Of Scope

- Do not implement new backend semantics.
- Do not introduce a backend IR, backend framework, registry, or pipeline
  stage.
- Do not change generated C++/Rust text intentionally.
- Do not update `docs/redesign/design-decisions.md` unless review discovers a
  genuinely new policy decision.
- Do not resume or modify the paused M254.91 `tslgen/` milestone in this review.

## Required Validation

Run or confirm:

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_select_and_lower.py
python -m pytest -q tslc/tests/test_generation_conditionals.py
python -m pytest -q tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_determinism.py
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
rg "BackendTranslator|create_backend_translation|env\\.translation|translation\\.catalog" tslc/src/tslc tslc/tests
git diff --check
```

The `rg` command should return no hits and exit 1.

Probe the full suite if the environment allows:

```bash
python -m pytest -q -x tslc/tests
```

If it fails in `test_build_verify.py::test_generated_profiles_build` because
`/opt/zig/zig c++` attempts to create `/root/.cache/zig/tmp/...` and hits
`ReadOnlyFileSystem`, record it as environmental.

## Expected Output

Return a review verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with any blocking findings and cite file/line references. If accepted,
update `docs/agent/current-redesign-state.md` and create the next concrete
prompt required by `docs/agent/next-run-prompt-protocol.md`.

## Stop Rule

Do not implement revisions during review unless a focused revision task is
explicitly created. Do not start the paused M254.91 work in this run.
