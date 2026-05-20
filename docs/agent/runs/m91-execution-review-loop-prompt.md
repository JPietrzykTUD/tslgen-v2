# M91 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 91.

Milestones 1 through 90 are accepted. Post-M90 planning is accepted and
selected:

```text
Milestone 91: Stage 8 Exact Array Pipeline Ownership Consolidation Slice
```

Use the orchestrated executor-review loop in this prompt. M91 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M91 planning until M91 review returns
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
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Perform a behavior-preserving Stage 8 exact array pipeline ownership
consolidation after M90. The slice should move exact array pipeline result
aggregation, stage/snapshot assembly, and public handoff aggregation into
focused private ownership so later lowering milestones can build on the
accepted M64-M90 handoff without growing `boundary.py` or
`_array_body_pipeline.py`.

M91 is maintainability architecture work. It must produce the same accepted
public behavior, diagnostics, stage outputs, deterministic keys, and pipeline
snapshots as M90.

## Scope

- Add focused private module ownership for exact array pipeline result and
  aggregate DTO behavior. Prefer a name such as
  `tslgen.lowering._array_body_pipeline_results` unless implementation
  evidence shows a clearer cohesive name.
- Add focused private module ownership for exact array stage construction and
  snapshot step assembly over accepted M64-M90 outputs. Prefer a name such as
  `tslgen.lowering._array_body_stage_assembly` unless implementation evidence
  shows a clearer cohesive name.
- Keep `boundary.py` as a public facade/projection surface.
- Keep `_array_body_pipeline.py` as orchestration over focused helpers instead
  of a catch-all owner for aggregate DTOs, stage construction, and snapshot
  assembly.
- Preserve accepted M64-M90 diagnostics, source locations, public imports,
  stage names/order, artifact kinds, deterministic keys, output identities,
  selected-branch-only behavior, no-external-input boundaries, and pipeline
  snapshots.
- Add or preserve import-boundary, line-count, behavior-preservation, and
  snapshot-stability tests for the public handoff.

## Out Of Scope

- New lowering semantics.
- Backend-uninit resolution, backend maps/catalog reads, backend translation,
  Stage 9 backend planning, renderer-ready IR, rendering, generated C++ or
  Rust output, generated tests, CLI/report/writer behavior, compiler
  execution, or Rust.
- Broad TSIL parsing, broad body/declaration/array/store/return/call/SVE
  semantics, `tmp.data()` semantics, `emit_return` semantics, source-body
  repair, or source-body normalization.
- Broad protocols, registries, raw-helper dispatch, callback maps, plugin
  systems, hidden backfeeds, fixpoint machinery, extension-specific
  hardwiring, or dispatch tables keyed by raw helper text/backend id/
  extension/type tag/corpus line number.
- Changing public behavior, diagnostic codes, accepted keys, stage/snapshot
  order, or selected-branch-only diagnostic behavior.
- Moving backend planning or dependency expansion into
  `_array_body_completion_package.py`.

## Required Inputs

- Accepted M64-M90 exact array pipeline stage outputs and public facade
  expectations.
- Existing exact array pipeline aggregate/result behavior.
- M90 line-count pressure: `boundary.py` measured 1,226 physical lines and
  `_array_body_pipeline.py` measured 1,043 physical lines after M90.
- Accepted M90 completion package behavior and tests.

## Expected Outputs

- New focused private module ownership for exact array pipeline result
  aggregation and stage/snapshot assembly.
- Stable public `tslgen.lowering` and `tslgen.lowering.boundary` imports.
- Stable deterministic Stage 8 pipeline snapshots and accepted exact array
  handoff keys.
- Reduced or stabilized responsibilities in `boundary.py` and
  `_array_body_pipeline.py`.
- No replacement private monolith. New private modules need clear ownership,
  one-way imports where practical, and no facade back-imports.

## Required Executor Task

Run exactly one write-capable executor for M91. The executor should:

1. Implement the smallest coherent exact array pipeline ownership
   consolidation described above.
2. Prefer focused private modules for result/aggregate ownership and
   stage/snapshot assembly. If different module names are chosen, document why
   they are the clearer ownership boundary and include them consistently in
   tests, validation, state updates, and the final report.
3. Preserve all accepted M64-M90 diagnostics, source locations, public imports,
   stage names/order, artifact kinds, deterministic keys, output identities,
   selected-branch-only behavior, no-external-input boundaries, and pipeline
   snapshots.
4. Add focused tests for behavior preservation, import boundaries, line-count
   reporting, and snapshot stability.
5. Avoid all out-of-scope semantic, backend, rendering, generated-output,
   source-repair, broad-protocol, hidden-backfeed, fixpoint, and hardwiring
   behavior.
6. Run the required validation commands below.
7. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m91 or pipeline_ownership or exact_array_body_pipeline or lowering_completion"
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
2. Boundary auditor: verify M91 is behavior-preserving Stage 8 exact array
   pipeline ownership consolidation only and does not add semantic lowering,
   backend planning, backend maps, rendering, generated output, broad TSIL,
   source-body repair, broad protocols, hidden backfeeds, fixpoint behavior,
   or hardwiring.
3. Extensibility auditor: verify focused module ownership, one-way imports,
   no replacement monolith, no broad dispatcher, no facade back-imports, no
   registry/callback/plugin machinery, and no catch-all growth.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M91 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M90 pending-acceptance wording remains.
6. Evidence auditor: verify the implementation is supported by accepted
   M64-M90 typed behavior and does not claim broader body, backend, SVE, or
   generated-output support.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M91 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M91
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M91 result

Record:

- M91 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m91-planning-plus-review-prompt.md
```

The post-M91 prompt must focus on the next highest-value redesign step, use
read-only planning/review subagents, and must not implement M92 unless that
future prompt explicitly selects an executor task.

Do not start post-M91 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
