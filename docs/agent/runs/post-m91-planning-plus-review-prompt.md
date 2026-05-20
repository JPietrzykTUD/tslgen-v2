# Post-M91 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 91: Stage 8 Exact Array Pipeline Ownership Consolidation Slice
```

Milestones 1 through 91 are accepted. M91 execution-review returned
`Accept With Follow-Ups`.

Do not implement code in this prompt, and do not start Milestone 92 execution.

For the next task, focus on lowering. Prefer candidates that make meaningful
progress from the accepted M91 Stage 8 exact array pipeline ownership
consolidation while keeping the pipeline composable, typed, maintainable, and
honest about unresolved backend/body semantics. The next milestone must not
fix `.tsl` implementation bodies, infer intended source meaning, hardwire
extension-specific tokens, add raw helper dispatch, backend translation,
rendering, generated output, broad TSIL parsing, broad registries, or
speculative fixpoint/backfeed machinery.

## Accepted M91 Result

M91 preserves accepted M64-M90 behavior while:

- adding focused `tslgen.lowering._array_body_pipeline_results` ownership for
  the exact array pipeline result DTO/key behavior;
- adding focused `tslgen.lowering._array_body_stage_assembly` ownership for
  exact stage construction, result assembly, and pipeline snapshot assembly;
- keeping `tslgen.lowering._array_body_pipeline` as orchestration over
  accepted lowerers and focused assembly helpers;
- preserving accepted diagnostics, source locations, public imports, stage
  names/order, artifact kinds, deterministic keys, output identities,
  selected-branch-only behavior, no-external-input boundaries, and pipeline
  snapshots;
- reducing `_array_body_pipeline.py` from 1,043 to 591 physical lines;
- avoiding new lowering semantics, backend planning, backend maps, rendering,
  generated output, broad TSIL parsing, source-body repair, broad protocols,
  hidden backfeeds, fixpoint machinery, and hardwiring.

M91 review recorded one non-blocking follow-up:

- `boundary.py` remains a 1,226-line broad compatibility facade. M91 did not
  grow it, but future lowering milestones should continue avoiding new
  ownership there and should prefer focused private modules with one-way
  imports.

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
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M91 execution.

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
-> exact lowering completion package handoff
-> behavior-preserving exact pipeline ownership consolidation
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M91.
Potential directions include, but are not limited to:

- a focused completion-package consumer boundary that lets later lowering work
  consume M90/M91 handoff facts without reaching across pipeline internals, if
  it produces one concrete typed output rather than wrapper-only abstraction;
- typed unresolved-dependency classification on the lowering side only, if it
  remains request/provenance data and does not read backend maps, translate
  backend text, create Stage 9 plans, or render output;
- the next exact lowering slice over a documented nearby body/request shape,
  if it consumes accepted typed facts without repairing source text, inferring
  body semantics, hardwiring extension-specific tokens, or broadening to
  generic TSIL parsing;
- a behavior-preserving extraction only if it directly protects the next
  lowering slice from catch-all growth and materially improves ownership.

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

Future package/completion consumers must treat runtime/protocol-shaped intake
as untrusted until concrete typed payloads are validated. Do not use broad
runtime protocols to smuggle later-stage facts into earlier-stage helpers.

Future unresolved dependencies are typed facts only unless a later accepted
milestone explicitly starts backend planning. Do not select backend maps,
Stage 9 planning, renderer-ready IR, rendering, or generated output from this
prompt unless the planning review deliberately returns to the roadmap and
records the phase boundary change.

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
   supported by accepted M57-M91 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale post-M91 handoff wording remains.

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
docs/agent/runs/post-m91-acceptance-finalization-prompt.md
```

Do not create an M92 execution prompt until the selected post-M91 planning
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
