# M78 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 78: Lowering Boundary Package Decomposition Slice
```

Milestones 1 through 77 are accepted. Post-M77 planning is accepted. M78 is the
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
- `docs/redesign/open-questions.md`
- `docs/redesign/frozen-parity-baselines.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Materially reduce `tslgen/src/tslgen/lowering/boundary.py` by moving the
accepted exact array-body / array-initialization lowering package behind
private, typed modules under `tslgen/src/tslgen/lowering/`, while preserving
all accepted M57-M77 behavior.

M78 is behavior-preserving package decomposition only. It must not add new
lowering semantics, backend translation, rendering, generated output, broad
parsing, file/catalog reads, or hardwired extension semantics.

The pre-M78 `boundary.py` baseline is 12,371 physical lines. M78 must reduce
that file by at least 1,000 physical lines, so the post-M78 count must be
11,371 physical lines or lower. Do not satisfy this by leaving duplicate moved
code behind.

## Executor Task

Use exactly one write-capable executor for implementation. If M78 is already
implemented and only awaiting review, skip implementation and run the
read-only review/audit workflow instead.

Implement one coherent behavior-preserving decomposition slice:

- Keep public imports stable through `tslgen.lowering` and the existing
  `tslgen.lowering.boundary` facade. Existing exported names must remain
  importable from accepted public paths.
- Extract one coherent private package area: the accepted exact array-body /
  array-initialization lowering tail from M63-M77.
- Prefer private modules with narrow ownership, such as
  `_array_body_pipeline.py`, `_array_body_models.py`,
  `_array_body_sources.py`, or `_array_body_diagnostics.py`, if those names fit
  the implementation. Do not create a broad framework.
- Move only code owned by the exact array-body / array-initialization package,
  such as exact array-body envelope slot/skeleton assembly, exact
  array-initialization slot/helper/base-type/vector-length/vector-alignment/
  helper-set/declaration-shell orchestration, exact structural sequence,
  predicate-path, post-branch call-site structural/request orchestration,
  pipeline result/snapshot integration, stage builders, source adapters,
  validators, and diagnostics that are used only by this path or are required
  for a coherent private boundary.
- Move remaining M75 exact predicate-init recognizer tokens such as
  `svbool_t`, `pg`, and `svptrue_b8` into `_exact_shapes.py` as slice-local
  structural evidence only.
- Leave shared helpers in `boundary.py` unless moving a small shared value is
  necessary for the coherent extraction and the public facade continues to
  re-export it.
- Avoid circular imports. New private modules should depend on explicit typed
  inputs and moved shared values, not broad imports from `boundary.py` that
  recreate the monolith indirectly.
- Preserve accepted M57-M77 diagnostics, stage names, stage ordering, output
  identities, keys, deterministic ordering, selected-branch-only diagnostics,
  public imports, and no-external-input boundaries.
- Preserve M77's private `_pipeline.py` fact/dependency snapshot behavior with
  no pending backfeeds. Tighten `_pipeline.py` typing or request identity only
  if directly required by the decomposition.
- Update redesign docs to record the decomposition boundary and measured
  `boundary.py` line-count result.

## Out Of Scope

- New lowering semantics or generated behavior.
- Whole-file rewrite of `boundary.py`, broad OO class hierarchy, migration map
  from legacy modules, runtime plugin system, broad stage/helper/slot registry,
  generic semantic dispatcher, hidden recursive backfeeds, or generic
  fixpoint/backfeed execution.
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
- Starting M79.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

Also run a focused M78 module-decomposition/import-stability command selected
by the executor. The command must be named in the final report.

Then run:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

The final report must record the new `boundary.py` line count and whether it
is 11,371 lines or lower.

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M78 stayed behavior-preserving and did not add
   backend translation, rendering, generated output, broad parsing, generic
   body/call/store/return/declaration/array semantics, raw helper dispatch,
   file/catalog reads, `tsldata` reads, host CPU queries, backend map reads, or
   runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the decomposition is typed,
   private, coherent, import-stable, and avoids broad registries, semantic
   dispatchers, runtime plugin systems, hidden recursive backfeeds, circular
   imports, broad class hierarchies, and hardwired extension semantics.
4. Validation auditor: review the validation commands, line-count result, and
   failures, if any.
5. Documentation auditor: verify roadmap, architecture, pipeline, semantic
   lowering, testing, and state docs match the implemented M78 decomposition.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. Do not start M79. The likely next prompt is a
post-M78 lowering-focused planning-plus-review prompt unless review records a
different accepted next action or stop condition.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. `boundary.py` line-count result and whether it meets the M78 threshold.
4. Validation commands and exact results.
5. Review/audit verdicts.
6. Follow-ups recorded, if any.
7. Next prompt created.
8. Whether M78 is accepted or what blocks acceptance.
