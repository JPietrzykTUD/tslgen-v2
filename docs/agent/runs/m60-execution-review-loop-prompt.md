# Milestone 60 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 60: Opaque Selected Branch Body Handoff Slice
```

Milestones 1 through 59 are accepted. Post-M59 planning is accepted and
selected M60. Do not start any later milestone.

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

Implement the smallest generation-time semantic lowering slice that creates an
opaque selected branch body handoff from accepted M59 branch-chain pruning.

M60 must:

- Consume only accepted M59 `GenerationSizeByteBranchChainPruning` or
  equivalent typed `generation_control_flow_pruning` stage output.
- Introduce a distinct typed opaque selected-body handoff value or equivalent
  typed stage output; do not stretch M59 pruning metadata into the reusable
  handoff contract.
- Preserve candidate id, selected type tag, selected literal, opaque body text,
  source/provenance, and originating branch-chain identity.
- Represent M59 byte-size `1` no-match cases explicitly without synthesizing a
  selected body.
- Prove unselected branch bodies are not inspected, parsed, or diagnosed by
  the handoff step.
- Keep branch bodies opaque.
- Preserve M57 predicate behavior, M58 stage records, M59 branch-chain
  pruning/no-match behavior, backend raw-helper rejection, and renderer
  non-evaluation.

Diagnostics in M60 must stay boundary-level, such as missing selected body
text, missing provenance, or unsupported source stage. They must not classify
or parse direct intrinsics, assignments, arrays, calls, casts, loops, vector
metadata, backend uninit, or SVE predicates.

## Acceptance Criteria

M60 must satisfy these criteria:

- Handoff consumes typed M59 pruning/stage output, not raw branch-chain helper
  text.
- A selected typed opaque body handoff is produced for the M59 `== 2`, `== 4`,
  and `== 8` selected arms.
- `si8` and `ui8` no-match cases do not synthesize a selected body.
- Selected body text and provenance are deterministic.
- Unselected and no-match branch bodies do not emit nested helper or body
  diagnostics.
- The branch-chain path does not invoke mini TSIL lowering or produce
  direct-intrinsic/SVE `TsilStatement` values.
- Accepted M57/M58/M59 behavior remains unchanged except for the new handoff
  output.
- Backend translation still rejects raw unresolved generation helpers.
- Renderers still do not evaluate generation helpers.

## Out Of Scope

M60 must not add:

- Direct `intrin<...>` / SVE body lowering.
- Assignment, variable, array, loop, call, cast, or `emit_return` lowering.
- SVE predicate semantics.
- `value<generation>(vector::length)`.
- `value<generation>(vector::alignment)`.
- Vector/register metadata.
- Backend uninit values.
- Backend translation expansion.
- Rendering or generated output.
- Generated tests.
- CLI/reporting/writer behavior.
- Rust.
- Compiler execution.
- Broad TSIL parsing.
- Broad `else if<generation>` syntax beyond accepted M59 behavior.
- Runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

## Evidence

Use accepted implementation and tests for:

- M57 `GenerationPredicate(kind="type.size_bytes.equals")`.
- M58 typed `GenerationLoweringStage` records.
- M59 typed `GenerationSizeByteBranchChainPruning` and body-opacity behavior.
- M42/M48/M51/M59 selected-branch-only diagnostic principles.

Use current corpus evidence:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

These lines show the selected branch bodies that M60 may hand forward as
opaque text/provenance. Surrounding SVE statements, direct intrinsics, vector
metadata, array construction, stores, and final `emit_return` remain evidence
only and must not be implemented by M60.

`frozen/` may be inspected only as optional syntax evidence. Do not introduce
any runtime dependency on `frozen/`.

## Phase 1: Executor

If M60 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M60 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M60 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M60 within the scope and out-of-scope boundaries above.
- It must consume typed M59 pruning/stage output, not raw branch-chain helper
  text.
- It must introduce a distinct typed opaque selected-body handoff value or
  equivalent typed stage output.
- It must not parse or lower selected or unselected body semantics.
- It must not invoke mini TSIL lowering or produce direct-intrinsic/SVE
  `TsilStatement` values for the branch-chain path.

The executor should report files changed, tests added or updated, validation
commands run, how typed M59 outputs are consumed, how body opacity is
preserved, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M60 selected-body handoff, no-match behavior, opaque bodies,
   unchanged M57/M58/M59 behavior, backend raw-helper rejection, and renderer
   non-evaluation.
3. Boundary auditor: confirm M60 implements only opaque selected-body handoff
   and does not add body parsing/lowering, mini TSIL statement lowering for
   branch-chain bodies, direct intrinsics, SVE semantics, vector metadata,
   backend translation, rendering/output, generated tests, CLI/reporting,
   writer behavior, Rust, compiler execution, broad TSIL parsing, runtime
   `frozen/`, or lowering-time file/catalog reads.
4. Extensibility auditor: confirm the handoff value is typed, distinct from
   M59 pruning metadata, deterministic, and suitable for future body-lowering
   slices without becoming a broad dispatcher or raw-text evaluator.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, testing
   strategy, and parity baselines for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by
   accepted M57/M58/M59 behavior plus `array.tsl:107-109`.

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

Do not broaden M60 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M60 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no post-M60 plan has been accepted, create a post-M60
  planning-plus-review prompt. Do not start a later milestone.

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
