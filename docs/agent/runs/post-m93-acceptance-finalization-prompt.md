# Post-M93 Acceptance Finalization Prompt

You are finalizing the accepted post-M93 planning result.

Do not implement code.

## Accepted Result

Post-M93 planning selected:

```text
Milestone 94: Lowering Operation Package Diagnostics and Provenance Ownership Split Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is behavior-preserving Stage 8 lowering maintainability
work. It splits M93 operation-package diagnostics, accepted-source narrowing,
mini-TSIL package-contract checks, exact-array provenance validation, and
package model ownership into focused private modules before adding any new
operation package families.

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
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_mini_tsil_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M94 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 93.
- Post-M93 planning accepted.
- Current action: execute Milestone 94.
- Active executor milestone:
  `Milestone 94: Lowering Operation Package Diagnostics and Provenance Ownership Split Slice`.
- Active run prompt:
  `docs/agent/runs/m94-execution-review-loop-prompt.md`.
- Next expected action: run the M94 execution-review loop.
- Boundary reminders:
  - M94 is behavior-preserving Stage 8 lowering maintainability work only.
  - M94 preserves the accepted M93 `lowering_operation_package` behavior for
    exactly accepted M86 mini-TSIL leaf returns and accepted M92 exact array
    backend-handoff requests.
  - M94 may split operation-package models, diagnostics, source narrowing,
    accepted M86 leaf-return package checks, and M92/M90/M89/M88/M72/M67
    provenance validation into focused private modules.
  - M94 must keep public `tslgen.lowering` and `tslgen.lowering.boundary`
    operation-package imports stable.
  - M94 must preserve accepted M93 diagnostics, diagnostic codes/locations,
    package keys, stage name/order, snapshots, object identity, deterministic
    ordering, selected-branch-only behavior, public imports, and
    no-external-input boundaries.
  - M94 must not add new operation package families, new lowering semantics,
    backend maps/catalog reads, backend-uninit resolution, Stage 9 backend
    planning, backend translation, renderer-ready IR, rendering, generated
    output, broad TSIL/body/call/store/return/declaration/array/SVE semantics,
    source repair, registries, semantic dispatchers, hidden backfeeds, fixpoint
    machinery, hardwiring, or runtime `frozen/` use.
  - M94 must prove `_operation_package.py` drops materially below the roughly
    1,000-line guardrail and that no new private operation-package module
    becomes a replacement monolith.

Create:

```text
docs/agent/runs/m94-execution-review-loop-prompt.md
```

The M94 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M94 scope, out-of-scope items,
required inputs, expected behavior-preserving outputs, tests, validation
commands, revision loop, and finalization rules.

Do not modify product code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m93-acceptance-finalization-prompt.md docs/agent/runs/m94-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M94.
