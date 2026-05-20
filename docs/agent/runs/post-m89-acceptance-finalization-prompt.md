# Post-M89 Acceptance Finalization Prompt

You are finalizing the accepted post-M89 planning result.

Do not implement code.

## Accepted Result

Post-M89 planning selected:

```text
Milestone 90: Exact Array Lowering Completion Package Slice
```

Internal planning/review returned:

```text
Accept With Follow-Ups
```

The accepted plan intentionally broadens the earlier backend-handoff idea into
one Stage 8 exact array lowering completion package, while keeping
"completion" limited to lowering-side handoff assembly.

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

## Task

Update repository workflow state so the next action is M90 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 89.
- Post-M89 planning accepted.
- Current action: execute Milestone 90.
- Active executor milestone:
  `Milestone 90: Exact Array Lowering Completion Package Slice`.
- Active run prompt:
  `docs/agent/runs/m90-execution-review-loop-prompt.md`.
- Next expected action: run the M90 execution-review loop.
- Boundary reminders:
  - M90 is Stage 8 exact lowering completion-package work only.
  - M90 consumes accepted typed M89 inventories and their accepted M88 package
    identity/provenance.
  - "Completion" means lowering-side handoff completion, not semantic body
    completion, backend readiness, renderer readiness, or generated output.
  - M90 must carry unresolved backend-deferred dependencies as typed facts
    only.
  - M90 must not resolve backend values, read backend maps/catalogs, start
    Stage 9 backend planning, render output, infer declaration/store/return/
    SVE/backend semantics, repair source text, broaden TSIL parsing, or
    introduce generic backend-value evaluation.
  - M90 should use focused private completion-package ownership and avoid
    growing `boundary.py`, `_array_body_pipeline.py`, `_array_body_models.py`,
    or `_array_body_backend_deferred_requests.py` into broader catch-all
    modules.

Create:

```text
docs/agent/runs/m90-execution-review-loop-prompt.md
```

The M90 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M90 scope, out-of-scope items, required
inputs, expected outputs, diagnostics, tests, validation commands, revision
loop, and finalization rules.

Do not modify product code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m90-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M90.
