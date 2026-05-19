# Post-M79 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M79 planning update.

Do not implement code.

## Accepted Result

The post-M79 planning update selected:

```text
Milestone 80: Exact Array-Body Validation Boundary Extraction Slice
```

The selected result is behavior-preserving exact array-body validation
boundary extraction. It moves accepted exact validation/request-record helper
ownership out of `boundary.py` only where the extraction can remain private,
typed, import-stable, and behavior-preserving.

## Task

Update repository workflow state so the next action is M80 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/behavioral-spec.md`

## Required Changes

Update only workflow files unless a narrow wording correction is needed:

- `docs/agent/current-redesign-state.md`
- create `docs/agent/runs/m80-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 79.
- Post-M79 planning accepted.
- Current action: execute Milestone 80.
- Active executor milestone:
  `Milestone 80: Exact Array-Body Validation Boundary Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m80-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M80 is behavior-preserving validation/request-record helper extraction
    only.
  - M80 must preserve accepted M57-M79 behavior, diagnostics, stage names,
    stage ordering, output identities, keys, deterministic ordering,
    selected-branch-only diagnostics, and public facade imports.
  - M80 must keep `boundary.py` as the public facade/coordinator.
  - Private lowering modules must not import `boundary.py`; imports should
    remain one-way from the facade to private typed modules.
  - M80 should create a private exact array-body validation boundary such as
    `tslgen.lowering._array_body_validation` or an equivalent coherent private
    split.
  - M80 should move only accepted exact validation, request-record selection,
    metadata lookup validation, and small construction helpers that can move
    without importing `boundary.py`.
  - M80 must add or preserve a private-import-boundary regression test for
    accepted private lowering modules.
  - M80 should materially reduce `boundary.py` from the 8,915-line post-M79
    baseline, targeting at least 1,500 net physical lines removed unless the
    executor documents that an import-boundary risk requires a narrower
    accepted reduction.
  - The line-count target must not justify moving unrelated shared generation
    or lowering models, creating a second monolith, or changing behavior.
  - M80 must not add new lowering semantics, helper evaluation, stage behavior,
    source-adapter behavior, stage-construction frameworks, registries,
    dispatchers, plugin systems, hidden backfeeds, fixpoint execution, broad
    TSIL/body/call/store/return/declaration/array parsing, raw helper
    dispatch, backend translation, rendering, generated output, CLI/report/
    writer behavior, Rust, compiler execution, file/catalog reads, `tsldata`
    reads, host CPU queries, backend map reads, or runtime `frozen/` use.

## Required M80 Execution Prompt Content

Create `docs/agent/runs/m80-execution-review-loop-prompt.md` as a concrete
orchestrated execution-review prompt.

It must include:

- accepted state through M79 and accepted post-M79 planning;
- the selected milestone title;
- read-first files:
  - `docs/agent/current-redesign-state.md`
  - `AGENTS.md`
  - `PLANS.md`
  - `docs/agent/review-checklist.md`
  - `docs/redesign/implementation-roadmap.md`
  - `docs/redesign/pipeline-design.md`
  - `docs/redesign/generation-time-semantic-lowering.md`
  - `docs/redesign/target-architecture.md`
  - `docs/redesign/design-decisions.md`
  - `docs/redesign/testing-strategy.md`
  - `docs/redesign/behavioral-spec.md`
  - `docs/redesign/open-questions.md`
  - `docs/redesign/frozen-parity-baselines.md`
  - `tslgen/src/tslgen/lowering/boundary.py`
  - `tslgen/src/tslgen/lowering/_array_body_models.py`
  - `tslgen/src/tslgen/lowering/_array_body_shapes.py`
  - `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_pipeline.py`
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/unit/test_lowering_boundary.py`
- one write-capable executor task for M80;
- read-only review/audit tasks after the executor:
  - reviewer using `docs/agent/review-checklist.md`;
  - boundary auditor;
  - extensibility/maintainability auditor;
  - validation auditor;
  - documentation auditor;
- revision-loop rules:
  - if review returns `Needs Revision`, run one focused revision executor and
    focused re-review;
  - if review returns `Return To Planner` or `Reject`, stop implementation and
    create the appropriate planner/rollback prompt;
  - if review returns `Accept` or `Accept With Follow-Ups`, update
    `docs/agent/current-redesign-state.md` and create the next concrete prompt
    under `docs/agent/runs/`.

The M80 execution prompt must require:

- behavior-preserving exact validation/request-record helper extraction only;
- public API/import stability through `tslgen.lowering` and the
  `boundary.py` facade;
- no private module imports from `boundary.py`;
- no duplicate moved code or compatibility wrappers that recreate the
  monolith;
- no moving source adapters or stage construction that still depend on
  facade-owned `GenerationLoweringStage` or `LoweredImplementation`, unless a
  tiny dependency move is required and remains behavior-preserving;
- no broad registry, dispatcher, plugin system, raw helper evaluator, generic
  TSIL parser, generic body/call/store/return/declaration/array parser,
  backend/rendering/output work, or extension hardwiring;
- exact recognizer tokens to remain structural evidence only;
- documentation updates recording the validation boundary and measured
  line-count result.

The M80 execution prompt must require validation:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

plus a focused M80 validation-boundary/import-stability command chosen by the
executor, and:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m79-acceptance-finalization-prompt.md docs/agent/runs/m80-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M80.
