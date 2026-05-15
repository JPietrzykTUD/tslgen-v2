# Post-M56 Acceptance Finalization Prompt

You are finalizing the accepted post-M56 planning update.

Do not implement code.

## Accepted Result

The post-M56 planning update selected:

```text
Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice
```

The original post-M56 internal review returned:

```text
Accept With Follow-Ups
```

The M57 plan was then revised after user feedback to split predicate lowering
from later branch-chain pruning.

The roadmap now also records draft staged-lowering follow-on candidates after
M57:

```text
Draft Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice
Draft Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice
Draft Milestone 60: Opaque Selected Branch Body Handoff Slice
```

These drafts are not active for execution and must be reviewed and accepted one
at a time by later planning passes.

Remaining follow-up is non-blocking:

```text
Branch-chain pruning over the selected size-byte equality predicates remains a
strong future lowering candidate after M57 predicate lowering is accepted.
```

Proceed only if the user explicitly accepts the post-M56 planning result.

## Task

Update repository workflow state so the next action is M57 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`

## Required Changes

Update only workflow docs/prompts:

- `docs/agent/current-redesign-state.md`
- `docs/agent/runs/m57-execution-review-loop-prompt.md`

Create `docs/agent/runs/m57-execution-review-loop-prompt.md` using the
orchestrated executor-review loop pattern:

- exactly one write-capable executor if M57 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 58.

The M57 active prompt must preserve these constraints:

- Generation-time semantic lowering only.
- Support exactly these size-byte equality generation predicates:

  ```text
  value<generation>(type::size_bytes(type<generation>(base::in))) == 2
  value<generation>(type::size_bytes(type<generation>(base::in))) == 4
  value<generation>(type::size_bytes(type<generation>(base::in))) == 8
  ```

- Consume the M55 typed `GenerationValue(kind="type.size_bytes")` behavior and
  explicit scalar size-byte rules.
- Produce typed boolean generation predicate results.
- Evaluate `si8`/`ui8` byte size `1` as `false` for all selected predicates.
- Preserve accepted M52-M56 behavior.
- Preserve backend raw-helper rejection and renderer non-evaluation.

Boundary reminders for M57:

- No branch pruning, `if<generation>` parsing, or `else if<generation>` syntax.
- No selected-arm or no-match branch-chain provenance.
- No standalone comparison forms outside the exact selected predicates.
- No general comparison parsing.
- No operators except the exact selected `==` predicates.
- No literals except `2`, `4`, and `8`.
- No reversed comparisons.
- No nested, chained, parenthesized, bit-width, arithmetic, or mixed
  comparisons.
- No final `else`.
- No broad `else if<generation>`, broad plain `else`, arbitrary generation
  branch chains, nested generation branches, broad no-final-else policy, or
  branch-body semantics.
- No SVE array body lowering, assignments, variables, arrays, calls, casts,
  loops, `emit_return`, `intrin<svptrue_b*>`, `intrin<svst1>`, direct
  `intrin<...>`, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, or vector
  predicate semantics.
- No backend translation, rendering, generated output, generated test sources,
  CLI/report/writer behavior, Rust, compiler execution, generated-test
  execution, vector/register metadata, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- No lowering file reads, raw TSL parsing, or catalog queries during
  evaluation.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m57-execution-review-loop-prompt.md
```

If other workflow docs/prompts are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M57.
