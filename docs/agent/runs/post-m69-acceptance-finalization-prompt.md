# Post-M69 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M69 planning update.

Do not implement code.

## Accepted Result

The post-M69 planning update selected:

```text
Milestone 70: Exact Array Initialization Vector-Length Request Resolution Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M70 execution
boundaries:

- M70 must consume explicit typed vector-length metadata supplied before
  lowering evaluation.
- M70 must not infer lanes from raw helper text, M66 slot text, M67 leaf text,
  SVE tokens, extension names, vector-bit strings, selected type tags, scalar
  sizes, host CPU state, catalog data, backend maps, renderer names, or raw
  `candidate_id` parsing.
- M70 must preserve scalable/runtime-lane uncertainty as an explicit typed
  value/policy or diagnostics; it must not fake a fixed integer lane count for
  SVE/runtime-lane extensions.
- M70 must preserve accepted M68 base-type behavior and accepted M69
  stage-pipeline behavior.
- M70 must keep vector alignment, backend uninit, declaration/array semantics,
  backend translation, rendering, generated output, generated tests,
  CLI/report/writer behavior, Rust, compiler execution, and runtime `frozen/`
  use out of scope.
- M70 must include the M69 follow-up for explicit pipeline-level M67
  diagnostic propagation coverage because it extends the extracted pipeline.

## Task

Update repository workflow state so the next action is M70 execution, and
create the concrete M70 execution-review prompt.

Do not start M70 execution in this prompt.

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
- create `docs/agent/runs/m70-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 69.
- Post-M69 planning accepted.
- Current action: execute Milestone 70.
- Active run prompt:
  `docs/agent/runs/m70-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 70: Exact Array Initialization Vector-Length Request Resolution Slice`.

The generated M70 execution-review loop prompt must require:

- exactly one write-capable executor if M70 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M70 Boundary Reminders

- M70 is generation-time lowering request resolution only.
- M70 resolves exactly the M67 `value<generation>(vector::length)` request
  through the accepted M69 extracted array-initialization stage pipeline.
- M70 must consume typed M67/M68/M69 request/result values and explicit typed
  vector-length metadata supplied before lowering evaluation.
- M70 must use typed candidate context fields such as candidate id, target
  extension, source extension, and selected type tag as structured fields. It
  must not parse `candidate_id` or raw text to derive semantic values.
- M70 must preserve accepted M68 base-type behavior and keep vector alignment
  and backend uninit requests unresolved.
- Runtime/scalable metadata must remain an explicit typed value/policy or
  produce diagnostics; M70 must not fake a fixed integer lane count for
  SVE/runtime-lane extensions.
- M70 must not resolve vector alignment, backend uninit, declaration/array
  semantics, stores, returns, direct-intrinsic/SVE semantics, backend
  translation, rendering, generated output, generated tests, CLI/report/writer
  behavior, Rust, compiler execution, broad TSIL parsing, lowering-time
  file/catalog reads, `tsldata` reads during lowering evaluation, host CPU
  queries, or runtime `frozen/` use.
- M70 must not add a broad vector metadata resolver, generic helper
  dispatcher, broad stage registry, or raw helper-string dispatcher.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m70-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M70.
