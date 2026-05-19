# M82 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 82: Selected-Body Envelope Ownership Extraction Slice
```

Milestones 1 through 81 are accepted. Post-M81 planning is accepted. M82 is
the active executor milestone.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/frozen-parity-baselines.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_generation_models.py`
- `tslgen/src/tslgen/lowering/_generation_queries.py`
- `tslgen/src/tslgen/lowering/_generation_control_flow.py`
- `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Move accepted selected-body concrete value-model ownership out of
`tslgen/src/tslgen/lowering/boundary.py` into a private typed lowering module
while preserving all accepted M42-M81 behavior and public import paths.

M82 is behavior-preserving selected-body value-model ownership extraction
only. It must not add selected-body semantics, generation helper semantics,
helper evaluation, source-adapter behavior, stage behavior, backend
translation, rendering, generated output, broad parsing, file/catalog reads,
or hardwired extension semantics.

The post-M81 `boundary.py` baseline is 5,438 physical lines. M82 should
materially reduce that file while keeping the extraction coherent. Do not use
line-count reduction to justify moving unrelated exact array-body pipeline
code, generation core helpers, source adapters, stage construction, or
lowering behavior. The final report must record the new line count and explain
the selected ownership boundary.

## Executor Task

Use exactly one write-capable executor for implementation. If M82 is already
implemented and only awaiting review, skip implementation and run the
read-only review/audit workflow instead.

Implement one coherent behavior-preserving selected-body value-model ownership
extraction slice:

- Keep public imports stable through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported names must remain
  importable from accepted public paths.
- Keep `boundary.py` as the public facade/coordinator around accepted lowering
  functions and normal pipeline integration.
- Create a private selected-body model module such as
  `tslgen.lowering._selected_body_models`, or an equivalent coherent private
  split.
- Move only the minimal cohesive selected-body value-model cluster needed to
  avoid circular private imports:
  - `OpaqueSelectedBranchBodyHandoff`
  - `NoSelectedBranchBodyHandoff`
  - `SelectedBranchBodyAssignmentFormRecognition`
  - `NoSelectedBranchBodyAssignmentFormRecognition`
  - `SelectedAssignmentDirectIntrinsicBodyIr`
  - `NoSelectedAssignmentDirectIntrinsicBodyIr`
  - `SelectedBodyEnvelopeEntry`
  - `SelectedBodyEnvelopeIr`
  - `NoSelectedBodyEnvelopeIr`
  - selected-body union aliases that can move without importing `boundary.py`
- Keep selected-body lowering functions in `boundary.py` unless a tiny helper
  move is required and remains behavior-preserving:
  `handoff_opaque_selected_branch_body`,
  `recognize_selected_branch_body_assignment_form`,
  `lower_selected_branch_body_ir`, and `lower_selected_body_envelope`.
- Tighten `_array_body_models.py` and `_array_body_validation.py` to consume
  concrete selected-body envelope model types where possible rather than broad
  selected/no-selected `hasattr` or cast seams. Use narrow local protocols only
  where a facade-owned value must remain.
- Add or preserve focused private-import-boundary regression coverage proving
  the new selected-body private module and accepted private lowering modules do
  not import `boundary.py` or the `tslgen.lowering` package facade, including
  common absolute and relative import forms.
- Preserve accepted M42-M81 diagnostics, diagnostic codes/severity/source
  locations/messages, selected-branch-only diagnostics, nested envelope
  identity, no-reparse behavior, stage names, stage ordering, output
  identities, keys, deterministic ordering, public imports, and
  no-external-input boundaries.
- Preserve private-module import direction. Private modules such as
  `_selected_body_models.py`, `_generation_models.py`,
  `_generation_queries.py`, `_generation_control_flow.py`,
  `_generation_diagnostics.py`, `_array_body_models.py`,
  `_array_body_shapes.py`, `_array_body_diagnostics.py`,
  `_array_body_validation.py`, `_exact_shapes.py`, and `_pipeline.py` must not
  import `boundary.py` or the `tslgen.lowering` package facade.

## Out Of Scope

- New lowering semantics, new selected-body semantics, new generation helper
  semantics, helper evaluation, new semantic output values, new stage
  behavior, broad direct-intrinsic semantics, broad TSIL parsing, exact
  return-emission IR, store semantics, return semantics, memory behavior,
  pointer semantics, variable scope/use-def/lifetime, declaration/array
  semantics, initializer behavior, `tmp.data()` semantics, `emit_return`,
  `assume_aligned`, ARM/SVE predicate/vector/register/intrinsic semantics,
  byte-size-to-token inference, source-operand semantics, or generated output.
- Moving `GenerationLoweringStage`, `GenerationContext`,
  `LoweredImplementation`, `LoweringRequest`, `lower_candidates`, source
  adapters, the exact array-body stage coordinator, or the M81 generation
  query/control-flow modules' ownership.
- Moving selected-body lowering functions beyond tiny behavior-preserving
  helper delegation.
- Moving mini-TSIL return lowering, broad assignment, variable, declaration,
  array, call, cast, loop, store, return, or multi-statement body lowering;
  broad vector metadata semantics; generic body/call/store/return/
  declaration/array IR; raw helper dispatch; registry, dispatcher, plugin,
  runtime plugin system, hidden backfeed, or fixpoint engine work.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, extension hardwiring, or runtime dependency on `frozen/`.
- Starting M83.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

Also run a focused M82 selected-body ownership/import-stability command
selected by the executor. The command must be named in the final report.

Then run:

```bash
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final report must record the new `boundary.py` line count, whether it is
below the 5,438-line post-M81 baseline, and any reason an import-boundary risk
required a narrower accepted reduction.

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M82 stayed behavior-preserving and did not add
   selected-body semantics, helper evaluation, raw helper dispatch, backend
   translation, rendering, generated output, broad parsing, source-adapter
   behavior, stage-construction frameworks, file/catalog reads, `tsldata`
   reads, host CPU queries, backend map reads, extension hardwiring, or
   runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the selected-body ownership
   extraction is a typed private ownership boundary, import-stable, and avoids
   broad registries, semantic dispatchers, runtime plugin systems, hidden
   recursive backfeeds, circular imports, broad class hierarchies, duplicate
   moved code, and hardwired extension semantics.
4. Validation auditor: review the validation commands, line-count result,
   focused M82 selected-body ownership/import-stability command, and failures,
   if any.
5. Documentation auditor: verify roadmap, architecture, pipeline, semantic
   lowering, behavioral spec, testing, and state docs match the implemented
   M82 selected-body ownership boundary and measured line-count result.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. Do not start M83. The likely next prompt is a
post-M82 lowering-focused planning-plus-review prompt unless review records a
different accepted next action or stop condition.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. `boundary.py` line-count result and whether it is below the M82 baseline.
4. Validation commands and exact results.
5. Review/audit verdicts.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. Whether M82 is accepted or what blocks acceptance.
