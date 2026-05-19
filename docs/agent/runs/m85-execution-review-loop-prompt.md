# M85 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 85.

Milestones 1 through 84 are accepted. Post-M84 planning is accepted and
selected:

```text
Milestone 85: Selected-Body Lowering Ownership Extraction Slice
```

Use the orchestrated executor-review loop in this prompt. M85 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start M86.

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
- `tslgen/src/tslgen/lowering/_selected_body_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_generation_models.py`
- `tslgen/src/tslgen/lowering/_generation_control_flow.py`
- `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Move accepted M60-M63 selected-body lowering function/source-helper ownership
out of `tslgen/src/tslgen/lowering/boundary.py` into a focused private typed
lowering module, likely `tslgen.lowering._selected_body_lowering`, while
preserving all accepted M42-M84 behavior, public imports, diagnostics, source
locations, stage names/order, output identities, deterministic keys,
selected-branch-only behavior, pipeline snapshots, and no-external-input
boundaries.

M85 is behavior-preserving lowering architecture work. It closes the ownership
gap left intentionally by M82 and M84: M82 moved selected-body value models
into `_selected_body_models.py`, and M84 left the selected-body public
lowerers in `boundary.py` while extracting exact array-body pipeline/source
ownership. Line count is useful, but the success criterion is cohesive
ownership extraction and behavior preservation.

## Scope

- Create a focused private selected-body lowering module such as
  `tslgen.lowering._selected_body_lowering`.
- Move the accepted public selected-body lowerer implementations out of
  `boundary.py`:
  - `handoff_opaque_selected_branch_body`
  - `recognize_selected_branch_body_assignment_form`
  - `lower_selected_branch_body_ir`
  - `lower_selected_body_envelope`
- Move only the private helpers directly owned by those lowerers: selected-body
  source coercion helpers, originating branch-chain id construction, selected
  body envelope consistency validation, selected-body assignment-form parsing
  delegation, and selected-body diagnostic helpers.
- Preserve public facade imports and calls through `tslgen.lowering.boundary`
  and `tslgen.lowering` by re-exporting or tiny delegating from the facade.
- Preserve accepted diagnostics, messages, source locations, stage names/order,
  stage keys, output object identities, selected-branch-only behavior,
  deterministic ordering, and pipeline snapshots.
- Keep private-module imports one-way. The new selected-body lowering module
  must not import `boundary.py` or the `tslgen.lowering` package facade.
- Record the post-M85 `boundary.py` line count measured against the accepted
  M84 1,898-line baseline.

## Out Of Scope

- New lowering semantics, new selected-body semantics, new stage names, new
  stage outputs, exact return-emission IR, `emit_return(tmp)` interpretation,
  `tmp.data()` semantics, store/call/body/return/declaration/array semantics
  beyond accepted exact structural/request records, broad TSIL parsing, broad
  selected-body parsing, broad source-adapter support, or helper-family
  expansion.
- Moving selected-body behavior into `_selected_body_models.py`; that module
  remains the value-model owner.
- Moving `LoweredImplementation`, `LoweringRequest`, `LoweringInput`,
  `LoweringInputSet`, `LoweringPlan`, `_lower_input`, `lower_candidates`,
  payload classification, generation control-flow pruning, exact array-body
  pipeline/source modules, exact array-body lowerers, stage construction for
  mini-TSIL output, or mini-TSIL parsing/lowering out of the facade.
- Importing `_array_body_sources.py` or `_array_body_lowering.py` from the new
  selected-body lowering module as a convenience dispatcher. Use a
  selected-body-local source-location helper or another narrow private helper
  if needed.
- Creating registries, generic dispatchers, plugin systems, callback maps,
  fixpoint/backfeed engines, raw helper dispatch, token-keyed semantic maps,
  or a selected-body framework.
- Treating selected literals, SVE-looking tokens, selected type tags, backend
  ids, renderer names, corpus line numbers, request ordinals, or raw source
  text as semantic dispatch keys. Existing exact tokens may remain structural
  provenance or invariant evidence only.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M86.

## Required Executor Task

Run exactly one write-capable executor for M85. The executor should:

1. Implement the smallest coherent behavior-preserving extraction that moves
   selected-body lowering ownership out of `boundary.py`.
2. Add focused M85 tests for public facade import/call stability, private
   import boundaries, selected-body diagnostic preservation, pipeline
   snapshots, stage order, keys, output identity, selected-branch-only
   behavior, and deterministic source locations.
3. Replace the M84 ownership guard that asserted selected-body lowerers were
   boundary-owned with tests proving stable public facade imports plus private
   selected-body lowering ownership.
4. Preserve all accepted public imports and existing lowering behavior.
5. Avoid moving selected-body behavior into `_selected_body_models.py`,
   importing exact array-body source/lowering modules as convenience
   dispatchers, broad protocols, broad structural `hasattr` seams, callback
   injection, duplicate moved code, and another catch-all private module.
6. Run the required validation commands below.
7. Return a concise implementation summary, files changed, validation results,
   and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m85 or selected_body_lowering or selected_body_handoff or selected_body_envelope"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different private module name than
`_selected_body_lowering.py`, update the py-compile command consistently in
this prompt, `docs/agent/current-redesign-state.md`, and the final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify the extraction is one behavior-preserving lowering
   ownership slice, private modules do not import the facade, selected-body
   behavior was not moved into `_selected_body_models.py`, exact array-body
   source/lowering modules are not convenience dispatchers, and no raw helper
   dispatch, broad TSIL/body/call/store/return semantics, backend/rendering/
   output leakage, hardwiring, or catch-all module was introduced.
3. Extensibility auditor: verify the staged lowering pipeline remains
   maintainable and future stages can be added without registries,
   dispatchers, broad protocols, callback injection, or hidden backfeeds.
4. Validation auditor: verify required commands ran, results are recorded, and
   tests cover the declared M85 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale M85/M84 handoff wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M85 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M85
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M85 result

Record:

- M85 accepted status and review verdict.
- Files changed.
- The `boundary.py` line count before and after M85.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m85-planning-plus-review-prompt.md
```

The post-M85 prompt must focus on lowering, use read-only planning/review
subagents, and must not implement M86 unless that future prompt explicitly
selects an executor task.

Do not start M86 in this prompt.
