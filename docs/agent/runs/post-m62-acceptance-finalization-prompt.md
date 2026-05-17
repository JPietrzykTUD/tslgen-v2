# Post-M62 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M62 planning update.

Do not implement product code.

## Accepted Result

The post-M62 planning update selected:

```text
Milestone 63: Backend-Neutral Selected Body Envelope IR Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

Remaining follow-ups are non-blocking:

```text
- M62's unsupported-source diagnostic test still asserts code/severity but not
  location/message text.
```

## Task

Update repository workflow state so the next action is M63 execution, and
create the concrete M63 execution-review prompt.

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

## Required Changes

Update only workflow documents:

- `docs/agent/current-redesign-state.md`
- `docs/agent/runs/m63-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 62.
- Post-M62 planning accepted.
- Current action: execute Milestone 63.
- Active run prompt: `docs/agent/runs/m63-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 63: Backend-Neutral Selected Body Envelope IR Slice`.
- Latest review verdict: post-M62 planning returned `Accept With Follow-Ups`.
- Follow-up recorded:
  M62's unsupported-source diagnostic test still asserts code/severity but not
  location/message text.

Create `docs/agent/runs/m63-execution-review-loop-prompt.md` as a concrete
executor-review-loop prompt for M63.

The M63 execution prompt must require a single write-capable executor followed
by read-only reviewer/audit subagents. It must require implementation,
focused tests, targeted validation, and final workflow handoff updates.

## M63 Boundary Reminders

- M63 is generation-time lowering/body-envelope IR work only.
- M63 must consume only accepted typed M62 `selected_body_ir_lowering` outputs
  or equivalent typed M62 values:
  `SelectedAssignmentDirectIntrinsicBodyIr` and
  `NoSelectedAssignmentDirectIntrinsicBodyIr`.
- M63 must expose a distinct post-M62 stage or typed value, such as
  `selected_body_envelope_lowering`.
- M63 must produce a backend-neutral selected-body envelope with deterministic
  ordering. For selected cases, the sequence is exact and singleton, wrapping
  only the existing M62 selected assignment/direct-intrinsic body IR.
- M63 must produce an explicit no-body envelope for M62 no-body-IR cases.
- M63 may preserve M62 target text, direct-intrinsic token text, empty argument
  list, original RHS/body text, selected type/literal, source location, branch
  identity, and provenance as typed facts.
- SVE-looking corpus text is evidence only. M63 must not make `svptrue_b*`,
  `pg`, `svbool_t`, `svst1`, vector metadata, backend uninit values, or
  `emit_return` architectural concepts or semantic rules.
- Backend translation must not parse raw generation helper text.
- Renderers must not evaluate generation-time helpers.
- No direct-intrinsic semantics, SVE predicate/vector semantics,
  byte-size-to-token inference, assignment binding, declaration handling,
  variable scope, array/store/return lowering, vector length/alignment,
  backend translation, rendering, output, CLI/report/writer, Rust, compiler
  execution, broad TSIL parsing, lowering-time file reads, raw TSL parsing,
  catalog queries, or runtime `frozen/` use is in M63.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m63-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M63.
