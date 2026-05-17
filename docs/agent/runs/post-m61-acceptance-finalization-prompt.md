# Post-M61 Acceptance Finalization Prompt

You are finalizing the accepted post-M61 planning update.

Do not implement code.

## Accepted Result

The post-M61 planning update selected:

```text
Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The remaining follow-ups are non-blocking:

- M62 must frame "direct-intrinsic" as unresolved backend-neutral
  selected-body IR, not backend intrinsic IR, SVE semantic validation,
  translation input, renderer-ready IR, or generated output.
- M62 should introduce a distinct post-form-recognition body-IR value/stage,
  such as `selected_body_ir_lowering`, rather than overloading M60 handoff or
  M61 form-recognition records.
- M62 tests should include a synthetic mismatch between selected byte-size
  literal and direct-intrinsic token text to prove the slice preserves M61
  typed facts instead of inferring a size-to-intrinsic mapping.

## Task

Update repository workflow state so the next action is M62 execution.

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

- Accepted through: Milestone 61.
- Post-M61 planning accepted.
- Current action: execute Milestone 62.
- Active executor milestone:
  `Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice`.
- Active run prompt:
  `docs/agent/runs/m62-execution-review-loop-prompt.md`.
- Latest review verdict:
  `Post-M61 planning accepted by user; M62 is active for execution.`
- Boundary reminders:
  - M62 is generation-time lowering body-IR work only.
  - M62 consumes accepted typed M61 `selected_body_form_recognition` outputs,
    not raw selected body text except as preserved provenance.
  - M62 may produce unresolved typed selected assignment/direct-intrinsic body
    IR only for the exact M61-recognized single-statement form
    `pg = intrin<svptrue_b16|svptrue_b32|svptrue_b64>();`.
  - M62 must expose a distinct post-form-recognition stage or typed value,
    such as `selected_body_ir_lowering`.
  - M62 must preserve target text, direct-intrinsic token text, original
    RHS/body text, selected type/literal, and provenance as typed IR facts.
  - M62 must not validate intrinsic names, infer SVE predicate meaning, prove
    `pg` scope/type, map byte-size literals to `svptrue_b*` tokens, create
    backend intrinsic IR, create backend translation requests, feed renderers,
    or emit generated output.
  - No broad assignment semantics, broad direct `intrin<...>` lowering,
    non-zero-argument calls, declarations, variables, arrays, stores, casts,
    loops, multi-statement bodies, `emit_return`, vector/register metadata,
    `value<generation>(vector::length)`,
    `value<generation>(vector::alignment)`, backend uninit values, backend
    translation, rendering, output, generated tests, CLI/reporting/writer,
    Rust, compiler execution, broad TSIL parsing, runtime `frozen/`, or
    lowering-time file reads/raw TSL parsing/catalog queries are in M62.

Create:

- `docs/agent/runs/m62-execution-review-loop-prompt.md`

The M62 execution-review loop prompt must:

- Use the orchestrated executor-review loop.
- Spawn exactly one write-capable executor if M62 is not already implemented.
- Use read-only reviewer, validation auditor, boundary auditor, extensibility
  auditor, documentation auditor, and evidence auditor subagents after
  execution.
- Require one focused revision executor and focused re-review only if the
  consolidated verdict is `Needs Revision`.
- Stop and create a planning/rollback prompt for `Return To Planner` or
  `Reject`.
- If accepted, update `docs/agent/current-redesign-state.md` and create the
  next concrete run prompt under `docs/agent/runs/`.
- Require the executor to consume only M61 typed form-recognition outputs and
  produce unresolved backend-neutral typed body IR.
- Require the executor to avoid raw body-text semantic matching except for
  preserving original text/provenance already carried by M61.
- Require tests for selected `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`
  IR records, no-selected-body/no-body-IR cases, a synthetic
  literal/token-mismatch case, unsupported M62 input diagnostics,
  M57-M61 regressions, backend raw-helper rejection, renderer non-evaluation,
  determinism, and no generated output/golden churn.
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
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m61-acceptance-finalization-prompt.md docs/agent/runs/m62-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M62.
