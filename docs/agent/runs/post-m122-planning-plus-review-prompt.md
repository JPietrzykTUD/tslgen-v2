# Post-M122 Lowering Planning Plus Review Prompt

Milestones 1 through 122 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M122 built the
tiny clean restart path from source loading through catalog construction,
selection, lowering, backend emission, artifact writing, and focused scalar
operation expansion. M122 broadened the accepted M121 scalar comparison path
from `equal` to the same-shape comparison operator family.

The next task must focus on lowering. This is a planning prompt, not an
implementation prompt. Do not modify implementation code.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- current clean lowering implementation under `tslgen/src/tslgen/lowering/`

## Goal

Select exactly one lowering-focused Milestone 123 for the clean restart path
and create the concrete M123 execution-review-loop prompt.

The planning must account for the product-owner concern that operation facts
observed in `tsldata/*` must not silently leak into product generator code as
unreviewed hardwired corpus data. The plan may keep the tiny accepted scalar
operation descriptors as documented bootstrap/core semantics only if it says
so explicitly, or it may select a thin lowering-owned step toward typed
operation/rule ownership. Do not solve that concern by adding backend manifest
reads, broad configuration plumbing, or renderer-side inference.

## Required Planner Task

Run a docs-only planning pass that:

1. Inspects the accepted M107-M122 clean restart path and current lowering
   modules.
2. Selects exactly one Milestone 123 focused on lowering.
3. Keeps the milestone thin, product-oriented, and compatible with the KISS
   restart charter.
4. Defines goal, scope, out-of-scope items, accepted outputs, validation, and
   review notes for M123 in `docs/redesign/implementation-roadmap.md`.
5. Updates `docs/redesign/behavioral-spec.md`,
   `docs/redesign/design-decisions.md`, or
   `docs/redesign/open-questions.md` only if the planning pass reveals a
   behavior, decision, or unresolved question that belongs there.
6. Creates `docs/agent/runs/m123-execution-review-loop-prompt.md` if planning
   is accepted.
7. Updates `docs/agent/current-redesign-state.md` to point to the next active
   prompt, per `docs/agent/next-run-prompt-protocol.md`.

## Planning Constraints

- The selected M123 must focus on lowering. It must not be primarily backend
  manifests, artifact writing, CLI work, package planning, generated-test
  execution, or old implementation migration.
- Do not add source syntax broadening unless the selected lowering slice
  explicitly needs one exact form and tests its diagnostic boundaries.
- Do not introduce broad TSIL parsing, vector/SIMD semantics, mask ABI policy,
  runtime floating/signed-ordering policy, dependency closure, registries,
  dispatchers, hidden backfeeds, fixpoint mechanisms, plugin systems, or a
  broad expression/type framework.
- Do not make `frozen/`, `tslgenold/`, or `tsldata/` a runtime dependency of
  the clean generator.
- Do not add a new IR category, request/result family, inventory, provenance
  wrapper, or pipeline stage unless the plan states why two concrete accepted
  stages need it now.
- If the next best step is to document accepted scalar operation descriptors as
  bootstrap/core semantics, keep that as a small lowering/design slice with
  tests or docs proportionate to the risk.
- If the next best step is a typed lowering-owned rule/input boundary, keep it
  narrow and do not turn it into backend-map evaluation or renderer-ready IR.

## Required Review/Audit Subagents

After drafting the M123 plan and execution prompt, use read-only subagents:

1. Architecture reviewer: verify the selected M123 is genuinely lowering
   focused, KISS-compatible, and does not add broad IR ceremony or renderer-side
   semantic inference.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not planned as runtime shortcuts.
3. Documentation auditor: verify roadmap, behavioral/design/open-question docs,
   current state, and the M123 prompt are coherent.
4. Validation auditor: verify the required docs-only validation ran and report
   the exact command result.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
```

This is a planning/docs-only prompt. Do not run the old `tslgenold` validation
profile as proof of the clean product path.

## Completion Rules

If planning review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- record follow-ups in state if any;
- create and point to `docs/agent/runs/m123-execution-review-loop-prompt.md`.

If planning review returns `Needs Revision`, create a focused planning revision
prompt instead. If it returns `Return To Planner` or `Reject`, record the stop
or return condition in state and create the appropriate next prompt.

Do not implement Milestone 123 in this prompt.

## Final Report

Report:

1. Selected M123 milestone.
2. Files/directories changed.
3. Planning/review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command and exact result.
