# Post-M50 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M50 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M50 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M51 execution can be activated.

## Accepted Result

The post-M50 planning update selected:

```text
Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

No blocking follow-up remains.

Non-blocking follow-ups remain recorded in
`docs/agent/current-redesign-state.md`.

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
- `docs/agent/runs/m51-execution-review-loop-prompt.md`

Create `docs/agent/runs/m51-execution-review-loop-prompt.md` as the next active
prompt. It must use the orchestrated executor-review loop pattern and include:

- exactly one write-capable executor if M51 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 52.

The M51 active prompt must constrain implementation to:

- Generation-time semantic lowering only.
- Exact signedness predicate branch form only:

  ```text
  if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
    ...
  } else {
    ...
  }
  ```

- Reuse M48 signedness predicate evaluation over typed M43
  `GenerationTypeRef(kind="base.in")` inputs.
- Reuse M42/M48 branch pruning, deterministic provenance, and
  selected-branch-only diagnostics.
- Treat plain `else` as equivalent to `else<generation>` only for this selected
  signedness predicate branch form.
- Preserve existing `else<generation>` signedness branch behavior.

Boundary reminders for M51:

- M51 must not add broad plain-`else` support for arbitrary generation
  branches.
- M51 must not add primitive-attribute plain `else` support.
- M51 must not add conversion or shift body parity.
- M51 must not add `switch<compile>`, `if<compile>`, direct `intrin<...>`,
  `let`, `var`, calls, vector transforms, loops, aliases, casts, arrays,
  generic lengths, immediates, vector/register metadata, backend translation,
  backend rendering, generated C++ output, generated test sources, Rust output,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, broad TSIL parsing, or branch-body semantics.
- M51 must not broaden signedness predicates beyond the selected M43
  `si32`/`ui32` `base.in` inputs.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is selected
  branch-shape evidence only; its enclosing `switch<compile>` and branch bodies
  remain out of scope.
- `frozen/` remains evidence only.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 50.
- Post-M50 planning accepted.
- Current action: run the Milestone 51 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m51-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice`.
- The boundary reminders above.
- Non-blocking follow-ups remain recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m51-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M51.
