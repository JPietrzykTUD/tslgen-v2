# Milestone 63 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 63: Backend-Neutral Selected Body Envelope IR Slice
```

Milestones 1 through 62 are accepted. Post-M62 planning is accepted and
selected M63. Do not start any later milestone.

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

Implement the smallest generation-time lowering/body-envelope IR slice that
consumes accepted typed M62 `selected_body_ir_lowering` output and wraps only
the M62 selected-body IR or no-body-IR result in a backend-neutral selected
body envelope.

M63 must:

- Consume only M62 `SelectedAssignmentDirectIntrinsicBodyIr` and
  `NoSelectedAssignmentDirectIntrinsicBodyIr` outputs from the distinct
  `selected_body_ir_lowering` stage, or equivalent typed M62 stage values.
- Produce a distinct typed selected-body envelope value or stage, such as
  `selected_body_envelope_lowering`.
- For selected cases, produce a deterministic typed sequence with exactly one
  entry wrapping the existing M62 selected assignment/direct-intrinsic body IR
  facts.
- For M62 no-body-IR cases, produce an explicit no-body envelope without
  synthesizing statements or body text.
- Preserve M62 target text, unresolved direct-intrinsic token text, explicit
  empty argument list, original RHS/body text, selected type/literal,
  candidate identity, branch-chain identity, source location, and provenance
  as typed envelope/entry facts.
- Keep the envelope backend-neutral and unresolved. It is not backend
  intrinsic IR, not a backend translation request, not renderer-ready body IR,
  and not SVE predicate/vector semantics.
- Consume typed M62 fields only. Preserved original body/RHS text may be
  carried as provenance, but M63 must not read, parse, or match it to derive
  semantics.

Diagnostics in M63 must stay boundary-level, such as unsupported M62 source
stage/type or inconsistent selected/no-body envelope input. They must not
classify or semantically validate direct intrinsics, SVE predicates,
assignment semantics, variable scope, array/store/return semantics, backend
support, vector metadata, surrounding SVE-looking statements, or
renderer/output behavior.

Suggested diagnostic names from planning:

- `TSL-LOWER-SELECTED-BODY-ENVELOPE-SOURCE-UNSUPPORTED`
- `TSL-LOWER-SELECTED-BODY-ENVELOPE-INCONSISTENT`

## Acceptance Criteria

M63 must satisfy these criteria:

- Envelope lowering consumes M62 typed selected-body IR/no-body-IR values, not
  M57/M58/M59 stage records, M60 handoff records, M61 form-recognition records,
  raw selected body text, raw branch-chain text, raw TSL, catalog data, or
  `frozen/` runtime input.
- Selected envelopes are produced for the M62 `svptrue_b16`, `svptrue_b32`,
  and `svptrue_b64` body-IR records.
- Selected envelopes contain exactly one deterministic typed sequence entry.
- `si8` and `ui8` no-body-IR cases produce explicit no-body envelopes without
  synthesizing a selected body, recognized form, sequence entry, or statement.
- Original selected body text, assignment target text, opaque RHS/source text,
  direct-intrinsic token text, empty argument list, selected type/literal,
  source location, branch identity, and provenance are deterministic.
- A synthetic mismatch between selected byte-size literal and direct-intrinsic
  token text is preserved inside the envelope without diagnosing, correcting,
  or mapping the facts.
- Preserved original body text is not reparsed to derive envelope facts.
- Unselected and no-match branch bodies do not emit envelope diagnostics.
- The branch-chain path does not invoke mini TSIL lowering and does not
  produce backend intrinsic, translation request, rendered code, or generated
  artifact values.
- Accepted M57/M58/M59/M60/M61/M62 behavior remains unchanged except for the
  new envelope output.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.

## Out Of Scope

M63 must not add:

- Parsing or matching preserved selected-body text to derive semantics.
- Assignment semantics, variable binding, declaration handling, target scope
  validation, proving that `pg` is an SVE predicate, or checking that `pg` was
  previously declared.
- Direct-intrinsic semantic validation.
- SVE predicate, vector, or register semantics.
- Mapping byte-size literals to `svptrue_b*` intrinsic tokens.
- Backend intrinsic IR, `BackendIntrinsicCall`, backend translation input,
  backend metadata lookup, or translation-map evaluation.
- Renderer-ready body/expression IR.
- General `intrin<...>` lowering.
- Non-zero-argument direct intrinsics.
- Primitive calls, casts, arrays, loops, declarations, stores, `emit_return`,
  returns, multi-statement body lowering, surrounding `svbool_t pg =
  intrin<svptrue_b8>()`, `intrin<svst1>(...)`, or backend uninit values.
- `value<generation>(vector::length)`.
- `value<generation>(vector::alignment)`.
- Vector/register metadata.
- Backend translation expansion.
- Rendering or generated output.
- Generated tests.
- CLI/reporting/writer behavior.
- Rust.
- Compiler execution.
- Generated-test execution.
- Broad TSIL parsing.
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
- M42/M48/M51/M59/M60/M61/M62 selected-branch-only diagnostic principles.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

These lines show the exact selected branch-body assignment/direct-intrinsic
forms that M62 already converted into unresolved typed body IR, which M63 may
wrap as a singleton envelope entry. Surrounding lines such as
`tsldata/primitives/load_store/array.tsl:105-106` and `:110-111` are evidence
only that the selected body appears inside a larger ordered body. They remain
out of scope for declarations, vector metadata, backend uninit, stores,
`emit_return`, and SVE semantics.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M63 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M63 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M63 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M63 within the scope and out-of-scope boundaries above.
- It must consume only typed M62 body-IR/no-body-IR outputs, not M60 handoff
  values, M61 form-recognition values, raw selected body text, raw branch-chain
  text, raw TSL, catalog data, or `frozen/` runtime input.
- It must introduce a distinct post-M62 envelope value or stage, such as
  `selected_body_envelope_lowering`.
- It must keep direct-intrinsic names unresolved and backend-neutral.
- It must not validate intrinsic names, infer SVE predicate meaning, map
  byte-size literals to `svptrue_b*` tokens, create backend intrinsic IR,
  create backend translation requests, feed renderers, or emit generated
  output.
- It must not invoke mini TSIL lowering or produce backend/rendering values for
  the branch-chain path.

The executor should report files changed, tests added or updated, validation
commands run, how typed M62 outputs are consumed, how selected-body envelopes
remain unresolved and non-rendering, how no-body cases remain unsynthesized,
and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M63 selected envelopes, no-body envelopes, deterministic
   sequence ordering, mismatch preservation, unsupported/inconsistent boundary
   diagnostics, unchanged M57/M58/M59/M60/M61/M62 behavior, backend raw-helper
   rejection, renderer non-evaluation, determinism, and no generated
   output/golden churn.
3. Boundary auditor: confirm M63 implements only backend-neutral selected-body
   envelope IR from M62 typed body-IR/no-body-IR outputs and does not add
   assignment semantics, direct intrinsic/SVE semantics, broad TSIL parsing,
   vector metadata, backend translation, rendering/output, generated tests,
   CLI/reporting, writer behavior, Rust, compiler execution, runtime
   `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the envelope/sequence value or stage is
   typed, deterministic, distinct from M60 handoff, M61 form metadata, and M62
   body IR, and suitable for future body-lowering slices without becoming a
   broad dispatcher or raw-text evaluator.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57/M58/M59/M60/M61/M62 behavior plus `array.tsl:107-109`, and
   that `array.tsl:105-111` is used only as evidence for the need for a
   body-envelope boundary.

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

Do not broaden M63 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M63 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M63 plan has been accepted, create a post-M63
  planning-plus-review prompt. Do not start M64.

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
