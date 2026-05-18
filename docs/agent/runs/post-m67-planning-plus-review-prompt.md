# Post-M67 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 67: Exact Array Initialization Helper Request IR Slice
```

Milestones 1 through 67 are accepted. M67 returned
`Accept With Follow-Ups` after one focused documentation revision. Do not
implement code in this prompt, and do not start M68 execution.

For the next task, focus on lowering. Prefer candidates that make the staged
generation-time/body-lowering pipeline more useful while staying typed,
maintainable, and narrow.

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

Select exactly one next milestone candidate for post-M67 execution.

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
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M67.
Potential directions include, but are not limited to:

- a narrow helper-resolution slice that consumes M67 request/provenance IR and
  resolves exactly one accepted helper family without broad expression
  evaluation,
- a generation type request-resolution slice that consumes the M67
  `type<generation>(base::in)` request while preserving the no-rendering and
  no-backend-translation boundary,
- a vector metadata request boundary or value-resolution slice for exactly one
  of `value<generation>(vector::length)` or
  `value<generation>(vector::alignment)`, if evidence and metadata policy are
  sufficiently clear,
- a typed array-type or declaration form boundary that remains over the M66/M67
  exact first-slot form/request IR and does not become generic `var` or
  `array_type` parsing,
- a next exact slot-specific form-IR slice from the accepted M64/M65 envelope,
  while preserving all other slots as opaque provenance,
- a maintainability slice that strengthens multi-pass/staged body-lowering
  extension points after M67 without adding a central raw-string dispatcher,
- a diagnostic or determinism hardening slice if it materially improves the
  typed lowering pipeline and is higher value than adding new semantics.

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
evaluation for multiple families, direct intrinsic semantics, SVE
predicate/vector semantics, broad vector metadata, backend translation,
rendering, output, generated tests, or compiler execution in one step.

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

If a helper-resolution candidate is selected, require it to consume typed M67
request/provenance IR and to resolve exactly the selected request family. It
must not reparse raw helper strings, bypass M67 through raw M66 slot text,
create backend translation requests, or feed renderers unless that exact
boundary is selected and justified as the one thin slice.

If a body-specific lowering candidate is selected, require it to consume typed
accepted stage outputs such as M67 `ExactArrayInitializationHelperRequestIr`,
M66 `ExactArrayInitializationSlotFormIr`, or M65
`ExactArrayBodyEnvelopeIr` values and to produce typed intermediate values.
It must not produce renderer-ready text or backend translation requests unless
that exact boundary is selected and justified as the one thin slice.

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
- M64 evidence follow-up: consider adding a small fixture comment tying
  inlined opaque array-body snippets to `array.tsl:105-111` if the next slice
  reuses those snippets.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   body-lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially helper evaluation,
   slot-specific lowering, direct-intrinsic/SVE/backend/rendering work, and
   broad TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M67 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M67 wording remains.

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
docs/agent/runs/post-m67-acceptance-finalization-prompt.md
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
