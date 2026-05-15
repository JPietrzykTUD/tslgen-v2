# Milestone 57 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice
```

Milestones 1 through 56 are accepted. Post-M56 planning is accepted after
user-requested revision and selected M57. Do not start Milestone 58.

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

Implement the smallest generation-time semantic lowering slice for exactly
these documented size-byte equality generation predicates:

```text
value<generation>(type::size_bytes(type<generation>(base::in))) == 2
value<generation>(type::size_bytes(type<generation>(base::in))) == 4
value<generation>(type::size_bytes(type<generation>(base::in))) == 8
```

M57 must consume the accepted M55 typed
`GenerationValue(kind="type.size_bytes")` behavior and explicit scalar
size-byte rules. It must lower the exact selected predicates to typed boolean
generation predicate results, for example:

```text
GenerationPredicate(kind="type.size_bytes.equals", literal=<int>, value=<bool>, type_tag=<tag>)
```

An equivalent typed value is acceptable if it stays within the established
lowering model.

Supported scalar predicate truth table:

```text
si8/ui8 -> false for == 2, == 4, and == 8
si16/ui16 -> true only for == 2
si32/ui32/f32 -> true only for == 4
si64/ui64/f64 -> true only for == 8
```

M57 must preserve accepted M55/M56 context precedence for the selected base
input type:

1. explicit `base_in_type`
2. typed `GenerationTypeRef(kind="base.in")`
3. compatible legacy context fallback

Preserve all accepted M52-M56 behavior, including backend raw-helper rejection
and renderer non-evaluation of generation-time helpers.

## Out Of Scope

M57 must not add:

- Branch pruning, `if<generation>` parsing, `else if<generation>` syntax,
  branch-chain syntax, selected-arm provenance, or no-match provenance.
- Standalone comparison forms outside the exact selected predicates.
- A general comparison parser or predicate expression engine.
- Operators other than the exact selected `==` predicates.
- Literals other than `2`, `4`, and `8`.
- Reversed comparisons such as `2 == value<generation>(...)`.
- Nested, chained, parenthesized, bit-width, arithmetic, or mixed comparisons.
- Final `else`, broad `else if<generation>`, broad plain `else`, arbitrary
  generation branch chains, nested generation branches, broad no-final-else
  policy, or branch-body semantics.
- SVE array body lowering, assignments, variables, arrays, calls, casts, loops,
  `emit_return`, `intrin<svptrue_b*>`, `intrin<svst1>`, direct
  `intrin<...>`, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, or vector
  predicate semantics.
- Backend translation, renderer behavior, generated output, generated test
  sources, CLI/report/writer behavior, Rust, compiler execution,
  generated-test execution, vector/register metadata, broad TSIL parsing, or
  runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

## Evidence

Use current corpus evidence for the selected size-byte equality predicates:

- `tsldata/primitives/load_store/array.tsl:107`
- `tsldata/primitives/load_store/array.tsl:108`
- `tsldata/primitives/load_store/array.tsl:109`

Use type-size evidence from:

- `tsldata/detail/types.tsl:2-9`
- `tsldata/detail/types.tsl:17-19`
- `tsldata/detail/types.tsl:10-16`
- `tsldata/detail/types.tsl:20-26`

Legacy `frozen/tsl-gen/tsl_gen/tsl_lib/tsl_parser/tsil.lark` may be inspected
only as optional syntax evidence. Do not introduce any runtime dependency on
`frozen/`.

## Phase 1: Executor

If M57 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M57 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M57 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M57 within the scope and out-of-scope boundaries above.

The executor should report files changed, tests added or updated, validation
commands run, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M57 behavior.
3. Boundary auditor: confirm M57 implements only the exact selected predicates
   and does not add branch-chain parsing/pruning, general comparisons,
   backend, renderer, output, CLI, Rust, compiler, vector/register, broad
   parsing, or `frozen/` runtime behavior.
4. Documentation auditor: check roadmap, lowering docs, behavioral spec, open
   questions, and design decisions for required updates or stale claims.
5. Evidence auditor: confirm the implementation and tests are justified by the
   documented corpus and legacy-evidence boundaries.

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

Do not broaden M57 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M57 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no M58 plan has been accepted, create a post-M57 planning-plus-review
  prompt. Do not start Milestone 58.

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
