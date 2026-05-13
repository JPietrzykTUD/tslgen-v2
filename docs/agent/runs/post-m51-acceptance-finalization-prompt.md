# Post-M51 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M51 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M51 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M52 execution can be activated.

## Accepted Result

The post-M51 planning update selected:

```text
Milestone 52: Concrete Integer Generation Type Semantics Slice
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
- `docs/agent/runs/m52-execution-review-loop-prompt.md`

Create `docs/agent/runs/m52-execution-review-loop-prompt.md` as the next active
prompt. It must use the orchestrated executor-review loop pattern and include:

- exactly one write-capable executor if M52 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 53.

The M52 active prompt must constrain implementation to:

- Generation-time semantic lowering only.
- Existing exact M43 type query forms only:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

- Existing exact M48/M51 signedness predicate branch forms only:

  ```text
  if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
    ...
  } else<generation> {
    ...
  }
  ```

  and the same exact predicate with M51 plain `else`.

- Extend those accepted typed semantics from `si32`/`ui32` to only:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Preserve M42/M48/M51 branch provenance, deterministic ordering, and
  selected-branch-only diagnostics.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.
- Preserve M45/M46 backend translation limits: M52 must not expand suffix or
  type-spelling translation beyond accepted selected `si32`/`ui32` behavior.

Boundary reminders for M52:

- M52 must express signed/unsigned companion behavior as typed rules or typed
  evaluator functions, not raw text rewriting.
- M52 must keep wildcard/group selectors such as `?i?`, `?i64`, `si?`, `ui?`,
  and `idqword` unsupported as selected concrete type tags during lowering.
- M52 must not add backend translation expansion, C++ or Rust rendering,
  generated output, generated test sources, CLI/reporting, writer behavior,
  compiler execution, generated-test execution, vector/register metadata,
  vector length/alignment, generic lengths, aliases, casts, arrays, loops,
  calls, direct `intrin<...>`, `switch<compile>`, `if<compile>`, generalized
  plain `else`, branch-body semantics, shift body parity, or conversion body
  parity.
- Evidence from shifts and conversions is type/signedness-helper evidence only.
- `frozen/` remains evidence only.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 51.
- Post-M51 planning accepted.
- Current action: run the Milestone 52 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m52-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 52: Concrete Integer Generation Type Semantics Slice`.
- The boundary reminders above.
- Non-blocking follow-ups remain recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m52-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M52.
