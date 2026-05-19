# Post-M77 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M77 planning update.

Do not implement code.

## Accepted Result

The post-M77 planning update selected:

```text
Milestone 78: Lowering Boundary Package Decomposition Slice
```

The planning result is behavior-preserving lowering package decomposition. It
must materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted exact array-body / array-initialization lowering package behind
private typed modules while preserving accepted M57-M77 behavior.

## Task

Update repository workflow state so the next action is M78 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`

## Required Changes

Update only workflow files unless a narrow wording correction is needed:

- `docs/agent/current-redesign-state.md`
- create `docs/agent/runs/m78-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 77.
- Post-M77 planning accepted.
- Current action: execute Milestone 78.
- Active executor milestone:
  `Milestone 78: Lowering Boundary Package Decomposition Slice`.
- Active run prompt:
  `docs/agent/runs/m78-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M78 is behavior-preserving lowering package decomposition only.
  - M78 must move the accepted exact array-body / array-initialization lowering
    package from M63-M77 out of `boundary.py` into private typed modules.
  - M78 must preserve public `tslgen.lowering` and
    `tslgen.lowering.boundary` imports.
  - M78 must reduce `boundary.py` by at least 1,000 physical lines from the
    12,371-line pre-M78 baseline and must not leave duplicate moved code
    behind.
  - M78 may move exact package-owned models, orchestration, stage builders,
    source adapters, validators, and diagnostics only when they are
    exclusively consumed by the exact array-body / array-initialization path or
    necessary for a coherent private boundary.
  - M78 must move remaining M75 exact predicate-init recognizer tokens such as
    `svbool_t`, `pg`, and `svptrue_b8` into `_exact_shapes.py` only as
    slice-local structural evidence.
  - M78 must not add new lowering semantics, generic body/call/store/return/
    declaration/array semantics, broad TSIL parsing, raw helper dispatch,
    backend translation, rendering, generated output, CLI/report/writer
    behavior, Rust, compiler execution, lowering-time file/catalog reads,
    `tsldata` reads, host CPU queries, backend map reads, runtime `frozen/`
    use, broad registries, runtime plugins, semantic dispatchers, hidden
    backfeeds, or fixpoint execution.

## Required M78 Execution Prompt Content

Create `docs/agent/runs/m78-execution-review-loop-prompt.md` as a concrete
orchestrated execution-review prompt.

It must include:

- accepted state through M77 and accepted post-M77 planning;
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
  - `docs/redesign/open-questions.md`
  - `docs/redesign/frozen-parity-baselines.md`
  - `tslgen/src/tslgen/lowering/boundary.py`
  - `tslgen/src/tslgen/lowering/_exact_shapes.py`
  - `tslgen/src/tslgen/lowering/_pipeline.py`
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/unit/test_lowering_boundary.py`
- one write-capable executor task for M78;
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

The M78 execution prompt must require:

- behavior-preserving package decomposition only;
- public API/import stability through `tslgen.lowering` and the
  `boundary.py` facade;
- a coherent exact array-body / array-initialization extraction target, not a
  whole-file rewrite;
- at least 1,000 physical lines removed from `boundary.py` relative to the
  12,371-line pre-M78 baseline;
- no duplicate moved code left behind;
- no broad registry, semantic dispatcher, raw helper evaluator, generic call
  parser, generic body parser, runtime plugin system, backend/rendering/output
  work, or extension hardwiring;
- exact recognizer tokens to remain structural evidence only;
- documentation updates recording the decomposition boundary and measured
  line-count result.

The M78 execution prompt must require validation:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

plus a focused M78 module-decomposition/import-stability command chosen by the
executor, and:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m77-acceptance-finalization-prompt.md docs/agent/runs/m78-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M78.
