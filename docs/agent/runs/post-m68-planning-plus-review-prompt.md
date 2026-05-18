# Post-M68 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 68: Exact Array Initialization Base-Type Helper Request Resolution Slice
```

Milestones 1 through 68 are accepted. M68 returned
`Accept With Follow-Ups` after one focused documentation revision. Do not
implement code in this prompt, and do not start M69 execution.

For the next task, focus on lowering. Prefer candidates that make the staged
generation-time/body-lowering pipeline more useful, more maintainable, and
more extensible while preserving the no-hardwiring boundary.

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

Select exactly one next milestone candidate for post-M68 execution.

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
-> normal pipeline integration
-> exact first-slot form IR
-> exact helper request IR
-> exact base-type request resolution
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M68.
Potential directions include, but are not limited to:

- a maintainability slice that extracts the growing M64-M68
  array-initialization stage assembly tail into a typed helper/pipeline
  extension point without changing behavior;
- a small typed stage-contract hardening slice for future request-resolution
  stages, if it avoids a central semantic dispatcher and keeps stage output
  validation maintainable;
- a vector metadata request-resolution planning or implementation slice for
  exactly one of `value<generation>(vector::length)` or
  `value<generation>(vector::alignment)`, only if the selected metadata inputs
  and diagnostics can be defined without host CPU dependencies, catalog/file
  reads during lowering evaluation, or backend rendering;
- a typed resolver-family boundary that prepares future vector/backend helper
  request resolvers while consuming M67/M68 typed request records and avoiding
  raw helper-string dispatch;
- a backend-uninit request boundary, only if it stays as typed request/model
  planning and does not cross into renderer-ready text or generated output;
- a typed array-type/declaration boundary over the exact M66/M67/M68 first-slot
  IR, only if it does not become generic `var`, `array_type`, allocation, or
  lifetime semantics;
- a next exact slot-specific form-IR slice from the accepted M64/M65 envelope,
  while preserving all other slots as opaque provenance;
- a diagnostic or determinism hardening slice if it materially improves the
  typed lowering pipeline and has higher value than adding new semantics.

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

Do not select a milestone that combines broad statement lowering, helper
evaluation for multiple families, direct intrinsic semantics,
SVE predicate/vector/register semantics, broad vector metadata,
backend translation, rendering, output, generated tests, or compiler execution
in one step.

Unless explicitly selected as the one thin slice, keep these out of scope:

- broad assignment, variable, declaration, array, call, cast, loop, store,
  return, or multi-statement body lowering
- broad direct `intrin<...>` semantics
- SVE predicate, vector, or register semantics
- byte-size-to-`svptrue_b*` token inference
- broad vector metadata semantics
- broad `type<generation>(...)`, `value<generation>(...)`,
  `type<backend>(...)`, or `value<backend>(...)` evaluation
- backend uninit semantics
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

No-hardwiring remains a blocking planning boundary. Future request-resolution
milestones must consume typed request/result/context values and accepted typed
rules. They must not use ad-hoc tables or `if`/`elif` branches keyed by raw
helper text, selected type tags, or request ordinals directly to semantic
outputs. Source text may remain provenance/invariant evidence only.

If a helper-resolution candidate is selected, require it to consume typed M67
request/provenance IR and any accepted M68 typed resolution values needed by
the selected slice. It must resolve exactly the selected request family. It
must not reparse raw helper strings, bypass M67 through raw M66 slot text,
call raw query-string helper evaluators on M67 leaf text, create backend
translation requests, or feed renderers unless that exact boundary is selected
and justified as the one thin slice.

If a body-specific lowering candidate is selected, require it to consume typed
accepted stage outputs such as M68
`ExactArrayInitializationBaseTypeResolutionIr`, M67
`ExactArrayInitializationHelperRequestIr`, M66
`ExactArrayInitializationSlotFormIr`, or M65 `ExactArrayBodyEnvelopeIr`
values and to produce typed intermediate values. It must not produce
renderer-ready text or backend translation requests unless that exact boundary
is selected and justified as the one thin slice.

M66 exact slot text and M67 leaf text may remain local provenance only. They
must not become raw-text dispatchers, broad parsers, or sources of
backend-specific behavior.

Record continuing non-blocking follow-ups where appropriate:

- M67 review follow-up: consider tightening
  `ExactArrayInitializationHelperRequestRecord` model invariants so
  `request_kind` is validated against the expected leaf spec.
- M67 validation follow-up: strengthen bad-leaf diagnostic tests to assert
  exact path, line, column, and actionable message text.
- M65 validation follow-up: add an explicit determinism test for integrated
  typed skeleton input ordering if a nearby slice touches that behavior.
- M68 extensibility follow-up: before adding vector/backend helper resolver
  stages, consider extracting the M64-M68 `_lower_input` array-body stage
  assembly tail into a small typed array-initialization stage helper.
- M68 extensibility follow-up: `GenerationLoweringStage.__post_init__` remains
  a central stage-name-to-output-type table. It is type validation, not
  semantic dispatch, but it is a future maintainability pressure point.
- M68 extensibility follow-up: `_ExactArrayInitializationBaseTypeRequestRule`
  has an unused `result_kind`; remove it or let the typed rule drive the
  result-kind invariant before adding sibling vector/backend resolver rules.
- M68 documentation follow-up: consider adding
  `tsldata/primitives/load_store/array.tsl:105` to the general
  `type<generation>(base::in)` helper inventory in
  `docs/redesign/generation-time-semantic-lowering.md`.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   body-lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially helper evaluation,
   slot-specific lowering, direct-intrinsic/SVE/backend/rendering work,
   raw helper dispatch, and broad TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M68 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M68 wording remains.

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
docs/agent/runs/post-m68-acceptance-finalization-prompt.md
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
