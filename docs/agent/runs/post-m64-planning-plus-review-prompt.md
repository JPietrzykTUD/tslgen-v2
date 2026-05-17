# Post-M64 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 64: Exact Array Body Envelope Slot Assembly Slice
```

Milestones 1 through 64 are accepted. M64 returned
`Accept With Follow-Ups` after one focused revision. Do not implement code in
this prompt, and do not start M65 execution.

For the next task, focus on lowering. Prefer candidates that advance the
generation-time lowering pipeline from the accepted exact array-body envelope
toward maintainable, typed body-specific lowering while preserving staged
boundaries.

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
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Planning Target

Select exactly one next milestone candidate for post-M64 execution.

The selected candidate should advance the staged lowering direction:

```text
typed values
-> typed predicates
-> control-flow pruning
-> selected-body handoff
-> selected-body form recognition
-> unresolved selected-body IR
-> selected-body envelope
-> exact array-body slot envelope
-> body-specific lowering
```

Compare lowering-focused candidates that could reasonably follow M64.
Potential directions include, but are not limited to:

- a typed skeleton-producing or pipeline-integration slice that supplies the
  exact M64 array-body skeleton without broad TSIL parsing,
- a narrow slot-specific lowering slice that consumes
  `ExactArrayBodyEnvelopeIr` and refines exactly one opaque slot while keeping
  other slots opaque,
- a maintainability slice that wires the M64 envelope through the staged
  lowering pipeline without turning `lower_candidates` into a raw-text
  dispatcher,
- a nearby generation-time helper needed by the accepted array-body evidence,
  if it remains narrower and higher value than slot-specific body lowering,
- a diagnostic or boundary hardening slice that materially improves the typed
  lowering pipeline and is higher value than new semantics.

Treat all candidates as candidates, not as preaccepted. The planning result
must define:

- milestone title and number
- goal
- scope
- out-of-scope items
- required inputs from accepted milestones
- expected typed outputs
- validation criteria
- tests required
- evidence paths
- review risks
- next concrete prompt path

## Boundary Rules

The next milestone must remain one thin architectural slice.

Do not select a milestone that combines broad statement lowering, direct
intrinsic semantics, SVE predicate/vector semantics, vector metadata, backend
translation, rendering, output, generated tests, or compiler execution in one
step.

Unless explicitly selected as the one thin slice, keep these out of scope:

- broad assignment, variable, declaration, array, call, cast, loop, store,
  return, or multi-statement body lowering
- broad direct `intrin<...>` semantics
- SVE predicate, vector, or register semantics
- byte-size-to-`svptrue_b*` token inference
- `value<generation>(vector::length)` or
  `value<generation>(vector::alignment)`
- backend uninit values
- backend translation expansion
- rendering or generated output
- generated tests
- CLI/reporting/writer behavior
- Rust
- compiler execution
- broad TSIL parsing
- runtime dependency on `frozen/`
- lowering-time file reads, raw TSL parsing, or catalog queries during
  evaluation

If a body-specific lowering candidate is selected, require it to consume typed
accepted stage outputs such as M64 `ExactArrayBodyEnvelopeIr` values and to
produce typed intermediate values, not renderer-ready text or backend
translation requests unless that exact boundary is selected and justified.

SVE-looking corpus text may be used as evidence only. It must not become
architecture, semantic dispatch, or backend-specific lowering logic.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   body-lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially slot-specific lowering
   versus direct-intrinsic/SVE/backend/rendering work.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M64 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M64 wording remains.

After local planning updates, run read-only review subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary re-review: confirm the selected plan remains one thin slice and
   does not start implementation.
3. Documentation re-review: confirm docs and workflow state match the selected
   planning result.

If review returns `Needs Revision`, perform only focused
documentation/planning revisions and run focused re-review. Do not implement
product code.

If review returns `Return To Planner` or `Reject`, stop and create the
appropriate next planning or rollback prompt under `docs/agent/runs/`.

## Required Repository Updates

Update planning documentation only as needed, usually:

- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

Before finishing, update `docs/agent/current-redesign-state.md` and create the
next concrete prompt under `docs/agent/runs/`.

If the planning result is internally accepted and needs human acceptance before
execution, create:

```text
docs/agent/runs/post-m64-acceptance-finalization-prompt.md
```

That finalization prompt should convert human acceptance into the selected
milestone execution-review loop prompt. Do not start execution here.

## Validation

Run:

```bash
git diff --check
```

If the planning pass changes only a subset of docs, include any narrower
diff-check command that was useful, but the final validation must include the
full `git diff --check`.

## Final Report

Report:

1. Planning and review subagents used.
2. Selected milestone and why it advances lowering.
3. Files changed.
4. Consolidated planning review verdict.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. State transition made.
8. Validation command and exact result.
9. Whether the repo is ready for the next action.
