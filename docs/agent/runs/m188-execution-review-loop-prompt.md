# M188 Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records post-lowering backend/output transition planning as accepted.

This is an implementation task. Use the executor-review loop: one
write-capable executor, then read-only architecture/boundary, evidence,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Post-M187 Lowering Completion Gate: lowering complete by current contract
Post-Lowering Backend/Output Transition Planning: M188 selected
```

Selected milestone:

```text
Milestone 188: Supplementary Asset And Template Boundary For C++/Rust Project Skeletons
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- existing backend/output code under `tslgen/src/tslgen/backends`,
  `tslgen/src/tslgen/rendering` if present, `tslgen/src/tslgen/io`, and
  `tslgen/src/tslgen/pipeline`
- existing tests under `tslgen/tests`

## Goal

Introduce the accepted `supplementary/` layout and a small typed static
asset/template rendering boundary for deterministic C++ and Rust project
skeleton artifacts.

The milestone should prove that generated-project scaffolding can be copied
or rendered into an in-memory `ArtifactSet` from typed render context values
without moving backend semantics into template files.

## Scope

- Create the accepted supplementary layout:
  - `supplementary/buildsystem/cpp/static/`
  - `supplementary/buildsystem/cpp/templates/`
  - `supplementary/buildsystem/rust/static/`
  - `supplementary/buildsystem/rust/templates/`
  - `supplementary/helpers/cpp/`
  - `supplementary/helpers/rust/`
  - `supplementary/templates/cpp/`
  - `supplementary/templates/rust/`
- Add a small typed model for supplementary assets that distinguishes static
  copied assets from templated assets.
- Add a deterministic renderer/copy boundary that returns `ArtifactSet`
  values and diagnostics rather than writing files.
- Add one tiny C++ project-skeleton artifact set and one tiny Rust
  project-skeleton artifact set using typed render context values such as
  backend id, package/project name, artifact path, and helper file list.
- Add focused tests for deterministic ordering, golden content, missing
  template/static asset diagnostics, and the no-semantics-in-template
  boundary.
- Preserve existing tiny scalar C++/Rust generation behavior unless the
  executor deliberately routes only the existing function shell through a
  template with byte-stable output.

## Out Of Scope

- Backend type/value translation.
- Language/translation metadata ingestion from `tsldata/detail/lang/**`.
- Moving scalar/operator semantic tables into templates.
- Primitive body rendering beyond already accepted tiny outputs.
- Intrinsic translation.
- Source-operation translation for `cast<...>`, `mem<...>`, or `io<...>`.
- Mask keyword translation.
- Backend-control rendering.
- M187 `assume_aligned<...>`, `array_type<...>`, or `pack<...>` translation.
- Dependency closure.
- Helper semantic availability.
- Compiler invocation or generated-test execution.
- Filesystem writing beyond the existing artifact writer.
- Runtime dependencies on `frozen/` or `tslgenold`.

## Guardrails

- Templates may use presentation logic such as loops, indentation, optional
  sections, and list joining over typed render context values.
- Templates must not perform backend semantic decisions, type or intrinsic
  selection, feature gating, primitive selection, TSIL parsing, dependency
  closure, fallback selection, or source repair.
- Python backend/output code may build typed render contexts and copy/render
  supplementary assets, but backend semantics must live in typed
  rule/evaluator stages before rendering.
- Do not add a broad template framework if a small typed boundary proves the
  selected slice.
- If using Jinja2, keep it behind a tiny project-owned rendering interface and
  document the dependency expectation. If dependency policy is unclear, stop
  and return to planner rather than inventing a hidden runtime requirement.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py -k "m188 or tiny_fixture_generates_cpp_and_rust_artifact_values or artifact_writer"
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Run read-only review/audit subagents after the executor:

1. Architecture/boundary auditor: verify supplementary assets/templates do not
   own backend semantics and no lowering is reopened.
2. Evidence auditor: verify the selected slice matches repository evidence and
   does not make `frozen/` or `tslgenold/` a runtime dependency.
3. Documentation auditor: verify roadmap, state, and redesign docs describe
   the accepted boundary.
4. Validation auditor: verify exact validation results and workspace hygiene.

If review returns `Needs Revision`, make only focused fixes and re-run focused
review. If review returns `Return To Planner` or `Reject`, stop and create the
appropriate next prompt instead of continuing implementation.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M188 result;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Final Report

Report:

1. M188 verdict.
2. Files changed.
3. Boundary created.
4. Tests and validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
