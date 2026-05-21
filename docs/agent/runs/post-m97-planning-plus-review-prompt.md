# Post-M97 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M97.

Milestones 1 through 97 are accepted. M97 accepted:

```text
Milestone 97: Lowering Completion Gap Inventory Slice
```

The next task should focus on lowering. Do not implement code unless this
prompt explicitly selects an executor task; this prompt is planning and
review only.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select exactly one next milestone that advances the lowering redesign toward
completion while respecting the accepted M97 boundary.

Prefer a high-value lowering milestone that:

- keeps semantic lowering typed and staged;
- consumes accepted Stage 8 facts instead of raw source text;
- preserves package/provenance object identity where identity is the contract;
- avoids broad source repair, raw text rewriting, and best-effort correction;
- preserves composable pipeline ownership and small-module guardrails;
- does not add backend translation, rendering, output, or Stage 9 planning
  unless the selected scope explicitly and narrowly requires it;
- avoids growing `boundary.py` beyond its 1,300-line guardrail or turning
  `_operation_package_sources.py` into a central router.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M97 creates a private Stage 8 lowering completion gap inventory over
  accepted M96 `Stage8LoweringCompletionManifestIr` facts.
- `lowering_completion_gap_inventory` means lowering-owned gap/provenance
  inventory only. It does not mean semantic body completion, backend readiness,
  renderer readiness, dependency closure, operation scheduling, executable
  readiness, or generated-output readiness.
- M97 records only accepted unresolved backend-handoff dependency records as
  known gaps, plus a deterministic no-known-gap state for manifests without
  unresolved dependency records.
- M97 preserves source manifest, package record, package object, unresolved
  dependency record, and source dependency request object identity.
- Backend translation, backend map/catalog reads, backend-uninit resolution,
  Stage 9 planning, operation scheduling, dependency closure, renderer-ready
  IR, rendering, generated output, compiler execution, Rust, source-body
  repair, generic TSIL/body parsing, registries, dispatchers, hidden
  backfeeds, and fixpoint machinery remain out of scope unless a future
  milestone explicitly selects a narrow slice.
- Final M97 line counts were `boundary.py` 1,285,
  `_operation_package_sources.py` 819, `_lowering_completion_manifest.py` 776,
  and `_lowering_completion_gap_inventory.py` 564.
- `boundary.py` remains close to the guardrail. The next lowering slice should
  extract coordination/stage helper ownership before adding more state there.

## Required Subagents

Use read-only planning/review subagents:

1. Planner: propose one concrete next lowering milestone, with scope,
   out-of-scope boundaries, required tests, validation, and expected files.
2. Boundary auditor: check the proposal against lowering-stage, source-body
   integrity, backend/rendering, hardwiring, and no-repair boundaries.
3. Extensibility auditor: check module ownership, line-count pressure,
   composable pipeline fit, and whether the plan avoids new monoliths.
4. Documentation auditor: check whether roadmap/state/design docs would remain
   coherent after accepting the plan.

The main thread is the orchestrator. Consolidate the subagent results into one
planning verdict:

```text
Accept
Accept With Follow-Ups
Needs Revision
Return To Planner
Reject
```

If the plan needs local planning-doc corrections, make only documentation
changes. Do not modify implementation code or tests.

## Required Output

If the selected plan is accepted or accepted with follow-ups:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record the selected next milestone;
- create the next concrete run prompt under `docs/agent/runs/`.

If human acceptance is required before execution, create an acceptance
finalization prompt. If local policy permits direct execution next, create the
executor or execution-review-loop prompt. In both cases, point
`docs/agent/current-redesign-state.md` at the new prompt.

If the result is `Needs Revision`, create a focused planning-revision prompt.
If the result is `Return To Planner` or `Reject`, create the appropriate
planner/rollback prompt and record the stop/next condition.

## Validation

Run:

```bash
git diff --check
```

If other docs are changed, include them in the diff-check by running the same
repository-wide command.

## Final Report

Report:

1. Selected next milestone or stop condition.
2. Planning verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command and exact result.
