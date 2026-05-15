# Milestone 58 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice
```

Milestones 1 through 57 are accepted. Post-M57 planning is accepted and
selected M58. Do not start Milestone 59.

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
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`

## Milestone Scope

Implement the smallest behavior-preserving generation-time semantic lowering
stage-boundary slice.

M58 must make the accepted value -> predicate -> control-flow path explicit as
a typed staged contract:

```text
helper/expression recognition
-> typed generation values
-> typed generation predicates
-> generation control-flow pruning
-> selected body lowering
```

M58 must not add new helper semantics. It must define or refine typed records
around accepted M55 values, M56 values, and M57 predicates so future
control-flow pruning consumes typed results instead of reparsing raw generation
helper text:

```text
GenerationValue(kind="type.size_bytes")
GenerationValue(kind="type.size_bits")
GenerationPredicate(kind="type.size_bytes.equals")
```

The result must be an extendable and maintainable staged lowering contract, not
a cosmetic wrapper around current functions and not a broad central
string-matching or `if`/`elif` evaluator.

M58 must preserve accepted M55/M56/M57 observable lowered outputs exactly and
preserve accepted M42/M48/M51 generation branch-pruning behavior exactly.

Preserve backend raw-helper rejection and renderer non-evaluation. Keep
catalog-derived rule construction before lowering evaluation; lowering
evaluation must consume typed request/context values only.

## Acceptance Criteria

M58 must satisfy these criteria:

- Each introduced or refined stage boundary has explicit typed inputs and typed
  outputs suitable for future lowering stages.
- Adding a future helper family or future control-flow pruning stage should not
  require backend or renderer changes.
- Future M59 branch-chain pruning can consume typed predicate or staged results
  without re-evaluating raw generation helper text.
- The implementation avoids concentrating future extensibility into one broad
  central `if`/`elif` evaluator or broad string-matching dispatcher.
- The executor documents how a later M59 branch-chain pruning slice would
  consume the M58 typed predicate/stage output.
- Tests prove accepted M55/M56/M57 behavior is unchanged through the staged
  contract.
- Tests prove no size-byte branch-chain pruning was added.

## Out Of Scope

M58 must not add:

- New generation-time helper forms.
- New arithmetic, comparison, predicate, or helper semantics.
- Size-byte equality branch-chain pruning.
- `else if<generation>` support.
- No-match provenance for size-byte branch chains.
- Final `else`, broad no-final-else policy, nested generation branches, or
  broad generation control-flow semantics.
- Opaque selected branch body handoff.
- Direct `intrin<...>` / SVE body lowering, assignments, variables, arrays,
  calls, casts, loops, `emit_return`, `intrin<svptrue_b*>`, `intrin<svst1>`,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values,
  vector/register metadata, or vector predicate semantics.
- Backend translation expansion, renderer behavior, generated output,
  generated test sources, CLI/report/writer behavior, Rust, compiler
  execution, generated-test execution, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

## Evidence

Use accepted implementation and tests for:

- M55 `GenerationValue(kind="type.size_bytes")`
- M56 `GenerationValue(kind="type.size_bits")`
- M57 `GenerationPredicate(kind="type.size_bytes.equals")`
- M42/M48/M51 generation branch pruning

Use current corpus evidence as future-consumer context only:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

These lines show why typed predicates need a control-flow consumer later. M58
must not implement that branch-chain consumer.

Legacy `frozen/tsl-gen/tsl_gen/tsl_lib/tsl_parser/tsil.lark` may be inspected
only as optional syntax evidence. Do not introduce any runtime dependency on
`frozen/`.

## Phase 1: Executor

If M58 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M58 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M58 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M58 within the scope and out-of-scope boundaries above.
- It must keep M58 behavior-preserving for accepted M42/M48/M51/M55/M56/M57
  behavior.
- It must make extensibility/maintainability concrete through typed stage
  boundaries, not broad dispatch logic.

The executor should report files changed, tests added or updated, validation
commands run, the M59 consumption note, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M58 behavior-preserving stage-boundary behavior.
3. Boundary auditor: confirm M58 implements only the stage contract and does
   not add branch-chain pruning, `else if<generation>`, new helper semantics,
   general expression parsing, backend, renderer, output, CLI, Rust, compiler,
   vector/register, broad parsing, or `frozen/` runtime behavior.
4. Extensibility auditor: confirm the staged contract is maintainable and
   future stages can be added locally without backend/rendering changes or a
   broad central string-matching evaluator.
5. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, design decisions, target architecture, pipeline design, and
   testing strategy for required updates or stale claims.
6. Evidence auditor: confirm the implementation and tests are justified by the
   accepted M55/M56/M57 behavior plus documented future-consumer evidence.

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

Do not broaden M58 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M58 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no M59 plan has been accepted, create a post-M58 planning-plus-review
  prompt. Do not start Milestone 59.

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
