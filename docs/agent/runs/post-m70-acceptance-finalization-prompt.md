# Post-M70 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M70 planning update.

Do not implement code.

## Accepted Result

The post-M70 planning update selected:

```text
Milestone 71: Exact Array Initialization Vector-Alignment Request Resolution Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M71 execution
boundaries:

- M71 must consume accepted typed M67/M68/M69/M70 request/result/pipeline
  values.
- M71 must resolve exactly the M67
  `value<generation>(vector::alignment)` request from the exact first
  array-initialization slot.
- M71 must consume explicit typed vector-alignment metadata supplied before
  lowering evaluation.
- M71 must not infer alignment from vector length, vector bits, scalar byte
  size, selected type tags, SVE token text, extension names, host CPU state,
  catalog data, `tsldata`, backend maps, backend vector-alignment spellings,
  renderer names, or raw `candidate_id` parsing.
- M71 must preserve accepted M68 base-type behavior, accepted M69
  stage-pipeline behavior, and accepted M70 vector-length behavior.
- M71 must keep `value<backend>(uninit::array)` unresolved.
- M71 must keep declaration/array semantics, aligned load/store semantics,
  `assume_aligned`, backend translation, rendering, generated output,
  generated tests, CLI/report/writer behavior, Rust, compiler execution,
  broad TSIL parsing, lowering-time file/catalog reads, `tsldata` reads during
  lowering evaluation, host CPU queries, and runtime `frozen/` use out of
  scope.
- M71 validation should include the M70 hardening follow-up by explicitly
  guarding against catalog reads, `tsldata` reads, and host CPU queries during
  request resolution.

## Task

Update repository workflow state so the next action is M71 execution, and
create the concrete M71 execution-review prompt.

Do not start M71 execution in this prompt.

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
- create `docs/agent/runs/m71-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 70.
- Post-M70 planning accepted.
- Current action: execute Milestone 71.
- Active run prompt:
  `docs/agent/runs/m71-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 71: Exact Array Initialization Vector-Alignment Request Resolution Slice`.

The generated M71 execution-review loop prompt must require:

- exactly one write-capable executor if M71 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M71 Boundary Reminders

- M71 is generation-time lowering request resolution only.
- M71 resolves exactly the M67
  `value<generation>(vector::alignment)` request through the accepted M69/M70
  extracted array-initialization stage pipeline.
- M71 must consume typed M67/M68/M69/M70 request/result values and explicit
  typed vector-alignment metadata supplied before lowering evaluation.
- M71 must use typed candidate context fields such as candidate id, target
  extension, source extension, and selected type tag as structured fields. It
  must not parse `candidate_id` or raw text to derive semantic values.
- M71 must preserve accepted M68 base-type behavior and accepted M70
  vector-length behavior, and keep backend uninit unresolved.
- M71 must not derive alignment from vector length, vector bits, scalar byte
  size, selected type tag, extension name, SVE token text, backend id, renderer
  name, catalog data, `tsldata`, or host CPU state during lowering.
- M71 must not resolve backend uninit, declaration/array semantics, aligned
  load/store semantics, `assume_aligned`, stores, returns,
  direct-intrinsic/SVE semantics, backend translation, rendering, generated
  output, generated tests, CLI/report/writer behavior, Rust, compiler
  execution, broad TSIL parsing, lowering-time file/catalog reads, `tsldata`
  reads during lowering evaluation, host CPU queries, or runtime `frozen/` use.
- M71 must not add a broad vector metadata resolver, generic helper
  dispatcher, broad stage registry, or raw helper-string dispatcher.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m71-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M71.
