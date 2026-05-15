# Milestone 59 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice
```

Milestones 1 through 58 are accepted. Post-M58 planning is accepted and
selected M59. Do not start Milestone 60.

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

## Milestone Scope

Implement the smallest generation-time semantic lowering control-flow pruning
slice for the exact size-byte equality branch chain.

M59 must consume typed M57/M58 predicate and stage outputs instead of
re-evaluating raw generation helper text. It selects only the exact
no-final-else SVE size-byte chain from:

```text
tsldata/primitives/load_store/array.tsl:107-109
```

Supported chain shape:

```text
if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 2) { ... }
else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 4) { ... }
else if<generation>(value<generation>(type::size_bytes(type<generation>(base::in))) == 8) { ... }
```

M59 must:

- Support only the documented `== 2`, `== 4`, and `== 8` arm order.
- Select matching arms for byte sizes `2`, `4`, and `8`.
- Record explicit no-match provenance for byte size `1` without synthesizing a
  final `else`.
- Keep all branch bodies opaque.
- Preserve M55/M57/M58 observable value, predicate, and stage outputs.
- Preserve backend raw-helper rejection and renderer non-evaluation.
- Preserve M42/M48/M51 selected-branch-only diagnostic principles where they
  apply to the selected chain.

If M59 needs access to staged predicate details outside `_lower_input`, allow
only the smallest typed reuse cleanup needed to avoid duplicating private
staged-predicate assembly or re-evaluating raw helper text. Keep that cleanup
subordinate to the exact branch-chain pruning slice.

## Acceptance Criteria

M59 must satisfy these criteria:

- Branch-chain pruning consumes typed predicate/stage outputs, not raw helper
  text.
- Branch bodies remain opaque.
- Unselected/no-match bodies do not emit nested helper diagnostics.
- `si16` and `ui16` select the `== 2` arm.
- `si32`, `ui32`, and `f32` select the `== 4` arm.
- `si64`, `ui64`, and `f64` select the `== 8` arm.
- `si8` and `ui8` produce explicit no-match provenance with no synthesized
  `else`.
- Unsupported branch-chain shapes are rejected without enabling broad
  `else if<generation>` parsing.
- Accepted M55/M57/M58 behavior remains unchanged.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.

## Out Of Scope

M59 must not add:

- Broad `else if<generation>` syntax beyond the exact selected chain shape.
- Final `else`, reordered chains, missing arms, duplicate arms, nested
  branches, or broad no-final-else policy.
- Standalone comparison evaluation or a general comparison parser.
- M60 opaque selected branch body handoff.
- Direct `intrin<...>` / SVE body lowering.
- Assignments, variables, arrays, calls, casts, loops, vector/register
  metadata, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, or backend uninit values.
- Backend translation expansion, rendering, output, generated tests,
  CLI/reporting, writer behavior, Rust, compiler execution, broad TSIL
  parsing, or runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

## Evidence

Use accepted implementation and tests for:

- M55 `GenerationValue(kind="type.size_bytes")`
- M57 `GenerationPredicate(kind="type.size_bytes.equals")`
- M58 typed `GenerationLoweringStage` records
- M42/M48/M51 branch-pruning provenance and selected-branch-only diagnostics

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

These lines show the exact no-final-else size-byte branch chain selected for
M59. Surrounding SVE statements, direct intrinsics, vector metadata, array
construction, stores, and final `emit_return` remain evidence only and must not
be implemented by M59.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M59 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M59 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M59 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M59 within the scope and out-of-scope boundaries above.
- It must keep M59 behavior-preserving for accepted M42/M48/M51/M55/M57/M58
  behavior except for the selected branch-chain pruning behavior.
- It must make branch-chain pruning consume typed predicate/stage outputs, not
  raw helper text.
- It must keep branch bodies opaque and avoid M60 selected-body handoff.
- If a tiny staged-predicate reuse cleanup is needed, it must remain
  subordinate to the exact branch-chain pruning slice.

The executor should report files changed, tests added or updated, validation
commands run, how typed M57/M58 outputs are consumed, and any follow-ups or
blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M59 exact branch-chain pruning, no-match provenance, opaque
   bodies, and preserved M55/M57/M58 behavior.
3. Boundary auditor: confirm M59 implements only exact branch-chain pruning and
   does not add M60 body handoff, broad `else if<generation>`, general
   comparison parsing, backend, renderer, output, CLI, Rust, compiler, vector,
   broad parsing, or `frozen/` runtime behavior.
4. Extensibility auditor: confirm any staged-predicate reuse cleanup is local,
   typed, and subordinate to the exact pruning slice rather than a broad second
   evaluator or raw-text dispatcher.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, and
   testing strategy for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M55/M57/M58 behavior plus `array.tsl:107-109`.

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

Do not broaden M59 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M59 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no M60 plan has been accepted, create a post-M59 planning-plus-review
  prompt. Do not start Milestone 60.

The next prompt must follow `docs/agent/next-run-prompt-protocol.md`.

## Required Validation

Run targeted validation selected by the executor plus:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If Python implementation files changed, also run an appropriate compile or
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
