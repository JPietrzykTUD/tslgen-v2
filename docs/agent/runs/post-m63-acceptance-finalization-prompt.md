# Post-M63 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M63 planning update.

Do not implement product code.

## Accepted Result

The post-M63 planning update selected:

```text
Milestone 64: Exact Array Body Envelope Slot Assembly Slice
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

Update repository workflow state so the next action is M64 execution, and
create the concrete M64 execution-review prompt.

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
- `docs/agent/runs/m64-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 63.
- Post-M63 planning accepted.
- Current action: execute Milestone 64.
- Active run prompt: `docs/agent/runs/m64-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 64: Exact Array Body Envelope Slot Assembly Slice`.
- Latest review verdict: post-M63 planning returned `Accept With Follow-Ups`.
- Follow-up recorded:
  M62's unsupported-source diagnostic test still asserts code/severity but not
  location/message text.

Create `docs/agent/runs/m64-execution-review-loop-prompt.md` as a concrete
executor-review-loop prompt for M64.

The M64 execution prompt must require a single write-capable executor followed
by read-only reviewer/audit subagents. It must require implementation,
focused tests, targeted validation, and final workflow handoff updates.

## M64 Boundary Reminders

- M64 is generation-time lowering/body-envelope slot assembly work only.
- M64 must consume accepted typed M63 `selected_body_envelope_lowering`
  outputs or equivalent typed M63 envelope values:
  `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`.
- M64 must expose a distinct post-M63 stage or typed value, such as
  `array_body_envelope_slot_assembly`.
- M64 may assemble only the exact ordered structural array-body skeleton
  evidenced by `tsldata/primitives/load_store/array.tsl:105-111`.
- M64 must produce deterministic typed opaque slots around one selected-body
  slot that references the M63 envelope.
- Slot labels are structural/provenance labels only. They must not imply
  declaration, assignment, predicate, store, return, array, vector,
  direct-intrinsic, SVE, or backend semantics.
- M64 must not loosen M63's singleton selected-body envelope invariant.
- M64 must carry M63 no-body envelopes for `si8`/`ui8` without synthesizing
  selected branch text.
- SVE-looking corpus text is evidence only. M64 must not make `svbool_t`,
  `pg`, `svptrue_b*`, `svst1`, `tmp.data()`, vector metadata, backend uninit
  values, or `emit_return` architectural concepts or semantic rules.
- Backend translation must not parse raw generation helper text.
- Renderers must not evaluate generation-time helpers.
- No declaration semantics, assignment binding, variable scope, array
  semantics, direct-intrinsic semantics, SVE predicate/vector semantics,
  byte-size-to-token inference, store semantics, return semantics, vector
  length/alignment evaluation, backend uninit semantics, backend translation,
  rendering, output, CLI/report/writer, Rust, compiler execution, broad TSIL
  parsing, lowering-time file reads, raw TSL parsing, catalog queries, or
  runtime `frozen/` use is in M64.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m64-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M64.
