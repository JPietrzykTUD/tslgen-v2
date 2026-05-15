# Milestone 56 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 56: Size-Bytes Times-Eight Generation Value Arithmetic Slice
```

Milestones 1 through 55 are accepted. Post-M55 planning is accepted and selected
M56. Do not start Milestone 57.

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

## Milestone Scope

Implement the smallest generation-time semantic lowering slice for exactly this
documented expression:

```text
value<generation>(type::size_bytes(type<generation>(base::in))) * 8
```

M56 must consume the accepted M55 typed
`GenerationValue(kind="type.size_bytes")` behavior and explicit scalar
size-byte rules. It must lower the exact expression to a typed scalar bit-width
generation value, for example:

```text
GenerationValue(kind="type.size_bits", value=<int>, type_tag=<tag>)
```

Supported scalar results are:

```text
si8/ui8 -> 8
si16/ui16 -> 16
si32/ui32/f32 -> 32
si64/ui64/f64 -> 64
```

Preserve accepted M55 context precedence:

1. explicit `base_in_type`
2. typed `GenerationTypeRef(kind="base.in")`
3. compatible legacy context fallback

Preserve all accepted M52-M55 behavior, including backend raw-helper rejection
and renderer non-evaluation of generation-time helpers.

## Out Of Scope

M56 must not add:

- General arithmetic parsing or an arithmetic expression engine.
- Operators other than the exact selected `*` form.
- Literals other than the exact multiplier `8`.
- Reversed operands such as `8 * value<generation>(...)`.
- Parenthesized, nested, chained, division, addition, subtraction, modulo,
  unary, or mixed arithmetic.
- Comparisons such as `== 2`, `== 4`, or `== 8`.
- Branch pruning, `else if<generation>`, branch-chain syntax, plain/final
  `else` support, or no-final-else policy changes.
- Surrounding body lowering.
- Backend translation, renderer behavior, generated output, generated test
  sources, CLI/report/writer behavior, Rust, compiler execution,
  generated-test execution, vector/register metadata, broad TSIL parsing, or
  runtime dependency on `frozen/`.
- Lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

## Evidence

Use current corpus evidence for the selected expression form:

- `tsldata/primitives/io/out.tsl:43`
- `tsldata/primitives/io/out.tsl:46`
- `tsldata/primitives/io/out.tsl:48`
- `tsldata/primitives/io/out.tsl:50`
- `tsldata/primitives/io/out.tsl:52`
- `tsldata/primitives/io/out.tsl:70`
- `tsldata/primitives/io/out.tsl:73`
- `tsldata/primitives/io/out.tsl:75`
- `tsldata/primitives/io/out.tsl:77`
- `tsldata/primitives/io/out.tsl:79`
- `tsldata/primitives/misc/conflict.tsl:79`

Use type-size evidence from:

- `tsldata/detail/types.tsl:2-9`
- `tsldata/detail/types.tsl:17-19`
- `tsldata/detail/types.tsl:10-16`
- `tsldata/detail/types.tsl:20-26`

Legacy `frozen/tsl-gen/tsl_gen/tsl_lib/tsl_parser/tsil.lark` may be inspected
only as syntax evidence. Do not introduce any runtime dependency on `frozen/`.

## Phase 1: Executor

If M56 is already implemented and awaiting review, skip implementation and go
directly to Phase 2.

If M56 is not implemented, spawn exactly one write-capable executor subagent.
Tell the executor:

- It is not alone in the codebase.
- It must not revert or overwrite edits made by others.
- It owns only the M56 implementation slice, directly related tests, and any
  necessary redesign-doc updates.
- It must not edit `docs/agent/current-redesign-state.md`.
- It must not create the next run prompt.
- It must keep M56 within the scope and out-of-scope boundaries above.

The executor should report files changed, tests added or updated, validation
commands run, and any follow-ups or blockers.

## Phase 2: Review And Audit Subagents

After execution, run read-only review/audit subagents using the specified
subagent workflow:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Validation auditor: verify the required validation commands and assess test
   coverage for M56 behavior.
3. Boundary auditor: confirm M56 implements only the exact selected expression
   and does not add out-of-scope arithmetic, branch, backend, renderer, output,
   CLI, Rust, compiler, vector/register, broad parsing, or `frozen/` runtime
   behavior.
4. Documentation auditor: check roadmap, lowering docs, open questions, design
   decisions, and behavioral spec for required updates or stale claims.
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

Do not broaden M56 during revision.

If the verdict is `Return To Planner` or `Reject`, stop implementation. Create
the appropriate next planning or rollback prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

- Record any non-blocking follow-ups.
- Update `docs/agent/current-redesign-state.md` so M56 is accepted.
- Create the next concrete prompt under `docs/agent/runs/`.
- If no M57 plan has been accepted, create a post-M56 planning-plus-review
  prompt. Do not start Milestone 57.

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
