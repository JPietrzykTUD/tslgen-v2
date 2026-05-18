# Post-M69 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 69: Exact Array Initialization Stage Pipeline Extraction Slice
```

Milestones 1 through 69 are accepted. M69 returned
`Accept With Follow-Ups` with no blocking implementation, validation,
boundary, extensibility, documentation, or evidence issues.

Do not implement code in this prompt, and do not start M70 execution.

For the next task, focus on lowering. Prefer candidates that use the extracted
M69 typed array-initialization stage pipeline boundary to move functionality
forward without hardwiring, raw helper dispatch, backend rendering, or
generated output.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
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

Select exactly one next milestone candidate for post-M69 execution.

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
-> exact array-initialization stage pipeline extraction
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M69.
Potential directions include, but are not limited to:

- vector length request resolution for exactly
  `value<generation>(vector::length)`, consuming typed M67/M69 request
  pipeline values and explicit accepted metadata inputs without host CPU
  dependencies or lowering-time file/catalog reads;
- vector alignment request resolution for exactly
  `value<generation>(vector::alignment)`, only if the selected metadata model,
  diagnostics, and no-hardwiring boundary can be stated as one thin slice;
- a typed vector metadata rule/input boundary needed before either vector
  request resolver, if direct resolution would otherwise require speculative
  metadata policy;
- backend uninit request modeling for exactly
  `value<backend>(uninit::array)`, only if it remains typed request/model
  lowering and does not produce renderer-ready text or generated output;
- exact array-initialization first-slot declaration or array-type typed IR,
  only if it consumes M66/M67/M68/M69 typed values and does not become broad
  `var`, `array_type`, allocation, lifetime, store, or return semantics;
- a focused diagnostic/determinism hardening slice if it materially improves
  the extracted lowering pipeline and has higher value than new semantics.

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

No-hardwiring remains a blocking planning boundary. Future request-resolution
milestones must consume typed request/result/context values and accepted typed
rules or explicit typed metadata inputs. They must not use ad-hoc tables or
`if`/`elif` branches keyed by raw helper text, selected type tags, request
ordinals, SVE tokens, backend ids, or renderer names directly to semantic
outputs. Source text may remain provenance/invariant evidence only.

If a vector metadata candidate is selected, it must explain where the vector
length or alignment facts come from as typed inputs before lowering evaluation.
It must not query host CPU features, read `tsldata`, read the catalog, parse
raw TSL, or infer broad SVE/register semantics during lowering evaluation.

If a helper-resolution candidate is selected, require it to consume typed M67
request/provenance IR and the extracted M69 stage pipeline boundary. It must
resolve exactly the selected request family. It must not reparse raw helper
strings, bypass M67 through raw M66 slot text, call raw query-string helper
evaluators on M67 leaf text, create backend translation requests, or feed
renderers.

If a body-specific lowering candidate is selected, require it to consume typed
accepted stage outputs such as M69 pipeline result values, M68
`ExactArrayInitializationBaseTypeResolutionIr`, M67
`ExactArrayInitializationHelperRequestIr`, M66
`ExactArrayInitializationSlotFormIr`, or M65 `ExactArrayBodyEnvelopeIr`
values and to produce typed intermediate values. It must not produce
renderer-ready text or backend translation requests.

Keep these out of scope unless they are explicitly selected as the one thin
slice:

- broad assignment, variable, declaration, array, call, cast, loop, store,
  return, or multi-statement body lowering
- broad direct `intrin<...>` semantics
- SVE predicate, vector, or register semantics
- byte-size-to-`svptrue_b*` token inference
- broad vector metadata semantics
- broad `type<generation>(...)`, `value<generation>(...)`,
  `type<backend>(...)`, or `value<backend>(...)` evaluation
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

Record continuing non-blocking follow-ups where appropriate:

- M67 review follow-up: consider tightening
  `ExactArrayInitializationHelperRequestRecord` model invariants so
  `request_kind` is validated against the expected leaf spec.
- M67 validation follow-up: strengthen bad-leaf diagnostic tests to assert
  exact path, line, column, and actionable message text.
- M68 extensibility follow-up: `GenerationLoweringStage.__post_init__`
  remains a central stage-name-to-output-type table. It is type validation,
  not semantic dispatch, but it remains a future maintainability pressure
  point.
- M68 extensibility follow-up:
  `_ExactArrayInitializationBaseTypeRequestRule.result_kind` remains unused;
  remove it or let the typed rule drive the result-kind invariant before
  adding sibling resolver rules.
- M69 validation follow-up: consider adding an explicit pipeline-level M67
  diagnostic propagation test if a future slice touches the extracted
  array-initialization stage pipeline.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially vector metadata policy,
   helper evaluation, direct-intrinsic/SVE/backend/rendering work, raw helper
   dispatch, and broad TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M69 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M69 wording remains.

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
docs/agent/runs/post-m69-acceptance-finalization-prompt.md
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
