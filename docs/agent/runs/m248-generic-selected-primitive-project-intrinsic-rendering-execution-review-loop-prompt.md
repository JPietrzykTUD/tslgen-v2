# M248 Generic Selected Primitive Project Intrinsic Rendering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M247 as accepted.

This is an implementation task. Use the executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if `Needs Revision`
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 247: Selected Implementation Render Context Propagation
```

M247 added typed selected implementation render context to the intrinsic
body-token bridge. The bridge can now resolve extension-owned default
`intrin_compose` policy from selected backend, extension, type tag, and
`ExtensionCatalog`, and Rust call rendering has a typed already-qualified
name mode to avoid doubled `core::arch::*` paths.

## Goal

Connect the accepted M247 context-aware intrinsic body-token rendering path to
the generic real selected primitive project pipeline.

The proof slice is one representative real vector/intrinsic primitive from
`tsldata/primitives/arithmetic/fundamental.tsl`, rendered for C++ and Rust in
parity through `tslgen.pipeline.primitive_project_pipeline`, not through a
fixture-specific side path.

Use the existing selected implementation facts:

```text
SelectedPrimitiveBodyRenderEntry / selected implementation body
  + requested generated profile
  + selected extension
  + selected TypeTag
  + ExtensionCatalog
  + BackendMetadataCatalog
  -> generic selected primitive project pipeline
  -> M245 vector register type spelling
  -> M247 intrinsic body-token rendering
  -> existing primitive shape/profile templates
  -> deterministic ArtifactSet
```

This milestone should finally move the real project pipeline beyond scalar
raw-payload rendering for one selected vector profile. It is not another
`intrin_compose` micro-milestone.

## Scope

Implement the smallest coherent generic integration:

- Update `tslgen.pipeline.primitive_project_pipeline` or a narrow helper owned
  by that module. Do not add `real_avx2_pipeline.py`,
  `real_intrinsic_pipeline.py`, or any other sibling fixture pipeline.
- Carry selected extension/profile and selected type tag as typed data into
  project rendering. Supplying an explicit `ExtensionCatalog` input is
  acceptable and preferred over parsing extension files inside rendering.
- For non-scalar selected extensions, translate result and parameter type
  spellings through the accepted M245 `CurrentVector(extension, type_tag)`
  backend type-spelling path using the supplied extension catalog. Preserve
  accepted scalar behavior for scalar selected entries.
- For exact accepted `emit_return(PAYLOAD);` selected bodies whose payload
  contains backend intrinsic request islands, use the existing intrinsic
  discovery/lowering/handoff path and M247 intrinsic body-token bridge to
  render the payload. Do not introduce pairwise parent/child keyword handlers;
  the bridge consumes already-lowered body-token handoff values.
- Render one real selected implementation such as:

  ```text
  primitive: add
  selector_path: ("avx2", "f?")
  type_tag: f32
  requested profile: avx2
  parameters: ("left", "right")
  ```

- Expected C++ output should use extension register type spelling and
  `_mm256_add_ps(left, right)`.
- Expected Rust output should use extension register type spelling and a
  single `core::arch::x86_64::_mm256_add_ps(left, right)` path, not a doubled
  path.
- Preserve M243/M244 scalar add/sub behavior, deterministic artifacts, public
  pipeline imports, and M244.5 fixture-pipeline guardrails.

## Non-Negotiable Guardrails

- No new lowering semantics.
- No broad TSIL parser work.
- No dependency closure or primitive-call expansion.
- No pairwise `emit_return + intrin_compose` special case.
- No Python-owned C++/Rust primitive bodies or backend intrinsic spelling
  tables.
- No template-side intrinsic/type selection.
- No extension of `generated_primitive_pipeline.py`.
- No runtime dependency on `frozen` or `tslgenold`.
- If Rust unsafe/target-feature policy blocks build verification for the vector
  slice, diagnose or record that as a follow-up instead of hiding it in
  templates or Python raw snippets.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m248_generic_selected_primitive_project_intrinsic_rendering.py
tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py
tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py
tslgen/tests/test_m244_5_real_primitive_project_pipeline_consolidation.py
```

Cover:

- Real `add` `avx2/f32` selected entry renders C++ and Rust profile artifacts
  through `primitive_project_pipeline`.
- C++ function uses vector register spelling from `extension.tsl` and contains
  `_mm256_add_ps(left, right)`.
- Rust function uses vector register spelling from `extension.tsl` and contains
  exactly one `core::arch::x86_64::_mm256_add_ps(left, right)` call path.
- No raw TSIL, `intrin_compose<...>`, or doubled Rust qualification leaks into
  the generated primitive definition.
- Scalar M243/M244 behavior remains compatible.
- Missing extension catalog for a non-scalar intrinsic project slice is a
  diagnostic, not a local fallback table.
- Guardrails: no new fixture pipeline module, no `frozen`/`tslgenold` runtime
  dependency, no Python intrinsic spelling table, no template semantic fields.

## Out Of Scope

Broad vector/generic/mask/SVE coverage; dependency closure; primitive-call
rendering; source-operation rendering; loop/control rendering; generated tests
for vector semantics; real AVX/NEON compile/run verification unless existing
buildsystem and Rust unsafe/target-feature policy already make it direct; CLI
workflow; deleting `generated_primitive_pipeline.py`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py tslgen/tests/test_m244_5_real_primitive_project_pipeline_consolidation.py tslgen/tests/test_m245_extension_register_type_spelling_boundary.py tslgen/tests/test_m247_selected_implementation_render_context.py tslgen/tests/test_m248_generic_selected_primitive_project_intrinsic_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: generic selected project pipeline only; no
   fixture sibling pipeline, no pairwise keyword special case, no renderer or
   template semantic inference.
2. Evidence reviewer: selected fixture is real `tsldata` evidence; type and
   intrinsic spellings come from accepted metadata/catalogs, not Python tables.
3. Test reviewer: C++/Rust parity, scalar regression compatibility,
   diagnostics, determinism, and guardrails are covered.
4. Documentation reviewer: roadmap/state/spec/decision consistency and next
   prompt accuracy.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M249 inside M248.

## Final Report

Report:

1. Implementation summary.
2. How selected context reaches real project rendering.
3. C++/Rust generated output behavior.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
