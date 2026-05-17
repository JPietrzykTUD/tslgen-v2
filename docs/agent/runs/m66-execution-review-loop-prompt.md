# Milestone 66 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 66: Exact Array Initialization Slot Form IR Slice
```

Milestones 1 through 65 are accepted. Post-M65 planning is accepted and
selected M66. Do not start any later milestone.

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

Implement the smallest generation-time lowering/body-slot form-IR slice that
consumes accepted M65 exact array-body envelopes and refines only the exact
array-initialization slot into typed form IR.

M66 must:

- Consume accepted M65 `LoweredImplementation.array_body_envelopes`,
  `ExactArrayBodyEnvelopeIr`, or the typed
  `array_body_envelope_slot_assembly` stage.
- Select only the `opaque_pre_branch_array_initialization` slot with ordinal
  `0`.
- Recognize only the exact `array.tsl:105` slot form:
  `var<typed>(array_type<type<generation>(base::in), value<generation>(vector::length), value<generation>(vector::alignment)>, tmp, value<backend>(uninit::array))`.
- Produce an immutable typed form IR value, for example
  `ExactArrayInitializationSlotFormIr`.
- Preserve candidate id, selected type tag, branch-chain identity, envelope
  identity, slot ordinal, source location, original slot text, variable token
  `tmp`, and exact nested helper positions.
- Represent `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, and
  `value<backend>(uninit::array)` as unresolved typed/provenance leaves only.
- Append a distinct deterministic lowering stage after
  `array_body_envelope_slot_assembly`, for example
  `array_initialization_slot_form_lowering`.
- Preserve the accepted M65 envelope and all other M64/M65 slots as opaque,
  unchanged provenance.
- Produce structured diagnostics for invalid M66 boundary/form state.

M66 is exact slot form IR only. It is not semantic array initialization
lowering, declaration lowering, helper evaluation, backend translation, or
rendering.

## Acceptance Criteria

M66 must satisfy these criteria:

- Normal `lower_candidates` can produce the M66 exact array-initialization
  slot form IR when matching typed M65 skeleton input is supplied.
- The M66 output is keyed to the same accepted M65 envelope and slot `0`.
- The new stage appears after `array_body_envelope_slot_assembly`; previous
  M57-M65 stage order remains unchanged before that point.
- Selected M65 envelopes carrying `svptrue_b16`, `svptrue_b32`, and
  `svptrue_b64` provenance can lower the first slot form.
- `si8` and `ui8` no-body M65 envelopes can lower the first slot form without
  synthesizing selected branch text or changing the no-body envelope.
- Slots `1` through `4` remain opaque and unchanged.
- The output preserves envelope identity, slot ordinal, candidate id, selected
  type tag, branch-chain identity, source location, original slot text,
  variable token `tmp`, and unresolved helper leaves.
- Malformed slot text, missing slot, wrong label/ordinal, unsupported helper
  shape, unsupported source stage/type, and provenance mismatch produce
  structured diagnostics with source locations and actionable messages.
- Existing M57/M58/M59/M60/M61/M62/M63/M64/M65 behavior remains unchanged.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.
- No generated output, generated tests, golden fixtures, CLI/report/writer,
  Rust, or compiler behavior changes.

## Out Of Scope

M66 must not add:

- Evaluation of `type<generation>(base::in)`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Generic `var` parsing, generic `array_type` parsing, broad helper-expression
  parsing, broad declaration semantics, array allocation/lifetime semantics,
  variable binding/scope, array type/value semantics, or statement IR.
- Predicate-initialization slot lowering, selected-body slot changes, store
  slot lowering, return slot lowering, `tmp.data()` semantics, or
  `emit_return` semantics.
- SVE predicate/vector/register semantics, direct-intrinsic semantics,
  byte-size-to-`svptrue_b*` token inference, backend intrinsic IR, backend
  translation requests, translation-map evaluation, renderer-ready IR,
  rendering, generated C++/Rust output, generated tests, CLI/reporting/writer
  behavior, compiler execution, or Rust.
- Producing or recognizing `ExactArrayBodyEnvelopeSkeleton` from raw payload
  text.
- Broad TSIL parsing, lowering-time file reads, catalog queries, raw TSL
  parsing, runtime `frozen/` evidence, raw-string dispatch tables, or
  backend-specific branches.

Slot opaque text may be used only after typed M65 slot selection as local
exact-form evidence. It must not become a raw-text dispatcher.

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

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:105` for the exact
  array-initialization slot form.
- `tsldata/primitives/load_store/array.tsl:105-111` only as context that this
  slot is part of the accepted M64/M65 five-slot envelope.

The vector and backend-looking helpers remain unresolved evidence. M66 must
not derive semantics from them.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M66 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M66 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M66 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M66 within the scope and out-of-scope boundaries above.
- It must consume typed M65 envelope/stage outputs, not raw payload text.
- It must refine only the `opaque_pre_branch_array_initialization` slot with
  ordinal `0`.
- It must preserve all other slots as opaque unchanged provenance.
- It must keep base type, vector length, vector alignment, and backend uninit
  helpers unresolved.
- It must add structured diagnostics/tests for missing slot, wrong
  label/ordinal, malformed exact slot text, unsupported helper shape,
  unsupported source stage/type, and provenance mismatch.
- It must not evaluate helper semantics, add broad declaration/array/variable
  semantics, lower store/return slots, add SVE/direct-intrinsic/backend
  semantics, render output, or parse broad TSIL.

The executor should report files changed, tests added or updated, validation
commands run, how typed M65 inputs are consumed, how exact-form recognition
avoids raw payload scanning, how helper leaves remain unresolved, and any
follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for selected/no-body M66 integration, exact first-slot form IR,
   unchanged slots `1` through `4`, malformed/missing/wrong-slot/helper-shape/
   provenance diagnostics, deterministic stage ordering, unchanged M57-M65
   behavior, backend raw-helper rejection, renderer non-evaluation,
   determinism, and no generated output/golden churn.
3. Boundary auditor: confirm M66 implements only typed exact first-slot form IR
   and does not add helper evaluation, broad declaration/array semantics,
   store/return lowering, SVE/direct-intrinsic/backend/rendering/output work,
   generated tests, CLI/reporting, writer behavior, Rust, compiler execution,
   runtime `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the integration keeps the staged body
   lowering pipeline maintainable, consumes the enclosing
   `ExactArrayBodyEnvelopeIr`, avoids raw-text dispatchers, preserves M65 as
   the envelope source, and leaves future slot-specific lowerers room to follow
   the same pattern.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57-M65 behavior plus `array.tsl:105`, and that slot text is used
   only as local exact-form evidence.

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

Do not broaden M66 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M66 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M66 plan has been accepted, create a post-M66
  planning-plus-review prompt. Do not start M67.

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
7. State transition made.
8. Next prompt created.
9. Whether the repo is ready for the next action.
