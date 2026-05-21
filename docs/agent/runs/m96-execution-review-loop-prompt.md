# M96 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 96.

Milestones 1 through 95 are accepted. Post-M95 planning is accepted and
selected:

```text
Milestone 96: Stage-8 Lowering Completion Manifest Slice
```

Use the orchestrated executor-review loop in this prompt. M96 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M96 planning until M96 review returns
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
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`
- `tslgen/src/tslgen/lowering/_operation_package_mini_tsil.py`
- `tslgen/src/tslgen/lowering/_operation_package_exact_array.py`
- `tslgen/src/tslgen/lowering/_operation_package_selected_body.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Create one typed, deterministic Stage 8 lowering completion manifest over
accepted operation-package facts for each lowered candidate.

M96 gives later backend-planning work a single lowering-owned
readiness/provenance contract without starting backend planning, translating
backend values, or turning operation-package source integration into a package
router.

For M96, "completion" and "readiness" mean only that the accepted Stage 8
package/provenance facts present on the candidate have been assembled and
validated. They do not mean semantic body completion, backend readiness,
renderer readiness, executable readiness, or generated-output readiness.

## Scope

- Add focused private lowering ownership, such as
  `tslgen.lowering._lowering_completion_manifest`, for manifest models,
  diagnostics, validation, and assembly.
- Use a narrowly named typed output model such as
  `Stage8LoweringCompletionManifestIr`.
- Consume accepted `LoweringOperationPackageIr` values as the primary input.
- Support only the current accepted package families:
  `mini_tsil_leaf_return`, `exact_array_backend_handoff`, and
  `selected_body_direct_intrinsic`.
- Preserve family-specific M86 mini-TSIL leaf-return facts, accepted M92 exact
  array backend-handoff facts, and accepted M95 selected-body direct-intrinsic
  facts only through accepted package entries and already-preserved object
  references.
- Preserve package object identity, candidate id, package keys, source-family
  identity, package-entry identity, source locations, deterministic ordering,
  and unresolved dependency request references.
- Preserve accepted M92/M90 unresolved backend-handoff dependency references
  as unresolved lowering-side manifest records. Do not resolve them.
- Add one deterministic Stage 8 stage, such as
  `lowering_completion_manifest`, after accepted `lowering_operation_package`
  facts without changing accepted M86/M92/M95 package behavior, object
  identity, diagnostics, selected-branch-only behavior, stage ordering, or
  pipeline snapshots.
- Keep `boundary.py` and `_operation_package_sources.py` from absorbing new
  ownership. Any facade integration must be minimal and import-stable.

## Out Of Scope

- Backend translation, backend map/catalog reads, backend-uninit resolution,
  Stage 9 backend planning, operation scheduling, primitive dependency
  closure, wrapper planning, artifact planning, renderer-ready IR, rendering,
  generated C++ or Rust output, generated tests, CLI/report/writer behavior,
  compiler execution, or Rust.
- New operation-package source families, placeholder package kinds, generic
  operation registries, semantic dispatchers, callback maps, plugin systems,
  hidden recursive backfeeds, fixpoint machinery, or broad source protocols.
- Re-entering raw M86 statements, M92 handoff assembly, M63 envelopes, or the
  M90/M89/M72/M67 provenance chain except to validate object references already
  preserved by accepted operation-package entries.
- Direct-intrinsic/SVE semantics, byte-size-to-token inference, vector
  metadata inference, declaration/array/store/return/body semantics,
  `value<backend>(...)` evaluation, raw body text parsing, source-body repair,
  or generic TSIL/body parsing.
- Treating `svptrue_b*`, `pg`, selected literals, type tags, primitive names,
  extension ids, backend ids, source locations, or package-family tags as
  semantic dispatch keys.
- Treating any graph-like manifest structure as an operation DAG, dependency
  closure, backend plan, renderer IR, wrapper plan, artifact plan, registry,
  dispatcher, backfeed, or fixpoint mechanism.

## Required Inputs

- Accepted M86 mini-TSIL leaf-return package behavior and diagnostics.
- Accepted M92 exact array backend-handoff request package behavior and
  unresolved dependency provenance through M90/M89/M72/M67.
- Accepted M95 selected-body direct-intrinsic package behavior and provenance.
- Accepted M93/M94 operation-package facade, source-family distinction,
  deterministic package keys, diagnostics, and import/module-size guardrails.
- Current M95 line-count pressure points:
  - `tslgen/src/tslgen/lowering/boundary.py`: 1,300 physical lines.
  - `tslgen/src/tslgen/lowering/_operation_package_sources.py`: 819 physical
    lines.

## Expected Outputs

- One typed Stage 8 lowering completion manifest/readiness value per selected
  candidate with deterministic keys and package ordering.
- Manifest records that distinguish complete lowering facts from unresolved
  backend-handoff dependencies without converting either into backend plans.
- Diagnostics for unsupported sources, empty package sets, duplicate package
  keys, malformed package entries, wrong source family, mixed candidate
  context, source-location/provenance mismatches, wrong stage/order, ambiguous
  containers, and dependency provenance mismatches.
- Public facade stability if the manifest type is exported; otherwise a
  narrow private module boundary with tests proving imports remain one-way.

## Required Executor Task

Run exactly one write-capable executor for M96. The executor should:

