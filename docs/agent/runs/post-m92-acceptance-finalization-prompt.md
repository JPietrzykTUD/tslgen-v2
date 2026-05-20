# Post-M92 Acceptance Finalization Prompt

You are finalizing the accepted post-M92 planning result.

Do not implement code.

## Accepted Result

Post-M92 planning selected:

```text
Milestone 93: Dual-Source Lowering Operation Package Boundary Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is Stage 8 lowering package-boundary work. It packages
exactly two accepted typed source families: accepted M86 mini-TSIL leaf return
statements and accepted M92 exact array backend-handoff requests. It proves
that the lowering package boundary is not array-only without creating a broad
cross-primitive operation framework.

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
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/primitives/load_store/array.tsl`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_mini_tsil_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_handoff.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M93 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 92.
- Post-M92 planning accepted.
- Current action: execute Milestone 93.
- Active executor milestone:
  `Milestone 93: Dual-Source Lowering Operation Package Boundary Slice`.
- Active run prompt:
  `docs/agent/runs/m93-execution-review-loop-prompt.md`.
- Next expected action: run the M93 execution-review loop.
- Boundary reminders:
  - M93 is Stage 8 lowering operation package-boundary work only.
  - M93 packages exactly accepted M86 mini-TSIL leaf return values and
    accepted M92 exact array backend-handoff requests as distinct typed
    source-family entries.
  - M93 must preserve source-family identity and provenance rather than
    normalizing M86 and M92 into broad body semantics.
  - M93 must preserve accepted M57-M92 diagnostics, source locations, public
    imports, deterministic keys, selected-branch-only behavior,
    no-external-input boundaries, and pipeline snapshots.
  - M93 must not add backend-uninit resolution, backend map/catalog reads,
    Stage 9 backend planning, backend translation, renderer-ready IR,
    rendering, generated output, primitive dependency closure, operation
    scheduling, wrapper planning, artifact path planning, broad TSIL parsing,
    source repair, broad body/call/store/return/declaration/array/SVE
    semantics, operation registries, semantic dispatchers, hidden backfeeds,
    fixpoint machinery, or hardwiring.
  - M93 should use focused private package ownership and avoid growing
    `boundary.py`, `_stage_contracts.py`, or exact-array modules into broader
    catch-all modules.

Create:

```text
docs/agent/runs/m93-execution-review-loop-prompt.md
```

The M93 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M93 scope, out-of-scope items,
required inputs, expected typed outputs, diagnostics, tests, validation
commands, revision loop, and finalization rules.

Do not modify product code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m92-acceptance-finalization-prompt.md docs/agent/runs/m93-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M93.
