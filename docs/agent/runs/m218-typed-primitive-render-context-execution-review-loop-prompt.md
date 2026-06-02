# M218 Typed Primitive Render Context Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M217 as accepted.

This is an implementation task. Use the executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if Needs Revision
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 217: Primitive Template Boundary
```

M217 added minimal C++ and Rust primitive templates and a dedicated
`PrimitiveTemplateRenderContext`. It renders deterministic in-memory
`ArtifactSet` values only. Templates are presentation-only and must not own
backend semantics, raw TSIL interpretation, primitive selection, dependency
closure, type/intrinsic selection, or source repair.

M218 owns the fuller typed primitive render context for already-decided
primitive presentation values. M218 must not start real selected primitive
rendering. It should define the typed values that later stages can populate
after selection, dependency planning, body-token substitution, and backend
translation have already decided semantics.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/rendering/__init__.py`
- `tslgen/tests/test_m217_primitive_template_boundary.py`
- `supplementary/templates/cpp/primitive.hpp.in`
- `supplementary/templates/rust/primitive.rs.in`

## Goal

Define a typed primitive render model that feeds M217 primitive templates:

```text
typed already-decided primitive render model
-> C++ and Rust PrimitiveTemplateRenderContext values
-> M217 primitive templates
```

The render model distinguishes already-rendered presentation text from raw
source, raw TSIL, unresolved lowering requests, backend metadata lookups, and
selection/dependency inputs.

## Scope

Add a focused module and tests, likely:

```text
tslgen/src/tslgen/rendering/primitive_render_model.py
tslgen/tests/test_m218_typed_primitive_render_context.py
```

The implementation should:

- define small typed values or dataclasses for already-rendered primitive
  presentation facts, such as rendered declaration text, rendered definition
  text, rendered body text, include/import lines, namespace/module presentation
  text, backend id, profile name, and artifact logical path;
- define a typed primitive render record or equivalent that can group
  already-rendered declaration/definition/body values without interpreting
  them;
- define C++ and Rust backend primitive render models with deterministic
  ordering over already-rendered primitive records;
- add a narrow adapter that converts those render models into M217
  `PrimitiveTemplateRenderContext` values;
- keep C++ and Rust in parity;
- preserve deterministic ordering and artifact paths;
- diagnose or reject unresolved/raw semantic values if the API receives them
  directly;
- expose a narrow public API only if useful.

Use typed wrappers or dataclasses for text that is intentionally
already-rendered. Avoid bare unlabelled strings in public render-model objects
where a small value type makes the boundary clearer.

## Guardrails

- Do not render real selected primitives from the catalog.
- Do not perform primitive selection, dependency closure, topological sorting,
  or fallback resolution.
- Do not run body-token substitution or Rust intrinsic-call rendering.
- Do not parse raw TSIL, raw source bodies, statements, expressions,
  `emit_return(...)`, assignments, loops, braces, semicolons, operators, or
  array indexing.
- Do not add Jinja2 or another template dependency.
- Do not write artifacts, integrate generated projects, run build
  verification, or invoke compilers.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.
- Do not put semantic decisions into templates or the M218 adapter.

## Expected Tests

Add focused tests for:

- constructing a C++ typed primitive render model and adapting it to an M217
  `PrimitiveTemplateRenderContext`;
- constructing a Rust typed primitive render model and adapting it to an M217
  `PrimitiveTemplateRenderContext`;
- deterministic ordering of primitive records in adapted declaration/definition
  text;
- preservation of rendered body text as already-rendered presentation text;
- C++/Rust parity for profile and artifact path handling;
- no `ProjectSkeletonRenderContext` reuse;
- diagnostic/rejection for unresolved raw semantic values, such as raw TSIL or
  lowering-request sentinel values;
- public import stability if a public API is exposed.

Do not add generated project writing, compile tests, corpus rendering, or real
primitive selection in M218.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m218_typed_primitive_render_context.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: M218 introduces already-decided typed render
   model values only, keeps templates presentation-only, and does not perform
   selection/lowering/render semantics.
2. Evidence reviewer: M218 is the useful next step after M217 and prepares
   M219/M220/M223 without requiring them.
3. Test reviewer: coverage of C++/Rust adaptation, deterministic ordering,
   typed text boundary, diagnostics/rejections, and no skeleton-context reuse.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md`, `docs/redesign/domain-model.md`,
  or `docs/redesign/design-decisions.md` if the implementation clarifies
  behavior, domain values, or architecture;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M219.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
