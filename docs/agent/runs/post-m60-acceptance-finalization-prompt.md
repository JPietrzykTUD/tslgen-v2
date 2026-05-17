# Post-M60 Acceptance Finalization Prompt

You are finalizing the accepted post-M60 planning update.

Do not implement code.

## Accepted Result

The post-M60 planning update selected:

```text
Milestone 61: Selected Branch Body Assignment Form Recognition Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The remaining follow-ups are non-blocking:

- M61 must remain a single selected-body assignment-form recognition boundary,
  not direct intrinsic lowering, SVE predicate semantic lowering, assignment
  lowering, backend translation input, renderer-ready IR, or broad TSIL
  parsing.
- The M61 executor should introduce a distinct typed form-recognition value or
  stage envelope rather than stretching `selected_body_lowering` into a mixed
  semantic dispatcher.

## Task

Update repository workflow state so the next action is M61 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 60.
- Post-M60 planning accepted.
- Current action: execute Milestone 61.
- Active executor milestone:
  `Milestone 61: Selected Branch Body Assignment Form Recognition Slice`.
- Active run prompt:
  `docs/agent/runs/m61-execution-review-loop-prompt.md`.
- Latest review verdict:
  `Post-M60 planning accepted by user; M61 is active for execution.`
- Boundary reminders:
  - M61 is generation-time lowering form-recognition work only.
  - M61 consumes accepted typed M60 selected-body handoff outputs.
  - M61 must not consume raw branch-chain text, raw TSL, catalog data, or
    `frozen/` runtime input.
  - M61 may recognize only the exact selected single-statement assignment form
    from `tsldata/primitives/load_store/array.tsl:107-109`:
    `pg = intrin<svptrue_b16>();`,
    `pg = intrin<svptrue_b32>();`, and
    `pg = intrin<svptrue_b64>();`.
  - M61 output must be typed/provenanced form metadata only.
  - M61 must preserve target text, opaque RHS/direct-intrinsic token text,
    original body text, and M60 handoff identity.
  - M61 must not lower assignment semantics, validate direct intrinsics, infer
    SVE predicate meaning, map byte-size literals to intrinsic suffixes,
    inspect unselected branch bodies, or synthesize a body/form for
    `si8`/`ui8` no-match cases.
  - No direct `intrin<...>` / SVE body lowering, declarations, variables,
    arrays, calls, casts, loops, multi-statement bodies, vector/register
    metadata, `value<generation>(vector::length)`,
    `value<generation>(vector::alignment)`, backend uninit values, backend
    translation, rendering, output, generated tests, CLI/reporting/writer,
    Rust, compiler execution, broad TSIL parsing, runtime `frozen/`, or
    lowering-time file reads/raw TSL parsing/catalog queries are in M61.

Create:

- `docs/agent/runs/m61-execution-review-loop-prompt.md`

The M61 execution-review loop prompt must:

- Use the orchestrated executor-review loop.
- Spawn exactly one write-capable executor if M61 is not already implemented.
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
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m60-acceptance-finalization-prompt.md docs/agent/runs/m61-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M61.
