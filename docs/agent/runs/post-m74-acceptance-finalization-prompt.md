# Post-M74 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M74 planning update.

Do not implement code.

## Accepted Result

The post-M74 planning update selected:

```text
Milestone 75: Exact Predicate Path Structural Request IR Slice
```

The selected plan must remain:

- exact predicate path structural/request IR only;
- a typed lowering slice consuming accepted M74 sequence state;
- free of SVE predicate semantics, store semantics, backend translation,
  rendering, generated output, variable scope, and broad body semantics.

## Task

Update repository workflow state so the next action is M75 execution, and
create the concrete M75 execution-review prompt.

Do not start M75 execution in this prompt.

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
- create `docs/agent/runs/m75-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 74.
- Post-M74 planning accepted.
- Current action: execute Milestone 75.
- Active run prompt:
  `docs/agent/runs/m75-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 75: Exact Predicate Path Structural Request IR Slice`.

The generated M75 execution-review loop prompt must require:

- exactly one write-capable executor if M75 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor
  subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M75 Boundary Reminders

- M75 is generation-time lowering structural/request IR only.
- M75 consumes accepted M74 `ExactArrayBodyStructuralSequenceIr` values, the
  `array_body_structural_sequence_classification` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M74 sequence.
- M75 consumes accepted M63/M62 selected/no-body predicate update evidence
  reachable through M74.
- M75 produces one typed exact predicate-path structural/request IR value for
  the exact path across:
  - slot 1 predicate initialization;
  - slot 2 accepted selected/no-body predicate update evidence;
  - slot 3 post-branch store-call predicate-token use.
- M75 keeps `svbool_t`, `pg`, `svptrue_b8`, selected `svptrue_b16/b32/b64`,
  and slot-3 `pg` as structural tokens/request provenance only.
- M75 must preserve accepted M57/M58/M59/M60/M61/M62/M63/M64/M65/M66/M67/M68/
  M69/M70/M71/M72/M73/M74 behavior and outputs.
- M75 must use source text only as exact structural shape/provenance evidence.
- M75 must not interpret SVE predicate semantics, vector/register semantics,
  byte-size-to-token relationships, lane masks, `svst1`, `tmp.data()`, `a`,
  `emit_return`, `assume_aligned`, stores, returns, variable scope, allocation/
  lifetime, initializer behavior, backend uninit, backend maps, rendering,
  generated output, generic predicate/body/store semantics, broad TSIL
  parsing, lowering-time file/catalog reads, `tsldata` reads during lowering
  evaluation, host CPU queries, backend map reads, or runtime `frozen/` use.
- M75 must not add backend manifests, backend maps, language maps,
  translation maps, backend translation requests, renderer calls, generated
  artifacts, golden files, CLI/report/writer behavior, Rust behavior,
  compiler execution, or generated-test execution.
- M75 must not create broad helper registries, raw helper-string dispatch,
  generic predicate/body/store registries, slot-role registries, broad stage
  registries, semantic dispatchers, or public IR families beyond one exact
  predicate-path structural/request boundary value.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m75-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M75.
