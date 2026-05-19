# M79 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 79: Exact Array-Body Typed Model Ownership Extraction Slice
```

Milestones 1 through 78 are accepted. Post-M78 planning is accepted. M79 is the
active executor milestone.

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
- `tslgen/src/tslgen/lowering/_array_body_shapes.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted exact array-body / array-initialization typed model ownership into
private lowering modules while preserving all accepted M57-M78 behavior.

M79 is behavior-preserving typed model ownership extraction only. It must not
add new lowering semantics, helper evaluation, stage behavior, backend
translation, rendering, generated output, broad parsing, file/catalog reads,
or hardwired extension semantics.

The post-M78 `boundary.py` baseline is 11,109 physical lines. M79 should
reduce that file by at least 1,500 physical lines, so the post-M79 count
should be 9,609 physical lines or lower, unless the executor documents that an
import-boundary risk requires a narrower accepted reduction. Do not satisfy
the line-count target by moving unrelated shared models, leaving duplicate
moved code behind, or recreating `boundary.py` as a second monolith.

## Executor Task

Use exactly one write-capable executor for implementation. If M79 is already
implemented and only awaiting review, skip implementation and run the
read-only review/audit workflow instead.

Implement one coherent behavior-preserving model ownership extraction slice:

- Keep public imports stable through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported names must remain
  importable from accepted public paths.
- Keep `boundary.py` as the public facade/coordinator around accepted lowering
  functions and normal pipeline integration.
- Create a private exact array-body model boundary such as
  `tslgen.lowering._array_body_models`, or an equivalent coherent private
  module split, for exact-package typed aliases, dataclasses, and tiny
  protocols that are exclusively consumed by the exact M63-M78 array-body /
  array-initialization path.
- Consolidate duplicated exact helper `Literal` aliases currently split
  between `boundary.py` and `_array_body_shapes.py` into one private typed
  ownership location consumed by both modules.
- Move exact array-body / array-initialization typed IR/value models only when
  they can move without making a private module import `boundary.py`.
  Candidate model ownership includes exact envelope slots, unresolved helper
  leaves, helper request records, base/vector/backend request-resolution
  values, declaration-shell values, structural sequence values,
  predicate-path request values, and post-branch call-site request values.
- Replace targeted `_array_body_diagnostics.py` `Any` helper inputs only where
  the new model/protocol boundary supplies a local typed replacement.
  Diagnostics may use small private protocols for source-location, field-name,
  kind, and source-text access instead of importing `boundary.py`.
- Preserve accepted M57-M78 diagnostics, diagnostic codes/severity/source
  locations/messages, stage names, stage ordering, output identities, keys,
  deterministic ordering, selected-branch-only diagnostics, public imports,
  and no-external-input boundaries.
- Preserve the M78 private-module import direction. Private modules such as
  `_array_body_models.py`, `_array_body_shapes.py`,
  `_array_body_diagnostics.py`, `_exact_shapes.py`, and `_pipeline.py` must not
  import `boundary.py`.
- Keep exact recognizer tokens such as `svbool_t`, `pg`, `svptrue_b8`,
  `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `intrin`, `svst1`,
  `tmp.data()`, and `a` as structural evidence only.
- Update redesign docs to record the model ownership boundary and measured
  `boundary.py` line-count result.

## Out Of Scope

- New lowering semantics, new generation helper evaluation, new semantic
  output values, new stage behavior, or generated output.
- Whole-file rewrite of `boundary.py`, moving unrelated shared generation
  models, broad OO hierarchy, broad model hierarchy, generic body model,
  stage/helper/slot registry, semantic dispatcher, runtime plugin system,
  hidden recursive backfeeds, or fixpoint execution.
- Moving the full exact array-body stage coordinator, source-adapter cluster,
  validator cluster, or `_pipeline.py` payload/backfeed model unless a small
  dependency move is necessary for the model boundary and remains private.
- Store semantics, return semantics, memory behavior, pointer semantics,
  variable scope/use-def/lifetime, declaration/array semantics beyond accepted
  exact structural IR, initializer behavior, `tmp.data()` semantics,
  `emit_return`, `assume_aligned`, ARM/SVE predicate/vector/register/intrinsic
  semantics, byte-size-to-token inference, or source-operand semantics.
- Generic call IR, generic store IR, generic return IR, broad body IR, broad
  declaration/array/body/call/store/return parsing, raw helper-string
  dispatch, raw TSIL expression evaluation, generic call parsing, generic body
  parsing, or broad TSIL parsing.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M80.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_shapes.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_exact_shapes.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

Also run a focused M79 model-ownership/import-stability command selected by
the executor. The command must be named in the final report.

Then run:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final report must record the new `boundary.py` line count and whether it
is 9,609 lines or lower, or explain why an import-boundary risk justified a
narrower accepted reduction.

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M79 stayed behavior-preserving and did not add
   backend translation, rendering, generated output, broad parsing, generic
   body/call/store/return/declaration/array semantics, raw helper dispatch,
   helper evaluation, file/catalog reads, `tsldata` reads, host CPU queries,
   backend map reads, or runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the model extraction is one
   typed ownership boundary, private, coherent, import-stable, and avoids
   broad registries, semantic dispatchers, runtime plugin systems, hidden
   recursive backfeeds, circular imports, broad class hierarchies, and
   hardwired extension semantics.
4. Validation auditor: review the validation commands, line-count result,
   focused M79 model-ownership/import-stability command, and failures, if any.
5. Documentation auditor: verify roadmap, architecture, pipeline, semantic
   lowering, behavioral spec, testing, and state docs match the implemented
   M79 model ownership boundary and measured line-count result.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. Do not start M80. The likely next prompt is a
post-M79 lowering-focused planning-plus-review prompt unless review records a
different accepted next action or stop condition.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. `boundary.py` line-count result and whether it meets the M79 threshold.
4. Validation commands and exact results.
5. Review/audit verdicts.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. Whether M79 is accepted or what blocks acceptance.
