# Post-M86 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M86 planning update.

Do not implement product code.

## Accepted Result

The post-M86 planning update selected:

```text
Milestone 87: Exact Return-Emission Structural Request IR Slice
```

The selected plan adds the next lowering semantic frontier after the M77-M86
facade/module cleanup. It records only the exact trailing array-body
`emit_return(tmp);` shape, with insignificant whitespace, as typed
structural/request IR. The returned token must link to the accepted M73
declaration-shell variable token through accepted M74/M76 provenance.

This is not a `.tsl` body repair milestone. Unsupported or malformed nearby
forms are diagnostics/negative tests, not extra supported syntax.

## Read First

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

## Task

Update repository workflow state so the next action is M87 execution, then
create the concrete M87 execution-review loop prompt.

Update:

- `docs/agent/current-redesign-state.md`

Create:

- `docs/agent/runs/m87-execution-review-loop-prompt.md`

## Required State Changes

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 86.
- Post-M86 planning accepted.
- Current action: execute Milestone 87.
- Active executor milestone:
  `Milestone 87: Exact Return-Emission Structural Request IR Slice`.
- Active run prompt:
  `docs/agent/runs/m87-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M87 is generation-time/lowering structural-request work only.
  - M87 consumes accepted M74 `ExactArrayBodyStructuralSequenceIr` provenance
    and accepted M76 post-branch call-site provenance as typed inputs.
  - M87 records only the exact trailing `emit_return(tmp);` source shape,
    allowing insignificant whitespace.
  - The returned token must match the accepted M73 declaration-shell variable
    token as provenance only.
  - M87 must not correct, normalize, rewrite, complete, reorder, or guess the
    intended meaning of malformed `.tsl` implementation bodies.
  - Nearby or malformed return-emission forms are diagnostic boundaries, not
    supported syntax.
  - M87 must not broaden `emit_return(...)`, lower expressions inside
    `emit_return`, implement return-value semantics, variable lifetime/scope,
    `tmp.data()` semantics, store/call semantics, array semantics, backend
    translation, renderer-ready IR, rendering, generated output, generated
    tests, CLI/report/writer behavior, Rust, compiler execution, broad TSIL
    parsing, registries, dispatchers, plugin systems, raw helper dispatch,
    raw text rewriting, fixpoint/backfeed machinery, file/catalog reads,
    `tsldata` reads during lowering evaluation, backend map reads, host CPU
    queries, or runtime `frozen/` use.
  - M87 must preserve accepted M64-M86 diagnostics, source locations, stage
    names/order, output identities, deterministic keys, selected-branch-only
    behavior, public imports, and pipeline snapshots.
  - Production files should remain cohesive. If adding M87 would turn an
    existing exact array-body module into a catch-all or push it materially
    past the roughly 1,000-line guardrail, prefer a focused private
    return-emission module with one-way imports and import-boundary tests, or
    document why a temporary exception is safer.

## Required M87 Execution Prompt

Create `docs/agent/runs/m87-execution-review-loop-prompt.md` with:

- Accepted state: Milestones 1 through 86 accepted; post-M86 planning
  accepted.
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
  - `tsldata/primitives/load_store/array.tsl`
  - `tslgen/src/tslgen/lowering/boundary.py`
  - `tslgen/src/tslgen/lowering/_array_body_models.py`
  - `tslgen/src/tslgen/lowering/_array_body_lowering.py`
  - `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
  - `tslgen/src/tslgen/lowering/_array_body_sources.py`
  - `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_array_body_validation.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_stage_contracts.py`
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
- Clear instruction not to start post-M87 planning until review accepts M87.

## M87 Validation Commands

The M87 execution prompt must require:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_exact_shapes.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m87 or return_emission or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation creates a focused private return-emission module, include it
in the line-count, py-compile, and import-boundary validation.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m86-acceptance-finalization-prompt.md docs/agent/runs/m87-execution-review-loop-prompt.md
```

If other docs are changed during finalization, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. M87 execution prompt path created.
4. Boundary reminders recorded.
5. Validation command and exact result.
6. Whether the repo is ready to execute M87.
