# Post-M93 Planning Plus Review Prompt

You are planning the next accepted redesign milestone after Milestone 93.

Milestones 1 through 93 are accepted. M93 accepted
`Milestone 93: Dual-Source Lowering Operation Package Boundary Slice` with
`Accept With Follow-Ups`.

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
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select the next concrete milestone, with a strong preference for lowering
work that moves the project toward completion without widening beyond typed
Stage 8 boundaries prematurely.

The next plan must account for M93 follow-ups:

- `_operation_package.py` is close to the 1,000-line guardrail, so future
  package-family work should split diagnostics/provenance helpers before
  adding more families.
- `boundary.py` is 1,280 lines and must not absorb new ownership.
- Package source narrowing must not become a central semantic dispatcher.

## Required Subagent Workflow

Run read-only planning/review subagents:

1. Planner: propose exactly one next milestone and explain why it is the best
   lowering-focused next step.
2. Boundary auditor: verify the proposed scope does not add backend
   translation, rendering, generated output, source repair, broad TSIL/body
   semantics, or hardwiring.
3. Extensibility auditor: verify the proposed scope respects module-size,
   encapsulation, and composable-pipeline guardrails.
4. Documentation auditor: verify roadmap/state/doc wording can represent the
   proposed milestone without stale accepted-state language.

The main thread must consolidate the subagent results into one verdict:
`Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
`Reject`.

## Planning Constraints

- Prefer one thin architectural slice.
- Focus on lowering.
- Keep semantic behavior typed and explicit.
- Do not read backend maps/catalogs or create Stage 9 backend plans unless a
  future milestone explicitly selects Stage 9.
- Do not add renderer-ready IR, rendering, generated output, Rust, CLI/report/
  writer behavior, compiler execution, source-body repair, broad TSIL parsing,
  generic operation registries, broad semantic dispatchers, hidden backfeeds,
  or fixpoint machinery.
- Do not add new operation package families unless the plan first addresses
  the M93 package maintainability follow-up or explains why a narrower
  package-family slice is safer.

## Required Output

If planning is accepted, update:

- `docs/redesign/implementation-roadmap.md`
- any redesign docs needed to describe the selected milestone
- `docs/agent/current-redesign-state.md`

Then create:

- `docs/agent/runs/post-m93-acceptance-finalization-prompt.md`

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
6. Whether the repo is ready for human acceptance of the post-M93 plan.
