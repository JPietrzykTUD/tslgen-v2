# M80 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 80: Exact Array-Body Validation Boundary Extraction Slice
```

Milestones 1 through 79 are accepted. Post-M79 planning is accepted. M80 is
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
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving accepted
exact array-body / array-initialization validation and request-record helper
ownership into a private lowering module while preserving all accepted M57-M79
behavior.

M80 is behavior-preserving exact validation/request-record helper extraction
only. It must not add new lowering semantics, helper evaluation, stage
behavior, source-adapter behavior, backend translation, rendering, generated
output, broad parsing, file/catalog reads, or hardwired extension semantics.

The post-M79 `boundary.py` baseline is 8,915 physical lines. M80 should
reduce that file by at least 1,500 physical lines, so the post-M80 count
should be 7,415 physical lines or lower, unless the executor documents that an
import-boundary risk requires a narrower accepted reduction. Do not satisfy
the line-count target by moving unrelated shared models, leaving duplicate
moved code behind, or recreating `boundary.py` as a second monolith.

## Executor Task

Use exactly one write-capable executor for implementation. If M80 is already
implemented and only awaiting review, skip implementation and run the
read-only review/audit workflow instead.

Implement one coherent behavior-preserving validation-boundary extraction
slice:

- Keep public imports stable through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported names must remain
  importable from accepted public paths.
- Keep `boundary.py` as the public facade/coordinator around accepted lowering
  functions and normal pipeline integration.
- Create a private exact array-body validation module such as
  `tslgen.lowering._array_body_validation`, or an equivalent coherent private
  module split, for accepted exact validation, request-record selection,
  metadata lookup validation, and small construction helpers.
- Move only helpers that can move without making a private module import
  `boundary.py`. Candidate ownership includes
  `_validate_array_initialization_*`,
  `_array_initialization_*_request_record`,
  `_array_initialization_*_metadata_for_context` where narrow local protocols
  are enough, `_validate_array_body_structural_sequence_inputs`,
  `_validate_predicate_path_structural_request_input`,
  `_validate_post_branch_intrinsic_call_site_input`,
  `_exact_array_body_envelope_shape_is_supported`,
  `_structural_role_from_slot`, and `_array_initialization_leaf`.
- Use narrow private protocols only where the moved helpers need
  context-like values that remain facade-owned. Prefer leaving a helper in
  `boundary.py` over making a private module import `boundary.py`, duplicating
  ownership, or broadening structural protocols.
- Add or preserve a focused private-import-boundary regression test proving
  accepted private lowering modules, including the new validation module, do
  not import `boundary.py`.
- Preserve accepted M57-M79 diagnostics, diagnostic codes/severity/source
  locations/messages, stage names, stage ordering, output identities, keys,
  deterministic ordering, selected-branch-only diagnostics, public imports,
  and no-external-input boundaries.
- Preserve the M79 private-module import direction. Private modules such as
  `_array_body_models.py`, `_array_body_shapes.py`,
  `_array_body_diagnostics.py`, `_array_body_validation.py`,
  `_exact_shapes.py`, and `_pipeline.py` must not import `boundary.py`.
- Keep exact recognizer tokens such as `svbool_t`, `pg`, `svptrue_b8`,
  `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `intrin`, `svst1`,
  `tmp.data()`, `emit_return(tmp)`, and `a` as structural evidence only.
- Update redesign docs to record the validation boundary and measured
  `boundary.py` line-count result.

## Out Of Scope

- New lowering semantics, new generation helper evaluation, new semantic
  output values, new stage behavior, source-adapter behavior, or generated
  output.
- Moving source adapters that consume `GenerationLoweringStage` or
  `LoweredImplementation`, moving the full exact stage coordinator, moving
  `GenerationLoweringStage.__post_init__`, or changing public stage
  construction unless a tiny dependency move is required and remains
  behavior-preserving.
- Whole-file rewrite of `boundary.py`, moving unrelated shared generation
  models, broad OO hierarchy, broad model hierarchy, generic body model,
  stage/helper/slot registry, semantic dispatcher, runtime plugin system,
  hidden recursive backfeeds, or fixpoint execution.
- Store semantics, return semantics, memory behavior, pointer semantics,
  variable scope/use-def/lifetime, declaration/array semantics beyond accepted
  exact structural IR, initializer behavior, `tmp.data()` semantics,
  `emit_return`, `assume_aligned`, ARM/SVE predicate/vector/register/intrinsic
  semantics, byte-size-to-token inference, source-operand semantics, generic
  call/store/return/body/declaration/array parsing, broad TSIL parsing, or raw
  helper-string dispatch.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M81.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

Also run a focused M80 validation-boundary/import-stability command selected
by the executor. The command must be named in the final report.

Then run:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final report must record the new `boundary.py` line count and whether it
is 7,415 lines or lower, or explain why an import-boundary risk justified a
narrower accepted reduction.

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M80 stayed behavior-preserving and did not add
   backend translation, rendering, generated output, broad parsing, generic
   body/call/store/return/declaration/array semantics, source-adapter
   behavior, stage-construction frameworks, raw helper dispatch, helper
   evaluation, file/catalog reads, `tsldata` reads, host CPU queries, backend
   map reads, or runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the validation extraction is
   one typed private ownership boundary, import-stable, and avoids broad
   registries, semantic dispatchers, runtime plugin systems, hidden recursive
   backfeeds, circular imports, broad class hierarchies, and hardwired
   extension semantics.
4. Validation auditor: review the validation commands, line-count result,
   focused M80 validation-boundary/import-stability command, and failures, if
   any.
5. Documentation auditor: verify roadmap, architecture, pipeline, semantic
   lowering, behavioral spec, testing, and state docs match the implemented
   M80 validation boundary and measured line-count result.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. Do not start M81. The likely next prompt is a
post-M80 lowering-focused planning-plus-review prompt unless review records a
different accepted next action or stop condition.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. `boundary.py` line-count result and whether it meets the M80 threshold.
4. Validation commands and exact results.
5. Review/audit verdicts.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. Whether M80 is accepted or what blocks acceptance.
