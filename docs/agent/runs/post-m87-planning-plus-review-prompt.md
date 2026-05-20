# Post-M87 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 87: Exact Return-Emission Structural Request IR Slice
```

Milestones 1 through 87 are accepted. M87 execution-review returned
`Accept With Follow-Ups` after one focused maintainability revision.

Do not implement code in this prompt, and do not start Milestone 88 execution.

For the next task, focus on lowering. Prefer candidates that advance the typed
staged-lowering pipeline after the M87 exact return-emission structural/request
IR slice, especially a concrete semantic or structural lowering frontier that
can be expressed through typed requests, typed facts, and focused private stage
ownership. Do not select work that fixes `.tsl` implementation bodies, broadens
source syntax to guess intent, hardwires extension-specific tokens, adds raw
helper dispatch, backend translation, rendering, generated output, broad TSIL
parsing, broad registries, or speculative fixpoint/backfeed machinery.

## Accepted M87 Result

M87 preserves accepted M64-M86 behavior while:

- adding `ExactReturnEmissionStructuralRequestIr` for the exact trailing
  `emit_return(tmp);` structural/request slice;
- recognizing only `emit_return(<token>);` with insignificant whitespace and
  requiring the returned token to match the accepted M73 declaration-shell
  variable token as provenance only;
- consuming accepted M74 structural sequence provenance and accepted M76
  post-branch intrinsic call-site provenance as typed inputs;
- adding the deterministic
  `return_emission_structural_request_lowering` stage after the accepted M76
  post-branch call-site stage;
- keeping return-emission ownership in the focused private
  `tslgen.lowering._return_emission` module;
- preserving public facade imports, diagnostics, source locations, stage
  names/order, output identities, deterministic keys, selected-branch-only
  behavior, and pipeline snapshots;
- avoiding source-body repair, broad `emit_return(...)`, return/store/call/
  variable semantics, `tmp.data()` semantics, backend translation, rendering,
  generated output, broad TSIL parsing, raw helper dispatch, lowering-time
  file/catalog reads, `tsldata` reads during evaluation, backend map reads,
  host CPU queries, and runtime `frozen/` use.

M87 review recorded non-blocking follow-ups:

- Improve the returned-token mismatch diagnostic so it names the actual
  returned token and expected declaration token.
- Future exact array-body stages should split stage-specific source,
  validation, and diagnostic ownership instead of continuing to grow central
  exact array-body modules.
- Future import-boundary tests may prefix-match backend/rendering submodules
  and include `frozen` / `tsldata`.

The focused M87 revision removed a blocking extensibility issue: M87 output is
not part of the shared runtime `ExactArrayBodyLoweredImplementationSource`
protocol. `_return_emission.py` consumes direct M76 call-site values, the M76
stage output, or a private M76-only source protocol.

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
- `tsldata/primitives/load_store/array.tsl`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_return_emission.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M87 execution.

The selected candidate should advance lowering after:

```text
typed values
-> typed predicates
-> control-flow pruning
-> selected-body handoff/form/body IR/envelope
-> exact array-body envelope/helper/declaration/predicate/call-site/return path
-> composable lowering pipeline/module boundary
-> focused stage ownership
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M87.
Potential directions include, but are not limited to:

- exact whole-body structural package assembly that consumes accepted
  declaration, predicate-path, post-branch call-site, and return-emission typed
  requests into one source-ordered exact array-body structural package, without
  implementing declaration/store/return semantics or generated output;
- a focused stage-specific source/validation/diagnostic ownership split only
  if it unlocks the next semantic slice and does not become a pure line-count
  cleanup milestone;
- a typed deferred backend-value boundary refinement around the accepted
  `value<backend>(uninit::array)` request only if it remains request/fact
  lowering and does not translate backend text, query backend maps, or render
  output;
- a targeted return-emission diagnostic polish combined with a concrete
  lowering boundary improvement only if the combined slice is still thin and
  materially improves the next semantic frontier.

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
explicit typed metadata inputs. They must not use ad hoc tables or `if`/`elif`
branches keyed by raw helper text, selected type tags, request ordinals, SVE
tokens, backend ids, renderer names, corpus line numbers, or extension names
directly to semantic outputs. Source text may remain provenance/invariant
evidence only.

Lowering must not repair possibly wrong `.tsl` implementation bodies. If a
source body is malformed, unsupported, nearby, or ambiguous, the selected
milestone should produce structured diagnostics or leave it out of scope, not
correct, normalize, reorder, complete, or infer intended operands.

Future backfeeds must be typed facts, typed requests, dependencies, or
deterministic coordinator decisions. Do not select speculative fixpoint or
backfeed execution unless the milestone names one concrete typed need and
keeps it private, deterministic, and testable.

Keep files cohesive. If a selected slice would push a production file toward a
catch-all role or materially past the roughly 1,000-line guardrail, the plan
must either create focused private module ownership with one-way imports or
explain why a temporary exception is safer for that exact milestone.

Keep these out of scope unless explicitly selected as the one thin slice:

- broad assignment, variable, declaration, array, call, cast, loop, store,
  return, or multi-statement body lowering
- broad direct `intrin<...>` semantics
- SVE predicate, vector, memory, pointer, or register semantics
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

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers, catch-all
   modules, broad protocols, and premature fixpoint machinery.
3. Boundary auditor: identify scope risks, especially source-body repair,
   raw helper dispatch, broad body/call/store/return semantics, backend
   boundaries, circular imports, generic TSIL parsing, and hardwiring.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M87 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M87 wording remains.

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

## Required Finalization

Before finishing, update `docs/agent/current-redesign-state.md` and create the
next concrete run prompt under `docs/agent/runs/`, unless this prompt records a
stop condition.

For an accepted planning result that still needs human acceptance, create:

```text
docs/agent/runs/post-m87-acceptance-finalization-prompt.md
```

Do not create an M88 execution prompt until the selected post-M87 planning
result is explicitly accepted.

## Validation

Run:

```bash
git diff --check
```

If planning updates change only docs, do not run implementation tests unless
the planner explicitly justifies a documentation-triggered verification need.

## Final Report

Report:

1. Recommended next milestone and why it is highest value.
2. Internal review verdict and any follow-ups.
3. Files changed.
4. State transition made.
5. Next concrete prompt path created.
6. Validation command and exact result.
7. Whether the repo is waiting for human acceptance or ready for execution.
