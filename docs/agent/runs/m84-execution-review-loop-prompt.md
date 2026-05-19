# M84 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 84.

Milestones 1 through 83 are accepted. Post-M83 planning is accepted and
selected:

```text
Milestone 84: Exact Array-Body Pipeline And Source Adapter Ownership Extraction Slice
```

Use the orchestrated executor-review loop in this prompt. M84 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start M85.

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
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
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

## Goal

Move the accepted exact array-body staged-lowering pipeline and source-adapter
ownership out of `tslgen/src/tslgen/lowering/boundary.py` into one or more
private typed lowering modules while preserving all accepted M42-M83 behavior,
public imports, diagnostics, stage names/order, output identities,
deterministic keys, selected-branch-only behavior, pipeline snapshots, and
no-external-input boundaries.

M84 is behavior-preserving lowering architecture work. It is the next large
step toward making `boundary.py` a small facade, with a campaign target of
eventually bringing the facade toward roughly 1,000 physical lines. Line count
must remain subordinate to a cohesive ownership boundary.

## Scope

- Create a private exact array-body pipeline/source-adapter ownership module
  such as `tslgen.lowering._array_body_pipeline`,
  `tslgen.lowering._array_body_sources`, or an equivalent small set of
  cohesive private lowering modules.
- Move the accepted exact array-body stage-pipeline result/coordinator and its
  direct helper ownership out of `boundary.py`, including the M64-M76 exact
  array-body pipeline call sequence, stage construction helpers for the exact
  array-body stages, deterministic stage-output/source-location helpers, and
  exact pipeline skeleton lookup/assembly helpers.
- Move the accepted exact array-body source-adapter helpers out of
  `boundary.py`, including adapters for selected-body handoff, selected-body
  IR recognition, selected-body envelope, M63 envelope skeletons, M66-M76
  exact array-initialization outputs, predicate-path structural requests, and
  post-branch intrinsic-call-site structural requests.
- Move exact array-body skeleton validation helpers only when they belong to
  the same private exact array-body source/pipeline ownership boundary and can
  preserve diagnostics exactly.
- Keep `boundary.py` as the public facade for `GenerationContext`,
  `LoweringRequest`, `LoweringInput`, `LoweringInputSet`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, payload classification, mini-TSIL lowering, and public
  import compatibility unless a tiny delegate is required for public lowering
  functions.
- Preserve public API behavior by re-exporting or delegating from
  `tslgen.lowering.boundary` and `tslgen.lowering` where names are already
  public.
- Use only narrow typed protocols for facade-owned values, if needed. Private
  exact array-body modules must not import `boundary.py` or the
  `tslgen.lowering` package facade.
- Preserve accepted source locations, diagnostic codes/messages, stage names,
  stage ordering, stage keys, output object identities, pipeline snapshots,
  selected-branch-only behavior, and deterministic ordering.
- Record the post-M84 `boundary.py` line count. The expected target is a
  substantial reduction from 4,807 physical lines, with review pressure toward
  a facade below roughly 2,000 lines if the exact array-body ownership cluster
  can move without broad protocols or semantic expansion.

## Out Of Scope

- New semantic lowering behavior, new stage names, new stage outputs, exact
  return-emission IR, `emit_return(tmp)` interpretation, `tmp.data()`
  semantics, store/call/body/return/declaration/array semantics beyond the
  accepted exact structural/request records, broad TSIL parsing, broad source
  skeleton recognition, broad source-adapter support, or helper-family
  expansion.
- Moving `LoweredImplementation`, `LoweringRequest`, `LoweringInput`,
  `LoweringInputSet`, `LoweringPlan`, `lower_candidates`, payload
  classification, or mini-TSIL parsing out of the facade.
- Creating registries, generic dispatchers, plugin systems, callback maps,
  fixpoint/backfeed engines, raw helper dispatch, token-keyed semantic maps,
  or a second monolithic private module.
- Treating SVE-looking tokens, selected type tags, backend ids, renderer
  names, corpus line numbers, request ordinals, or raw source text as semantic
  dispatch keys. Existing exact tokens may move only as structural provenance
  or invariant evidence.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M85.

## Required Executor Task

Run exactly one write-capable executor for M84. The executor should:

1. Implement the smallest coherent behavior-preserving extraction that moves
   the exact array-body pipeline/source-adapter ownership out of `boundary.py`.
2. Add focused M84 tests for import boundaries, public facade stability,
   representative direct typed value/stage-output/`LoweredImplementation`-like
   source inputs, diagnostic preservation, pipeline snapshots, stage order,
   keys, output identity, selected-branch-only behavior, and deterministic
   source locations.
3. Preserve all accepted public imports and existing lowering behavior.
4. Avoid broad protocols, broad structural `hasattr` seams, callback
   injection, duplicate moved code, and a second private monolith.
5. Run the required validation commands below.
6. Return a concise implementation summary, files changed, validation results,
   and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m84 or array_body_pipeline or array_body_sources or array_body_lowering or source_adapter or exact_array"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different private module name than the listed
exact array-body modules, update the py-compile command consistently in this
prompt, `docs/agent/current-redesign-state.md`, and the final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify the extraction is one behavior-preserving lowering
   ownership slice, private modules do not import the facade, and no raw helper
   dispatch, broad TSIL/body/call/store/return semantics, backend/rendering/
   output leakage, hardwiring, or second monolith was introduced.
3. Extensibility auditor: verify the staged lowering pipeline remains
   maintainable and future stages can be added without registries,
   dispatchers, broad protocols, callback injection, or hidden backfeeds.
4. Validation auditor: verify required commands ran, results are recorded, and
   tests cover the declared M84 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale M84/M83 handoff wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M84 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M84
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M84 result

Record:

- M84 accepted status and review verdict.
- Files changed.
- The `boundary.py` line count before and after M84.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m84-planning-plus-review-prompt.md
```

The post-M84 prompt must focus on lowering, use read-only planning/review
subagents, and must not implement M85 unless that future prompt explicitly
selects an executor task.

Do not start M85 in this prompt.
