# Post-M91 Acceptance Finalization Prompt

You are finalizing the accepted post-M91 planning result.

Do not implement code.

## Accepted Result

Post-M91 planning selected:

```text
Milestone 92: Exact Array Lowering Backend-Handoff Request Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is lowering-side Stage 8 request/provenance work. It creates
one concrete typed backend-handoff request from the accepted M90 exact array
completion package, using the M91 stable pipeline ownership, without starting
backend planning or backend translation.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
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
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M92 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 91.
- Post-M91 planning accepted.
- Current action: execute Milestone 92.
- Active executor milestone:
  `Milestone 92: Exact Array Lowering Backend-Handoff Request Slice`.
- Active run prompt:
  `docs/agent/runs/m92-execution-review-loop-prompt.md`.
- Next expected action: run the M92 execution-review loop.
- Boundary reminders:
  - M92 is Stage 8 lowering-side backend-handoff request work only.
  - M92 consumes accepted typed M90 completion packages through M91 stable
    pipeline ownership.
  - M92 must produce one concrete typed request/provenance output for later
    backend planning, not a wrapper-only abstraction.
  - M92 must preserve accepted M64-M91 diagnostics, source locations, public
    imports, stage names/order, deterministic keys, output identities,
    selected-branch-only behavior, no-external-input boundaries, and pipeline
    snapshots.
  - M92 must not resolve backend values, read backend maps/catalogs, start
    Stage 9 backend planning, translate backend text, create renderer-ready
    IR, render output, infer declaration/store/return/SVE/body semantics,
    repair source text, broaden TSIL parsing, or introduce generic
    backend-value evaluation, broad protocols, hidden backfeeds, fixpoint
    machinery, or hardwiring.
  - M92 should use focused private handoff ownership and avoid growing
    `boundary.py`, `_array_body_pipeline.py`,
    `_array_body_completion_package.py`,
    `_array_body_pipeline_results.py`, or `_array_body_stage_assembly.py` into
    broader catch-all modules.

Create:

```text
docs/agent/runs/m92-execution-review-loop-prompt.md
```

The M92 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M92 scope, out-of-scope items,
required inputs, expected outputs, diagnostics, tests, validation commands,
revision loop, and finalization rules.

Do not modify product code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m92-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M92.
