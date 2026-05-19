# Post-M83 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 83: GenerationLoweringStage Output Contract Extraction Slice
```

Milestones 1 through 83 are accepted. M83 execution-review returned
`Accept With Follow-Ups`.

Do not implement code in this prompt, and do not start Milestone 84 execution.

For the next task, focus on lowering. Prefer candidates that continue the typed
staged-lowering direction, use the M83 private stage-contract boundary rather
than growing `boundary.py`, and improve maintainability or semantic coverage
without hardwiring, raw helper dispatch, backend translation, rendering,
generated output, broad declaration/array/body/call/store/return semantics,
broad TSIL parsing, broad registries, or extension-specific semantic shortcuts.

## Accepted M83 Result

M83 preserved accepted M42-M82 behavior while:

- creating `tslgen.lowering._stage_contracts` as the private stage-contract
  owner;
- moving `GenerationLoweringStageName`, `GenerationLoweringStageOutput`, typed
  `GenerationLoweringStageOutputContract` records, the stage-output validator,
  `GenerationLoweringStage`, and the minimal accepted mini-TSIL statement
  value-model dependency out of `boundary.py`;
- keeping source adapters, stage construction helpers, `LoweredImplementation`,
  `LoweringInput`, `LoweringRequest`, lower-candidate orchestration, and the
  public facade in `boundary.py`;
- preserving public imports through `tslgen.lowering` and
  `tslgen.lowering.boundary`;
- keeping private lowering modules, including `_stage_contracts.py`, from
  importing `boundary.py` or the `tslgen.lowering` package facade;
- preserving stage names/order, output identities, deterministic keys,
  pipeline snapshots, diagnostics, and invalid-stage/output exception behavior;
- reducing `boundary.py` from the accepted M82 4,965-line baseline to 4,807
  physical lines;
- adding focused M83 ownership/import-boundary and stage/output-contract tests
  while preserving the full lowering-boundary suite.

M83 review recorded one non-blocking follow-up:

- Package-level alias coverage is unchanged. `tslgen.lowering.boundary`
  exposes `GenerationLoweringStageName` and `GenerationLoweringStageOutput`,
  while `tslgen.lowering` does not expose those aliases. A future
  public-surface cleanup may either document those aliases as boundary-only or
  explicitly export/test them from `tslgen.lowering`.

Continuing follow-ups remain relevant:

- The focused M81 selector is mostly ownership/import coverage. A future
  cleanup may broaden the focused command or add a small M81-tagged diagnostic
  source-location preservation check.
- `boundary.py` still repeats `_context_for_candidate(item, request)` and
  selected-type-tag expressions across the exact-array pipeline call sequence.
  A future cleanup may hoist those facade-local values for readability.
- `_pipeline.py` still carries `object` payloads for stage/value references.
- Exact return-emission structural/request IR remains a high-value lowering
  candidate now that M77-M83 have reduced the main boundary and extracted the
  stage contract.

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
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_selected_body_models.py`
- `tslgen/src/tslgen/lowering/_generation_models.py`
- `tslgen/src/tslgen/lowering/_generation_queries.py`
- `tslgen/src/tslgen/lowering/_generation_control_flow.py`
- `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M83 execution.

The selected candidate should advance lowering after:

```text
typed values
-> typed predicates
-> control-flow pruning
-> selected-body handoff
-> selected-body form recognition
-> unresolved selected-body IR
-> selected-body envelope
-> exact array-body slot envelope
-> exact first-slot helper/request/resolution path
-> exact array-body structural/request path through post-branch call site
-> composable lowering pipeline/module boundary
-> lowering boundary package/model/validation decomposition
-> generation-time lowering core ownership extraction
-> selected-body model ownership extraction
-> stage-contract ownership extraction
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M83.
Potential directions include, but are not limited to:

- exact return-emission structural/request IR that consumes accepted M74-M83
  state and records only the exact `emit_return(tmp)` path, without return
  semantics, variable scope/lifetime, renderer-ready IR, or output;
- a focused exact-array pipeline readability/typed-boundary cleanup that
  hoists repeated facade-local context/type-tag calculations or tightens
  `_pipeline.py` payload contracts without creating a dispatcher, registry, or
  fixpoint engine;
- a focused public-surface cleanup for stage aliases only if the planner finds
  it materially improves the next lowering slice and does not broaden the
  public API accidentally;
- a small testing/boundary-hardening slice only if it materially protects the
  next lowering refactor or semantic slice and is not merely test churn.

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

M83's private `_stage_contracts.py` module is an accepted lowering internal,
not a public API commitment or permission for broad stage dispatch. Future
milestones may consume it only through typed local contracts and must preserve
public `tslgen.lowering` imports unless a public API change is explicitly
selected.

No-hardwiring remains a blocking planning boundary. Future lowering
milestones must consume typed request/result/context values and accepted typed
rules or explicit typed metadata inputs. They must not use ad hoc tables or
`if`/`elif` branches keyed by raw helper text, selected type tags, request
ordinals, SVE tokens, backend ids, renderer names, or corpus line numbers
directly to semantic outputs. Source text may remain provenance/invariant
evidence only.

Future backfeeds must be typed facts, typed requests, dependencies, or
deterministic coordinator decisions. Do not select speculative fixpoint or
backfeed execution unless the milestone names one concrete typed need and
keeps it private and deterministic.

If a return-emission-shaped candidate is selected, it must stay structural /
request only. It may record exact tokens and provenance already carried
through M74-M83, but it must not interpret `emit_return`, `tmp`, return value
semantics, variable lifetime, renderer-ready return IR, or generated output.

Keep these out of scope unless explicitly selected as the one thin slice:

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

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially private-boundary use,
   raw helper dispatch, broad body/call/store/return semantics, backend
   boundaries, circular imports, generic TSIL parsing, and hardwiring.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M83 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M83 wording remains.

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
docs/agent/runs/post-m83-acceptance-finalization-prompt.md
```

Do not create an M84 execution prompt until the selected post-M83 planning
result is explicitly accepted.

## Validation

Run:

```bash
git diff --check
```

## Final Report

Report:

1. Selected milestone recommendation.
2. Review/audit verdicts.
3. Files changed.
4. Next prompt created.
5. Validation command and exact result.
6. Whether human acceptance is required before execution.
