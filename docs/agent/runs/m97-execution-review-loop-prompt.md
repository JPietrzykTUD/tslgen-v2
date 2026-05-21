# M97 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 97.

Milestones 1 through 96 are accepted. Post-M96 planning is accepted and
selected:

```text
Milestone 97: Lowering Completion Gap Inventory Slice
```

Use the orchestrated executor-review loop in this prompt. M97 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M97 planning until M97 review returns
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
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Create one typed Stage 8 lowering-owned gap inventory over accepted M96
completion manifests.

M97 turns "what is still unresolved for lowering?" into explicit typed
inventory/provenance data without starting backend planning, resolving backend
values, repairing source bodies, parsing raw body text, or inferring broad
body semantics.

For M97, a "gap" means only a lowering-observed deferred or unsupported fact
visible from accepted M96 manifest facts. The initial supported gap is the
accepted unresolved backend-handoff dependency record preserved by M96. A
manifest without such records produces a deterministic no-known-gap inventory.

## Scope

- Add focused private lowering ownership, such as
  `tslgen.lowering._lowering_completion_gap_inventory`, for gap-inventory
  models, diagnostics, validation, and assembly.
- Use a narrowly named typed output model such as
  `Stage8LoweringCompletionGapInventoryIr`.
- Consume accepted M96 `Stage8LoweringCompletionManifestIr` values as the
  primary input.
- May accept `lowering_completion_manifest` stages or a narrow
  one-manifest container as source forms.
- Support only current accepted M96 manifest facts:
  - no-known-gap manifests;
  - accepted unresolved backend-handoff dependency records.
- Preserve source manifest, package record, package object, unresolved
  dependency record, source dependency request, candidate id, source
  locations, and deterministic keys by object identity where identity is the
  contract.
- Add one deterministic Stage 8 stage, such as
  `lowering_completion_gap_inventory`, after accepted
  `lowering_completion_manifest` facts only if the implementation preserves
  `boundary.py` at or below the 1,300-line guardrail.
- If stage integration would grow `boundary.py` beyond 1,300 lines, perform a
  behavior-preserving extraction first or keep M97 module-only and report
  stage integration as a follow-up.
- Keep `_operation_package_sources.py` unchanged. M97 consumes M96 manifests;
  it must not add another operation-package source family or source-router
  branch.

## Out Of Scope

- Backend translation, backend map/catalog reads, backend-uninit resolution,
  backend support decisions, Stage 9 backend planning, operation scheduling,
  primitive dependency closure, dependency solving, renderer-ready IR,
  rendering, generated output, generated tests, CLI/report/writer behavior,
  compiler execution, or Rust.
- New operation-package source families, package-family registries, semantic
  dispatchers, callback maps, plugin systems, hidden recursive backfeeds,
  fixpoint machinery, dependency-closure graphs, operation DAGs, broad source
  protocols, or broad source adapters.
- Re-entering raw M86 statements, M92 handoff assembly, M63 envelopes, M90/M89/
  M72/M67 provenance chains, raw body text, source-body repair, broad
  TSIL/body parsing, direct-intrinsic/SVE semantics, byte-size-to-token
  inference, declaration/array/store/return/body semantics, or broad
  `value<backend>(...)` evaluation.
- Treating `svptrue_b*`, `pg`, selected literals, type tags, primitive names,
  extension ids, backend ids, source locations, package-family tags, or
  manifest-state strings as semantic dispatch keys.
- Treating a gap inventory as backend readiness, renderer readiness, semantic
  body completion, dependency closure, operation scheduling, output readiness,
  backend plan, renderer IR, wrapper plan, artifact plan, registry,
  dispatcher, backfeed, or fixpoint mechanism.

## Required Inputs

- Accepted M96 `Stage8LoweringCompletionManifestIr` behavior, diagnostics,
  object-identity preservation, deterministic keys, private-module import
  boundary, and stage-contract integration.
- Accepted M96 unresolved dependency manifest records for M92/M90 backend
  handoff provenance.
