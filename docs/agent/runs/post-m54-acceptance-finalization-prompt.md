# Post-M54 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M54 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M54 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M55 execution can be activated.

## Accepted Result

The post-M54 planning update selected:

```text
Milestone 55: Base Scalar Size-Bytes Generation Value Query Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

The non-blocking follow-up is:

```text
Keep f32/f64 support scoped to the exact scalar size-bytes query; do not
broaden standalone base.in or signed/unsigned companion semantics to floats.
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

## Required Changes

Update only workflow docs/prompts:

- `docs/agent/current-redesign-state.md`
- `docs/agent/runs/m55-execution-review-loop-prompt.md`

Create `docs/agent/runs/m55-execution-review-loop-prompt.md` as the next active
prompt. It must use the orchestrated executor-review loop pattern and include:

- exactly one write-capable executor if M55 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 56.

The M55 active prompt must constrain implementation to:

- Generation-time semantic lowering only.
- Support exactly:

  ```text
  value<generation>(type::size_bytes(type<generation>(base::in)))
  ```

- Produce typed integer generation values for exactly these selected scalar
  base tags and byte values:

  ```text
  si8/ui8 -> 1
  si16/ui16 -> 2
  si32/ui32/f32 -> 4
  si64/ui64/f64 -> 8
  ```

- Introduce explicit typed scalar size-byte rule/value records or equivalent
  immutable typed values.
- Build or expose scalar size-byte rules from typed catalog/type-group data
  before lowering evaluation, following the M54 lowering-input pattern.
- Preserve all accepted M52-M54 concrete-integer type-query, signedness branch,
  rule-source, and catalog-wiring behavior.
- Accept `f32` and `f64` only for this exact size-bytes value query.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

Boundary reminders for M55:

- M55 must not reuse or mutate `ConcreteIntegerGenerationRuleSet` for float
  size semantics.
- M55 must not broaden standalone `type<generation>(base::in)` or
  `base::signed_of` / `base::unsigned_of` behavior to floats.
- M55 must not infer byte sizes from regex, tag spelling, wildcard/group
  selectors, or unselected concrete-looking tags such as `si128`.
- M55 must not treat `arith`, `f?`, `?i?`, `?i64`, `si?`, `ui?`, `dword`,
  `qword`, `idqword`, `dqword`, or other group selectors as selected scalar
  tags during lowering.
- M55 must not add `type::size_bytes(...)` over vector, mask, pointer, backend,
  alias, cast, array, generic, signed_of, or unsigned_of forms.
- M55 must not add arithmetic or comparisons over generation values, including
  `* 8`, `== 2`, `else if<generation>`, or branch pruning based on size-byte
  values.
- M55 must not lower enclosing IO, memory-copy, array, bit-count, conflict,
  conversion, load/store, loop, cast, call, direct `intrin<...>`,
  `switch<compile>`, or `if<compile>` bodies.
- M55 must not add backend translation expansion, C++ or Rust rendering,
  generated output, generated test sources, CLI/reporting, writer behavior,
  compiler execution, generated-test execution, vector/register metadata,
  broad TSIL parsing, or runtime dependency on `frozen/`.
- Lowering must not read files, parse raw TSL, or query the catalog during
  evaluation.
- `frozen/` remains evidence only.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 54.
- Post-M54 planning accepted.
- Current action: run the Milestone 55 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m55-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 55: Base Scalar Size-Bytes Generation Value Query Slice`.
- The boundary reminders above.
- Non-blocking follow-ups remain recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m55-execution-review-loop-prompt.md
```

If other workflow docs/prompts are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M55.
