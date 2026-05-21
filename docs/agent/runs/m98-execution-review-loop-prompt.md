# M98 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 98.

Milestones 1 through 97 are accepted. Post-M97 planning is accepted and
selected:

```text
Milestone 98: Stage 8 Lowering Stage-Assembly Ownership Extraction Slice
```

Use the orchestrated executor-review loop in this prompt. M98 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M98 planning until M98 review returns
`Accept` or `Accept With Follow-Ups`.

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
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Extract accepted Stage 8 stage construction and per-candidate Stage 8 result
assembly from `boundary.py` into a focused private stage-assembly module while
preserving all accepted M57-M97 behavior.

M98 is behavior-preserving architecture work. It is not a semantic lowering
milestone. It should make future lowering slices safer by reducing
`boundary.py` pressure without creating a replacement monolith.

## Scope

- Add focused private ownership, preferably
  `tslgen.lowering._lowering_stage_assembly`.
- The new module owns only:
  - accepted `GenerationLoweringStage` construction helpers;
  - per-candidate Stage 8 result assembly for the accepted
    operation-package, completion-manifest, and completion-gap-inventory tail.
- Move accepted stage helper construction out of `boundary.py` for existing
  stages such as recognition, typed generation values/predicates,
  generation-control-flow pruning, selected-body lowering, selected-body form/
  IR/envelope lowering, lowering operation packages, completion manifests, and
  completion gap inventories.
- Extract the repeated accepted operation-package -> completion-manifest ->
  completion-gap-inventory tail assembly into a narrow typed helper/result.
- Preserve `LoweringRequest`, `LoweredImplementation`, `LoweringPlan`, public
  imports, accepted diagnostics, accepted stage names, stage ordering, stage
  keys, deterministic ordering, output identities, source locations, and
  object identity behavior.
- Keep `boundary.py` as the public facade and owner for request/result models,
  `lower_candidates`, and `_lower_input` unless a tiny helper move is
  explicitly necessary for the selected stage-assembly extraction.
- Keep `_operation_package_sources.py` unchanged.

## Out Of Scope

- New lowering semantics, new generation-time helper forms, new
  operation-package families, broad TSIL/body parsing, raw body parsing,
  source-body repair, or best-effort source correction.
- Backend translation, backend map/catalog reads, backend-uninit resolution,
  backend support decisions, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, dependency solving, renderer-ready IR,
  rendering, generated output, generated tests, Rust, CLI/report/writer
  behavior, or compiler execution.
- Registries, dispatchers, callback maps, plugin systems, broad source
  protocols, hidden backfeeds, fixpoint machinery, operation DAGs, or
  dependency-closure graphs.
- Moving public request/result model ownership, changing public facade exports,
  or making the new module import `boundary.py`, the `tslgen.lowering` facade,
  backend modules, renderers, `tsldata`, or `frozen`.
- Treating `GenerationLoweringStage` construction as a broad dynamic stage
  registry, plugin system, source dispatcher, semantic router, backfeed, or
  fixpoint coordinator.

## Required Inputs

- Accepted M57-M97 lowering stage behavior, diagnostics, stage names, stage
  ordering, deterministic keys, output identities, selected-branch-only
  diagnostics, public imports, and no-external-input boundaries.
- Accepted M96 completion manifest and M97 completion gap inventory behavior
  and object-identity contracts.
