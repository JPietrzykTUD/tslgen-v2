# Post-M85 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M85 planning update.

Do not implement product code.

## Accepted Result

The post-M85 planning update selected:

```text
Milestone 86: Candidate Payload Intake And Mini-TSIL Leaf Lowering Extraction Slice
```

The selected plan is behavior-preserving lowering architecture work. It moves
accepted candidate payload-intake helpers and the accepted mini-TSIL leaf
return lowerer out of `tslgen/src/tslgen/lowering/boundary.py` into focused
private typed modules while preserving public facade imports, diagnostics,
source locations, stage names/order, output identities, deterministic keys,
selected-branch-only behavior, and pipeline snapshots.

Post-M85 planning review recorded one continuing follow-up: exact
return-emission structural/request IR remains a high-value semantic frontier,
but it is not part of M86.

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

Update repository workflow state so the next action is M86 execution, then
create the concrete M86 execution-review loop prompt.

Update:

- `docs/agent/current-redesign-state.md`

Create:

- `docs/agent/runs/m86-execution-review-loop-prompt.md`

## Required State Changes

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 85.
- Post-M85 planning accepted.
- Current action: execute Milestone 86.
- Active executor milestone:
  `Milestone 86: Candidate Payload Intake And Mini-TSIL Leaf Lowering Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m86-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M86 is behavior-preserving lowering architecture work.
  - M86 moves only the accepted payload-intake cluster and the accepted
    mini-TSIL leaf return-lowering cluster out of `boundary.py`.
  - The payload-intake module may own `LoweringStrategy`,
    `PayloadClassification`, `ClassifiedPayload`, `LoweringInput`,
    `_classify_payload`, and `_unsupported_payload_diagnostic`.
  - The payload-intake module must not own `LoweringInputSet`,
    `LoweringRequest`, `GenerationContext`, `LoweredImplementation`,
    `LoweringPlan`, `prepare_lowering_inputs`, `lower_candidates`,
    `_lower_input`, stage builders, source adapters, or semantic lowering
    orchestration.
  - The mini-TSIL module is leaf-return lowering only. It preserves the
    accepted direct parameter-add and `intrin_compose<add>` return forms and
    must not add new TSIL syntax, broad expression/body/return semantics,
    generation helper evaluation, selected-body/exact-array dependencies,
    backend translation, or renderer-facing IR.
  - `_lower_input` may only delegate the accepted payload-classification and
    mini-TSIL leaf return-lowering calls to focused private helpers while
    preserving the existing call order, diagnostics, and stage construction.
  - Intended import direction:
    `boundary.py -> _lowering_inputs`,
    `boundary.py -> _mini_tsil_lowering`,
    `_mini_tsil_lowering -> _lowering_inputs and _stage_contracts`,
    `_lowering_inputs -> candidates, diagnostics, result, values`.
  - The new private modules must not import `boundary.py`, `tslgen.lowering`,
    selected-body lowering modules, exact array-body modules, backend modules,
    renderers, `tsldata`, or `frozen/`.
  - M86 must preserve accepted M42-M85 behavior, public imports, diagnostics,
    source locations, stage names/order, output identities, deterministic
    keys, selected-branch-only behavior, payload classification keys,
    typed-opaque behavior, and pipeline snapshots.
  - M86 must not introduce a handler registry, plugin system, callback map,
    ordered lowerer table, generic TSIL statement dispatcher, raw text rewrite
    engine, raw-helper dispatch, token-keyed semantic map, broad
    source-adapter protocol, fixpoint/backfeed engine, backend translation,
    rendering, generated output, file/catalog reads, `tsldata` reads during
    lowering evaluation, host CPU queries, backend map reads, or runtime
    `frozen/` use.

## Required M86 Execution Prompt

Create `docs/agent/runs/m86-execution-review-loop-prompt.md` with:

- Accepted state: Milestones 1 through 85 accepted; post-M85 planning
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
  - `tslgen/src/tslgen/lowering/boundary.py`
  - `tslgen/src/tslgen/lowering/_stage_contracts.py`
  - `tslgen/src/tslgen/lowering/_generation_models.py`
  - `tslgen/src/tslgen/lowering/_generation_queries.py`
  - `tslgen/src/tslgen/lowering/_generation_control_flow.py`
  - `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_selected_body_lowering.py`
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
- Clear instruction not to start M87.

## M86 Validation Commands

The M86 execution prompt must require:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m86 or lowering_input or payload_classification or mini_tsil or typed_opaque"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses different private module names than
`_lowering_inputs.py` and `_mini_tsil_lowering.py`, update the py-compile and
line-count commands consistently in the execution prompt and state.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m85-acceptance-finalization-prompt.md docs/agent/runs/m86-execution-review-loop-prompt.md
```

If other docs are changed during finalization, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. M86 execution prompt path created.
4. Boundary reminders recorded.
5. Validation command and exact result.
6. Whether the repo is ready to execute M86.
