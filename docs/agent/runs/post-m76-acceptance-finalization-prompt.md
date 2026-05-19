# Post-M76 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M76 planning update.

Do not implement code.

## Accepted Result

The post-M76 planning update selected:

```text
Milestone 77: Composable Lowering Pipeline Module Boundary Slice
```

The planning result is behavior-preserving lowering architecture work. It
starts moving the accepted Stage 8 lowering path behind typed, composable
private module/stage boundaries while preserving accepted M57-M76 behavior.

## Task

Update repository workflow state so the next action is M77 execution.

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
- create `docs/agent/runs/m77-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 76.
- Post-M76 planning accepted.
- Current action: execute Milestone 77.
- Active executor milestone:
  `Milestone 77: Composable Lowering Pipeline Module Boundary Slice`.
- Active run prompt:
  `docs/agent/runs/m77-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M77 is behavior-preserving lowering architecture/refactor work only.
  - M77 must preserve accepted M57-M76 behavior, public lowering imports, stage
    names, output identities, diagnostics, and deterministic ordering.
  - M77 may introduce private typed stage, pipeline, fact, request,
    dependency, artifact-store, or coordinator-boundary values only where
    needed for the accepted M58-M76 pattern.
  - Future backfeeds must be typed facts, typed requests, dependencies, or
    deterministic coordinator decisions, not hidden recursion, raw helper
    dispatch, broad registries, or central semantic `if`/`elif` chains.
  - Exact tokens such as `pg`, `svptrue_b16`, `svptrue_b32`, `svptrue_b64`,
    `intrin`, `svst1`, `tmp.data()`, and `a` must remain slice-local
    structural evidence unless a future accepted milestone introduces explicit
    typed semantic rules.
  - No new lowering semantics, whole-file rewrite behavior, generic
    call/body/store/return/declaration/array parsing or IR, backend
    translation, rendering, generated output, CLI/report/writer behavior,
    Rust, compiler execution, lowering-time file/catalog reads, `tsldata`
    reads, host CPU queries, backend map reads, or runtime `frozen/` use is in
    M77.

## Required M77 Execution Prompt Content

Create `docs/agent/runs/m77-execution-review-loop-prompt.md` as a concrete
orchestrated execution-review prompt.

It must include:

- accepted state through M76 and accepted post-M76 planning;
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
  - `tslgen/src/tslgen/lowering/__init__.py`
  - `tslgen/tests/unit/test_lowering_boundary.py`
- one write-capable executor task for M77;
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

The M77 execution prompt must require:

- behavior-preserving extraction/refactor only;
- public API/import stability through `tslgen.lowering` and any existing
  `boundary.py` facade imports;
- a coherent private module/stage extraction under
  `tslgen/src/tslgen/lowering/`, not a whole-file rewrite;
- typed private pipeline/stage/fact/request/dependency boundaries where they
  are concretely needed;
- no broad registry, semantic dispatcher, raw helper evaluator, generic call
  parser, generic body parser, runtime plugin system, backend/rendering/output
  work, or extension hardwiring;
- exact recognizer tokens to remain structural evidence only;
- documentation updates if the module/pipeline boundary decision becomes more
  precise during execution.

The M77 execution prompt must require validation:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

plus a focused M77 module-boundary/import-preservation command chosen by the
executor, and:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m76-acceptance-finalization-prompt.md docs/agent/runs/m77-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M77.
