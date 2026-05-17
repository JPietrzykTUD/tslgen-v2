# Post-M59 Acceptance Finalization Prompt

You are finalizing the accepted post-M59 planning update.

Do not implement code.

## Accepted Result

The post-M59 planning update selected:

```text
Milestone 60: Opaque Selected Branch Body Handoff Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The remaining follow-ups are non-blocking:

- M60 handoff diagnostics must stay boundary-level and must not classify direct
  intrinsics, assignments, arrays, calls, casts, loops, vector metadata,
  backend uninit, or SVE predicates.
- The M60 executor must introduce a distinct typed opaque selected-body handoff
  value instead of expanding M59 pruning metadata into the reusable body-handoff
  contract.
- A future docs wording cleanup may clarify "selected opaque M60 handoff
  candidate" as "M60 selected-for-human-acceptance opaque handoff" in
  `docs/redesign/open-questions.md` and
  `docs/redesign/frozen-parity-baselines.md`.

## Task

Update repository workflow state so the next action is M60 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 59.
- Post-M59 planning accepted.
- Current action: execute Milestone 60.
- Active executor milestone:
  `Milestone 60: Opaque Selected Branch Body Handoff Slice`.
- Active run prompt:
  `docs/agent/runs/m60-execution-review-loop-prompt.md`.
- Latest review verdict:
  `Post-M59 planning accepted by user; M60 is active for execution.`
- Boundary reminders:
  - M60 is generation-time semantic lowering only.
  - M60 consumes accepted typed M59 branch-chain pruning/stage output.
  - M60 introduces a distinct typed opaque selected-body handoff value or
    equivalent typed stage output.
  - M60 must keep branch bodies opaque.
  - M60 must not parse or lower selected or unselected body semantics.
  - M60 must not synthesize a selected body for byte-size `1` no-match cases.
  - M60 must not invoke mini TSIL lowering or produce direct-intrinsic/SVE
    `TsilStatement` values for the branch-chain path.
  - Backend translation must not parse raw generation helper text.
  - Renderers must not evaluate generation-time helpers.
  - No direct `intrin<...>` / SVE body lowering, assignments, variables,
    arrays, calls, casts, loops, vector/register metadata,
    `value<generation>(vector::length)`,
    `value<generation>(vector::alignment)`, backend uninit values, backend
    translation, rendering, output, generated tests, CLI/reporting/writer,
    Rust, compiler execution, broad TSIL parsing, runtime `frozen/`, or
    lowering-time file reads/raw TSL parsing/catalog queries are in M60.

Create:

- `docs/agent/runs/m60-execution-review-loop-prompt.md`

The M60 execution-review loop prompt must:

- Use the orchestrated executor-review loop.
- Spawn exactly one write-capable executor if M60 is not already implemented.
- Use read-only reviewer, validation auditor, boundary auditor, extensibility
  auditor, documentation auditor, and evidence auditor subagents after
  execution.
- Require one focused revision executor and focused re-review only if the
  consolidated verdict is `Needs Revision`.
- Stop and create a planning/rollback prompt for `Return To Planner` or
  `Reject`.
- If accepted, update `docs/agent/current-redesign-state.md` and create the
  next concrete run prompt under `docs/agent/runs/`.
- Include required validation:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If Python implementation files change, require an appropriate compile or
static check.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m59-acceptance-finalization-prompt.md docs/agent/runs/m60-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M60.
