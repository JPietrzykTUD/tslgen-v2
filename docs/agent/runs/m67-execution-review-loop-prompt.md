# Milestone 67 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 67: Exact Array Initialization Helper Request IR Slice
```

Milestones 1 through 66 are accepted. Post-M66 planning is accepted and
selected M67. Do not start any later milestone.

Use the orchestrated executor-review loop described here. Do not skip state or
next-prompt updates unless this prompt explicitly records a stop condition.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Milestone Scope

Implement the smallest generation-time/body-lowering request/provenance IR
slice that consumes accepted M66 exact array-initialization slot form IR and
classifies only the exact unresolved helper leaves from that form into typed
deferred helper request records.

M67 must:

- Consume accepted M66 `ExactArrayInitializationSlotFormIr` values or the
  `array_initialization_slot_form_lowering` stage output.
- Classify exactly these four M66 leaves into typed deferred request records:
  - `type<generation>(base::in)`;
  - `value<generation>(vector::length)`;
  - `value<generation>(vector::alignment)`;
  - `value<backend>(uninit::array)`.
- Preserve source leaf text, leaf kind, source locations, candidate id,
  selected type tag, branch-chain identity, envelope identity, slot ordinal,
  variable token `tmp`, and deterministic request ordering.
- Produce immutable typed request/provenance IR values, for example
  `ExactArrayInitializationHelperRequestIr` and per-leaf request records.
- Append a distinct deterministic lowering stage after
  `array_initialization_slot_form_lowering`, for example
  `array_initialization_helper_request_lowering`.
- Preserve the accepted M66 form IR and the accepted M64/M65 opaque slot
  boundaries unchanged.
- Produce structured diagnostics for invalid M67 boundary/request state.

M67 is request/provenance IR only. It is not helper evaluation, semantic value
resolution, backend translation, renderer preparation, or output generation.

## Acceptance Criteria

M67 must satisfy these criteria:

- Normal `lower_candidates` can produce the M67 helper request IR when matching
  typed M65/M66 skeleton input is supplied.
- M67 consumes the M66 form/stage output, not raw slot text or raw helper
  strings.
- The M67 output is keyed to the same accepted M66 form and contains exactly
  the four supported helper leaf requests in deterministic order.
- The new stage appears after `array_initialization_slot_form_lowering`;
  previous M57-M66 stage order remains unchanged before that point.
- Selected paths carrying `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`
  provenance can produce M67 request IR.
- `si8` and `ui8` no-body paths can produce M67 request IR without
  synthesizing selected branch text or changing the no-body envelope.
- The output preserves source leaf text, leaf kind, source locations,
  candidate id, selected type tag, branch-chain identity, envelope identity,
  slot ordinal, variable token `tmp`, and deterministic request ordering.
- M67 does not resolve any helper and does not produce `GenerationTypeRef`,
  `GenerationValue`, vector metadata values, backend uninit values, backend
  translation requests, renderer-ready IR, or generated output.
- Unsupported source stage/type, missing M66 form, missing helper leaf,
  mismatched helper leaf, duplicate helper leaf, unsupported helper leaf, and
  provenance mismatch produce structured diagnostics with source locations and
  actionable messages.
- Existing M57/M58/M59/M60/M61/M62/M63/M64/M65/M66 behavior remains unchanged.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.
- No generated output, generated tests, golden fixtures, CLI/report/writer,
  Rust, or compiler behavior changes.

## Out Of Scope

M67 must not add:

- Evaluation, resolution, normalization, translation, or rendering of
  `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Calls to existing generation helper evaluators, including M43 base type
  resolution.
- `GenerationTypeRef`, `GenerationValue`, vector metadata values, backend
  uninit values, backend translation requests, renderer-ready IR, generated
  output, or generated tests.
- Generic helper parsing, generic `var` parsing, generic `array_type` parsing,
  broad declaration semantics, array allocation/lifetime semantics, variable
  binding/scope, array type/value semantics, or statement IR.
- Predicate-initialization slot lowering, selected-body slot changes, store
  slot lowering, return slot lowering, `tmp.data()` semantics, or
  `emit_return` semantics.
- SVE predicate/vector/register semantics, direct-intrinsic semantics,
  byte-size-to-`svptrue_b*` token inference, backend intrinsic IR, backend
  translation requests, translation-map evaluation, rendering, generated
  C++/Rust output, generated tests, CLI/reporting/writer behavior, compiler
  execution, or Rust.
