# Post-M98 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M98.

Milestones 1 through 98 are accepted. M98 accepted:

```text
Milestone 98: Stage 8 Lowering Stage-Assembly Ownership Extraction Slice
```

The next task should focus on lowering. Do not implement code unless this
prompt explicitly selects an executor task; this prompt is planning and review
only.

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
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select exactly one next milestone that advances the lowering redesign toward
completion while respecting the accepted M98 boundary.

Prefer a high-value lowering milestone that:

- keeps semantic lowering typed and staged;
- builds on accepted Stage 8 facts instead of raw source text;
- preserves accepted M57-M98 diagnostics, stage names, ordering, keys, output
  identities, object identities, and public imports;
- avoids broad source repair, raw text rewriting, and best-effort correction;
- preserves composable pipeline ownership and small-module guardrails;
- does not add backend translation, rendering, output, or Stage 9 planning
  unless the selected scope explicitly and narrowly requires it;
- avoids growing `boundary.py`, `_operation_package_sources.py`, or
  `_lowering_stage_assembly.py` into new monoliths.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M98 is accepted behavior-preserving Stage 8 architecture work only.
- M98 added focused private `_lowering_stage_assembly.py` ownership for
  accepted `GenerationLoweringStage` construction helpers and per-candidate
  operation-package -> completion-manifest -> completion-gap-inventory result
  assembly.
- `boundary.py` remains the public facade and request/result model owner.
- `_operation_package_sources.py` remains unchanged and must not receive more
  coordination ownership.
- M98 added no new lowering semantics, operation-package families, source-body
  parsing, source repair, backend translation, backend map/catalog reads,
  backend-uninit resolution, Stage 9 planning, operation scheduling,
  dependency closure, renderer-ready IR, rendering, generated output, Rust,
  CLI/report/writer behavior, compiler execution, registries, dispatchers,
  callback maps, hidden backfeeds, fixpoint machinery, or hardwiring.
- Final M98 line counts were `boundary.py` 1,241,
  `_lowering_stage_assembly.py` 189, `_operation_package_sources.py` 819,
  `_lowering_completion_manifest.py` 776, and
  `_lowering_completion_gap_inventory.py` 564.
- Future lowering work may consume the stage-assembly helper, but must not
  broaden it into a generic coordinator, registry, dispatcher, callback map,
  hidden backfeed, fixpoint mechanism, or semantic lowering milestone.

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
