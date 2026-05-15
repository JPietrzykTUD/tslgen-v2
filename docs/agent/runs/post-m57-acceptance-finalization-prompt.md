# Post-M57 Acceptance Finalization Prompt

You are finalizing the accepted post-M57 planning update.

Do not implement code.

## Accepted Result

The post-M57 planning update selected:

```text
Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice
```

The internal post-M57 planning review returned:

```text
Accept With Follow-Ups
```

The blocking docs issue found during review was corrected locally before this
prompt was created: state wording now treats M58 as selected for human
acceptance while M59/M60 remain draft candidates only.

Remaining follow-ups are non-blocking:

```text
Keep M58 behavior-preserving while making the lowering stage contract
extendable and maintainable; avoid both cosmetic wrappers and broad lowering
refactors.
M57 evidence/test follow-up: add explicit unsupported-tag predicate coverage
for bword and fdqword later.
```

Proceed only if the user explicitly accepts the post-M57 planning result.

## Task

Update repository workflow state so the next action is M58 execution.

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
- `docs/agent/runs/m58-execution-review-loop-prompt.md`

Create `docs/agent/runs/m58-execution-review-loop-prompt.md` using the
orchestrated executor-review loop pattern:

- exactly one write-capable executor if M58 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 59.

The M58 active prompt must preserve these constraints:

- Generation-time semantic lowering stage boundary only.
- No new generation-time helper semantics.
- M58 must introduce a genuinely extendable and maintainable staged lowering
  contract, not merely rename or wrap the current functions.
- Each stage boundary introduced or refined by M58 must have explicit typed
  inputs and outputs suitable for future stages.
- Define or refine typed stage records around accepted M55 values, M56 values,
  and M57 predicates so later control-flow pruning consumes typed results
  instead of reparsing raw generation helper text.
- Future stages, especially M59 branch-chain pruning, must be able to consume
  typed predicate results without backend/rendering changes and without
  re-evaluating raw generation helper text.
- Preserve existing M55/M56/M57 observable lowered outputs exactly.
- Preserve existing M42/M48/M51 branch-pruning behavior exactly.
- Preserve backend raw-helper rejection and renderer non-evaluation.
- Keep catalog-derived rule construction before lowering evaluation.

The M58 active prompt must make these acceptance criteria explicit:

- The result is a typed stage contract or equivalent explicit stage records
  that make adding later lowering stages local and predictable.
- Adding a future helper family or future control-flow pruning stage should not
  require backend or renderer changes.
- The implementation must not concentrate future extensibility into one broad
  central `if`/`elif` evaluator or broad string-matching dispatcher.
- The executor should document how a later M59 branch-chain pruning slice would
  consume the M58 typed predicate/stage output.
- Tests must prove accepted M55/M56/M57 behavior is unchanged through the
  staged contract and that no branch-chain pruning was added.

Boundary reminders for M58:

- No size-byte equality branch-chain pruning.
- No `else if<generation>` support.
- No no-match provenance for size-byte branch chains.
- No final `else`, broad no-final-else policy, nested generation branches, or
  broad generation control-flow semantics.
- No new arithmetic, comparison, predicate, or helper semantics.
- No opaque selected branch body handoff.
- No direct `intrin<...>` / SVE body lowering, assignments, variables, arrays,
  loops, calls, casts, vector/register metadata, vector length/alignment, or
  backend uninit values.
- No backend translation expansion, rendering, generated output, generated
  test sources, CLI/reporting, writer behavior, Rust, compiler execution,
  generated-test execution, broad TSIL parsing, or runtime dependency on
  `frozen/`.
- No lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m58-execution-review-loop-prompt.md
```

If other workflow docs/prompts are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M58.
