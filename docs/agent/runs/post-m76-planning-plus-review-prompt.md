# Post-M76 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 76: Exact Post-Branch Intrinsic Call-Site Structural Request IR Slice
```

Milestones 1 through 76 are accepted. M76 returned
`Accept With Follow-Ups` after one focused documentation revision. Review and
audit found no blocking implementation, validation, boundary, extensibility,
documentation, or evidence issues after that revision.

Do not implement code in this prompt, and do not start Milestone 77 execution.

For the next task, focus on lowering. Prefer candidates that continue the
typed, staged exact array-body / array-initialization lowering pipeline and
move functionality forward without hardwiring, raw helper dispatch, backend
translation, rendering, generated output, broad declaration/array semantics,
broad call/store/return semantics, or broad body-slot semantics.

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

Select exactly one next milestone candidate for post-M76 execution.

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
-> exact vector-length request resolution
-> exact vector-alignment request resolution
-> exact helper-set completion
-> exact first-slot declaration-shell structural IR
-> exact array-body structural sequence and slot-role classification
-> exact predicate-path structural/request IR
-> exact post-branch intrinsic call-site structural/request IR
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M76.
Potential directions include, but are not limited to:

- exact return-emission structural/request refinement that consumes accepted
  M76/M75/M74 state and records only the exact `emit_return(tmp)` path without
  return semantics, variable scope/lifetime, renderer-ready IR, or output;
- exact post-branch call-site argument/provenance refinement only if it remains
  structural/provenance-only and does not interpret `svst1`, `tmp.data()`,
  `a`, memory behavior, alignment behavior, store semantics, backend maps,
  rendering, or generated output;
- exact backend-uninit deferred-value handoff refinement that consumes the
  accepted M72/M73 path and remains an unresolved typed backend-value boundary,
  without backend translation or renderer text;
- focused private maintainability cleanup of the repeated exact resolver,
  source-adapter, provenance, diagnostic, or stage-output validation pattern,
  only if it is driven by concrete M68-M76 pressure and does not create a
  broad registry, central dispatcher, raw-helper evaluator, general call/body
  parser, or public IR surface beyond genuinely consumed typed boundary
  values;
- focused typed handoff from M76 call-site state to a later lowering boundary,
  only if it does not define variable scope, use-def analysis, allocation/
  lifetime, statement execution semantics, store semantics, return semantics,
  backend behavior, or generic body IR.

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

No-hardwiring remains a blocking planning boundary. Future lowering milestones
must consume typed request/result/context values and accepted typed rules or
explicit typed metadata inputs. They must not use ad-hoc tables or `if`/`elif`
branches keyed by raw helper text, selected type tags, request ordinals, SVE
tokens, backend ids, renderer names, or corpus line numbers directly to
semantic outputs. Source text may remain provenance/invariant evidence only.

If an array-body or array-initialization structural/request IR candidate is
selected, it must consume accepted typed inputs such as M76 call-site IR, M75
predicate-path IR, M74 structural sequence IR, M73 declaration-shell IR, M72
helper-set completions, M71 vector-alignment resolutions, M70 vector-length
resolutions, M68 base-type resolutions, M67 helper requests, M66 slot forms,
M65 envelope values, M64 slot-envelope values, or M63 selected-body envelope
values. It must produce typed intermediate values only. It must not produce
backend text, backend translation requests, renderer-ready IR, generated
output, generic declaration semantics, generic array semantics, generic body
semantics, allocation/lifetime semantics, initializer semantics, variable
scope semantics, stores, returns, `tmp.data()` semantics, `emit_return`
semantics, `assume_aligned`, or broad `var` / `array_type` / call parsing.

If a return-emission-shaped candidate is selected, it must stay structural/
request only. It may record exact tokens and provenance already carried through
M74/M75/M76, but it must not interpret `emit_return`, `tmp`, return value
semantics, variable lifetime, renderer-ready return IR, or generated output.

If a call-site or store-call-shaped candidate is selected, it must stay
structural/request only. It may record exact tokens and provenance already
carried through M76, but it must not interpret `svst1`, `pg`, `tmp.data()`,
`a`, memory behavior, alignment behavior, backend intrinsic semantics, or
renderer-ready output.

If a backend-uninit candidate is selected, the result must remain an unresolved
typed policy, typed deferred backend-value boundary, or explicit unsupported
diagnostic. It must not translate `value<backend>(uninit::array)` into
C++/Rust/backend text, create renderer-ready text, query backend maps, or make
backend translation/rendering part of lowering.

If a maintainability cleanup is selected, it must be private, typed, and
anchored to the exact accepted M68-M76 pattern. It must not add a broad stage
registry, generic helper-set registry, raw-helper parser, raw query evaluator,
slot-role registry, generic call parser, generic body parser, semantic
dispatcher, or public IR surface beyond genuinely consumed typed boundary
values.

Keep these out of scope unless they are explicitly selected as the one thin
slice:

- broad assignment, variable, declaration, array, call, cast, loop, store,
  return, or multi-statement body lowering
- broad direct `intrin<...>` semantics
- SVE predicate, vector, or register semantics
- byte-size-to-`svptrue_b*` token inference
- `tmp.data()`, `emit_return`, `assume_aligned`, aligned store semantics, or
  generated return semantics
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
- M68 extensibility follow-up:
  `_ExactArrayInitializationBaseTypeRequestRule.result_kind` remains unused;
  remove it or let the typed rule drive the result-kind invariant before
  adding sibling resolver rules.
- M69 review follow-up: consider adding explicit pipeline-level M67
  diagnostic propagation tests when future slices touch the extracted
  array-initialization stage pipeline.
- M71 validation follow-up: consider a broader pipeline-level guard against
  catalog reads, `tsldata` reads, and host CPU queries.
- M71 public-boundary follow-up: keep future `tslgen.lowering.__all__`
  additions limited to genuinely consumed typed boundary values.
- M72 review follow-up: the generic unsupported-source diagnostic for
  `lower_exact_array_initialization_helper_set_completion` omits the accepted
  `LoweredImplementation` source form from final fallback wording.
- M72 extensibility follow-up: `GenerationLoweringStage.__post_init__`
  remains a central stage-name-to-output-type validation table. It is not
  semantic dispatch, but it is a growing maintainability pressure point.
- M74 review follow-up: the public sequence currently carries a private
  `_ExactArrayBodyStructuralRole` tuple internally. Future consumers should
  keep that role detail internal or deliberately promote one exact role value;
  do not let it grow into per-role public tuples, a slot-role registry, broad
  body IR, or semantic dispatcher.
- M75 review follow-up: consider hardening
  `ExactPredicatePathStructuralRequestIr` constructor invariants so direct
  construction cannot represent non-exact predicate/update/store token facts
  that the resolver path rejects.
- M75 documentation follow-up: refresh the behavioral-spec TSIL semantic/
  lowering parity table to include M73, M74, and M75, and clean up
  post-acceptance planned/selected wording in the redesign docs.
- M75 validation follow-up: strengthen remaining M75 diagnostic tests with
  exact path, line, column, and actionable message assertions where practical.
- M76 extensibility follow-up: `GenerationLoweringStage.__post_init__` remains
  a central stage-name-to-output-type validation table and is growing with each
  exact Stage 8 slice. Before several more exact lowering stages land, plan a
  small cleanup that preserves typed stage-specific attachment points without
  turning into a broad registry or dispatcher.
- M76 extensibility follow-up: keep future exact-shape recognizers slice-local.
  M76's comma-split parser is accepted only for the exact
  `intrin<svst1>(pg, tmp.data(), a);` shape and must not become a general
  call/body parser.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially M76-to-next-body-slot
   boundaries, backend-uninit/backend boundaries, raw helper dispatch, broad
   declaration/array/body lowering, variable/allocation/store/return
   semantics, generic call parsing, and broad TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M76 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M76 wording remains.

After local planning updates, run read-only review subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary re-review: confirm the selected plan remains one thin slice and
   does not start implementation.
3. Documentation re-review: confirm docs and workflow state match the selected
   planning result.

If review returns `Needs Revision`, perform only focused documentation/planning
revisions and run focused re-review. Do not implement product code.

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
docs/agent/runs/post-m76-acceptance-finalization-prompt.md
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
