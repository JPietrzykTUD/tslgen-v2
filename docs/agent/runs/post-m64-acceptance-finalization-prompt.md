# Post-M64 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M64 planning update.

Do not implement product code.

## Accepted Result

The post-M64 planning update selected:

```text
Milestone 65: Exact Array Body Envelope Pipeline Integration Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

Remaining follow-ups are non-blocking:

```text
- M65 execution must make the skeleton-required policy concrete: no-skeleton
  input preserves existing M63-only behavior unless a candidate is explicitly
  marked as requiring a skeleton.
- M65 execution should require explicit diagnostic expectations for missing
  required skeleton input, duplicate/conflicting skeletons, skeletons supplied
  for candidates without M63 envelopes, and skeleton/envelope provenance
  mismatches.
- Existing M62 diagnostic-location/message and M64 fixture-comment follow-ups
  remain non-blocking cleanup items.
```

## Task

Update repository workflow state so the next action is M65 execution, and
create the concrete M65 execution-review prompt.

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
- `docs/agent/runs/m65-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 64.
- Post-M64 planning accepted.
- Current action: execute Milestone 65.
- Active run prompt: `docs/agent/runs/m65-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 65: Exact Array Body Envelope Pipeline Integration Slice`.
- Latest review verdict: post-M64 planning returned `Accept With Follow-Ups`.
- Follow-ups recorded:
  - M65 execution must make the skeleton-required policy concrete.
  - M65 execution should include explicit diagnostic expectations for missing,
    duplicate/conflicting, orphaned, and mismatched skeleton integration state.
  - Existing M62 and M64 cleanup follow-ups remain non-blocking.

Create `docs/agent/runs/m65-execution-review-loop-prompt.md` as a concrete
executor-review-loop prompt for M65.

The M65 execution prompt must require a single write-capable executor followed
by read-only reviewer/audit subagents. It must require implementation,
focused tests, targeted validation, and final workflow handoff updates.

## M65 Boundary Reminders

- M65 is generation-time lowering pipeline-integration work only.
- M65 consumes accepted M63 `SelectedBodyEnvelopeIr` /
  `NoSelectedBodyEnvelopeIr` outputs and accepted M64
  `ExactArrayBodyEnvelopeSkeleton` input supplied in memory.
- Skeleton lookup must be keyed by typed candidate id, selected type tag, and
  branch-chain identity, not raw body text.
- M65 must call the accepted M64 `assemble_exact_array_body_envelope` boundary
  and populate `LoweredImplementation.array_body_envelopes`.
- M65 must append a deterministic
  `GenerationLoweringStage(stage="array_body_envelope_slot_assembly", ...)`
  after `selected_body_envelope_lowering`.
- M65 must preserve existing M57-M64 outputs and stage ordering before the new
  final stage.
- No-skeleton input should preserve existing M63-only behavior unless a
  candidate is explicitly marked as requiring a skeleton.
- M65 must diagnose missing required skeleton input, duplicate/conflicting
  skeletons, skeletons supplied for candidates without M63 envelopes, and
  skeleton/envelope provenance mismatches.
- Unsupported or non-exact skeleton shape should continue through existing M64
  diagnostics.
- M65 must not produce or recognize skeletons from raw payload text.
- M65 must not parse broad TSIL or `array.tsl` at lowering evaluation time.
- M65 must not lower slot-specific semantics or treat M64 slot labels as
  semantic statement kinds.
- M65 must not add declaration, assignment, array, store, return, variable,
  `tmp.data()`, `emit_return`, direct-intrinsic, SVE predicate/vector/register,
  byte-size-to-`svptrue_b*`, vector length/alignment, backend uninit, backend
  translation, renderer-ready IR, rendering, output, CLI/report/writer, Rust,
  compiler, generated-test, file-read, catalog-query, raw TSL parsing, or
  runtime `frozen/` behavior.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m65-execution-review-loop-prompt.md
```

If other workflow docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M65.
