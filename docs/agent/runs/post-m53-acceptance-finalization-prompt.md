# Post-M53 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M53 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M53 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M54 execution can be activated.

## Accepted Result

The post-M53 planning update selected:

```text
Milestone 54: Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups
```

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
- `docs/agent/runs/m54-execution-review-loop-prompt.md`

Create `docs/agent/runs/m54-execution-review-loop-prompt.md` as the next active
prompt. It must use the orchestrated executor-review loop pattern and include:

- exactly one write-capable executor if M54 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 55.

The M54 active prompt must constrain implementation to:

- Pipeline/lowering-input wiring only.
- Build or expose the accepted M53 `ConcreteIntegerGenerationRuleSet` from
  typed catalog/type-group data before lowering evaluation.
- Thread that immutable rule set through the normal lowering-input path, such
  as `GenerationContext` / `LoweringRequest` construction or a focused
  pipeline/API adapter.
- Preserve all accepted M52/M53 outputs for:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

  and exact M48/M51 signedness predicate branch pruning.

- Preserve exactly these selected concrete tags:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Prove explicit catalog-derived rule data is consumed by lowering and that
  missing or inconsistent explicit rule data is not hidden by a synthetic
  default fallback.
- Preserve M52/M53 diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless an explicit catalog-derived
  rule-source diagnostic is required for missing or inconsistent rule data.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.
- Preserve M45/M46 backend translation limits: M54 must not expand suffix or
  type-spelling translation beyond accepted selected `si32`/`ui32` behavior.

Boundary reminders for M54:

- M54 must not add new generation-time helper forms such as `type::size_bytes`.
- M54 must not infer broad integer semantics from regex or tag spelling alone.
- M54 must not treat wildcard/group selectors such as `?i?`, `?i64`, `si?`,
  `ui?`, `idqword`, `dword`, or `qword` as selected concrete type tags during
  lowering.
- M54 must not add backend translation expansion, C++ or Rust rendering,
  generated output, generated test sources, CLI/reporting, writer behavior,
  compiler execution, generated-test execution, vector/register metadata,
  vector length/alignment, generic lengths, aliases, casts, arrays, loops,
  calls, direct `intrin<...>`, `switch<compile>`, `if<compile>`, generalized
  plain `else`, branch-body semantics, broad TSIL parsing, or broad generic
  semantic-rule registries.
- Lowering must not read files, parse raw TSL, query the catalog during
  evaluation, or import/execute `frozen/`.
- `frozen/` remains evidence only.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 53.
- Post-M53 planning accepted.
- Current action: run the Milestone 54 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m54-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 54: Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice`.
- The boundary reminders above.
- Non-blocking follow-ups remain recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m54-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M54.
