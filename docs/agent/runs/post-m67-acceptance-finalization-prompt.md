# Post-M67 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M67 planning update.

Do not implement code.

## Accepted Result

The post-M67 planning update selected:

```text
Milestone 68: Exact Array Initialization Base-Type Helper Request Resolution Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking and must be carried into M68 execution
boundaries:

- M68 must be a typed request-resolution adapter over M67 IR, not a raw
  `type<generation>(...)` evaluator over M67 leaf text.
- M68 must not call raw query-string helper evaluators such as
  `resolve_generation_type_query(...)` on M67 leaf text unless the evaluator is
  refactored behind a typed, non-text entry point and tests prove no raw helper
  text is parsed.
- M68 must leave vector length, vector alignment, backend uninit,
  declaration/array semantics, backend translation, rendering, generated
  output, Rust, CLI/report/writer behavior, compiler execution, and generated
  tests out of scope.
- M68 must not use `Catalog`, file reads, `tsldata`, or `frozen/` during
  lowering evaluation; selected type context and rules must arrive through
  typed lowering request/context inputs.

## Task

Update repository workflow state so the next action is M68 execution, and
create the concrete M68 execution-review prompt.

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
- create `docs/agent/runs/m68-execution-review-loop-prompt.md`

Do not modify implementation code or tests.

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 67.
- Post-M67 planning accepted.
- Current action: execute Milestone 68.
- Active run prompt:
  `docs/agent/runs/m68-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 68: Exact Array Initialization Base-Type Helper Request Resolution Slice`.

The generated M68 execution-review loop prompt must require:

- exactly one write-capable executor if M68 is not already implemented;
- read-only reviewer, validation-auditor, boundary-auditor,
  extensibility-auditor, documentation-auditor, and evidence-auditor subagents;
- a focused revision loop for `Needs Revision`;
- next-prompt generation after `Accept` or `Accept With Follow-Ups`.

## M68 Boundary Reminders

- M68 is generation-time/body-lowering request-resolution work only.
- M68 consumes accepted M67 `ExactArrayInitializationHelperRequestIr` values,
  the `array_initialization_helper_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M67
  `array_initialization_helper_requests` entry.
- M68 resolves exactly the M67 base-type request record:
  - request ordinal `0`;
  - request kind `generation_type`;
  - helper leaf kind `type_generation_base_in`;
  - source text `type<generation>(base::in)` as provenance/invariant evidence
    only.
- M68 produces a typed result equivalent to
  `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)` or an
  M68-specific typed wrapper carrying that value and source M67 request
  provenance.
- M68 must append a deterministic stage after
  `array_initialization_helper_request_lowering`, for example
  `array_initialization_base_type_request_resolution`.
- M68 must preserve source M67 request IR, source request record, leaf source
  text as provenance only, source locations, candidate id, selected type tag,
  branch-chain identity, envelope identity, slot ordinal, variable token
  `tmp`, and deterministic result ordering.
- M68 must preserve the vector length, vector alignment, and backend uninit
  M67 requests as unresolved request/provenance records.
- M68 must not parse, regex-match, normalize, or dispatch on M67
  `leaf_source_text`, M66 `original_slot_text`, raw TSIL, raw TSL, or helper
  strings.
- M68 must not call raw query-string helper evaluators such as
  `resolve_generation_type_query(...)` on M67 leaf text unless refactored
  behind a typed, non-text entry point and tests prove no raw helper text is
  parsed.
- M68 must not resolve `base.signed_of`, `base.unsigned_of`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- M68 must not produce `GenerationValue`, vector metadata values, backend
  uninit values, backend translation requests, renderer-ready values,
  generated output, generated tests, CLI/report/writer behavior, Rust, or
  compiler execution.
- M68 must not add generic helper parsing, generic `var` parsing, generic
  `array_type` parsing, declaration semantics, array allocation/lifetime,
  variable scope, store/return lowering, `tmp.data()`, `emit_return`,
  direct-intrinsic/SVE semantics, broad TSIL parsing, lowering-time file reads,
  catalog queries during evaluation, raw-text dispatch tables, or runtime
  `frozen/` use.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m68-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M68.