- Current line-count pressure points:
  - `tslgen/src/tslgen/lowering/boundary.py`: 1,300 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package_sources.py`: 819 physical
    lines.

## Expected Outputs

- A typed Stage 8 lowering completion gap inventory per accepted manifest.
- A no-known-gap inventory state for manifests without explicit unresolved
  dependency records.
- Gap records for accepted unresolved backend-handoff dependencies that
  preserve M96 object references without resolving them.
- Diagnostics for unsupported sources, missing manifests, multiple manifests,
  wrong stage/order, malformed manifests, candidate/source-location mismatch,
  and copied/equal-but-not-identical manifest/package/dependency records.
- Import-boundary and line-count guardrails proving the new private module
  does not become a replacement monolith and pressure-point modules do not
  grow.

## Required Executor Task

Run exactly one write-capable executor for M97. The executor should:

1. Implement the Stage 8 lowering completion gap inventory described above.
2. Add focused private ownership, preferably in
   `tslgen.lowering._lowering_completion_gap_inventory`; split only if one
   file would mix too many responsibilities or approach the module-size
   guardrail.
3. Consume accepted M96 `Stage8LoweringCompletionManifestIr` values as the
   primary input, not raw source text, operation-package source adapters,
   backend maps, catalog data, renderer data, or generated output.
4. Keep `_operation_package_sources.py` unchanged.
5. Preserve accepted M86/M92/M95 package behavior and accepted M96 manifest
   behavior exactly.
6. Preserve source manifest, package record, package object, unresolved
   dependency record, source dependency request, candidate id, source
   locations, deterministic ordering, keys, object identities, and no-external
   input boundaries.
7. Add focused tests for positive inventory construction, no-known-gap state,
   unresolved dependency gap records, identity preservation, diagnostics,
   determinism, stage integration if implemented, public/private surface
   stability, import boundaries, line-count guardrails, and forbidden
   behaviors.
8. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   raw-body parsing, broad-body-semantics, broad-protocol, registry/
   dispatcher, scheduler, dependency-solver, hidden-backfeed, fixpoint, and
   hardwiring behavior.
9. Run the required validation commands below.
10. Return a concise implementation summary, files changed, validation
    results, line counts, and any follow-ups.

## Required Tests

- Positive tests for gap inventories over accepted M96 manifests produced from:
  - accepted M86 mini-TSIL leaf-return packages;
  - accepted M95 selected-body direct-intrinsic packages;
  - accepted M92 exact-array backend-handoff packages;
  - mixed package sets.
- Tests proving exact-array inventory records preserve unresolved dependency
  record and source dependency request object identity from M96.
- Tests for no-known-gap inventories where a manifest has no unresolved
  dependencies.
- Determinism tests for repeated inventory construction, inventory keys, stage
  output keys if integrated, and reordered inputs.
- Pipeline/stage tests proving `lowering_completion_gap_inventory` follows
  `lowering_completion_manifest` when stage integration is implemented.
- Negative tests for unsupported source, empty/missing manifests, multiple
  manifests, wrong stage, malformed manifest, candidate/source-location
  mismatch, and copied/equal-but-not-identical manifest/package/dependency
  records.
- Import-boundary and private-module tests proving the new module does not
  import `boundary.py`, the `tslgen.lowering` package facade, backend modules,
  renderers, `tsldata`, or `frozen`.
- Line-count tests proving `boundary.py <= 1300`,
  `_operation_package_sources.py <= 819`, and the new gap-inventory module is
  below the module-size guardrail.
- Negative assertions proving M97 does not read backend maps/catalogs, resolve
  backend-uninit, create Stage 9 plans, create renderer-ready IR, render
  output, generate artifacts, repair source text, parse raw body text,
  interpret SVE/direct-intrinsic tokens, infer byte-size-to-token mappings,
  introduce registries/dispatchers/callback maps, schedule operations, solve
  dependencies, add hidden backfeeds, or run fixpoint machinery.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m97 or completion_gap_inventory or completion_manifest"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses different focused private module names, include
those files consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M97 is Stage 8 lowering gap-inventory/provenance
   work only and does not add raw body text parsing, source repair,
   SVE/direct-intrinsic semantics, byte-size-to-token inference, backend
   resolution, backend maps/catalog reads, Stage 9 planning, backend
   translation, renderer-ready IR, rendering, generated output, broad
   TSIL/body semantics, registries/dispatchers, hidden backfeeds, fixpoint
   behavior, scheduling, dependency solving, or hardwiring.
3. Extensibility auditor: verify gap-inventory ownership is cohesive, private
   modules keep one-way imports where practical, `boundary.py` remains at or
   below 1,300 lines, `_operation_package_sources.py` remains unchanged and at
   or below 819 lines, no new module becomes a replacement monolith, and the
   implementation remains compatible with a composable lowering pipeline.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M97 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M96 pending-acceptance wording remains.

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
create the next concrete prompt under `docs/agent/runs/`. Do not mark M97
accepted until this internal review result is reached.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. Line counts.
6. State transition and next concrete run prompt.
