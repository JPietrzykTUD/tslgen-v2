# Post-M99 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M99 planning update.

Do not implement code.

## Accepted Result

The post-M99 planning update selected:

```text
Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

The follow-ups are non-blocking execution guardrails:

- M100 must consume explicit typed C++ `value_array_uninit` rule/metadata input;
  it must not read backend maps/catalogs/manifests or `tsldata/detail/lang`
  during lowering.
- M100 must produce typed backend value translation-result state only; it must
  not produce renderer-ready IR, declaration/body IR, generated C++ or Rust
  output, artifact plans, Stage 9 backend planning, scheduling, dependency
  closure, or generic backend helper evaluation.
- M100 must reject or defer non-exact-array M99 request records, including
  `selected_body_direct_intrinsic_handoff`, and must not infer direct-
  intrinsic/SVE semantics.
- M100 must use focused module ownership and avoid growing `boundary.py`, M99
  request-inventory modules, existing near-guardrail backend translation
  modules, or broad lowering tests into replacement monoliths.

## Task

Update repository workflow state so the next action is M100 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`
- `docs/agent/runs/m100-execution-review-loop-prompt.md`

`docs/agent/current-redesign-state.md` should state:

- Accepted through: Milestone 99.
- Post-M99 planning accepted.
- Current action: execute Milestone 100.
- Active executor milestone:
  `Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice`.
- Active run prompt:
  `docs/agent/runs/m100-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M100 consumes accepted M99 `exact_array_backend_value_uninit_array`
    request inventory records only.
  - M100 consumes explicit typed C++ `value_array_uninit` rule/metadata input.
  - M100 must not read backend maps/catalogs/manifests or `tsldata/detail/lang`
    during lowering.
  - M100 produces typed backend value translation-result state only.
  - No Rust, generic backend helper evaluation, selected-body direct-intrinsic/
    SVE semantics, renderer-ready IR, rendering, generated output, Stage 9
    backend planning, operation scheduling, dependency closure, CLI/report/
    writer, compiler execution, raw source parsing, source repair, hidden
    backfeeds, or fixpoint work is in M100.

Create the M100 execution-review-loop prompt under
`docs/agent/runs/m100-execution-review-loop-prompt.md`.

The M100 prompt must specify:

- one write-capable executor;
- read-only reviewer, boundary auditor, extensibility auditor, validation
  auditor, and documentation auditor;
- focused revision-loop rules for `Needs Revision`;
- stop rules for `Return To Planner` or `Reject`;
- next-prompt generation on `Accept` or `Accept With Follow-Ups`;
- required validation from the M100 roadmap section.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check
```

If other docs are changed, include them in the diff-check by running the same
repository-wide command.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Next concrete run prompt created.
5. Validation command and exact result.
6. Whether the repo is ready to execute M100.
