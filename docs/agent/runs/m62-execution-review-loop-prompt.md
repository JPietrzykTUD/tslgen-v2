# Milestone 62 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice
```

Milestones 1 through 61 are accepted. Post-M61 planning is accepted and
selected M62. Do not start any later milestone.

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

Implement the smallest generation-time lowering body-IR slice that consumes
accepted typed M61 `selected_body_form_recognition` output and converts only
the exact selected assignment/direct-intrinsic form into unresolved
backend-neutral selected-body IR:

```text
pg = intrin<svptrue_b16>();
pg = intrin<svptrue_b32>();
pg = intrin<svptrue_b64>();
```

M62 must:

- Consume only M61 `SelectedBranchBodyAssignmentFormRecognition` and
  `NoSelectedBranchBodyAssignmentFormRecognition` outputs from the distinct
  `selected_body_form_recognition` stage, or equivalent typed stage values.
- Produce a distinct typed selected assignment/direct-intrinsic body IR value
  for the exact M61-recognized single-statement form.
- Preserve candidate id, selected type tag, selected byte-size literal,
  originating branch-chain identity, original body text, source/provenance,
  assignment target text, opaque RHS text, direct-intrinsic token text, and
  explicit empty argument list.
- Represent `si8` and `ui8` byte-size `1` no-selected-body/no-form cases as
  explicit no-selected-body/no-body-IR results without synthesizing a body.
- Expose the result through a distinct post-form-recognition stage or typed
  value, such as `selected_body_ir_lowering`, instead of overloading M60
  handoff or M61 form-recognition metadata.
- Keep the selected body IR unresolved and backend-neutral. It is not backend
  intrinsic IR, not a backend translation request, not renderer-ready text, and
  not SVE predicate semantics.
- Consume typed M61 fields only. Preserved original body/RHS text may be
  carried as provenance, but M62 must not read, parse, or match it to derive
  semantics.

Diagnostics in M62 must stay boundary-level, such as unsupported M61
form-recognition boundary state, missing provenance, missing direct-intrinsic
token metadata, or inconsistent selected form-to-IR input. They must not
classify or semantically validate direct intrinsics, SVE predicates, assignment
semantics, variable scope, backend support, vector metadata, surrounding SVE
statements, or renderer/output behavior.

## Acceptance Criteria

M62 must satisfy these criteria:

- Body-IR lowering consumes M61 typed form-recognition output, not M58 stage
  records, M59 pruning results, M60 handoff records, raw selected body text,
  raw branch-chain text, raw TSL, catalog data, or `frozen/` runtime input.
- Selected typed body-IR output is produced for the M61 recognized
  `svptrue_b16`, `svptrue_b32`, and `svptrue_b64` forms.
- `si8` and `ui8` no-form cases do not synthesize a selected body, recognized
  form, or body IR.
- Original selected body text, assignment target text, opaque RHS/source text,
  direct-intrinsic token text, empty argument list, selected type/literal, and
  provenance are deterministic.
- A synthetic mismatch between selected byte-size literal and direct-intrinsic
  token text preserves both facts without diagnosing, correcting, or mapping
  them.
- Unselected and no-match branch bodies do not emit body-IR diagnostics.
- The branch-chain path does not invoke mini TSIL lowering and does not produce
  backend intrinsic, translation request, rendered code, or generated artifact
  values.
- Accepted M57/M58/M59/M60/M61 behavior remains unchanged except for the new
  body-IR output.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.

## Out Of Scope

M62 must not add:

- Assignment semantics, variable binding, declaration handling, target scope
  validation, proving that `pg` is an SVE predicate, or checking that `pg` was
  previously declared.
- Direct-intrinsic semantic validation.
- SVE predicate semantics.
- Mapping byte-size literals to `svptrue_b*` intrinsic tokens.
- Backend intrinsic IR, `BackendIntrinsicCall`, backend translation input,
  backend metadata lookup, or translation-map evaluation.
- General `intrin<...>` lowering.
- Non-zero-argument direct intrinsics.
- Primitive calls, casts, arrays, loops, declarations, stores, `emit_return`,
  multi-statement body lowering, surrounding `svbool_t pg =
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
- Central raw-string dispatch tables for body semantics.

## Evidence

Use accepted implementation and tests for:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed `GenerationSizeByteBranchChainPruning` and body-opacity behavior.
- M60 typed opaque selected-body handoff and no-selected-body behavior.
- M61 typed selected-body assignment-form recognition and no-form behavior.
- M42/M48/M51/M59/M60/M61 selected-branch-only diagnostic principles.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

These lines show the exact selected branch-body assignment/direct-intrinsic
forms that M62 may convert from M61 metadata into typed unresolved body IR.
Surrounding lines such as `tsldata/primitives/load_store/array.tsl:105-106`
and `:110-111` are out-of-scope evidence only for deferred declarations,
vector metadata, backend uninit, stores, and `emit_return`.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M62 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M62 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M62 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M62 within the scope and out-of-scope boundaries above.
- It must consume only typed M61 form-recognition outputs, not raw selected
  body text except as preserved provenance already carried by M61.
- It must introduce a distinct post-form-recognition body-IR value or stage,
  such as `selected_body_ir_lowering`.
- It must keep direct-intrinsic names unresolved and backend-neutral.
- It must not validate intrinsic names, infer SVE predicate meaning, map
  byte-size literals to `svptrue_b*` tokens, create backend intrinsic IR,
  create backend translation requests, feed renderers, or emit generated
  output.
- It must not invoke mini TSIL lowering or produce backend/rendering values for
  the branch-chain path.

The executor should report files changed, tests added or updated, validation
commands run, how typed M61 outputs are consumed, how selected-body IR remains
unresolved and non-rendering, how no-form/no-match bodies remain unsynthesized,
and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M62 body IR records, no-selected-body/no-body-IR behavior, the
   literal/token mismatch guard, unsupported M62 input diagnostics, unchanged
   M57/M58/M59/M60/M61 behavior, backend raw-helper rejection, renderer
   non-evaluation, determinism, and no generated output/golden churn.
3. Boundary auditor: confirm M62 implements only unresolved typed selected
   assignment/direct-intrinsic body IR from M61 form-recognition output and
   does not add assignment semantics, direct intrinsic/SVE semantics, broad
   TSIL parsing, vector metadata, backend translation, rendering/output,
   generated tests, CLI/reporting, writer behavior, Rust, compiler execution,
   runtime `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the body-IR value/stage envelope is typed,
   deterministic, distinct from M60 handoff and M61 form metadata, and suitable
   for future body-lowering slices without becoming a broad dispatcher or
   raw-text evaluator.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57/M58/M59/M60/M61 behavior plus `array.tsl:107-109`.

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

Do not broaden M62 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M62 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M62 plan has been accepted, create a post-M62
  planning-plus-review prompt. Do not start a later milestone.

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
