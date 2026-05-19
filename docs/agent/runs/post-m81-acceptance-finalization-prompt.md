# Post-M81 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M81 planning update.

Do not implement code.

## Accepted Result

The post-M81 planning update selected:

```text
Milestone 82: Selected-Body Envelope Ownership Extraction Slice
```

The selected result is behavior-preserving selected-body model ownership
extraction. It moves the accepted M60-M63 selected-body handoff/form/body-IR/
envelope value-model cluster out of `boundary.py` only where the extraction can
remain private, typed, import-stable, and behavior-preserving.

## Task

Update repository workflow state so the next action is M82 execution.

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
- create `docs/agent/runs/m82-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 81.
- Post-M81 planning accepted.
- Current action: execute Milestone 82.
- Active executor milestone:
  `Milestone 82: Selected-Body Envelope Ownership Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m82-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M82 is behavior-preserving selected-body value-model ownership extraction
    only.
  - M82 must preserve accepted M42-M81 behavior, diagnostics, stage names,
    stage ordering, output identities, keys, deterministic ordering,
    selected-branch-only diagnostics, nested envelope identity, no-reparse
    behavior, and public facade imports.
  - M82 must keep `boundary.py` as the public facade/coordinator.
  - Private lowering modules must not import `boundary.py` or the
    `tslgen.lowering` package facade; imports should remain one-way from the
    facade to private typed modules.
  - M82 should create a private selected-body model boundary such as
    `tslgen.lowering._selected_body_models` or an equivalent coherent private
    split.
  - M82 should move only the minimal cohesive selected-body value-model cluster
    needed to avoid circular private imports:
    `OpaqueSelectedBranchBodyHandoff`, `NoSelectedBranchBodyHandoff`,
    `SelectedBranchBodyAssignmentFormRecognition`,
    `NoSelectedBranchBodyAssignmentFormRecognition`,
    `SelectedAssignmentDirectIntrinsicBodyIr`,
    `NoSelectedAssignmentDirectIntrinsicBodyIr`,
    `SelectedBodyEnvelopeEntry`, `SelectedBodyEnvelopeIr`,
    `NoSelectedBodyEnvelopeIr`, and selected-body union aliases that can move
    without importing `boundary.py`.
  - M82 should keep selected-body lowering functions in `boundary.py` unless a
    tiny helper move is required and remains behavior-preserving:
    `handoff_opaque_selected_branch_body`,
    `recognize_selected_branch_body_assignment_form`,
    `lower_selected_branch_body_ir`, and `lower_selected_body_envelope`.
  - M82 should tighten `_array_body_models.py` and
    `_array_body_validation.py` to consume concrete selected-body envelope
    model types where possible rather than broad selected/no-selected
    `hasattr` or cast seams.
  - M82 should materially reduce `boundary.py` from the 5,438-line post-M81
    baseline, but line count must not justify moving unrelated exact
    array-body pipeline code, duplicating moved helpers, creating a second
    monolith, or changing behavior.
  - M82 must not add new lowering semantics, selected-body semantics,
    generation helper semantics, helper evaluation, stage behavior, source
    adapter behavior, stage-construction frameworks, registries, dispatchers,
    plugin systems, hidden backfeeds, fixpoint execution, broad TSIL/body/
    call/store/return/declaration/array parsing, raw helper dispatch, backend
    translation, rendering, generated output, CLI/report/writer behavior,
    Rust, compiler execution, file/catalog reads, `tsldata` reads, host CPU
    queries, backend map reads, extension hardwiring, or runtime `frozen/` use.

## Required M82 Execution Prompt Content

Create `docs/agent/runs/m82-execution-review-loop-prompt.md` as a concrete
orchestrated execution-review prompt.

It must include:

- accepted state through M81 and accepted post-M81 planning;
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
  - `tslgen/src/tslgen/lowering/_generation_models.py`
  - `tslgen/src/tslgen/lowering/_generation_queries.py`
  - `tslgen/src/tslgen/lowering/_generation_control_flow.py`
  - `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_array_body_models.py`
  - `tslgen/src/tslgen/lowering/_array_body_validation.py`
  - `tslgen/src/tslgen/lowering/_array_body_shapes.py`
  - `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_pipeline.py`
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/unit/test_lowering_boundary.py`
- one write-capable executor task for M82;
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

The M82 execution prompt must require:

- behavior-preserving selected-body value-model ownership extraction only;
- public API/import stability through `tslgen.lowering` and the
  `boundary.py` facade;
- no private module imports from `boundary.py` or the `tslgen.lowering`
  package facade;
- no duplicate moved code or compatibility wrappers that recreate the
  monolith;
- no moving source adapters or stage construction that still depend on
  facade-owned `GenerationLoweringStage` or `LoweredImplementation`;
- no broad registry, dispatcher, plugin system, raw helper evaluator, generic
  TSIL parser, generic body/call/store/return/declaration/array parser,
  backend/rendering/output work, or extension hardwiring;
- selected-body tokens to remain provenance/invariant evidence only;
- documentation updates recording the selected-body ownership boundary and
  measured line-count result.

The M82 execution prompt must require validation:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

plus a focused M82 selected-body ownership/import-stability command chosen by
the executor, and:

```bash
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m81-acceptance-finalization-prompt.md docs/agent/runs/m82-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M82.
