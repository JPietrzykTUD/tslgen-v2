# Milestone 61 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 61: Selected Branch Body Assignment Form Recognition Slice
```

Milestones 1 through 60 are accepted. Post-M60 planning is accepted and
selected M61. Do not start any later milestone.

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

Implement the smallest generation-time lowering form-recognition slice that
consumes accepted M60 selected-body handoff output and recognizes exactly the
selected branch-body assignment form:

```text
pg = intrin<svptrue_b16>();
pg = intrin<svptrue_b32>();
pg = intrin<svptrue_b64>();
```

M61 must:

- Consume only accepted typed M60 `OpaqueSelectedBranchBodyHandoff` and
  `NoSelectedBranchBodyHandoff` values, or equivalent typed selected-body
  handoff stage output.
- Introduce a distinct typed selected-body assignment-form recognition value,
  or equivalent typed stage envelope, instead of stretching
  `selected_body_lowering` into a mixed semantic dispatcher.
- Preserve candidate id, selected type tag, selected literal, originating
  branch-chain identity, original opaque body text, selected statement
  source/provenance, assignment target text, and opaque RHS/source text.
- Record direct-intrinsic token text only as form metadata for later slices.
- Represent `si8` and `ui8` byte-size `1` no-match handoffs explicitly without
  synthesizing a body or recognized form.
- Keep recognition deterministic and selected-branch-only.
- Preserve M57 predicate behavior, M58 stage records, M59 branch-chain
  pruning/no-match behavior, M60 handoff behavior, backend raw-helper
  rejection, and renderer non-evaluation.

Diagnostics in M61 must stay form-recognition boundary-level, such as missing
provenance, unsupported handoff source, extra statements, unsupported target
shape, unsupported RHS shape, missing selected body text, or malformed selected
body text. They must not classify or semantically validate direct intrinsics,
SVE predicates, assignment semantics, variable scope, backend support, vector
metadata, surrounding SVE statements, or renderer/output behavior.

## Acceptance Criteria

M61 must satisfy these criteria:

- Recognition consumes typed M60 handoff output, not raw branch-chain text, raw
  TSL, catalog data, or `frozen/` runtime input.
- A selected typed form-recognition output is produced for the M60 selected
  `== 2`, `== 4`, and `== 8` bodies.
- `si8` and `ui8` no-match cases do not synthesize a selected body or
  recognized form.
- Original selected body text, assignment target text, opaque RHS/source text,
  direct-intrinsic token text, and provenance are deterministic.
- Unselected and no-match branch bodies do not emit body-form diagnostics.
- The branch-chain path does not invoke mini TSIL lowering and does not produce
  direct-intrinsic/SVE `TsilStatement`, backend intrinsic, translation
  request, rendered code, or generated artifact values.
- Accepted M57/M58/M59/M60 behavior remains unchanged except for the new
  form-recognition output.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.

## Out Of Scope

M61 must not add:

- Assignment semantics, variable binding, declaration handling, target scope
  validation, or proving that `pg` is an SVE predicate.
- Direct `intrin<...>` lowering.
- Intrinsic-name validation.
- SVE predicate semantics.
- Mapping byte-size literals to SVE suffixes.
- Backend intrinsic IR or backend translation input.
- Surrounding SVE body forms such as `svbool_t pg = intrin<svptrue_b8>()`,
  `intrin<svst1>(...)`, array construction, backend uninit, `emit_return`,
  vector length/alignment, declarations, variables, arrays, calls, casts,
  loops, or multi-statement bodies.
- `value<generation>(vector::length)`.
- `value<generation>(vector::alignment)`.
- Vector/register metadata.
- Backend translation expansion.
- Rendering or generated output.
- Generated tests.
- CLI/reporting/writer behavior.
- Rust.
- Compiler execution.
- Broad TSIL parsing.
- Runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.
- Central raw-string dispatch tables for body semantics.

## Evidence

Use accepted implementation and tests for:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed `GenerationSizeByteBranchChainPruning` and body-opacity behavior.
- M60 typed opaque selected-body handoff and no-selected-body behavior.
- M42/M48/M51/M59/M60 selected-branch-only diagnostic principles.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

These lines show the exact selected branch-body assignment forms that M61 may
recognize as typed form metadata. Surrounding lines such as
`tsldata/primitives/load_store/array.tsl:105-106` and `:110-111` are
out-of-scope evidence only for deferred declarations, vector metadata, backend
uninit, stores, and `emit_return`.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M61 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M61 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M61 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M61 within the scope and out-of-scope boundaries above.
- It must consume typed M60 handoff output, not raw branch-chain text, raw TSL,
  catalog data, or `frozen/` runtime input.
- It must introduce a distinct typed form-recognition value or stage envelope.
- It must not lower assignment semantics, validate direct intrinsics, infer SVE
  predicate meaning, or parse broad body semantics.
- It must not invoke mini TSIL lowering or produce direct-intrinsic/SVE
  `TsilStatement` values for the branch-chain path.

The executor should report files changed, tests added or updated, validation
commands run, how typed M60 outputs are consumed, how selected-body form
recognition remains non-semantic, how unselected/no-match bodies remain
uninspected, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M61 selected form recognition, no-match behavior, unsupported
   form diagnostics, unchanged M57/M58/M59/M60 behavior, backend raw-helper
   rejection, and renderer non-evaluation.
3. Boundary auditor: confirm M61 implements only selected-body assignment-form
   recognition and does not add assignment semantics, direct intrinsic/SVE
   semantics, broad TSIL parsing, vector metadata, backend translation,
   rendering/output, generated tests, CLI/reporting, writer behavior, Rust,
   compiler execution, runtime `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the form-recognition value/stage envelope is
   typed, deterministic, distinct from M60 handoff metadata, and suitable for
   future body-lowering slices without becoming a broad dispatcher or raw-text
   evaluator.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57/M58/M59/M60 behavior plus `array.tsl:107-109`.

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

Do not broaden M61 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M61 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M61 plan has been accepted, create a post-M61
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
2. Review/audit subagents used.
3. Consolidated verdict.
4. Revision loop count.
5. Files changed.
6. Validation commands and exact results.
7. Follow-ups recorded, if any.
8. Next prompt created.
9. Current state update.
10. Whether the repo is ready for the next action.
