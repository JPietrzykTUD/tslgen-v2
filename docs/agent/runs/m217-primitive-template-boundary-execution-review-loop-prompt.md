# M217 Primitive Template Boundary Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M216 as accepted.

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
Milestone 216: Backend Rendering Roadmap Planning
```

M216 accepted the template-first backend/rendering roadmap. Primitive
templates move before more real backend-specific primitive rendering so C++ and
Rust source structure does not accumulate as large raw strings in Python.
Backend-facing rendering milestones should keep C++ and Rust in parity unless
a prompt records a concrete temporary exception and nearby catch-up milestone.

M216 selected M217 as the next executable milestone. M217 establishes minimal
C++ and Rust primitive template files and a primitive-template rendering
boundary. M218 owns the fuller typed primitive render context for real selected
primitive rendering.

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
- `tslgen/src/tslgen/rendering/supplementary.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/io/artifacts.py`
- `tslgen/tests/test_m191_generated_project_smoke_boundary.py`
- `supplementary/buildsystem/cpp/templates/`
- `supplementary/buildsystem/rust/templates/`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Implement the smallest primitive-template boundary for both C++ and Rust:

```text
typed already-decided primitive template context
+ supplementary/templates/{cpp,rust} template files
-> deterministic in-memory primitive template artifacts
```

Templates may own language presentation structure. They must not decide
backend semantics.

## Scope

Add minimal primitive template files under:

```text
supplementary/templates/cpp/
supplementary/templates/rust/
```

Add a focused renderer module and tests, likely:

```text
tslgen/src/tslgen/rendering/primitive_templates.py
tslgen/tests/test_m217_primitive_template_boundary.py
```

The implementation should:

- define a dedicated typed primitive-template render context;
- not reuse `ProjectSkeletonRenderContext`, because its field guard and
  allowed fields are skeleton-specific;
- support C++ and Rust in the same milestone;
- render only deterministic in-memory `ArtifactSet` values;
- load template files from `supplementary/templates/{cpp,rust}/`;
- consume already-decided presentation fields only, such as backend id,
  artifact path, profile name, includes/imports, namespace/module presentation
  text, and already-rendered primitive declaration/definition/body text;
- keep real selected primitive context population for M218;
- reject unsupported fields, compound field shapes, unknown fields, and fields
  that would make templates own backend semantics;
- diagnose missing C++ and Rust primitive template files;
- preserve deterministic artifact ordering;
- expose a narrow public API only if useful.

Use the accepted M188 standard-library formatting approach unless the executor
documents a concrete presentation-only reason to introduce a different
template engine. Do not add Jinja2 or another dependency merely because future
templates may become more complex.

## Template Boundary Guardrails

The primitive-template field guard must differ from the skeleton guard.
Primitive templates may need names like `primitive_definitions` or
`rendered_body_text` because these are already-decided presentation values in
this boundary. But they must reject unresolved semantic fields or source forms
such as:

- raw `tsil`;
- raw source payloads needing interpretation;
- lowering requests;
- backend metadata lookup keys;
- primitive selectors;
- dependency rules or unsorted dependency lists;
- type or intrinsic selection inputs;
- feature gates that are not already rendered presentation text;
- fallback or overload resolution inputs.

If a field would require the template or renderer to decide a type spelling,
intrinsic spelling, primitive selection, dependency order, TSIL form, or source
repair, it belongs before the render context.

## Expected Tests

Add focused tests for:

- rendering a minimal C++ primitive template artifact from fixture
  already-rendered primitive text;
- rendering a minimal Rust primitive template artifact from fixture
  already-rendered primitive text;
- deterministic artifact order when both backends are rendered;
- missing C++ template diagnostic;
- missing Rust template diagnostic;
- unknown field diagnostic;
- unsupported compound field diagnostic;
- semantic/unresolved field diagnostic;
- proof that `ProjectSkeletonRenderContext` is not required or reused for the
  primitive-template boundary;
- public import stability if a public API is exposed.

Do not add real selected primitive rendering, corpus rendering, generated
project writing, or compile tests in M217.

## Out Of Scope

- Full selected primitive render context; this is M218.
- Real primitive selection, dependency closure, or topological primitive
  ordering.
- Rust intrinsic-call rendering; this is M219.
- Shared body-token replacement/provenance contract; this is M220.
- Non-intrinsic body-token substitution; this is M221.
- Generated project integration, artifact writing, or build verification.
- Jinja2 or another template dependency without a selected presentation-only
  need.
- New lowering, raw TSIL rescans, statement parsing, expression parsing,
  source repair, or runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m217_primitive_template_boundary.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: M217 keeps templates presentation-only,
   avoids renderer-side semantics, uses a dedicated primitive-template context,
   and keeps C++/Rust parity.
2. Evidence reviewer: M217 is the useful next step after M216 and does not
   require Rust intrinsic calls or shared body-token substitution first.
3. Test reviewer: coverage of C++/Rust rendering, deterministic artifacts,
   diagnostics, and no skeleton-context reuse.
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
  or `docs/redesign/design-decisions.md` only if the implementation clarifies
  behavior, domain values, or architecture beyond ADR-063;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M218.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
