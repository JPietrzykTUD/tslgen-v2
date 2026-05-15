# Post-M55 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M55 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M55 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M56 execution can be activated.

## Accepted Result

The post-M55 planning update selected:

```text
Milestone 56: Size-Bytes Times-Eight Generation Value Arithmetic Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The non-blocking follow-up is:

```text
Exact size-byte equality branch pruning over == 2, == 4, and == 8 remains a
strong future lowering candidate, but it is deferred from M56 because it also
opens else-if generation branch-chain syntax and selected-branch pruning policy.
```

## Read First

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Required Changes

Update only workflow docs/prompts:

- `docs/agent/current-redesign-state.md`
- `docs/agent/runs/m56-execution-review-loop-prompt.md`

Create `docs/agent/runs/m56-execution-review-loop-prompt.md` as the next
active prompt. It must use the orchestrated executor-review loop pattern and
include:

- exactly one write-capable executor if M56 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 57.

The M56 active prompt must constrain implementation to:

- Generation-time semantic lowering only.
- Support exactly:

  ```text
  value<generation>(type::size_bytes(type<generation>(base::in))) * 8
  ```

- Consume the accepted M55 typed `GenerationValue(kind="type.size_bytes")`
  behavior and explicit scalar size-byte rules.
- Produce typed integer generation values for exactly these selected scalar
  base tags and bit-width values:

  ```text
  si8/ui8 -> 8
  si16/ui16 -> 16
  si32/ui32/f32 -> 32
  si64/ui64/f64 -> 64
  ```

- Carry the lowered result as a typed generation value, such as
  `GenerationValue(kind="type.size_bits", value=<int>, type_tag=<tag>)`, or an
  equivalent immutable value object.
- Preserve M55 context precedence: explicit override, context selected tag,
  then selected candidate tag when enabled.
- Preserve all accepted M52-M55 type-query, signedness branch, rule-source,
  catalog-wiring, and size-byte query behavior.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

Boundary reminders for M56:

- M56 must not add general arithmetic expression parsing.
- M56 must not accept operators other than the exact selected `*` expression.
- M56 must not accept literal values other than `8`.
- M56 must not accept reversed operands such as `8 * value<generation>(...)`.
- M56 must not accept parenthesized, nested, chained, divided, added,
  subtracted, modulo, unary, or mixed arithmetic expressions.
- M56 must not add comparisons such as `== 2`, `== 4`, or `== 8`.
- M56 must not add branch pruning based on size values,
  `else if<generation>`, branch-chain syntax, or no-final-else branch policy.
- M56 must not lower enclosing IO, conflict, array, bit-count, horizontal,
  conversion, mask, load/store, loop, cast, call, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, or memory-copy bodies.
- M56 must not add backend suffix/type-spelling expansion, backend type/value
  translation, C++ or Rust rendering, generated output, generated test
  sources, CLI/reporting, writer behavior, compiler execution,
  generated-test execution, vector/register metadata, broad TSIL parsing, or
  runtime dependency on `frozen/`.
- Lowering must not read files, parse raw TSL, or query the catalog during
  evaluation.
- `frozen/` remains evidence only.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 55.
- Post-M55 planning accepted.
- Current action: run the Milestone 56 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m56-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 56: Size-Bytes Times-Eight Generation Value Arithmetic Slice`.
- The boundary reminders above.
- Non-blocking follow-ups remain recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m56-execution-review-loop-prompt.md
```

If other workflow docs/prompts are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M56.
