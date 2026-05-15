# Post-M58 Acceptance Finalization Prompt

You are finalizing the accepted post-M58 planning update.

Do not implement code.

## Accepted Result

The post-M58 planning update selected:

```text
Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice
```

The internal post-M58 planning review returned:

```text
Needs Revision
```

The blocking review issue was workflow-handoff only and was corrected locally
before this prompt was created: `docs/agent/current-redesign-state.md` now
points at this finalization prompt, M59 is selected for human acceptance, and
M60 remains draft.

Remaining follow-ups are non-blocking:

```text
The eventual M59 executor prompt must keep any M58 staged-predicate reuse
cleanup explicitly subordinate to the exact branch-chain pruning slice.
M57 evidence/test follow-up: add explicit unsupported-tag predicate coverage
for bword and fdqword later.
```

Proceed only if the user explicitly accepts the post-M58 planning result.

## Task

Update repository workflow state so the next action is M59 execution.

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
- `docs/agent/runs/m59-execution-review-loop-prompt.md`

Create `docs/agent/runs/m59-execution-review-loop-prompt.md` using the
orchestrated executor-review loop pattern:

- exactly one write-capable executor if M59 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 60.

The M59 active prompt must preserve these constraints:

- Generation-time semantic lowering control-flow pruning only.
- Consume typed M57/M58 predicate and stage outputs instead of re-evaluating raw
  generation helper text.
- Select only the exact no-final-else SVE size-byte chain from
  `tsldata/primitives/load_store/array.tsl:107-109`.
- Support only the documented `== 2`, `== 4`, and `== 8` arm order.
- Select matching arms for byte sizes `2`, `4`, and `8`.
- Record explicit no-match provenance for byte size `1` without synthesizing a
  final `else`.
- Keep all branch bodies opaque.
- Preserve M55/M57/M58 observable value, predicate, and stage outputs.
- Preserve backend raw-helper rejection and renderer non-evaluation.
- If M59 needs access to staged predicate details outside `_lower_input`, allow
  only the smallest typed reuse cleanup needed to avoid duplicating private
  staged-predicate assembly or re-evaluating raw helper text.

Boundary reminders for M59:

- No broad `else if<generation>` syntax beyond the exact selected chain shape.
- No final `else`, reordered chains, missing arms, duplicate arms, nested
  branches, or broad no-final-else policy.
- No standalone comparison evaluation or general comparison parser.
- No M60 opaque selected branch body handoff.
- No direct `intrin<...>` / SVE body lowering, assignments, variables, arrays,
  calls, casts, loops, vector/register metadata,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting, writer
  behavior, Rust, compiler execution, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- No lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

The M59 active prompt must make these acceptance criteria explicit:

- Future branch-chain pruning consumes typed predicate/stage outputs, not raw
  helper text.
- Branch bodies remain opaque and unselected/no-match bodies do not emit nested
  helper diagnostics.
- `si16`/`ui16` select the `== 2` arm.
- `si32`/`ui32`/`f32` select the `== 4` arm.
- `si64`/`ui64`/`f64` select the `== 8` arm.
- `si8`/`ui8` produce explicit no-match provenance with no synthesized else.
- Unsupported branch-chain shapes are rejected without enabling broad
  `else if<generation>` parsing.
- Accepted M55/M57/M58 behavior remains unchanged.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m59-execution-review-loop-prompt.md
```

If other workflow docs/prompts are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M59.