- Current line-count pressure points after M97:
  - `tslgen/src/tslgen/lowering/boundary.py`: 1,285 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package_sources.py`: 819 physical
    lines.

## Expected Outputs

- A focused private stage-assembly module, preferably
  `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`, below the
  module-size guardrail.
- `boundary.py` reduced or at minimum kept at or below its M97 line count
  while continuing to act as the public facade.
- `_operation_package_sources.py` unchanged.
- Behavior-preserving stage construction for all accepted M57-M97 stage facts.
- Behavior-preserving per-candidate completion-tail assembly for accepted
  operation packages, completion manifests, and completion gap inventories.
- Import-boundary and line-count guardrails proving the new module is not a
  replacement monolith.

## Required Executor Task

Run exactly one write-capable executor for M98. The executor should:

1. Implement the behavior-preserving Stage 8 stage-assembly ownership
   extraction described above.
2. Add focused private ownership, preferably in
   `tslgen.lowering._lowering_stage_assembly`.
3. Move only accepted stage-construction helpers and accepted per-candidate
   completion-tail assembly out of `boundary.py`.
4. Preserve `boundary.py` as the public facade and owner of request/result
   models, `lower_candidates`, and `_lower_input` unless a tiny helper move is
   explicitly necessary for the stage-assembly extraction.
5. Keep `_operation_package_sources.py` unchanged.
6. Preserve accepted M57-M97 diagnostics, stage names, stage ordering, stage
   keys, deterministic ordering, output identities, object identities,
   selected-branch-only diagnostics, public imports, and no-external-input
   boundaries.
7. Add focused tests for stage-construction parity, per-candidate completion
   tail assembly, mini-TSIL and exact-array pipeline parity, object-identity
   preservation, deterministic keys/order, public import stability, import
   boundaries, line-count guardrails, and forbidden behaviors.
8. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   raw-body parsing, broad-body-semantics, broad-protocol, registry/
   dispatcher, scheduler, dependency-solver, hidden-backfeed, fixpoint, and
   hardwiring behavior.
9. Run the required validation commands below.
10. Return a concise implementation summary, files changed, validation
    results, line counts, and any follow-ups.

## Required Tests

- Stage-construction parity tests proving stage names, outputs, output
  identities, stage keys, and ordering match accepted pre-M98 behavior.
- Mini-TSIL and exact-array path parity tests proving the operation-package ->
  completion-manifest -> completion-gap-inventory tail remains unchanged.
- Tests proving M96 package/manifest and M97 gap-inventory object identities
  are preserved across the extracted assembly helper.
- Determinism tests for repeated lowering, stage keys, lowered implementation
  keys, and reordered accepted inputs where applicable.
- Public import stability tests for the accepted `tslgen.lowering` and
  `tslgen.lowering.boundary` surfaces.
- Import-boundary tests proving the new module does not import `boundary.py`,
  the `tslgen.lowering` package facade, backend modules, renderers, `tsldata`,
  or `frozen`.
- Line-count tests requiring `boundary.py <= 1285`,
  `_operation_package_sources.py <= 819`, and the new stage-assembly module
  below the module-size guardrail.
- Negative assertions proving M98 introduces no backend maps/catalog reads,
  backend-uninit resolution, Stage 9 planning, renderer-ready IR,
  rendering/output, source repair, raw body parsing, registries, dispatchers,
  schedulers, hidden backfeeds, fixpoint behavior, or hardwiring.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m98 or stage_assembly or completion_manifest or completion_gap_inventory or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private module name, include
that file consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M98 is behavior-preserving Stage 8 lowering
   stage-assembly/result-assembly ownership only and does not add raw body
   text parsing, source repair, new lowering semantics, backend resolution,
   backend maps/catalog reads, Stage 9 planning, backend translation,
   renderer-ready IR, rendering, generated output, broad TSIL/body semantics,
   registries/dispatchers, hidden backfeeds, fixpoint behavior, scheduling,
   dependency solving, or hardwiring.
3. Extensibility auditor: verify the extracted module is cohesive and narrow,
   does not become a replacement monolith, keeps one-way imports where
   practical, does not import `boundary.py` or the package facade, keeps
   `boundary.py <= 1285`, keeps `_operation_package_sources.py` unchanged and
   `<= 819`, and remains compatible with a composable lowering pipeline.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M98 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M97 pending-acceptance wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue.

If review returns `Reject`, stop implementation and create a rollback/redesign
prompt under `docs/agent/runs/`.

If review returns `Accept` or `Accept With Follow-Ups`, update
`docs/agent/current-redesign-state.md`, update relevant redesign docs, and
create the next concrete prompt under `docs/agent/runs/`. Do not mark M98
accepted until this internal review result is reached.

## Finalization Rules

When M98 is accepted internally:

- mark M98 accepted in `docs/agent/current-redesign-state.md`;
- update relevant redesign docs with implementation results, validation
  results, and any follow-ups;
- create the next concrete prompt under `docs/agent/runs/`, likely
  `post-m98-planning-plus-review-prompt.md`;
- keep the next task focused on lowering unless review returns
  `Return To Planner`, `Reject`, or a stop condition.

Do not start Milestone 99 in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
