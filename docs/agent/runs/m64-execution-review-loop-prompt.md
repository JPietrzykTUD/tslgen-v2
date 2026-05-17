# Milestone 64 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 64: Exact Array Body Envelope Slot Assembly Slice
```

Milestones 1 through 63 are accepted. Post-M63 planning is accepted and
selected M64. Do not start any later milestone.

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

Implement the smallest generation-time lowering/body-envelope slot assembly
slice that consumes accepted typed M63 `selected_body_envelope_lowering`
output and assembles only the exact ordered structural array-body skeleton
evidenced by:

```text
tsldata/primitives/load_store/array.tsl:105-111
```

M64 must:

- Consume only M63 `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`
  outputs from the distinct `selected_body_envelope_lowering` stage, or
  equivalent typed M63 envelope values.
- Produce a distinct typed exact array-body envelope value or stage, such as
  `array_body_envelope_slot_assembly`.
- Represent the exact body as deterministic ordered slots:
  - one opaque pre-branch array-initialization slot for the line 105 shape,
  - one opaque pre-branch predicate-initialization slot for the line 106 shape,
  - one selected-body envelope slot that references the M63 envelope for the
    lines 107-109 branch-chain path,
  - one opaque post-branch store-call slot for the line 110 shape,
  - one opaque post-branch return-emission slot for the line 111 shape.
- Treat slot labels as structural/provenance labels only. They must not imply
  declaration, assignment, predicate, store, return, array, vector,
  direct-intrinsic, SVE, or backend semantics.
- Preserve deterministic slot order, slot ordinal, opaque source text,
  source/provenance, candidate id, selected type tag, branch-chain identity,
  and a typed reference to the nested M63 envelope.
- Carry M63 no-body envelopes for `si8` and `ui8` without synthesizing selected
  branch text, selected statements, or body semantics.
- Keep the result backend-neutral and unresolved. It is not `TsilStatement`
  IR, not backend intrinsic IR, not a backend translation request, not
  renderer-ready body IR, and not SVE predicate/vector semantics.

M64 may use exact-shape structural recognition to assemble slots, but it must
not split the body into semantic statements or dispatch behavior from raw text.
Raw body text may be preserved as opaque provenance only.

Diagnostics in M64 must stay boundary-level, such as unsupported source
stage/type, missing M63 envelope, duplicate selected-body slot, unsupported
exact skeleton, missing or extra slot, reordered slot, or candidate/type/branch
provenance mismatch. They must not classify or semantically validate SVE,
direct intrinsics, declarations, arrays, stores, returns, vector metadata,
backend support, or renderer/output behavior.

Suggested diagnostic names from planning:

- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SOURCE-UNSUPPORTED`
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED`
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER`
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH`

## Acceptance Criteria

M64 must satisfy these criteria:

- Exact array-body envelope slot assembly consumes M63 typed selected/no-body
  envelope values, not M57/M58/M59 stage records, M60 handoff records, M61
  form-recognition records, M62 body IR records, raw selected body text, raw
  branch-chain text, raw TSL, catalog data, or `frozen/` runtime input.
- Selected envelopes are assembled for the M63 selected-body envelopes carrying
  `svptrue_b16`, `svptrue_b32`, and `svptrue_b64` provenance.
- `si8` and `ui8` no-body envelopes produce exact array-body slot envelopes
  with the M63 no-body envelope in the selected-body slot and no synthesized
  selected branch text.
- Each accepted case produces exactly five deterministic ordered slots.
- Opaque surrounding slots preserve source text and provenance only.
- The selected-body slot references the M63 envelope and does not re-open M63
  selected-body text to derive target, RHS, intrinsic token, byte size, or SVE
  facts.
- A synthetic mismatch between selected byte-size literal and direct-intrinsic
  token text remains preserved in the nested M63 envelope without diagnosing,
  correcting, or mapping the facts.
- Reordered, missing, duplicate, extra, or non-exact skeleton inputs produce
  structured M64 diagnostics without semantic classification.
- Mismatched candidate/type/branch provenance between the exact structural
  skeleton and nested M63 envelope produces structured M64 diagnostics.
- The branch-chain path does not invoke mini TSIL lowering and does not
  produce backend intrinsic, translation request, rendered code, or generated
  artifact values.
- Accepted M57/M58/M59/M60/M61/M62/M63 behavior remains unchanged except for
  the new exact array-body envelope output.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.

## Out Of Scope

M64 must not add:

- Broad TSIL parsing or multi-statement body lowering.
- Splitting body text into semantic statements.
- Declaration semantics, assignment binding, variable scope, array type/value
  semantics, `tmp.data()` semantics, store semantics, return semantics,
  primitive calls, casts, or loops.
- Direct-intrinsic semantic validation.
- SVE predicate, vector, or register semantics.
- Meaning for `svbool_t`, `pg`, `svptrue_b8`, `svptrue_b16/b32/b64`, or
  `svst1`.
- Mapping byte-size literals to `svptrue_b*` intrinsic tokens.
- Evaluation of `value<generation>(vector::length)`.
- Evaluation of `value<generation>(vector::alignment)`.
- Evaluation of `value<backend>(uninit::array)`.
- Backend intrinsic IR, `BackendIntrinsicCall`, backend translation input,
  backend metadata lookup, or translation-map evaluation.
- Renderer-ready body/expression IR.
- Backend translation expansion.
- Rendering or generated output.
- Generated tests or golden generated output changes.
- CLI/reporting/writer behavior.
- Rust.
- Compiler execution.
- Generated-test execution.
- Runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, catalog queries, or
  catalog-derived rule construction during evaluation.
- Dictionaries, raw string keys, backend-specific branches, or central
  raw-string dispatch tables as the downstream semantic model.

## Evidence

Use accepted implementation and tests for:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed `GenerationSizeByteBranchChainPruning` and body-opacity behavior.
- M60 typed opaque selected-body handoff and no-selected-body behavior.
- M61 typed selected-body assignment-form recognition and no-form behavior.
- M62 typed selected assignment/direct-intrinsic body IR and no-body-IR
  behavior.
- M63 typed selected-body envelope and no-body envelope behavior.
- M42/M48/M51/M59/M60/M61/M62/M63 selected-branch-only diagnostic principles.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:105`
- `tsldata/primitives/load_store/array.tsl:106`
- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`
- `tsldata/primitives/load_store/array.tsl:110`
- `tsldata/primitives/load_store/array.tsl:111`

These lines show the exact ordered body shape that M64 may represent as
structural slots. The surrounding SVE-looking material is evidence only for the
shape and must remain opaque. `array.tsl:107-109` is already covered through
M57-M63 and enters M64 through the typed M63 envelope.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M64 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M64 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M64 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M64 within the scope and out-of-scope boundaries above.
- It must consume only typed M63 envelope outputs or the
  `selected_body_envelope_lowering` stage, plus in-memory typed/provenanced
  exact skeleton input already supplied to lowering.
- It must not consume M60/M61/M62 raw text as a semantic shortcut.
- It must introduce a distinct post-M63 exact array-body envelope value or
  stage, such as `array_body_envelope_slot_assembly`.
- It must keep surrounding slots opaque and structural.
- It must not loosen M63's singleton selected-body envelope invariant.
- It must not synthesize selected branch text for M63 no-body envelopes.
- It must not validate intrinsic names, infer SVE predicate meaning, map
  byte-size literals to `svptrue_b*` tokens, create backend intrinsic IR,
  create backend translation requests, feed renderers, or emit generated
  output.
- It must not invoke mini TSIL lowering or produce backend/rendering values for
  the branch-chain path.

The executor should report files changed, tests added or updated, validation
commands run, how typed M63 outputs are consumed, how exact surrounding slots
remain opaque and non-semantic, how no-body cases remain unsynthesized, and any
follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for selected M64 exact envelopes, no-body exact envelopes,
   deterministic five-slot ordering, mismatch preservation through nested M63
   envelopes, unsupported/reordered/missing/extra/provenance diagnostics,
   unchanged M57/M58/M59/M60/M61/M62/M63 behavior, backend raw-helper
   rejection, renderer non-evaluation, determinism, and no generated
   output/golden churn.
3. Boundary auditor: confirm M64 implements only exact structural
   array-body slot assembly over M63 typed envelope outputs and does not add
   broad TSIL parsing, semantic statement lowering, SVE/direct-intrinsic
   semantics, declaration/array/store/return semantics, vector metadata,
   backend translation, rendering/output, generated tests, CLI/reporting,
   writer behavior, Rust, compiler execution, runtime `frozen/`, or
   lowering-time file/catalog reads.
4. Extensibility auditor: confirm the slot-envelope value or stage is typed,
   deterministic, distinct from M60 handoff, M61 form metadata, M62 body IR,
   and M63 selected-body envelopes, and suitable for future slot-specific
   body-lowering slices without becoming a broad dispatcher or raw-text
   evaluator.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57/M58/M59/M60/M61/M62/M63 behavior plus `array.tsl:105-111`, and
   that the corpus body is used only as exact structural evidence.

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

Do not broaden M64 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M64 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M64 plan has been accepted, create a post-M64
  planning-plus-review prompt. Do not start M65.

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
