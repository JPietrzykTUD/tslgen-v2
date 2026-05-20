# Post-M87 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M87 planning update.

Do not implement product code.

## Accepted Result

The post-M87 planning update selected:

```text
Milestone 88: Exact Array Body Structural Package Assembly Slice
```

The selected plan assembles accepted M64-M87 exact array-body facts into one
typed, source-ordered structural package for the selected `array.tsl:105-111`
body shape. It is typed aggregation/provenance validation only.

This is not a `.tsl` body repair milestone and not semantic body lowering.
Unsupported, missing, duplicate, mismatched, out-of-order, or
provenance-inconsistent inputs are diagnostics/negative tests, not reasons to
guess or correct source intent.

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

Update repository workflow state so the next action is M88 execution, then
create the concrete M88 execution-review loop prompt.

Update:

- `docs/agent/current-redesign-state.md`

Create:

- `docs/agent/runs/m88-execution-review-loop-prompt.md`

## Required State Changes

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 87.
- Post-M87 planning accepted.
- Current action: execute Milestone 88.
- Active executor milestone:
  `Milestone 88: Exact Array Body Structural Package Assembly Slice`.
- Active run prompt:
  `docs/agent/runs/m88-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M88 is generation-time/lowering structural package assembly only.
  - M88 consumes accepted M64-M87 typed exact array-body facts.
  - M88 assembles one source-ordered typed structural package, such as
    `ExactArrayBodyStructuralPackageIr`, for the selected
    `array.tsl:105-111` body shape.
  - M88 must preserve member object identity/provenance and validate common
    candidate/source/branch/type context.
  - M88 must not correct, normalize, rewrite, complete, reorder, reparse, or
    guess the intended meaning of malformed `.tsl` implementation bodies.
  - M88 must not implement declaration semantics, array semantics, variable
    lifetime/scope, allocation semantics, initializer behavior, store
    semantics, return-value semantics, `tmp.data()` pointer semantics,
    `emit_return` semantics, `assume_aligned` semantics, `intrin<svst1>`
    semantics, SVE predicate/vector/register semantics, memory behavior,
    backend uninit translation, backend translation, backend map reads,
    renderer-ready IR, rendering, generated output, generated tests,
    CLI/report/writer behavior, Rust, compiler execution, broad TSIL parsing,
    registries, dispatchers, plugin systems, raw helper dispatch, raw text
    rewriting, fixpoint/backfeed machinery, file/catalog reads, `tsldata`
    reads during lowering evaluation, host CPU queries, or runtime `frozen/`
    use.
  - M88 should use focused private package ownership, such as
    `tslgen.lowering._array_body_package`, and must not turn
    `_array_body_models.py`, `_array_body_sources.py`,
    `_array_body_validation.py`, `_array_body_diagnostics.py`, or
    `_array_body_pipeline.py` into catch-all modules.
  - M88 must preserve accepted M64-M87 diagnostics, source locations, stage
    names/order, output identities, deterministic keys, selected-branch-only
    behavior, public imports, and pipeline snapshots.

## Required M88 Execution Prompt

Create `docs/agent/runs/m88-execution-review-loop-prompt.md` with:

- Accepted state: Milestones 1 through 87 accepted; post-M87 planning
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
  - `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
  - `tslgen/src/tslgen/lowering/_array_body_sources.py`
  - `tslgen/src/tslgen/lowering/_array_body_validation.py`
  - `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
  - `tslgen/src/tslgen/lowering/_return_emission.py`
  - `tslgen/src/tslgen/lowering/_pipeline.py`
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
- Clear instruction not to start post-M88 planning until review accepts M88.

## M88 Validation Commands

The M88 execution prompt must require:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m88 or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private package module name,
include that file consistently in the line-count, py-compile, and
import-boundary validation.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m87-acceptance-finalization-prompt.md docs/agent/runs/m88-execution-review-loop-prompt.md
```

If other docs are changed during finalization, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. M88 execution prompt path created.
4. Boundary reminders recorded.
5. Validation command and exact result.
6. Whether the repo is ready to execute M88.
