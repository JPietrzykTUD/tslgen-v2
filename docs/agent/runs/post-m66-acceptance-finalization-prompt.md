# Post-M66 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M66 planning update.

Do not implement code.

## Accepted Result

The post-M66 planning update selected:

```text
Milestone 67: Exact Array Initialization Helper Request IR Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M67 execution
boundaries:

- M67 is typed deferred helper-request/provenance IR only, not helper
  evaluation.
- M67 must not produce `GenerationTypeRef`, `GenerationValue`, backend
  translation requests, resolved vector metadata values, backend uninit values,
  renderer-ready IR, or generated output.
- M67 must consume M66 `ExactArrayInitializationSlotFormIr` / leaf records and
  must not reparse raw slot text or dispatch from raw helper strings.

## Task

Update repository workflow state so the next action is M67 execution, and
create the concrete M67 execution-review prompt.

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
- create `docs/agent/runs/m67-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 66.
- Post-M66 planning accepted.
- Current action: execute Milestone 67.
- Active run prompt:
  `docs/agent/runs/m67-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 67: Exact Array Initialization Helper Request IR Slice`.

The generated M67 execution-review loop prompt must require:

- exactly one write-capable executor if M67 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M67 Boundary Reminders

- M67 is generation-time/body-lowering request/provenance IR only.
- M67 consumes accepted M66 `ExactArrayInitializationSlotFormIr` values or the
  `array_initialization_slot_form_lowering` stage output.
- M67 classifies exactly these four M66 leaves into typed deferred request
  records:
  - `type<generation>(base::in)`;
  - `value<generation>(vector::length)`;
  - `value<generation>(vector::alignment)`;
  - `value<backend>(uninit::array)`.
- M67 must preserve source leaf text, leaf kind, source locations, candidate
  id, selected type tag, branch-chain identity, envelope identity, slot
  ordinal, variable token `tmp`, and deterministic request ordering.
- M67 must append a deterministic stage after
  `array_initialization_slot_form_lowering`, for example
  `array_initialization_helper_request_lowering`.
- M67 must not call existing generation helper evaluators, including M43 base
  type resolution.
- M67 must not evaluate, resolve, translate, normalize, or render any helper.
- M67 must not produce `GenerationTypeRef`, `GenerationValue`, vector
  metadata values, backend uninit values, backend translation requests,
  renderer-ready IR, generated output, generated tests, CLI/report/writer
  behavior, Rust, or compiler execution.
- M67 must not add generic helper parsing, generic `var` parsing, generic
  `array_type` parsing, declaration semantics, array allocation/lifetime,
  variable scope, store/return lowering, `tmp.data()`, `emit_return`,
  direct-intrinsic/SVE semantics, broad TSIL parsing, file/catalog reads during
  lowering, raw-text dispatch tables, or runtime `frozen/` use.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m67-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M67.
