# M77 Execution Review Loop Prompt

You are executing and reviewing:

```text
Milestone 77: Composable Lowering Pipeline Module Boundary Slice
```

Milestones 1 through 76 are accepted. Post-M76 planning is accepted. M77 is the
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
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Milestone Goal

Make Stage 8 lowering more maintainable and extensible by introducing a
behavior-preserving, private composable pipeline/module boundary under
`tslgen/src/tslgen/lowering/`.

M77 starts breaking the large lowering boundary apart around accepted M58-M76
stage contracts without adding new lowering semantics, backend behavior,
rendering, generated output, broad parsing, or hardwired extension semantics.

The design should reflect lowering as a staged typed pipeline. Future
backfeeds must be represented as typed facts, typed requests, dependencies, or
deterministic coordinator decisions. Do not implement them as hidden recursive
stage calls, broad registries, raw helper dispatch, or central semantic
`if`/`elif` chains.

## Executor Task

Use exactly one write-capable executor for implementation.

Implement one coherent behavior-preserving extraction/refactor slice:

- Keep the public lowering API stable through `tslgen.lowering` and any
  existing `boundary.py` facade imports used by tests or downstream code.
- Introduce private typed pipeline/module contracts only where they are
  concretely needed by the accepted M58-M76 pattern. Acceptable concepts
  include stage input, stage output, artifact/fact store, stage dependency, or
  deferred request, provided they are typed values and not a broad runtime
  plugin system.
- Move one coherent cluster of Stage 8 lowering implementation out of the
  monolithic `boundary.py` into one or more modules under
  `tslgen/src/tslgen/lowering/`. Prefer the accepted exact array-body /
  array-initialization stage assembly and exact structural/request helpers if
  that is the smallest safe cluster that proves the boundary.
- Preserve all accepted M57-M76 stage names, outputs, diagnostics,
  deterministic ordering, public typed boundary values, and selected-branch
  diagnostics.
- Keep exact-shape recognizer constants slice-local. Tokens such as `pg`,
  `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `intrin`, `svst1`,
  `tmp.data()`, and `a` may remain exact structural evidence for accepted
  slices, but they must not become extension semantics, SVE semantics, store
  semantics, memory semantics, or backend dispatch keys.
- Reduce or isolate the growing `GenerationLoweringStage.__post_init__`
  validation-table pressure only if it can be done while preserving typed
  stage-specific attachment points. Do not replace it with an untyped
  registry, raw dispatcher, or semantic lookup keyed by strings.
- Update redesign docs if the private module/pipeline boundary decision
  becomes more precise during execution.

## Out Of Scope

- New lowering semantics or generated behavior.
- Whole-file rewrite of `boundary.py` or broad OO redesign.
- Store semantics, return semantics, memory behavior, pointer semantics,
  variable scope/use-def/lifetime, declaration/array semantics, initializer
  behavior, `tmp.data()` semantics, `emit_return`, `assume_aligned`, ARM/SVE
  predicate/vector/register/intrinsic semantics, or byte-size-to-token
  inference.
- Generic call IR, generic store IR, generic return IR, broad body IR, broad
  slot-role registries, broad helper registries, broad stage registries,
  central semantic dispatchers, runtime plugin systems, raw helper-string
  dispatch, raw TSIL expression evaluation, generic call parsing, generic body
  parsing, or broad TSIL parsing.
- Backend manifests, backend maps, language maps, translation maps, backend
  translation requests, renderer-ready IR, generated artifacts, golden files,
  generated tests, CLI/report/writer behavior, Rust behavior, compiler
  execution, generated-test execution, lowering-time file/catalog reads,
  `tsldata` reads during lowering evaluation, host CPU queries, backend map
  reads, or runtime dependency on `frozen/`.
- Starting M78.

## Required Validation

Run:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
```

Also run a focused M77 module-boundary/import-preservation command selected by
the executor. The command must be named in the final report.

Then run:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Required Subagent Workflow

After the single write-capable executor finishes and validation has been run,
use read-only review/audit subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M77 stayed behavior-preserving and did not add
   backend translation, rendering, generated output, broad parsing, generic
   call/body/store/return semantics, raw helper dispatch, file/catalog reads,
   `tsldata` reads, host CPU queries, backend map reads, or runtime `frozen/`.
3. Extensibility/maintainability auditor: verify the new module/pipeline
   boundary is typed, private, composable, and avoids broad registries,
   semantic dispatchers, runtime plugin systems, hidden recursive backfeeds,
   and hardwired extension semantics.
4. Validation auditor: review the validation commands and failures, if any.
5. Documentation auditor: verify roadmap, architecture, pipeline, testing, and
   state docs match the implemented M77 boundary.

If review returns `Needs Revision`, run one focused revision executor limited
to the blocking issues, then run focused re-review.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md` and create the next concrete prompt
under `docs/agent/runs/`. If human acceptance is required by local policy,
create a post-M77 acceptance-finalization prompt rather than directly starting
M78.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Validation commands and exact results.
4. Review/audit verdicts.
5. Follow-ups recorded, if any.
6. Next prompt created.
7. Whether M77 is accepted or what blocks acceptance.
