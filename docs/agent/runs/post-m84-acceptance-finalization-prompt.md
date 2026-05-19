# Post-M84 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M84 planning update.

Do not implement product code.

## Accepted Result

The post-M84 planning update selected:

```text
Milestone 85: Selected-Body Lowering Ownership Extraction Slice
```

The selected plan is behavior-preserving lowering architecture work. It moves
the accepted M60-M63 selected-body lowering function/source-helper ownership
out of `tslgen/src/tslgen/lowering/boundary.py` into a focused private typed
lowering module, likely `tslgen.lowering._selected_body_lowering`, while
preserving public facade imports, diagnostics, source locations, stage
names/order, output identities, deterministic keys, selected-branch-only
behavior, and pipeline snapshots.

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
- `docs/redesign/open-questions.md`

## Task

Update repository workflow state so the next action is M85 execution, then
create the concrete M85 execution-review loop prompt.

Update:

- `docs/agent/current-redesign-state.md`

Create:

- `docs/agent/runs/m85-execution-review-loop-prompt.md`

## Required State Changes

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 84.
- Post-M84 planning accepted.
- Current action: execute Milestone 85.
- Active executor milestone:
  `Milestone 85: Selected-Body Lowering Ownership Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m85-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M85 is behavior-preserving lowering architecture work.
  - M85 moves accepted M60-M63 selected-body lowerer/source-helper ownership
    out of `boundary.py` into a focused private typed lowering module such as
    `_selected_body_lowering.py`.
  - M85 must preserve accepted M42-M84 behavior, public imports, diagnostics,
    source locations, stage names/order, output identities, deterministic
    keys, selected-branch-only behavior, and pipeline snapshots.
  - `boundary.py` remains the public facade for request/result models,
    `lower_candidates`, `_lower_input`, payload classification, mini-TSIL
    lowering, generation control-flow pruning, and exact array-body pipeline
    orchestration.
  - The new private selected-body lowering module must not import
    `boundary.py`, `tslgen.lowering`, `_array_body_sources.py`, or
    `_array_body_lowering.py` as convenience dispatchers.
  - M85 must not move selected-body behavior into `_selected_body_models.py`.
  - M85 must not add new selected-body semantics, broad TSIL/body/call/store/
    return semantics, exact return-emission IR, backend translation,
    rendering, generated output, registries, generic dispatchers, callback
    maps, fixpoint/backfeed engines, raw-helper dispatch, file/catalog reads,
    `tsldata` reads during lowering evaluation, host CPU queries, backend map
    reads, or runtime `frozen/` use.

## Required M85 Execution Prompt

Create `docs/agent/runs/m85-execution-review-loop-prompt.md` with:

- Accepted state: Milestones 1 through 84 accepted; post-M84 planning accepted.
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
  - `docs/redesign/open-questions.md`
  - `tslgen/src/tslgen/lowering/boundary.py`
  - `tslgen/src/tslgen/lowering/_selected_body_models.py`
  - `tslgen/src/tslgen/lowering/_stage_contracts.py`
  - `tslgen/src/tslgen/lowering/_generation_models.py`
  - `tslgen/src/tslgen/lowering/_generation_control_flow.py`
  - `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
  - `tslgen/src/tslgen/lowering/_array_body_sources.py`
  - `tslgen/src/tslgen/lowering/_array_body_lowering.py`
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
- Clear instruction not to start M86.

## M85 Validation Commands

The M85 execution prompt must require:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m85 or selected_body_lowering or selected_body_handoff or selected_body_envelope"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different private module name than
`_selected_body_lowering.py`, update the py-compile command consistently in
the execution prompt and state.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m84-acceptance-finalization-prompt.md docs/agent/runs/m85-execution-review-loop-prompt.md
```

If other docs are changed during finalization, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. M85 execution prompt path created.
4. Boundary reminders recorded.
5. Validation command and exact result.
6. Whether the repo is ready to execute M85.
