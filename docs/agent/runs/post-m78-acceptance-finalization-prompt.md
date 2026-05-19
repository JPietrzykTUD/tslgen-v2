# Post-M78 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M78 planning update.

Do not implement code.

## Accepted Result

The post-M78 planning update selected:

```text
Milestone 79: Exact Array-Body Typed Model Ownership Extraction Slice
```

The selected result is behavior-preserving typed model ownership extraction.
It may combine the M78 follow-ups only because they share one ownership
boundary: exact array-body / array-initialization typed models are still owned
by `boundary.py` while exact helper aliases and diagnostics now live in
private lowering modules.

## Task

Update repository workflow state so the next action is M79 execution.

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
- create `docs/agent/runs/m79-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 78.
- Post-M78 planning accepted.
- Current action: execute Milestone 79.
- Active executor milestone:
  `Milestone 79: Exact Array-Body Typed Model Ownership Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m79-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M79 is behavior-preserving typed model ownership extraction only.
  - M79 must preserve accepted M57-M78 behavior, diagnostics, stage names,
    stage ordering, output identities, keys, deterministic ordering,
    selected-branch-only diagnostics, and public facade imports.
  - M79 must keep `boundary.py` as the public facade/coordinator.
  - Private lowering modules must not import `boundary.py`; imports should
    remain one-way from the facade to private typed modules.
  - M79 should create a private exact array-body model boundary such as
    `tslgen.lowering._array_body_models` or an equivalent coherent private
    split.
  - M79 must consolidate duplicated exact helper `Literal` aliases currently
    split between `boundary.py` and `_array_body_shapes.py`.
  - M79 must replace targeted `_array_body_diagnostics.py` `Any` inputs only
    where the new private typed model/protocol boundary supplies the needed
    attributes.
  - M79 should materially reduce `boundary.py` from the 11,109-line post-M78
    baseline, targeting at least 1,500 net physical lines removed unless the
    executor documents that an import-boundary risk requires a narrower
    accepted reduction.
  - The line-count target must not justify moving unrelated shared generation
    or lowering models, creating a second monolith, or changing behavior.
  - M79 must not add new lowering semantics, helper evaluation, stage behavior,
    registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
    execution, broad TSIL/body/call/store/return/declaration/array parsing,
    raw helper dispatch, backend translation, rendering, generated output,
    CLI/report/writer behavior, Rust, compiler execution, file/catalog reads,
    `tsldata` reads, host CPU queries, backend map reads, or runtime `frozen/`
    use.

## Required M79 Execution Prompt Content

Create `docs/agent/runs/m79-execution-review-loop-prompt.md` as a concrete
orchestrated execution-review prompt.

It must include:

- accepted state through M78 and accepted post-M78 planning;
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
  - `tslgen/src/tslgen/lowering/_array_body_shapes.py`
  - `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_pipeline.py`
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/unit/test_lowering_boundary.py`
- one write-capable executor task for M79;
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

The M79 execution prompt must require:

- behavior-preserving typed model ownership extraction only;
- public API/import stability through `tslgen.lowering` and the
  `boundary.py` facade;
- no private module imports from `boundary.py`;
- no duplicate moved code or duplicated exact helper alias ownership left
  behind;
- no broad registry, dispatcher, plugin system, raw helper evaluator, generic
  TSIL parser, generic body/call/store/return/declaration/array parser,
  backend/rendering/output work, or extension hardwiring;
- exact recognizer tokens to remain structural evidence only;
- documentation updates recording the model ownership boundary and measured
  line-count result.

The M79 execution prompt must require validation:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

plus a focused M79 model-ownership/import-stability command chosen by the
executor, and:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m78-acceptance-finalization-prompt.md docs/agent/runs/m79-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M79.
