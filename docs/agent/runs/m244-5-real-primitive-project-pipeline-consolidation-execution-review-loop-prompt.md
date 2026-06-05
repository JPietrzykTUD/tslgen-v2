# M244.5 Real Primitive Project Pipeline Consolidation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M244 as accepted.

This is an implementation task focused on pipeline naming/ownership
consolidation. It must not add backend feature behavior. Use the
executor-review loop:

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
Milestone 244: Real Scalar Emit-Return Matrix Rendering
```

M243/M244 proved useful behavior: real `.tsl` source from
`tsldata/primitives/arithmetic/fundamental.tsl` can be parsed through
`OuterTslParser`, selected for explicit real primitive implementation bodies,
rendered through existing C++ and Rust primitive/profile/project templates,
written manifest-clean, and build verified.

M244 also exposed a fixture-to-architecture smell:
`tslgen.pipeline.real_scalar_pipeline` is named after selected source data.
`scalar` is an extension/profile value from TSL data, not a durable pipeline
owner. If left in place, future work may naturally create sibling pipelines
such as `real_avx2_pipeline.py` or `real_neon_pipeline.py`, which would be the
wrong architecture.

M224's `generated_primitive_pipeline.py` is also not the real product
pipeline despite its generic name. It is a tiny regression/demo path using
`TslParser`, tiny source fixtures, local scalar/operator spelling tables, and
`LoweredBinaryOperationExpression`.

ADR-068 records the accepted guardrail: fixture names and selected source-data
constraints must not become production pipeline architecture.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/agent/runs/m244-real-scalar-emit-return-matrix-rendering-execution-review-loop-prompt.md`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/pipeline/real_scalar_pipeline.py`
- `tslgen/src/tslgen/pipeline/__init__.py`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py`
- `tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py`
- `tsldata/primitives/arithmetic/fundamental.tsl`

## Goal

Replace the fixture-shaped real scalar bridge with a generically owned real
selected primitive project bridge:

```text
real selected primitive implementation entries
-> exact body boundary adapters
-> backend type/body translation
-> PrimitiveRenderPlan records
-> primitive profile artifacts
-> generated project artifacts
```

The behavior proven by M243/M244 must remain accepted, but production module
and public API names must describe durable generator ownership. Selected facts
such as `scalar`, `add`, `sub`, `si32`, and exact `emit_return(PAYLOAD);`
forms belong in selected-entry data, tests, or body-boundary adapters, not in
pipeline/module identity.

## Scope

Implement the smallest safe consolidation:

- Replace `tslgen/src/tslgen/pipeline/real_scalar_pipeline.py` with a generic
  module such as `tslgen/src/tslgen/pipeline/primitive_project_pipeline.py`.
- Rename public real-pipeline models/functions to generic ownership names,
  for example:
  - `SelectedPrimitiveBodyRenderEntry`
  - `SelectedPrimitiveProjectResult`
  - `build_primitive_project_artifacts_from_selected_bodies`
- Keep scalar/add/sub/type-tag defaults only as selected-entry fixtures or
  test helpers, not module/class/function ownership.
- Preserve the accepted M243/M244 behavior, diagnostics, deterministic output,
  public project artifacts, manifest-clean write, and C++/Rust build
  verification.
- Remove or stop exporting `real_scalar_*` public names unless a genuine
  external API reason is documented in the roadmap/spec. Do not add a broad
  compatibility wrapper just to preserve poor names.
- Mark `generated_primitive_pipeline.py` clearly as M224 tiny/regression-only
  in its module docstring and docs. It must not be described as the real
  generated primitive pipeline.
- Record a follow-up that the M224 tiny regression path should be deleted once
  the generic real selected primitive project pipeline covers its regression
  value.
- Add guard coverage that production pipeline module names do not encode
  selected primitive names, extension/profile names, type tags, signatures, or
  exact body forms.

## Guardrails

- Do not add vector/register type spelling in M244.5.
- Do not render real vector/intrinsic functions.
- Do not broaden primitive selection, dependency closure, profile selection,
  or catalog semantics.
- Do not reopen lowering or add new TSIL/source parsing.
- Do not parse target-language operators or expressions.
- Do not add sibling fixture pipelines such as `real_avx2_pipeline.py`.
- Do not hide semantic decisions in templates.
- Do not create compatibility aliases for poor names unless the need is
  explicitly documented and tested as an external API boundary.
- Do not make `frozen` or `tslgenold` runtime dependencies.

## Expected Tests

Update existing M243/M244 tests and add a focused M244.5 guard test if useful,
likely:

```text
tslgen/tests/test_m244_5_real_primitive_project_pipeline_consolidation.py
```

Cover:

- M243 single selected real primitive behavior still renders/build-verifies
  C++ and Rust scalar projects through the generic real pipeline.
- M244 add/sub x ten-type selected matrix still renders/build-verifies C++ and
  Rust scalar projects through the generic real pipeline.
- The old `real_scalar_pipeline.py` module is gone or no longer imported.
- Public exports use generic real selected primitive project names.
- `generated_primitive_pipeline.py` is explicitly labelled M224
  tiny/regression-only.
- Guardrails reject or detect production pipeline filenames/public API names
  derived from selected extension/profile names, primitive names, type tags,
  signatures, or exact body forms.
- Existing M224 tiny regression tests remain compatible and still prove only
  the regression path.

## Out Of Scope

- M245 vector register type spelling.
- Real vector/intrinsic generated-project rendering.
- New backend translation semantics.
- New lowering semantics.
- New primitive selector/catalog/dependency behavior.
- Real primitive `tests:` metadata rendering.
- Generated CLI/API changes.
- Rust unsafe policy changes.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m241_primitive_profile_artifact_presentation_boundary.py tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py tslgen/tests/test_m244_5_real_primitive_project_pipeline_consolidation.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: generic real selected primitive project
   ownership is restored, no fixture-shaped pipeline remains, and no M245
   feature work slipped in.
2. Evidence reviewer: M243/M244 behavior still comes from real
   `fundamental.tsl` evidence, while M224 remains tiny/regression-only.
3. Test reviewer: accepted behavior, renamed public imports, regression-only
   labelling, and fixture-name guardrails are covered.
4. Documentation reviewer: AGENTS/PLANS guardrails, roadmap/state/spec
   consistency, and M245 deferral are accurate.
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
- create or update the next concrete prompt under `docs/agent/runs/`;
- do not start M245 inside M244.5.

## Final Report

Report:

1. Consolidation summary.
2. Names/modules removed, renamed, or preserved as regression-only.
3. M243/M244 behavior preservation summary.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
