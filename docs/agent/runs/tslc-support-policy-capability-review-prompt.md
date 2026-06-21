# TSLc Support Policy Capability Review Prompt

## Accepted State

This is an ad hoc `tslc/` worktree review prompt, not a numbered `tslgen/`
redesign milestone. The old numbered `tslgen/` milestone line remains paused
and must not be resumed from this prompt.

The implemented slice centralizes current prototype support decisions in a
small support-policy object and removes behavior branches that inferred compiler
capability from a source extension identity such as `generic`. Catalog-derived
selection views live beside the policy rather than inside it.

## Read First

- `AGENTS.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/review-checklist.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/design-decisions.md`
- `tslc/src/tslc/support_policy.py`
- `tslc/src/tslc/support_policy_views.py`
- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/select/selector.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/lower/queries.py`
- `tslc/src/tslc/lower/region_handlers/common.py`
- `tslc/src/tslc/backend/translation.py`
- `tslc/src/tslc/backend/cpp.py`
- `tslc/src/tslc/backend/rust.py`
- `tslc/src/tslc/backend/cpp_translation.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/tests/test_support_policy.py`
- `tslc/tests/test_support_policy_views.py`

## Scope

Review the support-policy capability slice and confirm that:

- `SupportPolicy` owns supported backend ids, emitted extension families,
  signature kinds, maskable signature forms/suffixes, immediate and variadic
  kinds, pointer/index kinds, target-marker values, and deferred cases;
- `tslc.support_policy_views` owns catalog-derived scans such as selectable
  variants, mask/immediate split-name discovery, and representation target
  candidate filtering, so `SupportPolicy` stays facts/predicates only;
- extension behavior is derived from typed catalog metadata such as
  `vector_bits_kind`, `size_parameter_name`, and `vector_register_type_policy`,
  not hard-coded source extension identities;
- selection skips variadic sized-vector forms through policy capability checks;
- lowering records sized-vector and lane-parameter facts on lowered
  specializations/targets instead of making backends rediscover those facts;
- query evaluation resolves source extension names through the catalog and then
  asks capability questions;
- backend renderers may spell the current generated sized-vector substrate, but
  they do not infer capability from source extension names;
- existing generated C++/Rust behavior and validation behavior remain stable.

## Out Of Scope

- Do not rename the generated C++/Rust static substrate.
- Do not broaden support for deferred extension families, scalable vectors,
  sized-vector extension-dimension representation changes, variadic sized-vector
  loops, or masked gather/scatter.
- Do not change source syntax, primitive semantics, or generated output
  intentionally beyond capability plumbing.
- Do not migrate or resume the old numbered `tslgen/` milestone line.

## Required Validation

Run or confirm:

```bash
git diff --check
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_build_verify.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
./verify.sh
```

Also confirm the capability-branch scan has no production hits:

```bash
rg -n 'generic_extension|extension_name == "generic"|isa_name == "generic"|isa_name == "scalar"|== "generic"|== "scalar"|generic_vector_spelling|skips_variadic_on_family|supports_generic_target_dimension' tslc/src/tslc tslc/tests/test_support_policy*.py
```

## Expected Output

Return a review verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with blocking findings and cite file/line references. If accepted, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
required by `docs/agent/next-run-prompt-protocol.md`.

## Stop Rule

Do not implement revisions during review unless a focused revision task is
explicitly created. Do not start the paused old `tslgen` milestone line in this
run.