- Producing or recognizing M66 forms from raw payload text.
- Broad TSIL parsing, lowering-time file reads, catalog queries, raw TSL
  parsing, runtime `frozen/` evidence, raw-string dispatch tables, or
  backend-specific branches.

Preserved leaf text may be used only as provenance already carried by typed
M66 leaf records. It must not become a raw-text dispatcher.

## Evidence

Use accepted implementation and tests for:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed size-byte branch-chain pruning.
- M60 typed opaque selected-body handoff and no-selected-body behavior.
- M61 typed selected-body assignment-form recognition.
- M62 typed selected assignment/direct-intrinsic body IR and no-body-IR
  behavior.
- M63 typed selected-body envelope and no-body envelope behavior.
- M64 typed exact array-body skeleton/envelope assembly, opaque slot
  preservation, selected/no-body handling, deterministic stage construction,
  and boundary diagnostics.
- M65 normal lowering pipeline integration for
  `LoweredImplementation.array_body_envelopes`.
- M66 exact array-initialization slot form IR, unresolved helper leaves, and
  `array_initialization_slot_form_lowering` stage output.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:105` for the exact
  array-initialization slot form.
- `tsldata/primitives/load_store/array.tsl:105-111` only as context that this
  slot is part of the accepted M64/M65 five-slot envelope.

The vector and backend-looking helpers remain unresolved evidence. M67 must
not derive semantic values from them.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M67 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M67 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M67 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M67 within the scope and out-of-scope boundaries above.
- It must consume typed M66 form/stage outputs, not raw slot text or raw
  helper strings.
- It must classify exactly the four accepted M66 helper leaves into deferred
  typed request/provenance records.
- It must preserve source leaf text, leaf kind, source locations, candidate
  id, selected type tag, branch-chain identity, envelope identity, slot
  ordinal, variable token `tmp`, and deterministic request ordering.
- It must add structured diagnostics/tests for unsupported source stage/type,
  missing form, missing helper leaf, mismatched helper leaf, duplicate helper
  leaf, unsupported helper leaf, and provenance mismatch.
- It must not evaluate or resolve helpers, call existing helper evaluators,
  create `GenerationTypeRef` or `GenerationValue`, create backend translation
  requests, add broad declaration/array/variable semantics, lower store/return
  slots, add SVE/direct-intrinsic/backend semantics, render output, or parse
  broad TSIL.

The executor should report files changed, tests added or updated, validation
commands run, how typed M66 inputs are consumed, how raw helper dispatch is
avoided, how helper leaves remain unresolved, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for selected/no-body M67 integration, exact four-leaf request IR,
   unsupported source/form/leaf/provenance diagnostics, deterministic stage
   ordering, unchanged M57-M66 behavior, backend raw-helper rejection,
   renderer non-evaluation, determinism, and no generated output/golden churn.
3. Boundary auditor: confirm M67 implements only typed deferred helper
   request/provenance IR and does not add helper evaluation, type/value
   resolution, broad declaration/array semantics, store/return lowering,
   SVE/direct-intrinsic/backend/rendering/output work, generated tests,
   CLI/reporting, writer behavior, Rust, compiler execution, runtime
   `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the integration keeps the staged body
   lowering pipeline maintainable, consumes the M66 form IR, avoids raw-text
   dispatchers, preserves M66 leaf provenance, and leaves future helper
   resolver stages room to follow the same typed request pattern.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57-M66 behavior plus `array.tsl:105`, and that leaf text is used
   only as typed M66 provenance.

Review and audit subagents are read-only unless a later revision task
explicitly assigns one focused write-capable executor.

## Phase 3: Consolidated Verdict

The orchestrator must consolidate subagent results into one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

Findings must be specific and file/line grounded where applicable.

## Phase 4: Revision Loop If Needed

If the consolidated verdict is `Needs Revision`, run exactly one focused
write-capable revision executor for the blocking issues only. Then run focused
read-only re-review for the changed areas.

Do not broaden M67 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M67 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M67 plan has been accepted, create a post-M67
  planning-plus-review prompt. Do not start M68.

The next prompt must follow `docs/agent/next-run-prompt-protocol.md`.

## Required Validation

Run targeted validation selected by the executor plus:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If Python implementation files change, also run an appropriate compile or
static check for those files. Include exact commands and exact results in the
final report.

## Final Report

Report:

1. Executor status.
2. Files changed.
3. Validation commands and exact results.
4. Review/audit subagents used.
5. Consolidated verdict.
6. Follow-ups recorded, if any.
