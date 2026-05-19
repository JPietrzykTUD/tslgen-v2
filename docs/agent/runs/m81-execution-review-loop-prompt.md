# M81 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 81: Generation-Time Lowering Core Ownership Extraction Slice
```

Milestones 1 through 80 are accepted. Post-M80 planning is accepted. M81 is
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
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/domain/generation_rules.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted generation-time lowering core into private typed lowering modules
while preserving all accepted M42-M80 behavior.

M81 is behavior-preserving generation-time lowering ownership extraction only.
It must not add new helper semantics, helper evaluation, source-adapter
behavior, stage behavior, backend translation, rendering, generated output,
broad parsing, file/catalog reads, or hardwired extension semantics.

The post-M80 `boundary.py` baseline is 7,208 physical lines. M81 should reduce
that file by at least 1,400 physical lines, so the post-M81 count should be
5,808 physical lines or lower, unless the executor documents that an
import-boundary risk requires a narrower accepted reduction. Do not satisfy
the line-count target by moving unrelated exact array-body pipeline code,
leaving duplicate moved code behind, or recreating `boundary.py` as a second
monolith.

## Executor Task

Use exactly one write-capable executor for implementation. If M81 is already
implemented and only awaiting review, skip implementation and run the
read-only review/audit workflow instead.

Implement one coherent behavior-preserving generation-core ownership
extraction slice:

- Keep public imports stable through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported names must remain
  importable from accepted public paths.
- Keep `boundary.py` as the public facade/coordinator around accepted lowering
  functions and normal pipeline integration.
- Create private generation-time lowering modules:
  `tslgen.lowering._generation_models`,
  `tslgen.lowering._generation_queries`,
  `tslgen.lowering._generation_control_flow`, and
  `tslgen.lowering._generation_diagnostics`.
- Move accepted generation-time model ownership where it can remain
  import-stable, including `GenerationTypeRef`, `GenerationValue`,
  `GenerationPredicate`, `GenerationExpressionRecognition`,
  `PrunedGenerationBranch`, `GenerationSizeByteBranchChainArm`,
  `GenerationSizeByteBranchChainPruning`,
  `TsilPrimitiveAttributeCondition`, and `TsilTypeSignednessCondition`.
- Move accepted generation helper parsing/resolution support where it can move
  without importing `boundary.py`, including exact generation type/value/
  predicate query parsing, `base.in`, signed/unsigned companion, scalar
  `type.size_bytes` / `type.size_bits`, exact size-byte equality predicate,
  primitive-attribute condition, signedness condition, generation `if` /
  plain-else / size-byte branch-chain parsing, and related diagnostics.
- Use narrow private protocols only where moved helpers need context-like or
  item-like values that remain facade-owned. Prefer leaving a helper in
  `boundary.py` over making a private module import `boundary.py`, duplicating
  ownership, or broadening protocols.
- Keep source adapters and orchestration that still depend on
  `LoweringInput`, `LoweringRequest`, `LoweredImplementation`,
  `GenerationLoweringStage`, candidate selection, or the exact array-body
  pipeline in `boundary.py` unless a tiny delegation move is required and
  remains behavior-preserving.
- Add or preserve focused private-import-boundary regression coverage proving
  the new generation private modules and accepted private lowering modules do
  not import `boundary.py`, including common absolute and relative import
  forms.
- Preserve accepted M42-M80 diagnostics, diagnostic codes/severity/source
  locations/messages, selected-branch-only diagnostics, stage names, stage
  ordering, output identities, keys, deterministic ordering, public imports,
  and no-external-input boundaries.
- Preserve private-module import direction. Private modules such as
  `_generation_models.py`, `_generation_queries.py`,
  `_generation_control_flow.py`, `_generation_diagnostics.py`,
  `_array_body_models.py`, `_array_body_shapes.py`,
  `_array_body_diagnostics.py`, `_array_body_validation.py`,
  `_exact_shapes.py`, and `_pipeline.py` must not import `boundary.py`.

## Out Of Scope

- New lowering semantics, new generation helper evaluation, new semantic
  output values, new stage behavior, new generation helper families, broad
  `type<generation>` / `value<generation>` / `type<backend>` /
  `value<backend>` evaluation, exact return-emission IR, store semantics,
  return semantics, memory behavior, pointer semantics, variable
  scope/use-def/lifetime, declaration/array semantics, initializer behavior,
  `tmp.data()` semantics, `emit_return`, `assume_aligned`, ARM/SVE predicate/
  vector/register/intrinsic semantics, byte-size-to-token inference,
  source-operand semantics, or generated output.
- Moving `LoweredImplementation`, `GenerationLoweringStage`,
  `GenerationContext`, `LoweringRequest`, `lower_candidates`, the full exact
  array-body stage coordinator, or source adapters that consume
  `GenerationLoweringStage` / `LoweredImplementation`, unless a tiny
  dependency move is required and remains behavior-preserving.
- Moving mini-TSIL return lowering, broad assignment, variable, declaration,
  array, call, cast, loop, store, return, or multi-statement body lowering;
  broad direct `intrin<...>` semantics; broad vector metadata semantics;
  generic body/call/store/return/declaration/array IR; broad TSIL parsing;
  raw helper dispatch; registry, dispatcher, plugin, or fixpoint/backfeed
  engine work.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M82.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

Also run a focused M81 generation-core/import-stability command selected by
the executor. The command must be named in the final report.

Then run:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final report must record the new `boundary.py` line count and whether it
is 5,808 lines or lower, or explain why an import-boundary risk justified a
narrower accepted reduction.

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M81 stayed behavior-preserving and did not add
   helper evaluation, raw helper dispatch, backend translation, rendering,
   generated output, broad parsing, source-adapter behavior, stage-construction
   frameworks, file/catalog reads, `tsldata` reads, host CPU queries, backend
   map reads, or runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the generation-core
   extraction is a typed private ownership boundary, import-stable, and avoids
   broad registries, semantic dispatchers, runtime plugin systems, hidden
   recursive backfeeds, circular imports, broad class hierarchies, and
   hardwired extension semantics.
4. Validation auditor: review the validation commands, line-count result,
   focused M81 generation-core/import-stability command, and failures, if any.
5. Documentation auditor: verify roadmap, architecture, pipeline, semantic
   lowering, behavioral spec, testing, and state docs match the implemented
   M81 generation-core ownership boundary and measured line-count result.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. Do not start M82. The likely next prompt is a
post-M81 lowering-focused planning-plus-review prompt unless review records a
different accepted next action or stop condition.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. `boundary.py` line-count result and whether it meets the M81 threshold.
4. Validation commands and exact results.
5. Review/audit verdicts.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. Whether M81 is accepted or what blocks acceptance.
