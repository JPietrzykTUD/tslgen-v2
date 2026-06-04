# M227 V/V Function-Shape Template Render Boundary Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M225 as accepted, M226 as stopped by preflight, and M226.5 as
accepted planning.

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
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
```

M226 preflight found a real `avx2` `add` fixture but stopped because the
current primitive render path still assembles whole C++/Rust function strings
in Python. M226.5 selected the smallest cleanup: carry exact `v:=(v,v)`
signature-shape information from catalog/lowering into render planning, use
C++/Rust supplementary shape templates for the function presentation, and keep
already-translated body text as a leaf presentation value.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/agent/runs/m2265-signature-shape-template-render-model-cleanup-planning-prompt.md`
- `tslgen/src/tslgen/domain/signatures.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/rendering/primitive_render_model.py`
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `supplementary/templates/cpp/primitive.hpp.in`
- `supplementary/templates/rust/primitive.rs.in`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m225_generated_profile_build_flags.py`

You may inspect `new_chat_test` only as negative evidence. Do not copy it
wholesale.

## Goal

Implement exact `v:=(v,v)` primitive function-shape rendering for C++ and Rust
without adding new whole-function C++/Rust source assembly in Python.

The selected signature shape must be a typed render-planning value derived
from the catalog/lowering `PrimitiveSignature`; do not infer it from raw
strings in renderer or template code.

## Scope

Add the smallest implementation and tests needed to prove:

- `LoweredFunctionSignature` or an immediate lowering-to-render adapter carries
  the selected typed signature-shape selector for exact `v:=(v,v)`;
- the taxonomy category of any new typed value is documented in code/docs as a
  render-model/presentation value or rule input, not a new lowering IR family;
- unsupported signature shapes diagnose before rendering instead of falling
  back to Python function string assembly;
- C++ and Rust supplementary shape templates exist for exact `v:=(v,v)`;
- templates receive only already-decided presentation fields such as function
  name text, result type text, parameter declaration text, and already-rendered
  body text;
- templates do not parse TSIL, select intrinsics/types, choose fallbacks,
  inspect catalog objects, or decide semantics;
- rendered shape-template output becomes existing
  `RenderedPrimitiveDefinitionText`, so current file-level primitive templates
  still compose profile artifacts;
- the current M224/M225 scalar tiny generated project path still passes;
- if non-scalar profile artifact replacement is needed for future M226, add
  only a narrow selected-profile replacement policy and focused tests.

Likely files include:

```text
tslgen/src/tslgen/lowering/model.py
tslgen/src/tslgen/lowering/lowerer.py
tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py
tslgen/src/tslgen/rendering/primitive_render_model.py
tslgen/src/tslgen/rendering/primitive_render_plan.py
tslgen/src/tslgen/rendering/primitive_templates.py
tslgen/src/tslgen/rendering/generated_primitive_project.py
supplementary/templates/cpp/shapes/v_assign_v_v.hpp.in
supplementary/templates/rust/shapes/v_assign_v_v.rs.in
tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py
```

Use better file names if the existing rendering package suggests them.

## Guardrails

- Do not implement the real `avx2` intrinsic fixture in M227.
- Do not add or broaden intrinsic/intrinsic-compose semantics.
- Do not add broad signature/template framework behavior. Support exact
  normalized `v:=(v,v)` only.
- Do not parse TSIL, repair source, or infer source semantics.
- Do not add new whole C++/Rust function/header/module source strings in
  Python. Python may build typed render records and already-translated leaf
  text values.
- Do not hide semantics in templates. Templates may format fields, indentation,
  loops, and optional presentation sections only.
- Do not use `frozen/` or `tslgenold/` as runtime dependencies.
- Do not copy `new_chat_test` wholesale.
- Keep C++ and Rust in parity.

## Expected Tests

Add focused tests for:

- `v:=(v,v)` carried from parsed/catalog/lowering state to the render-planning
  selector;
- exact C++ and Rust shape templates render a simple tiny scalar body with no
  Python whole-function assembly;
- unsupported nearby signature shape produces a diagnostic and does not render;
- template field validation rejects semantic-looking fields for shape
  templates as well as file-level primitive templates;
- deterministic artifact output across repeated runs;
- M224 and M225 generated project tests continue to pass;
- selected-profile replacement policy if added, including scalar compatibility
  and a non-scalar profile path such as `avx2`.

Do not add real x86 intrinsic fixture tests in M227.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: signature-shape selection is typed before
   rendering; templates do presentation only; no new raw whole-function
   language assembly path is added.
2. Evidence reviewer: M227 does not copy `new_chat_test`, does not implement
   the real M226 fixture, and keeps M224/M225 behavior.
3. Test reviewer: exact `v:=(v,v)` positive coverage, unsupported-shape
   diagnostics, C++/Rust parity, deterministic output, and selected-profile
   replacement if added.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md`, `docs/redesign/domain-model.md`,
  or `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not resume M226 inside M227.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
