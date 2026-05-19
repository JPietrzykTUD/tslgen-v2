# Post-M83 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M83 planning update.

Do not implement product code.

## Accepted Result

The post-M83 planning update selected:

```text
Milestone 84: Exact Array-Body Pipeline And Source Adapter Ownership Extraction Slice
```

The selected plan is behavior-preserving lowering architecture work. It moves
one cohesive accepted exact array-body staged-lowering pipeline/source-adapter
ownership cluster out of `tslgen/src/tslgen/lowering/boundary.py` into private
typed lowering modules. It is the next large step toward making `boundary.py`
a small facade, with a campaign target of eventually bringing the facade
toward roughly 1,000 physical lines.

## Read First

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`

## Task

Update repository workflow state so the next action is M84 execution, then
create the concrete M84 execution-review loop prompt.

Update:

- `docs/agent/current-redesign-state.md`

Create:

- `docs/agent/runs/m84-execution-review-loop-prompt.md`

## Required State Changes

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 83.
- Post-M83 planning accepted.
- Current action: execute Milestone 84.
- Active executor milestone:
  `Milestone 84: Exact Array-Body Pipeline And Source Adapter Ownership Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m84-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M84 is behavior-preserving lowering architecture work.
  - M84 moves accepted exact array-body pipeline/source-adapter ownership out
    of `boundary.py` into private typed lowering modules.
  - M84 must preserve accepted M42-M83 behavior, public imports, diagnostics,
    source locations, stage names/order, output identities, deterministic
    keys, selected-branch-only behavior, and pipeline snapshots.
  - `boundary.py` remains the public facade for request/result models,
    `lower_candidates`, payload classification, and mini-TSIL lowering.
  - Private exact array-body modules must not import `boundary.py` or the
    `tslgen.lowering` package facade.
  - M84 must not create a second monolith, registry, generic dispatcher,
    callback map, plugin system, fixpoint/backfeed engine, raw-helper
    dispatcher, token-keyed semantic table, broad TSIL parser, broad source
    adapter, or new semantic evaluator.
  - M84 must not add exact return-emission IR, `emit_return(tmp)`
    interpretation, `tmp.data()` semantics, store/call/body/return/
    declaration/array semantics beyond accepted exact structural/request
    records, backend translation, rendering, generated output,
    CLI/report/writer behavior, Rust, compiler execution, file/catalog reads,
    `tsldata` reads during lowering evaluation, host CPU queries, backend map
    reads, or runtime `frozen/` use.
  - Existing exact tokens may move only as structural provenance or invariant
    evidence, not semantic dispatch keys.

## Required M84 Execution Prompt

Create `docs/agent/runs/m84-execution-review-loop-prompt.md` with:

- Accepted state: Milestones 1 through 83 accepted; post-M83 planning accepted.
- Selected milestone title and roadmap scope.
- Read-first files including:
  - `docs/agent/current-redesign-state.md`
  - `AGENTS.md`
  - `PLANS.md`
  - `docs/agent/next-run-prompt-protocol.md`
  - `docs/agent/review-checklist.md`
  - `docs/redesign/implementation-roadmap.md`
  - `docs/redesign/generation-time-semantic-lowering.md`
  - `docs/redesign/behavioral-spec.md`
  - `docs/redesign/pipeline-design.md`
  - `docs/redesign/target-architecture.md`
  - `docs/redesign/testing-strategy.md`
  - `docs/redesign/design-decisions.md`
  - `tslgen/src/tslgen/lowering/boundary.py`
  - `tslgen/src/tslgen/lowering/_stage_contracts.py`
  - `tslgen/src/tslgen/lowering/_selected_body_models.py`
  - `tslgen/src/tslgen/lowering/_generation_models.py`
  - `tslgen/src/tslgen/lowering/_generation_queries.py`
  - `tslgen/src/tslgen/lowering/_generation_control_flow.py`
  - `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_array_body_models.py`
  - `tslgen/src/tslgen/lowering/_array_body_shapes.py`
  - `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_array_body_validation.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_pipeline.py`
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/unit/test_lowering_boundary.py`
- One write-capable executor task.
- Read-only review/audit subagents after implementation:
  - reviewer
  - boundary auditor
  - extensibility auditor
  - validation auditor
  - documentation auditor
- Focused revision loop rules for `Needs Revision`.
- Stop rules for `Return To Planner` and `Reject`.
- Next-prompt generation rules for `Accept` or `Accept With Follow-Ups`.
- Clear instruction not to start M85.

## M84 Validation Commands

The M84 execution prompt must require:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m84 or array_body_pipeline or source_adapter or exact_array"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different private module name than
`_array_body_pipeline.py`, update the py-compile command consistently in the
execution prompt and state.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m83-acceptance-finalization-prompt.md docs/agent/runs/m84-execution-review-loop-prompt.md
```

If other docs are changed during finalization, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. M84 execution prompt path created.
4. Boundary reminders recorded.
5. Validation command and exact result.
6. Whether the repo is ready to execute M84.
