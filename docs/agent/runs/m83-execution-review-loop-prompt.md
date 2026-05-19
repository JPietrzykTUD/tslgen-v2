# M83 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 83: GenerationLoweringStage Output Contract Extraction Slice
```

Milestones 1 through 82 are accepted. Post-M82 planning is accepted. Human
acceptance was recorded. M83 is the active executor milestone.

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
- `tslgen/src/tslgen/lowering/_selected_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Move the accepted generation lowering stage-name/output validation contract out
of `tslgen/src/tslgen/lowering/boundary.py` into a private typed lowering
module while preserving all accepted M42-M82 behavior, public import paths,
stage names, stage ordering, output identities, deterministic keys,
diagnostics, pipeline snapshots, and no-external-input boundaries.

M83 is behavior-preserving lowering architecture work only. It must make the
staged lowering pipeline easier to extend by extracting contract validation,
not by adding stage execution dispatch, a registry, a plugin system, a
fixpoint/backfeed engine, source adapters, or new semantic lowering behavior.

The accepted M82 `boundary.py` baseline is 4,965 physical lines. M83 should
reduce that file while keeping the extraction coherent. Do not use line-count
reduction to justify moving unrelated exact array-body code, generation-helper
code, selected-body code, source adapters, pipeline execution, or
lower-candidate orchestration. The final report must record the new line count
and explain the selected stage-contract ownership boundary.

## Executor Task

Use exactly one write-capable executor for implementation. If M83 is already
implemented and only awaiting review, skip implementation and run the
read-only review/audit workflow instead.

Implement one coherent behavior-preserving stage output-contract ownership
extraction slice:

- Create a private typed stage-contract module such as
  `tslgen.lowering._stage_contracts`, or an equivalent coherent private
  lowering module.
- Move or own the stage contract data currently encoded by
  `GenerationLoweringStage.__post_init__`, including the accepted mapping from
  each `GenerationLoweringStageName` to the allowed output model type or types.
- Preserve public imports through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported stage names and stage
  model names must remain importable from accepted public paths.
- Preserve the existing public `GenerationLoweringStage` behavior:
  stage names, stage ordering, output object identity, deterministic `key`
  behavior, invalid-stage `ValueError`, invalid-output `TypeError`, and message
  shape.
- Keep `boundary.py` as the public facade/coordinator for lowering requests,
  candidate/source adapters, `LoweredImplementation`, `LoweringInput`,
  `LoweringRequest`, lower-candidate orchestration, and existing stage
  construction unless a tiny dependency move is required to avoid an import
  cycle.
- If the stage-output union depends on mini-TSIL statement value models in a
  way that blocks import-safe extraction, move only the minimal mini-TSIL
  value-model cluster needed by the contract. Do not move mini-TSIL parsing or
  broad statement/body semantics.
- Preserve accepted M42-M82 diagnostics, diagnostic codes/severity/source
  locations/messages, selected-branch-only diagnostics, stage names, stage
  ordering, output identities, keys, deterministic ordering, public imports,
  and no-external-input boundaries.
- Preserve private-module import direction. The new stage-contract private
  module and existing private lowering modules must not import `boundary.py`
  or the `tslgen.lowering` package facade.
- Add or preserve focused private-import-boundary regression coverage proving
  the new stage-contract private module and accepted private lowering modules
  do not import `boundary.py` or the `tslgen.lowering` package facade,
  including common absolute and relative import forms.

## Out Of Scope

- New stage names, new stage ordering, new stage outputs, new diagnostics, new
  lowering semantics, exact return-emission IR, store/call/body/return
  semantics, broad TSIL parsing, generic body/call/store/return/declaration/
  array IR, generic source adapters, source skeleton recognition, helper
  evaluation, broad generation helper families, raw helper dispatch, semantic
  dispatchers, registries, runtime plugins, hidden backfeed, fixpoint/backfeed
  execution, or broad pipeline payload rewrites.
- Moving `LoweredImplementation`, `LoweringInput`, `LoweringRequest`,
  `lower_candidates`, source adapters, exact array-body pipeline coordination,
  selected-body lowering functions, generation query/control-flow functions,
  or backend/rendering/output-facing behavior.
- Interpreting `emit_return`, `tmp`, `tmp.data()`, `svst1`, `pg`, SVE-looking
  tokens, selected type tags, backend ids, renderer names, or corpus line
  numbers as semantic dispatch keys.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, extension hardwiring, or runtime dependency on `frozen/`.
- Starting M84.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m83 or stage_contract or generation_lowering_stage"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If the executor chooses a different private module name than
`_stage_contracts.py`, update the py-compile command accordingly and explain
the choice in the final report.

The final report must record the new `boundary.py` line count, whether it is
below the 4,965-line accepted M82 baseline, and any reason an import-boundary
risk required a narrower accepted reduction.

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M83 stayed behavior-preserving and did not add
   new stage behavior, exact return-emission IR, store/call/body/return
   semantics, raw helper dispatch, backend translation, rendering, generated
   output, broad parsing, source-adapter behavior, file/catalog reads,
   `tsldata` reads, host CPU queries, backend map reads, extension hardwiring,
   or runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the stage-contract extraction
   is a typed private ownership boundary, import-stable, and avoids broad
   registries, semantic dispatchers, runtime plugin systems, hidden recursive
   backfeeds, circular imports, broad class hierarchies, duplicate moved code,
   and hardwired extension semantics.
4. Validation auditor: review the validation commands, line-count result,
   focused M83 stage-contract/import-stability command, and failures, if any.
5. Documentation auditor: verify roadmap, architecture, pipeline, semantic
   lowering, behavioral spec, testing, and state docs match the implemented
   M83 stage-contract ownership boundary and measured line-count result.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. Do not start M84. The likely next prompt is a
post-M83 lowering-focused planning-plus-review prompt unless review records a
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
8. Whether M83 is accepted or what blocks acceptance.
