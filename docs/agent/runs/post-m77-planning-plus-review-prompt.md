# Post-M77 Planning Plus Review Prompt

You are planning the next redesign milestone after:

```text
Milestone 77: Composable Lowering Pipeline Module Boundary Slice
```

Milestones 1 through 77 are accepted. M77 returned
`Accept With Follow-Ups` after one focused documentation revision. Review and
audit found no blocking implementation, validation, boundary, extensibility,
documentation, or evidence issues after that revision.

Do not implement code in this prompt, and do not start Milestone 78 execution.

For the next task, focus on lowering. Prefer candidates that continue the
typed staged lowering direction and use the new private M77 module/pipeline
boundary without hardwiring, raw helper dispatch, backend translation,
rendering, generated output, broad declaration/array/body/call/store/return
semantics, broad TSIL parsing, or broad registries.

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
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Target

Select exactly one next milestone candidate for post-M77 execution.

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
-> next typed lowering step
```

Compare lowering-focused candidates that could reasonably follow M77.
Potential directions include, but are not limited to:

- exact return-emission structural/request IR that consumes accepted M74/M75/M76
  state and records only the exact `emit_return(tmp)` path without return
  semantics, variable scope/lifetime, renderer-ready IR, or output;
- focused cleanup of the remaining inline M75 exact predicate-init tokens by
  moving them into `_exact_shapes.py`, only if selected as a thin
  behavior-preserving slice and not mixed with new semantics;
- focused tightening of `_pipeline.py` typed payload/protocol boundaries or
  pending-backfeed request identity, only if selected as a concrete
  maintainability slice and not turned into a broad registry/fixpoint engine;
- exact backend-uninit deferred-value handoff refinement that consumes the
  accepted M72/M73 path and remains an unresolved typed backend-value boundary,
  without backend translation or renderer text;
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

M77's private `_pipeline.py` and `_exact_shapes.py` modules are accepted
lowering internals, not public API commitments or permission for broad
registries. Future milestones may consume them only through typed local
contracts and must preserve public `tslgen.lowering` imports unless a public
API change is explicitly selected.

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
request only. It may record exact tokens and provenance already carried through
M74/M75/M76/M77, but it must not interpret `emit_return`, `tmp`, return value
semantics, variable lifetime, renderer-ready return IR, or generated output.

If a call-site or store-call-shaped candidate is selected, it must stay
structural/request only. It may record exact tokens and provenance already
carried through M76/M77, but it must not interpret `svst1`, `pg`, `tmp.data()`,
`a`, memory behavior, alignment behavior, backend intrinsic semantics, or
renderer-ready output.

If a backend-uninit candidate is selected, the result must remain an unresolved
typed policy, typed deferred backend-value boundary, or explicit unsupported
diagnostic. It must not translate `value<backend>(uninit::array)` into
C++/Rust/backend text, create renderer-ready text, query backend maps, or make
backend translation/rendering part of lowering.

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
  a central stage-name-to-output-type validation table and is growing with each
  exact Stage 8 slice.
- M77 follow-up: `_pipeline.py` is typed around stage names, artifact kinds,
  dependencies, and backfeed policy, but still carries `object` payloads for
  stage/value references; future extraction should tighten this with a small
  local protocol or typed stage/value boundary when a concrete consumer needs
  it.
- M77 follow-up: before real backfeed requests are used,
  `ExactArrayBodyPipelineSnapshot.key` should include request kind/source stage
  identity for pending backfeed requests, not only `request.key`.
- M77 follow-up: later cleanup can move remaining inline M75 predicate-init
  exact tokens such as `svbool_t`, `pg`, and `svptrue_b8` into
  `_exact_shapes.py` as slice-local structural evidence.

## Required Subagent Workflow

Use read-only planning and audit subagents before finalizing the plan:

1. Lowering planner: compare lowering-focused next milestones and recommend
   one candidate.
2. Extensibility auditor: assess whether the candidate keeps the staged
   lowering pipeline maintainable and avoids broad dispatchers.
3. Boundary auditor: identify scope risks, especially M77 private-boundary
   use, raw helper dispatch, broad body/call/store/return semantics,
   backend-uninit/backend boundaries, and generic TSIL parsing.
4. Evidence auditor: verify evidence paths and whether the candidate is
   supported by accepted M57-M77 behavior plus current corpus evidence.
5. Documentation auditor: check which roadmap/spec/testing docs need planning
   updates and whether stale M77 wording remains.

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
docs/agent/runs/post-m77-acceptance-finalization-prompt.md
```

Do not create an M78 execution prompt until the selected post-M77 planning
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
7. Whether the repo is ready for post-M77 planning acceptance or what blocks it.
