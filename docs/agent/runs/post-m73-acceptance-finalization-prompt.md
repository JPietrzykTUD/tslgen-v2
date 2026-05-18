# Post-M73 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M73 planning update.

Do not implement code.

## Accepted Result

The post-M73 planning update selected:

```text
Milestone 74: Exact Array Body Structural Sequence And Slot-Role Classification Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M74 execution
boundaries:

- M74 must be exact array-body structural sequence and structural/provenance
  slot-role classification only, not generic body IR or executable statement
  semantics.
- M74 must consume accepted typed M64/M65 exact array-body envelope state and
  accepted M73 `ExactArrayInitializationDeclarationShellIr` values, the
  corresponding stage outputs, or a typed `LoweredImplementation` carrying
  exactly one matching envelope and declaration shell.
- M74 must produce one typed source-ordered structural sequence for the exact
  `array.tsl:105-111` body, with five structural/provenance roles:
  first-slot declaration shell, opaque predicate-init-shaped slot,
  selected-body envelope slot, opaque post-branch store-call-shaped slot, and
  opaque return-emission-shaped slot.
- M74 must attach the accepted M73 declaration shell only to slot ordinal `0`
  and preserve the accepted M63/M64 selected/no-body envelope only in the
  selected-body slot.
- M74 must derive roles from accepted typed slot identity and provenance, not
  from raw body text, corpus line numbers, helper strings, SVE tokens, backend
  ids, renderer names, or catalog data.
- M74 must not interpret `svbool_t`, `pg`, `intrin<svptrue_b8>`,
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `emit_return`,
  `assume_aligned`, stores, returns, direct intrinsics, SVE predicate/vector/
  register semantics, byte-size-to-token relationships, backend uninit,
  backend maps, rendering, generated output, generic body/declaration/array
  semantics, allocation/lifetime, initializer behavior, variable scope, broad
  TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, or runtime `frozen/` use.
- M74 should add at most one exact public structural-sequence IR value and one
  exact stage/output pairing; it must not add a generic body IR hierarchy,
  per-role public tuples, slot-role registry, broad stage registry, or
  semantic dispatcher.

## Task

Update repository workflow state so the next action is M74 execution, and
create the concrete M74 execution-review prompt.

Do not start M74 execution in this prompt.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
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

Update:

- `docs/agent/current-redesign-state.md`
- create `docs/agent/runs/m74-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 73.
- Post-M73 planning accepted.
- Current action: execute Milestone 74.
- Active run prompt:
  `docs/agent/runs/m74-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 74: Exact Array Body Structural Sequence And Slot-Role Classification Slice`.

The generated M74 execution-review loop prompt must require:

- exactly one write-capable executor if M74 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor
  subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M74 Boundary Reminders

- M74 is generation-time lowering structural/provenance IR only.
- M74 consumes accepted M64/M65 exact array-body envelope state and accepted
  M73 exact first-slot declaration-shell structural IR.
- M74 produces one typed source-ordered structural sequence for the exact
  `array.tsl:105-111` body.
- M74 role labels are structural/provenance labels only; they are not
  executable statements or generic body IR.
- M74 must preserve accepted M63/M64/M65/M66/M67/M68/M69/M70/M71/M72/M73
  behavior and outputs.
- M74 must use source text only as provenance/invariant evidence.
- M74 must not interpret `svbool_t`, `pg`, `intrin<svptrue_b8>`,
  `svptrue_b16/b32/b64`, `intrin<svst1>`, `tmp.data()`, `emit_return`,
  `assume_aligned`, stores, returns, direct intrinsics, SVE predicate/vector/
  register semantics, byte-size-to-token relationships, backend uninit,
  backend maps, rendering, generated output, generic body/declaration/array
  semantics, allocation/lifetime, initializer behavior, variable scope, broad
  TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, or runtime `frozen/` use.
- M74 must not add backend manifests, backend maps, language maps,
  translation maps, backend translation requests, renderer calls, generated
  artifacts, golden files, CLI/report/writer behavior, Rust behavior,
  compiler execution, or generated-test execution.
- M74 must not create broad helper registries, raw helper-string dispatch,
  generic body/declaration/array registries, slot-role registries, broad stage
  registries, or public IR families beyond one exact selected structural
  sequence boundary value.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m74-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M74.
