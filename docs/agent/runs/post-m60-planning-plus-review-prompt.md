# Post-M60 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 60: Opaque Selected Branch Body Handoff Slice
```

Milestones 1 through 60 are accepted. M60 returned
`Accept With Follow-Ups` with no blocking implementation issues and no focused
revision. Do not implement code in this prompt.

The user asked that the next task focus on lowering. Prefer candidates that
advance the generation-time semantic lowering pipeline and keep it extendable
and maintainable.

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

Select exactly one next milestone candidate for post-M60 execution.

The selected candidate should advance the staged lowering direction:

```text
typed values -> typed predicates -> control-flow pruning -> selected-body handoff -> body-specific lowering
```

Compare narrow lowering-focused candidates that could reasonably follow M60.
Potential directions include, but are not limited to:

- an explicit typed selected-body form recognition boundary that keeps body
  semantics opaque unless a later stage owns them
- a first body-specific lowering slice for one documented selected body form
- another exact generation-time value or predicate helper that unlocks later
  body lowering
- a maintainability slice that makes the staged lowering pipeline easier to
  extend without broad dispatchers or raw-text evaluators

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

Do not select a milestone that combines multiple body-language areas or jumps
from opaque handoff directly to broad TSIL lowering.

Unless explicitly selected as the one thin slice, keep these out of scope:

- direct `intrin<...>` / SVE body lowering
- assignment, variable, array, call, cast, loop, or vector metadata lowering
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

If a body-specific lowering candidate is selected, keep it to exactly one
documented body form and require typed inputs/outputs suitable for future
stages. Do not select a milestone that turns M60 opaque body text into a broad
raw-text evaluator.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the recommended candidate keeps the
   staged lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially body-specific lowering
   versus broad TSIL parsing or backend/rendering work.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M55-M60 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M60 candidate wording remains.

After local planning updates, run read-only review subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary re-review: confirm the selected plan remains lowering-only and
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
docs/agent/runs/post-m60-acceptance-finalization-prompt.md
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
