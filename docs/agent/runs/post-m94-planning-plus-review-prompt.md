# Post-M94 Planning Plus Review Prompt

You are planning the next accepted redesign milestone after Milestone 94.

Milestones 1 through 94 are accepted. M94 accepted
`Milestone 94: Lowering Operation Package Diagnostics and Provenance Ownership Split Slice`
with `Accept With Follow-Ups`.

Do not implement code unless this prompt explicitly selects a separate
executor task. This prompt is for planning and internal review only.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`
- `tslgen/src/tslgen/lowering/_operation_package_exact_array.py`
- `tslgen/src/tslgen/lowering/_operation_package_mini_tsil.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select the next concrete milestone, with a strong preference for lowering work
that moves the project toward completion without widening beyond typed Stage 8
boundaries prematurely.

The next plan must account for M94 follow-ups:

- `_operation_package_sources.py` remains focused at 604 lines but uses
  duck-typed accepted containers through `hasattr`/`getattr` for the M93
  surface. Future package-family work must not grow that into a generic source
  protocol or dispatcher.
- The current line-count test asserts each operation-package module remains
  below 1,000 lines. A future maintainability pass may choose a tighter
  threshold for operation-package private modules so a near-guardrail
  replacement monolith cannot technically pass.

## Required Subagent Workflow

Run read-only planning/review subagents:

1. Planner: propose exactly one next milestone and explain why it is the best
   lowering-focused next step.
2. Boundary auditor: verify the proposed scope does not add backend
   translation, rendering, generated output, source repair, broad TSIL/body
   semantics, hardwiring, Stage 9 backend planning, registries, dispatchers,
   hidden backfeeds, or fixpoint machinery.
3. Extensibility auditor: verify the proposed scope respects module-size,
   encapsulation, composable-pipeline, typed-boundary, import-direction, and
   no-second-monolith guardrails. It must specifically consider the M94
   `_operation_package_sources.py` follow-up if the plan touches operation
   package source intake or future package families.
4. Documentation auditor: verify roadmap/state/doc wording can represent the
   proposed milestone without stale accepted-state language.

The main thread must consolidate the subagent results into one verdict:
`Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
`Reject`.

## Planning Constraints

- Prefer one thin architectural slice.
- Focus on lowering unless a more urgent accepted-state correction blocks
  progress.
- Keep semantic behavior typed and explicit.
- Do not read backend maps/catalogs or create Stage 9 backend plans unless a
  future milestone explicitly selects Stage 9.
- Do not add renderer-ready IR, rendering, generated output, Rust, CLI/report/
  writer behavior, compiler execution, source-body repair, broad TSIL parsing,
  generic operation registries, broad semantic dispatchers, hidden backfeeds,
  or fixpoint machinery.
- Do not add new operation package families unless the plan explains why the
  M94 package-source follow-up remains contained and why the selected family
  already has accepted typed source facts, evidence, diagnostics, and tests.

## Required Output

If planning is accepted, update:

- `docs/redesign/implementation-roadmap.md`
- any redesign docs needed to describe the selected milestone
- `docs/agent/current-redesign-state.md`

Then create:

- `docs/agent/runs/post-m94-acceptance-finalization-prompt.md`

The finalization prompt must convert human acceptance into the next concrete
executor or execution-review-loop prompt under `docs/agent/runs/`.

If planning needs revision, create a focused planning revision prompt instead.
If the workflow should stop, record an explicit stop condition in
`docs/agent/current-redesign-state.md`.

## Required Validation

Run:

```bash
git diff --check
```

## Final Report

Report:

1. Selected next milestone or stop/revision result.
2. Subagent verdicts.
3. Files changed.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready for human acceptance of the post-M94 plan.
