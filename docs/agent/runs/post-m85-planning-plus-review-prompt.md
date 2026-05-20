# Post-M85 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 85: Selected-Body Lowering Ownership Extraction Slice
```

Milestones 1 through 85 are accepted. M85 execution-review returned `Accept`
after one focused revision.

Do not implement code in this prompt, and do not start Milestone 86 execution.

For the next task, focus on lowering. Prefer candidates that advance the typed
staged-lowering pipeline or continue cohesive lowering package decomposition
without hardwiring, raw helper dispatch, backend translation, rendering,
generated output, broad declaration/array/body/call/store/return semantics,
broad TSIL parsing, broad registries, fixpoint/backfeed machinery, or
extension-specific semantic shortcuts.

## Accepted M85 Result

M85 preserved accepted M42-M84 behavior while:

- moving accepted M60-M63 selected-body lowerer/source-helper ownership into
  `tslgen.lowering._selected_body_lowering`;
- keeping `boundary.py` as the public facade/coordinator for request/result
  models, `_lower_input`, `lower_candidates`, payload classification,
  mini-TSIL lowering, generation control-flow pruning, and exact array-body
  pipeline orchestration;
- preserving public imports, diagnostics, source locations, stage names/order,
  output identities, deterministic keys, selected-branch-only behavior, and
  pipeline snapshots;
- keeping `_selected_body_models.py` as a value-model owner only;
- keeping the private selected-body lowering module from importing
  `boundary.py`, `tslgen.lowering`, `_array_body_sources.py`, or
  `_array_body_lowering.py` as convenience dispatchers;
- reducing `boundary.py` from the accepted M84 1,898-line baseline to 1,417
  physical lines;
- adding focused M85 tests for public facade stability, private import
  boundaries, selected-body diagnostics, `PrunedGenerationBranch`
  source-location preservation, selected-body stage/output identity, and
  deterministic source locations while preserving the full lowering-boundary
  suite.

M85 review recorded no non-blocking follow-ups.

Continuing follow-ups remain relevant:

- Exact return-emission structural/request IR remains a high-value lowering
  candidate now that M77-M85 have reduced the main boundary and extracted the
  stage/output, exact-array pipeline/source, and selected-body lowering
  ownership clusters.
- `_array_body_lowering.py` and `_array_body_sources.py` must not become new
  catch-all modules.
- `_pipeline.py` still carries `object` payloads for stage/value references.
- A future public-surface cleanup may either document
  `GenerationLoweringStageName` and `GenerationLoweringStageOutput` aliases as
  boundary-only or explicitly export/test them from `tslgen.lowering`.

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
- `tslgen/src/tslgen/lowering/_selected_body_lowering.py`
- `tslgen/src/tslgen/lowering/_selected_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
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

Select exactly one next milestone candidate for post-M85 execution.

The selected candidate should advance lowering after:

```text
typed values
-> typed predicates
-> control-flow pruning
-> selected-body handoff/form/body IR/envelope
-> exact array-body envelope/helper/declaration/predicate/call-site path
-> composable lowering pipeline/module boundary
-> lowering boundary package/model/validation decomposition
-> generation-time lowering core ownership extraction
-> selected-body model ownership extraction
-> stage-contract ownership extraction
-> exact array-body pipeline/source-adapter ownership extraction
-> selected-body lowering ownership extraction
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M85.
Potential directions include, but are not limited to:

- exact return-emission structural/request IR that consumes accepted M74-M85
  state and records only the exact `emit_return(tmp)` path, without return
  semantics, variable scope/lifetime, renderer-ready IR, or generated output;
- a behavior-preserving split of `_array_body_lowering.py` around a concrete
  typed exact-array public-lowering ownership boundary if that unlocks the next
  semantic slice and does not create a new facade-shaped module;
- a focused `_pipeline.py` typed-payload tightening only if it materially
  improves the next semantic slice and avoids a registry, dispatcher,
  fixpoint/backfeed engine, or broad stage framework;
- a small testing/boundary-hardening slice only if it protects a concrete next
  lowering refactor or semantic slice and is not merely test churn.

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
tokens, backend ids, renderer names, or corpus line numbers directly to
semantic outputs. Source text may remain provenance/invariant evidence only.

Future backfeeds must be typed facts, typed requests, dependencies, or
deterministic coordinator decisions. Do not select speculative fixpoint or
backfeed execution unless the milestone names one concrete typed need and
keeps it private and deterministic.

If a return-emission-shaped candidate is selected, it must stay structural /
request only. It may record exact tokens and provenance already carried
through M74-M85, but it must not interpret `emit_return`, `tmp`, return value
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
   lowering pipeline maintainable and avoids broad dispatchers, catch-all
   modules, and premature fixpoint machinery.
3. Boundary auditor: identify scope risks, especially private-boundary use,
   raw helper dispatch, broad body/call/store/return semantics, backend
   boundaries, circular imports, generic TSIL parsing, and hardwiring.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M85 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M85 wording remains.

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
docs/agent/runs/post-m85-acceptance-finalization-prompt.md
```

Do not create an M86 execution prompt until the selected post-M85 planning
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
4. Next concrete prompt path created.
5. Validation command and exact result.
6. Whether the repo is waiting for human acceptance or ready for execution.
