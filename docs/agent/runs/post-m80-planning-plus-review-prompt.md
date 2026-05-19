# Post-M80 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 80: Exact Array-Body Validation Boundary Extraction Slice
```

Milestones 1 through 80 are accepted. M80 returned
`Accept With Follow-Ups`. Review and audit found no blocking implementation,
validation, boundary, documentation, or evidence issues after workflow
documentation finalization.

Do not implement code in this prompt, and do not start Milestone 81 execution.

For the next task, focus on lowering. Prefer candidates that continue the
typed staged-lowering direction, keep `tslgen/src/tslgen/lowering/boundary.py`
shrinking through coherent private ownership boundaries, and improve
maintainability without hardwiring, raw helper dispatch, backend translation,
rendering, generated output, broad declaration/array/body/call/store/return
semantics, broad TSIL parsing, broad registries, or extension-specific
semantic shortcuts.

## Accepted M80 Result

M80 preserved accepted M57-M79 behavior while:

- creating `tslgen.lowering._array_body_validation` as the private exact
  array-body / array-initialization validation and request-record helper owner;
- moving exact validation, request-record selection, metadata lookup
  validation, `_exact_array_body_envelope_shape_is_supported`,
  `_structural_role_from_slot`, `_array_initialization_leaf`, and source-span
  helper ownership out of `boundary.py`;
- keeping source adapters and stage/`LoweredImplementation` adapters in
  `boundary.py`;
- keeping public `tslgen.lowering` and `tslgen.lowering.boundary` imports
  stable;
- keeping private lowering modules from importing `boundary.py`;
- reducing `boundary.py` from the post-M79 8,915-line baseline to 7,208
  physical lines, below the M80 threshold of 7,415 lines;
- adding focused ownership/import-boundary tests, including relative-import
  hardening for private modules.

M80 follow-ups are non-blocking:

- The selected/no-selected body envelope seam still uses narrow structural
  protocols/casts because concrete M63 envelope models remain facade-owned.
  A future lowering slice should either move selected-body envelope ownership
  deliberately or keep selected-body concrete checks at the facade boundary
  rather than broadening structural checks.
- Continuing M76/M77 maintainability follow-ups remain relevant:
  `GenerationLoweringStage.__post_init__` is a growing stage/output validation
  table, and `_pipeline.py` still carries `object` payloads for stage/value
  references.

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
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M80 execution.

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
-> exact array-body typed model ownership extraction
-> exact array-body validation boundary extraction
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M80.
Potential directions include, but are not limited to:

- another behavior-preserving extraction slice that moves one coherent
  facade-owned exact array-body source-adapter, stage-construction, or
  selected-body envelope ownership boundary out of `boundary.py`, only if it
  can remain private, typed, and import-stable;
- a focused shared-model/protocol cleanup slice that resolves the M80
  selected/no-selected envelope seam without changing behavior or public
  imports;
- exact return-emission structural/request IR that consumes accepted M74-M80
  state and records only the exact `emit_return(tmp)` path, without return
  semantics, variable scope/lifetime, renderer-ready IR, or output;
- focused tightening of `_pipeline.py` typed payload/protocol boundaries or
  pending-backfeed request identity, only if selected as a concrete
  maintainability slice and not turned into a broad registry/fixpoint engine;
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

M80's private `_array_body_models.py`, `_array_body_shapes.py`,
`_array_body_diagnostics.py`, `_array_body_validation.py`, `_exact_shapes.py`,
and `_pipeline.py` modules are accepted lowering internals, not public API
commitments or permission for broad registries. Future milestones may consume
them only through typed local contracts and must preserve public
`tslgen.lowering` imports unless a public API change is explicitly selected.

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
through M74-M80, but it must not interpret `emit_return`, `tmp`, return value
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

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially M80 private-boundary
   use, raw helper dispatch, broad body/call/store/return semantics, backend
   boundaries, circular imports, and generic TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M80 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M80 wording remains.

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
docs/agent/runs/post-m80-acceptance-finalization-prompt.md
```

Do not create an M81 execution prompt until the selected post-M80 planning
result is explicitly accepted.

## Validation

Run:

```bash
git diff --check
```

## Final Report

Report:

1. Selected milestone title and number.
2. Planning summary and why it is the best next lowering step.
3. Subagent planning/audit/review verdicts.
4. Files changed.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. Validation command and exact result.
8. Whether the post-M80 planning result is ready for human acceptance.
