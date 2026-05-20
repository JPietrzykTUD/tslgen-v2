# Post-M88 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 88: Exact Array Body Structural Package Assembly Slice
```

Milestones 1 through 88 are accepted. M88 execution-review returned
`Accept With Follow-Ups` after one focused extensibility revision.

Do not implement code in this prompt, and do not start Milestone 89 execution.

For the next task, focus on lowering. Prefer candidates that make a meaningful
step forward from the accepted M88 typed structural package while keeping the
pipeline composable, typed, and maintainable. The next milestone must not fix
`.tsl` implementation bodies, infer intended source meaning, hardwire
extension-specific tokens, add raw helper dispatch, backend translation,
rendering, generated output, broad TSIL parsing, broad registries, or
speculative fixpoint/backfeed machinery.

## Accepted M88 Result

M88 preserves accepted M64-M87 behavior while:

- adding focused `tslgen.lowering._array_body_package` ownership for exact
  array-body package assembly, package members, package source selection, and
  package diagnostics;
- adding `ExactArrayBodyStructuralPackageIr` as one source-ordered typed
  structural package over accepted M64-M87 exact array-body facts;
- preserving member object identity/provenance instead of copying or
  normalizing facts into semantic body nodes;
- adding the deterministic `array_body_structural_package_assembly` stage
  after `return_emission_structural_request_lowering`;
- validating candidate id, target extension, source extension, selected type
  tag, branch-chain id, source sequence identity, source order, member
  presence, and provenance consistency;
- diagnosing missing, duplicate, malformed, mismatched, out-of-order, and
  provenance-inconsistent facts;
- treating protocol-shaped `return_emission_structural_requests` entries as
  untrusted runtime data and diagnosing malformed entries instead of raising;
- preserving public facade imports, diagnostics, source locations, stage
  names/order, output identities, deterministic keys, selected-branch-only
  behavior, and pipeline snapshots;
- avoiding source-body repair, semantic body lowering, declaration/store/
  return/SVE/backend semantics, renderer-ready IR, rendering, generated output,
  broad TSIL parsing, raw helper dispatch, lowering-time file/catalog reads,
  `tsldata` reads during evaluation, backend map reads, host CPU queries,
  hidden backfeeds, and runtime `frozen/` use.

M88 review recorded non-blocking follow-ups:

- `_array_body_pipeline.py` and `boundary.py` remain near or over the preferred
  line-count comfort zone and should not be allowed to drift back into catch-
  all ownership.
- The large lowering unit test file should eventually be split by stage/module.
- Future protocol-shaped intake must keep treating runtime entries as
  untrusted data until their typed payload is validated.

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
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_return_emission.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M88 execution.

The selected candidate should advance lowering after:

```text
typed values
-> typed predicates
-> control-flow pruning
-> selected-body handoff/form/body IR/envelope
-> exact array-body envelope/helper/declaration/predicate/call-site/return path
-> composable lowering pipeline/module boundary
-> exact structural package handoff
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M88.
Potential directions include, but are not limited to:

- a typed deferred backend-value boundary refinement around the accepted
  `value<backend>(uninit::array)` request, if it remains request/fact lowering
  and does not translate backend text, query backend maps, or render output;
- a typed package-consumer boundary that lets future stages consume the M88
  package through one focused input contract without broad protocols,
  registries, callback dispatch, or fixpoint machinery;
- the next exact structural lowering slice over the packaged body, if it
  recognizes one documented structural request without implementing body
  semantics, repairing source text, or hardwiring extension-specific tokens;
- a focused stage-specific source/validation/diagnostic ownership split only
  if it unlocks the next semantic slice and does not become pure line-count
  cleanup.

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

Future package consumers must treat runtime/protocol-shaped intake as
untrusted until the concrete typed payload is validated. Do not use broad
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
   supported by accepted M57-M88 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale post-M88 handoff wording remains.

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
docs/agent/runs/post-m88-acceptance-finalization-prompt.md
```

Do not create an M89 execution prompt until the selected post-M88 planning
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
