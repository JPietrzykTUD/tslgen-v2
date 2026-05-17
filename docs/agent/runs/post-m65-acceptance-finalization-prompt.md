# Post-M65 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M65 planning update.

Do not implement product code.

## Accepted Result

The post-M65 planning update selected:

```text
Milestone 66: Exact Array Initialization Slot Form IR Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

Remaining follow-ups are non-blocking:

```text
- M66 execution must keep the slice as exact array-initialization slot form IR,
  not semantic array/declaration lowering.
- M66 execution may use the typed M65 slot opaque text only for local
  exact-form recognition; it must not scan raw payloads or become a raw-text
  dispatcher.
- M66 execution must preserve the M65 follow-up for an explicit integrated
  skeleton-input ordering determinism test, unless it includes that regression
  directly.
- Existing M62 diagnostic-location/message and M64 fixture-comment follow-ups
  remain non-blocking cleanup items.
```

## Task

Update repository workflow state so the next action is M66 execution, and
create the concrete M66 execution-review prompt.

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
- `docs/agent/runs/m66-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 65.
- Post-M65 planning accepted.
- Current action: execute Milestone 66.
- Active run prompt: `docs/agent/runs/m66-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 66: Exact Array Initialization Slot Form IR Slice`.
- Latest review verdict: post-M65 planning returned `Accept With Follow-Ups`.
- Follow-ups recorded:
  - M66 execution must remain exact first-slot form IR, not broad semantic
    array/declaration lowering.
  - M66 execution must consume typed M65 envelope/stage outputs, not raw
    payloads.
  - M66 execution must keep vector length/alignment, base type, and backend
    uninit helpers unresolved.
  - Existing M65 determinism and older cleanup follow-ups remain non-blocking
    unless addressed directly.

Create `docs/agent/runs/m66-execution-review-loop-prompt.md` as a concrete
executor-review-loop prompt for M66.

The M66 execution prompt must require a single write-capable executor followed
by read-only reviewer/audit subagents. It must require implementation,
focused tests, targeted validation, and final workflow handoff updates.

## M66 Boundary Reminders

- M66 is generation-time lowering/body-slot form IR only.
- M66 consumes accepted M65 `LoweredImplementation.array_body_envelopes`,
  `ExactArrayBodyEnvelopeIr`, or the typed
  `array_body_envelope_slot_assembly` stage.
- M66 refines only the `opaque_pre_branch_array_initialization` slot with
  ordinal `0`.
- M66 must preserve all other M64/M65 slots as opaque unchanged provenance.
- M66 may recognize only the exact `array.tsl:105` slot form:
  `var<typed>(array_type<type<generation>(base::in), value<generation>(vector::length), value<generation>(vector::alignment)>, tmp, value<backend>(uninit::array))`.
- M66 should produce typed form IR preserving candidate id, selected type tag,
  branch-chain identity, envelope identity, slot ordinal, source location,
  original slot text, variable token `tmp`, and unresolved helper leaves.
- M66 should append a deterministic stage after
  `array_body_envelope_slot_assembly`, such as
  `array_initialization_slot_form_lowering`.
- M66 must not evaluate `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- M66 must not add generic `var` parsing, generic `array_type` parsing, broad
  helper-expression parsing, broad declaration semantics, array allocation,
  variable binding/scope, store/return lowering, `tmp.data()`,
  `emit_return`, SVE/direct-intrinsic semantics, vector metadata semantics,
  backend uninit semantics, backend translation, renderer-ready IR, rendering,
  generated output, generated tests, CLI/report/writer behavior, Rust,
  compiler execution, file/catalog reads, raw TSL parsing, runtime `frozen/`,
  skeleton production, or broad TSIL parsing.
- Slot opaque text may be used only as local exact-form evidence after typed
  M65 slot selection. It must not become a raw-text dispatcher.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m66-execution-review-loop-prompt.md
```

If other workflow docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M66.
