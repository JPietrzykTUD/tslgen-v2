# Post-M178 Lowering Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M178 as accepted.

You are planning the next lowering milestone after:

```text
Milestone 178: Source-Owned Request Island Scanner Consolidation
```

Milestones 1 through 178 are accepted. M178 was a behavior-preserving
refactor: exact request-island scanner mechanics are now shared, but no new
lowering semantics were added.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/generation-value-query-inventory.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/lowering/`
- `tslgen/tests/`
- `tsldata/**/*.tsl` only as corpus evidence for source forms and frequency.

## Goal

Select the next concrete M179 lowering milestone.

The selected milestone should be the highest-value remaining lowering slice
that moves the research prototype closer to generating code from changing
`.tsl` source data while keeping the implementation small and reviewable.

Prefer a slice that:

- is grounded in actual `tsldata/**/*.tsl` source forms;
- uses the accepted lowering boundaries from M127-M178;
- benefits from the M178 scanner helper where exact source islands are needed;
- reduces a real generation blocker rather than adding another narrow
  request/result layer;
- can be implemented and reviewed in one execution-review-loop prompt.

## Required Planning Task

This is a planning-only run. Do not edit production code or tests.

1. Inspect the accepted roadmap and lowering inventory.
2. Inventory the remaining generation/body lowering gaps that are still
   relevant after M178.
3. Select exactly one M179 milestone, or record an explicit stop/return to
   planner condition if the next slice cannot be selected without a design
   decision.
4. Define M179 goal, scope, out-of-scope work, expected tests, required
   validation, and review/audit subagents.
5. Update `docs/redesign/implementation-roadmap.md`.
6. Update `docs/agent/current-redesign-state.md`.
7. Create the next concrete prompt under `docs/agent/runs/`, normally an
   `m179-...-execution-review-loop-prompt.md`.

## Required Planning Subagents

Use read-only planning/review subagents before finalizing the selected
milestone:

1. Evidence planner: inspect `tsldata/**/*.tsl` and redesign inventories to
   list the remaining lowering candidates and their corpus grounding.
2. Boundary/simplicity auditor: challenge the proposed M179 slice for
   overengineering, broad TSIL parsing, backend rendering, source repair,
   or another one-off request/result family.
3. Documentation reviewer: verify the roadmap, state update, and next run
   prompt are coherent and follow the next-run prompt protocol.

The orchestrator owns final milestone selection, state updates, and next
prompt creation.

## Design Guardrails

- Keep the next task focused on lowering.
- Do not implement M179 in this prompt.
- Do not introduce a broad TSIL grammar, expression interpreter, backend
  renderer, source rewriter, dependency scheduler, registry, dispatcher,
  plugin map, or worklist unless the selected milestone proves it is required
  by at least two accepted boundaries.
- Do not treat target-language-like raw text as semantics.
- Do not make `frozen`, `tslgenold`, or runtime `tsldata` a runtime
  dependency.
- Prefer source-owned exact keyword/request islands and typed facts over
  ad-hoc string rewriting.

## Validation

Run:

```bash
git diff --check
```

## Completion Rules

If planning review accepts the selected M179 milestone:

- update `docs/agent/current-redesign-state.md` to point at the new M179
  prompt;
- update `docs/redesign/implementation-roadmap.md` with the selected M179
  milestone;
- create the M179 concrete run prompt under `docs/agent/runs/`;
- record validation results.

If planning review finds the next slice is unclear, do not guess. Record the
blocking design question or stop condition in `docs/agent/current-redesign-state.md`
and create the appropriate follow-up planning prompt.

Do not start M179 implementation in this prompt.

## Final Report

Report:

1. Selected M179 milestone and why it is useful.
2. Planning subagent verdicts and any follow-ups.
3. Files changed.
4. Validation command and exact result.
5. Next active prompt path.
