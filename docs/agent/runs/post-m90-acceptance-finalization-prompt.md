# Post-M90 Acceptance Finalization Prompt

You are finalizing the accepted post-M90 planning result.

Do not implement code.

## Accepted Result

Post-M90 planning selected:

```text
Milestone 91: Stage 8 Exact Array Pipeline Ownership Consolidation Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is behavior-preserving Stage 8 lowering architecture work.
It consolidates exact array pipeline result aggregation, stage/snapshot
assembly, and public handoff aggregation into focused private ownership before
adding more lowering semantics.

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
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M91 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 90.
- Post-M90 planning accepted.
- Current action: execute Milestone 91.
- Active executor milestone:
  `Milestone 91: Stage 8 Exact Array Pipeline Ownership Consolidation Slice`.
- Active run prompt:
  `docs/agent/runs/m91-execution-review-loop-prompt.md`.
- Next expected action: run the M91 execution-review loop.
- Boundary reminders:
  - M91 is behavior-preserving Stage 8 exact array pipeline ownership
    consolidation only.
  - M91 may move exact array pipeline result DTOs, stage construction helpers,
    snapshot step assembly, and public handoff aggregation into focused private
    modules.
  - M91 must preserve accepted M64-M90 diagnostics, source locations, stage
    names/order, output identities, deterministic keys, selected-branch-only
    behavior, public imports, no-external-input boundaries, and pipeline
    snapshots.
  - M91 must keep `boundary.py` as a public facade/projection surface and
    `_array_body_pipeline.py` as orchestration over focused helpers.
  - M91 must not add new lowering semantics, backend-uninit resolution,
    backend maps/catalog reads, backend translation, Stage 9 backend planning,
    renderer-ready IR, rendering, generated output, CLI/report/writer
    behavior, Rust, compiler execution, broad TSIL parsing, broad body/
    declaration/array/store/return/call/SVE semantics, source-body repair,
    broad protocols, registries, raw-helper dispatch, callback maps, plugin
    systems, hidden backfeeds, fixpoint machinery, or extension-specific
    hardwiring.
  - M91 must not create a replacement private monolith; new private modules
    need clear ownership and one-way imports.

Create:

```text
docs/agent/runs/m91-execution-review-loop-prompt.md
```

The M91 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M91 scope, out-of-scope items,
required inputs, expected outputs, tests, validation commands, revision loop,
and finalization rules.

Do not modify product code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m91-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M91.
