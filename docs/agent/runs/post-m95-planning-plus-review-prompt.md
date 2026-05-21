# Post-M95 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M95.

Milestones 1 through 95 are accepted. M95 accepted:

```text
Milestone 95: Selected-Body Direct-Intrinsic Operation Package Slice
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
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_selected_body.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select exactly one next milestone that advances the lowering redesign toward
completion while respecting the accepted M95 boundary.

Prefer a high-value lowering milestone that:

- keeps semantic lowering typed and staged;
- avoids broad source repair or raw text rewriting;
- preserves composable pipeline ownership and small-module guardrails;
- does not add backend translation/rendering/output unless the selected scope
  explicitly and narrowly requires it;
- avoids growing `boundary.py` beyond its guardrail or turning
  `_operation_package_sources.py` into a central package router.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M95 packages accepted M63/M62 selected-body direct-intrinsic facts as Stage 8
  typed provenance only.
- `svptrue_b*`, `pg`, selected literals, type tags, branch ids, extension ids,
  primitive names, backend ids, and source locations are provenance, not
  semantic dispatch keys.
- Backend translation, renderer-ready IR, rendering, generated output,
  compiler execution, Rust, source-body repair, generic TSIL/body parsing,
  registries, dispatchers, hidden backfeeds, and fixpoint machinery remain out
  of scope unless a future milestone explicitly selects a narrow slice.
- `_operation_package_sources.py` is 819 lines and should not receive another
  package family without a split plan.
- `boundary.py` is 1,300 lines and must not absorb new lowering ownership.

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
