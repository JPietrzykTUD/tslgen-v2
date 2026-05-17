# Milestone 65 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 65: Exact Array Body Envelope Pipeline Integration Slice
```

Milestones 1 through 64 are accepted. Post-M64 planning is accepted and
selected M65. Do not start any later milestone.

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

Implement the smallest generation-time lowering pipeline-integration slice that
makes accepted M64 exact array-body envelopes available from the normal
lowering path when typed/provenanced exact skeleton input is supplied.

M65 must:

- Consume accepted M63 `SelectedBodyEnvelopeIr` and
  `NoSelectedBodyEnvelopeIr` values produced by the
  `selected_body_envelope_lowering` stage inside the normal lowering path.
- Consume accepted M64 `ExactArrayBodyEnvelopeSkeleton` values supplied in
  memory through the lowering request/input boundary.
- Key skeleton lookup by typed candidate id, selected type tag, and
  originating branch-chain identity, not by raw body text.
- Call the accepted M64 `assemble_exact_array_body_envelope` boundary for a
  matching typed skeleton.
- Populate `LoweredImplementation.array_body_envelopes` with the resulting
  `ExactArrayBodyEnvelopeIr`.
- Append a deterministic
  `GenerationLoweringStage(stage="array_body_envelope_slot_assembly", ...)`
  after the accepted M63 `selected_body_envelope_lowering` stage.
- Preserve existing M57-M64 values, diagnostics, deterministic ordering,
  selected/no-body behavior, backend raw-helper rejection, and renderer
  non-evaluation.
- Make the skeleton-required policy concrete: no-skeleton input preserves
  existing M63-only behavior unless a candidate is explicitly marked as
  requiring a skeleton.
- Keep surrounding M64 slots opaque and structural.

M65 is pipeline wiring only. It is not skeleton recognition, not semantic
array-body lowering, not slot-specific lowering, not backend translation, and
not rendering.

## Acceptance Criteria

M65 must satisfy these criteria:

- Normal `lower_candidates` can produce an `ExactArrayBodyEnvelopeIr` when
  matching typed skeleton input is supplied.
- The resulting envelope is available through
  `LoweredImplementation.array_body_envelopes`.
- The final generated lowering stage is
  `array_body_envelope_slot_assembly` and references the same envelope stored
  in `array_body_envelopes`.
- The new stage appears after `selected_body_envelope_lowering`; previous
  M57-M64 stage order remains unchanged before that point.
- Selected M63 envelopes carrying `svptrue_b16`, `svptrue_b32`, and
  `svptrue_b64` provenance assemble through normal lowering.
- `si8` and `ui8` no-body M63 envelopes assemble through normal lowering
  without synthesized selected branch text.
- No-skeleton input preserves existing M63-only behavior unless the selected
  candidate is explicitly marked as requiring an array-body skeleton.
- Missing required skeleton input, duplicate/conflicting skeletons, skeletons
  supplied for candidates without M63 envelopes, and skeleton/envelope
  provenance mismatches produce structured diagnostics with source location
  and actionable messages.
- Unsupported or non-exact skeleton shape continues through existing M64
  diagnostics.
- Existing M57/M58/M59/M60/M61/M62/M63/M64 behavior remains unchanged.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.
- No generated output, generated tests, golden fixtures, CLI/report/writer,
  Rust, or compiler behavior changes.

## Out Of Scope

M65 must not add:

- Producing or recognizing `ExactArrayBodyEnvelopeSkeleton` from raw payload
  text.
- Broad TSIL parsing or exact skeleton recognition from `array.tsl` text.
- Slot-specific lowering or semantic interpretation of M64 slot labels.
- Declaration semantics, assignment binding, variables, arrays, stores,
  returns, primitive calls, casts, loops, `tmp.data()`, or `emit_return`.
- SVE predicate, vector, or register semantics, including meaning of
  `svbool_t`, `pg`, `svptrue_b8`, `svptrue_b16/b32/b64`, or `svst1`.
- Byte-size-to-`svptrue_b*` token validation or inference.
- Evaluation of `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or
  `value<backend>(uninit::array)`.
- Backend intrinsic IR, backend translation requests, translation-map
  evaluation, renderer-ready IR, rendering, generated C++/Rust output,
  generated tests, CLI/reporting/writer behavior, compiler execution, or Rust.
- File reads, catalog queries, raw TSL parsing, or runtime `frozen/` evidence
  during lowering evaluation.
- Dictionaries, raw string keys, backend-specific branches, or central
  raw-string dispatch tables as the downstream semantic model.

## Evidence

Use accepted implementation and tests for:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed `GenerationSizeByteBranchChainPruning`.
- M60 typed opaque selected-body handoff and no-selected-body behavior.
- M61 typed selected-body assignment-form recognition.
- M62 typed selected assignment/direct-intrinsic body IR and no-body-IR
  behavior.
- M63 typed selected-body envelope and no-body envelope behavior.
- M64 typed exact array-body skeleton/envelope assembly, diagnostics,
  selected/no-body handling, deterministic stage construction, and mismatch
  preservation.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:105-111`

These lines justify the exact array-body skeleton shape only. The SVE-looking
tokens, vector metadata helpers, backend uninit helper, store call, and return
text remain opaque evidence. M65 must not derive semantics from them.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M65 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M65 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M65 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M65 within the scope and out-of-scope boundaries above.
- It must wire typed/provenanced `ExactArrayBodyEnvelopeSkeleton` input through
  the normal lowering input/request boundary.
- It must key skeleton lookup by typed candidate id, selected type tag, and
  originating branch-chain identity.
- It must call the M64 `assemble_exact_array_body_envelope` boundary rather
  than duplicate M64 assembly logic.
- It must populate `LoweredImplementation.array_body_envelopes` and append the
  `array_body_envelope_slot_assembly` stage after
  `selected_body_envelope_lowering`.
- It must make the no-skeleton behavior explicit and tested.
- It must add structured diagnostics/tests for missing required skeleton input,
  duplicate/conflicting skeletons, orphaned skeletons, and provenance mismatch.
- It must not produce or recognize skeletons from raw payload text.
- It must not parse broad TSIL or inspect `array.tsl` during lowering
  evaluation.
- It must not add slot semantics, SVE/direct-intrinsic semantics, vector
  metadata, backend translation, rendering, generated output, CLI/reporting,
  writer behavior, Rust, compiler execution, or runtime `frozen/` behavior.

The executor should report files changed, tests added or updated, validation
commands run, how typed M63/M64 inputs are consumed, how skeleton lookup avoids
raw body text, how no-skeleton behavior is defined, and any follow-ups or
blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for selected and no-body M65 pipeline integration, no-skeleton
   behavior, missing/duplicate/orphaned/mismatched skeleton diagnostics,
   deterministic stage ordering, unchanged M57-M64 behavior, backend
   raw-helper rejection, renderer non-evaluation, determinism, and no
   generated output/golden churn.
3. Boundary auditor: confirm M65 implements only typed pipeline integration and
   does not add skeleton recognition, broad TSIL parsing, slot semantics,
   SVE/direct-intrinsic/vector/backend/rendering/output work, generated tests,
   CLI/reporting, writer behavior, Rust, compiler execution, runtime `frozen/`,
   or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the integration keeps the staged lowering
   pipeline maintainable, uses typed skeleton keys, avoids raw-text
   dispatchers, and preserves M64 as the assembly boundary.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57-M64 behavior plus `array.tsl:105-111`, and that corpus body
   text is used only as exact structural evidence.

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

Do not broaden M65 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M65 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M65 plan has been accepted, create a post-M65
  planning-plus-review prompt. Do not start M66.

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