1. Implement the Stage 8 lowering completion manifest described above.
2. Add focused manifest ownership, preferably in
   `tslgen.lowering._lowering_completion_manifest`; split only if one file
   would mix too many responsibilities or approach the module-size guardrail.
3. Consume accepted `LoweringOperationPackageIr` values as the primary input,
   not raw package source values or raw body text.
4. Keep `_operation_package.py` as a narrow operation-package facade and do
   not turn `_operation_package_sources.py` into a manifest router,
   package-family registry, source dispatcher, callback map, or broad source
   protocol.
5. Preserve accepted M86 mini-TSIL leaf-return, accepted M92 exact-array
   backend-handoff, and accepted M95 selected-body direct-intrinsic package
   behavior exactly.
6. Preserve public import paths, stage name/order, package keys, manifest keys,
   diagnostics, source locations, pipeline snapshots, selected-branch-only
   behavior, object identity, and no-external-input boundaries.
7. Add focused tests for positive manifest construction, diagnostics,
   deterministic keys/order, unresolved dependency reference preservation,
   pipeline/stage integration, public-surface stability, import boundaries,
   line-count guardrails, and forbidden behaviors.
8. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   broad-body-semantics, broad-protocol, registry/dispatcher, scheduler,
   hidden-backfeed, fixpoint, and hardwiring behavior.
9. Run the required validation commands below.
10. Return a concise implementation summary, files changed, validation
    results, line counts, and any follow-ups.

## Required Tests

- Positive tests for manifest construction from:
  - accepted M86 mini-TSIL leaf-return packages;
  - accepted M92 exact-array backend-handoff packages;
  - accepted M95 selected-body direct-intrinsic packages;
  - mixed per-candidate package sets.
- Tests proving exact-array unresolved backend-value requests are referenced
  by identity and provenance, not copied, resolved, or translated.
- Negative tests for unsupported sources, empty package sets, duplicate
  package keys, malformed package entries, wrong source family, candidate
  mismatch, source-location mismatch, provenance mismatch, ambiguous
  containers, and wrong stage/order.
- Determinism tests for reordered package inputs, manifest keys, stage output
  keys, and repeated pipeline runs.
- Pipeline/stage tests proving `lowering_completion_manifest` appears after
  accepted `lowering_operation_package` facts and preserves existing
  M86/M92/M95 package behavior, object identities, selected-branch-only
  behavior, and snapshots.
- Existing M86/M92/M95 positive, diagnostic, identity/provenance,
  determinism, integration, and snapshot tests must continue to pass unchanged
  or with only behavior-preserving test ownership updates.
- Import-boundary and public-facade tests for the new manifest module, proving
  private lowering modules do not import `boundary.py`, the `tslgen.lowering`
  package facade, backend modules, renderers, `tsldata`, or `frozen`.
- Line-count tests proving `boundary.py` does not grow beyond the current
  1,300-line pressure point, `_operation_package_sources.py` does not grow
  beyond the current 819-line pressure point unless it is first reduced by
  behavior-preserving extraction, and the new manifest module does not become
  a replacement monolith.
- Negative assertions proving M96 does not read backend maps/catalogs, resolve
  backend-uninit, create Stage 9 plans, create renderer-ready IR, render
  output, generate artifacts, repair source text, parse raw body text,
  interpret SVE/direct-intrinsic tokens, infer byte-size-to-token mappings,
  introduce registries/dispatchers/callback maps, schedule operations, solve
  dependencies, add hidden backfeeds, or run fixpoint machinery.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package*.py tslgen/src/tslgen/lowering/_lowering_completion_manifest*.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m96 or completion_manifest or operation_package"
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
2. Boundary auditor: verify M96 is Stage 8 lowering manifest/provenance work
   only and does not add raw body text parsing, source repair,
   SVE/direct-intrinsic semantics, byte-size-to-token inference, backend
   resolution, backend maps/catalog reads, Stage 9 planning, backend
   translation, renderer-ready IR, rendering, generated output, broad
   TSIL/body semantics, registries/dispatchers, hidden backfeeds, fixpoint
   behavior, scheduling, dependency solving, or hardwiring.
3. Extensibility auditor: verify manifest ownership is cohesive, private
   modules keep one-way imports where practical, `boundary.py` remains a
   minimal facade/coordinator, `_operation_package_sources.py` does not become
   a generic source protocol/router/dispatcher, no new module becomes a
   replacement monolith, and the implementation is compatible with a
   composable lowering pipeline.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M96 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M95 pending-acceptance wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M96 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M96
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M96 result

Record:

- M96 accepted status and review verdict.
- Files changed.
- Final validation commands and exact results.
- Line counts for `boundary.py`, `_operation_package_sources.py`, and the new
  manifest module(s).
- Follow-ups, if any.
- Boundary reminders that M96 is Stage 8 manifest/provenance only and does not
  start Stage 9 backend planning or generated output.

Then create the next concrete prompt under `docs/agent/runs/`, normally:

```text
docs/agent/runs/post-m96-planning-plus-review-prompt.md
```

The next prompt must focus on lowering unless the accepted M96 review records a
different explicit direction.

## Stop Rule

Do not start Milestone 97 in this prompt. Stop after M96 implementation,
review, accepted-result state updates, and next-prompt creation.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
