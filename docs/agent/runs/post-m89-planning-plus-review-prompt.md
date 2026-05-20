# Post-M89 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 89: Exact Array Backend-Deferred Request Inventory Slice
```

Milestones 1 through 89 are accepted. M89 execution-review returned
`Accept With Follow-Ups` with no blocking issues and no focused revision.

Do not implement code in this prompt, and do not start Milestone 90 execution.

For the next task, focus on lowering. Prefer candidates that make a meaningful
step forward from the accepted M88 structural package and M89 backend-deferred
request inventory while keeping the pipeline composable, typed, and
maintainable. The next milestone must not fix `.tsl` implementation bodies,
infer intended source meaning, hardwire extension-specific tokens, add raw
helper dispatch, backend translation, rendering, generated output, broad TSIL
parsing, broad registries, or speculative fixpoint/backfeed machinery.

## Accepted M89 Result

M89 preserves accepted M64-M88 behavior while:

- adding focused `tslgen.lowering._array_body_backend_deferred_requests`
  ownership for exact array backend-deferred request inventory assembly, source
  selection, validation, and diagnostics;
- adding `ExactArrayBackendDeferredRequestInventoryIr` and
  `ExactArrayBackendDeferredRequestInventoryMemberIr`;
- producing exactly one inventory member for the accepted
  `value_backend_uninit_array` deferred backend-value fact;
- preserving object identity/provenance for the accepted M88 package, M73
  declaration shell, M72 deferred backend-uninit value, and M67 backend-value
  request record;
- adding the deterministic `array_backend_deferred_request_inventory` stage
  after `array_body_structural_package_assembly`;
- diagnosing unsupported, missing, duplicate, malformed, context-mismatched,
  wrong-policy, wrong-request, wrong-source-text, source-location,
  slot/variable, and provenance-mismatched inputs;
- avoiding backend-uninit resolution, backend maps, backend translation,
  Stage 9 backend planning, renderer-ready IR, rendering, generated output,
  generic backend-value evaluation, source-body repair, broad protocols,
  hidden backfeeds, and runtime `frozen/` use.

M89 review recorded non-blocking follow-ups:

- `boundary.py` is over the rough production-file guardrail, and
  `_array_body_pipeline.py` is essentially at it. Future lowering work should
  avoid adding more responsibility to either without focused extraction or a
  documented temporary exception.
- `_array_body_models.py` remains a pre-existing large model module.
- `_array_body_backend_deferred_requests.py` is acceptable for M89 but must not
  become a generic backend-request catch-all; split source adaptation,
  validation, and diagnostics if backend-deferred work grows.
- Optional test hardening: add explicit target/source extension mismatch cases
  for M89-style context validation if a later adjacent slice touches this
  surface.

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
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M89 execution.

The selected candidate should advance lowering after:

```text
typed values
-> typed predicates
-> control-flow pruning
-> selected-body handoff/form/body IR/envelope
-> exact array-body envelope/helper/declaration/predicate/call-site/return path
-> composable lowering pipeline/module boundary
-> exact structural package handoff
-> exact backend-deferred request inventory
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M89.
Potential directions include, but are not limited to:

- a focused package/inventory consumer boundary that lets later stages consume
  M88/M89 facts without reaching across many pipeline outputs, if it produces
  one concrete typed output rather than a wrapper-only abstraction;
- the next exact structural lowering slice over the packaged body, if it
  recognizes one documented structural request without implementing body
  semantics, repairing source text, hardwiring extension-specific tokens, or
  broadening to generic TSIL parsing;
- a focused module split for `_array_body_pipeline.py` or the lowering facade
  only if it unlocks the next lowering slice and does not become pure line-
  count cleanup;
- an explicit typed boundary preparing for backend planning only if it remains
  a lowering-side request/inventory handoff and does not read backend maps,
  translate backend text, create Stage 9 plans, or render output.

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

Future package/inventory consumers must treat runtime/protocol-shaped intake
as untrusted until the concrete typed payload is validated. Do not use broad
runtime protocols to smuggle later-stage facts into earlier-stage helpers.

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
- backend translation expansion or backend map reads
- Stage 9 backend planning
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
   supported by accepted M57-M89 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale post-M89 handoff wording remains.

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
docs/agent/runs/post-m89-acceptance-finalization-prompt.md
```

Do not create an M90 execution prompt until the selected post-M89 planning
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
