# Post-M78 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 78: Lowering Boundary Package Decomposition Slice
```

Milestones 1 through 78 are accepted. M78 returned
`Accept With Follow-Ups`. Review and audit found no blocking implementation,
validation, boundary, documentation, or evidence issues.

Do not implement code in this prompt, and do not start Milestone 79 execution.

For the next task, focus on lowering. Prefer candidates that continue the
typed staged-lowering direction and keep reducing the maintainability pressure
around `tslgen/src/tslgen/lowering/boundary.py` without hardwiring, raw helper
dispatch, backend translation, rendering, generated output, broad declaration/
array/body/call/store/return semantics, broad TSIL parsing, or broad
registries.

## Accepted M78 Result

M78 preserved accepted M57-M77 behavior while:

- moving exact array-initialization helper/slot shape rules into
  `tslgen.lowering._array_body_shapes`;
- moving extracted exact array-body / array-initialization diagnostics into
  `tslgen.lowering._array_body_diagnostics`;
- moving exact predicate-init structural tokens and recognizer regex into
  `tslgen.lowering._exact_shapes`;
- keeping public `tslgen.lowering` and `tslgen.lowering.boundary` imports
  stable;
- reducing `boundary.py` from 12,371 physical lines to 11,109 physical lines.

M78 follow-ups are non-blocking:

- `_array_body_diagnostics.py` uses `Any` for several attribute-dependent
  diagnostic helper inputs to preserve one-way private imports and avoid
  circularity. A future slice should replace this with small local protocols
  or move the relevant typed models with the diagnostics.
- Exact helper `Literal` aliases are duplicated between `boundary.py` and
  `_array_body_shapes.py`; a future typed-model extraction should consolidate
  ownership to reduce drift risk.

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
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M78 execution.

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
-> behavior-preserving composable lowering pipeline/module boundary
-> lowering boundary package decomposition
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M78.
Potential directions include, but are not limited to:

- a focused typed-model extraction that consolidates the exact
  array-initialization helper `Literal` aliases and shape/rule model ownership
  currently split between `boundary.py` and `_array_body_shapes.py`, while
  preserving public facade imports and no new semantics;
- a focused diagnostics-typing slice that replaces `_array_body_diagnostics.py`
  `Any` helper inputs with small private protocols or moved exact typed models,
  without importing `boundary.py` from private modules or creating circular
  dependencies;
- another behavior-preserving package-decomposition slice that moves one
  coherent exact array-body source-adapter, validator, or stage-construction
  cluster out of `boundary.py`, with a measurable but realistic line-count
  reduction and no duplicate moved code;
- exact return-emission structural/request IR that consumes accepted M74-M78
  state and records only the exact `emit_return(tmp)` path, without return
  semantics, variable scope/lifetime, renderer-ready IR, or output;
- focused tightening of `_pipeline.py` typed payload/protocol boundaries or
  pending-backfeed request identity, only if selected as a concrete
  maintainability slice and not turned into a broad registry/fixpoint engine.

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

M78's private `_array_body_shapes.py`, `_array_body_diagnostics.py`,
`_exact_shapes.py`, and `_pipeline.py` modules are accepted lowering internals,
not public API commitments or permission for broad registries. Future
milestones may consume them only through typed local contracts and must
preserve public `tslgen.lowering` imports unless a public API change is
explicitly selected.

No-hardwiring remains a blocking planning boundary. Future lowering milestones
must consume typed request/result/context values and accepted typed rules or
explicit typed metadata inputs. They must not use ad-hoc tables or `if`/`elif`
branches keyed by raw helper text, selected type tags, request ordinals, SVE
tokens, backend ids, renderer names, or corpus line numbers directly to
semantic outputs. Source text may remain provenance/invariant evidence only.

Future backfeeds must be typed facts, typed requests, dependencies, or
deterministic coordinator decisions. Do not select speculative fixpoint or
backfeed execution unless the milestone names one concrete typed need and
keeps it private and deterministic.

If a return-emission-shaped candidate is selected, it must stay structural/
request only. It may record exact tokens and provenance already carried
through M74-M78, but it must not interpret `emit_return`, `tmp`, return value
semantics, variable lifetime, renderer-ready return IR, or generated output.

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

- M76 extensibility follow-up: `GenerationLoweringStage.__post_init__` remains
  a central stage-name-to-output-type validation table and is growing with
  each exact Stage 8 slice.
- M77 follow-up: `_pipeline.py` is typed around stage names, artifact kinds,
  dependencies, and backfeed policy, but still carries `object` payloads for
  stage/value references; future extraction should tighten this with a small
  local protocol or typed stage/value boundary when a concrete consumer needs
  it.
- M77 follow-up: before real backfeed requests are used,
  `ExactArrayBodyPipelineSnapshot.key` should include request kind/source stage
  identity for pending backfeed requests, not only `request.key`.
- M78 follow-up: `_array_body_diagnostics.py` uses `Any` for several
  attribute-dependent diagnostic helper inputs; future decomposition should
  replace this with small private protocols or move the relevant typed models
  with the diagnostics.
- M78 follow-up: exact helper `Literal` aliases are duplicated between
  `boundary.py` and `_array_body_shapes.py`; future typed-model extraction
  should consolidate ownership to reduce drift risk.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially M78 private-boundary
   use, raw helper dispatch, broad body/call/store/return semantics, backend
   boundaries, circular imports, and generic TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M78 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M78 wording remains.

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
docs/agent/runs/post-m78-acceptance-finalization-prompt.md
```

Do not create an M79 execution prompt until the selected post-M78 planning
result is explicitly accepted.

## Validation

Run:

```bash
git diff --check
```

## Final Report

Report:

1. Selected candidate and why.
2. Files changed.
3. Review/audit verdicts.
4. Follow-ups recorded, if any.
5. Validation command and exact result.
6. Next prompt created.
7. Whether the repo is ready for post-M78 planning acceptance or what blocks it.
