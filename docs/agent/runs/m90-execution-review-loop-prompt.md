# M90 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 90.

Milestones 1 through 89 are accepted. Post-M89 planning is accepted and
selected:

```text
Milestone 90: Exact Array Lowering Completion Package Slice
```

Use the orchestrated executor-review loop in this prompt. M90 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M90 planning until M90 review returns
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
- `tsldata/primitives/load_store/array.tsl`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Consume the accepted M89 exact array backend-deferred request inventory and
its accepted M88 structural package, then produce one typed Stage 8 exact
array lowering completion package for the selected `array.tsl:105-111` body.

"Completion" means completion of the current lowering-side handoff: accepted
exact array lowering facts are packaged with explicit unresolved dependencies
for later backend planning. It does not mean semantic body completion, backend
readiness, renderer readiness, generated output, or broad TSIL support.

## Scope

- Add focused private ownership, such as
  `tslgen.lowering._array_body_completion_package`, for exact array lowering
  completion-package assembly, source selection, validation, and diagnostics.
- Consume accepted `ExactArrayBackendDeferredRequestInventoryIr` values, the
  `array_backend_deferred_request_inventory` stage output, or one narrowly
  validated source carrying exactly one accepted M88 package and one matching
  accepted M89 inventory.
- Reach accepted M64-M87 structural facts through the M88 package and accepted
  M89 inventory references, not by re-collecting broad pipeline outputs.
- Produce a typed value, such as `ExactArrayLoweringCompletionPackageIr`,
  carrying stable identity, source location/provenance, candidate id, target
  extension, source extension, selected type tag, branch-chain id, the accepted
  M88 package reference, the accepted M89 inventory reference, and explicit
  unresolved dependency records.
- Represent the accepted M89 `value_backend_uninit_array` inventory member as
  an unresolved dependency by typed reference only. Preserve object identity to
  the accepted M72 deferred backend-uninit value and M67 backend-value request
  record.
- Add one deterministic Stage 8 stage after
  `array_backend_deferred_request_inventory`, such as
  `array_lowering_completion_package`.
- Treat protocol-shaped/runtime sources as untrusted until concrete typed M88
  package and M89 inventory payloads are validated.
- Preserve accepted M64-M89 diagnostics, source locations, stage names/order,
  output identities, deterministic keys, selected-branch-only behavior, public
  imports, and pipeline snapshots.
- Keep `boundary.py`, `_array_body_pipeline.py`, `_array_body_models.py`, and
  `_array_body_backend_deferred_requests.py` changes minimal. The new focused
  module should own the completion-package logic.

## Out Of Scope

- Backend-uninit resolution, backend map reads, backend catalog reads,
  `tsldata/detail/lang` reads, Stage 9 backend planning, backend translation,
  renderer-ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, or Rust.
- Generic `value<backend>(...)`, `type<backend>(...)`, backend modifier, or
  backend helper evaluation.
- Declaration semantics, array semantics, allocation/lifetime, initializer
  behavior, variable scope, store semantics, return semantics, `tmp.data()`
  pointer semantics, SVE predicate/vector/register semantics, memory behavior,
  direct-intrinsic semantics, or broad body semantics.
- Re-interpreting `svst1`, `tmp.data()`, `svptrue_b*`, `emit_return(tmp)`, or
  the accepted structural slots as semantic body facts.
- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad TSIL parsing, raw helper dispatch, registries, callback maps, plugin
  systems, dispatch tables keyed by raw helper text/backend id/extension/type
  tag/corpus line number, reflection over package members, hidden backfeeds,
  fixpoint execution, or broad source protocols.

## Required Inputs

- Accepted M89 `ExactArrayBackendDeferredRequestInventoryIr`.
- Accepted M88 `ExactArrayBodyStructuralPackageIr`, reached through the M89
  inventory and validated by identity/provenance.
- Accepted M73 declaration shell, M72 deferred backend-uninit value, and M67
  backend-value request record as references through M88/M89.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:105-111`.

## Expected Outputs

- A typed exact array lowering completion package carrying stable completion
  identity, source location/provenance, candidate id, target extension, source
  extension, selected type tag, branch-chain id, accepted M88 package
  reference, accepted M89 inventory reference, package member references, and
  explicit unresolved dependency records.
- One unresolved dependency record for the accepted M89
  `value_backend_uninit_array` inventory member, preserving typed
  `deferred_backend_value` policy and M72/M67 object identity.
- A deterministic pipeline stage snapshot entry for the completion-package
  stage after `array_backend_deferred_request_inventory`.
- Structured diagnostics for unsupported source, missing/duplicate package,
  missing/duplicate inventory, malformed entries, package/inventory mismatch,
  context mismatch, source-location mismatch, wrong inventory member set,
  wrong policy, and provenance mismatch.

## Required Executor Task

Run exactly one write-capable executor for M90. The executor should:

1. Implement the smallest coherent exact array lowering completion-package
   slice described above.
2. Add focused M90 tests for positive package assembly, direct/stage/source
   inputs, identity/provenance preservation, unresolved dependency records,
   malformed source diagnostics, context/provenance/member-set diagnostics,
   deterministic stage order, selected-branch-only behavior, pipeline
   snapshots, and import boundaries.
3. Preserve all accepted M64-M89 diagnostics, source locations, stage
   names/order, output identities, deterministic keys, selected-branch-only
   behavior, public imports, and pipeline snapshots.
4. Avoid backend-uninit resolution, backend maps, backend translation, Stage 9
   backend planning, renderer-ready IR, rendering, generated output, generic
   backend-value evaluation, body/declaration/store/return/SVE semantics,
   source-body repair, raw helper dispatch, broad protocols, hidden backfeeds,
   and catch-all modules.
5. Run the required validation commands below.
6. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_array_body_completion_package.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m90 or lowering_completion or backend_deferred or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private module name, include
that file consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and the final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M90 stays Stage 8 lowering-side completion-package
   handoff only, consumes accepted typed M88/M89 facts, and does not add
   backend resolution, backend maps, Stage 9 backend planning, rendering/
   output, generic backend-value evaluation, source-body repair, broad
   protocols, hardwiring, or semantic body completion.
3. Extensibility auditor: verify focused module ownership, one-way imports,
   minimal facade/pipeline changes, no catch-all module growth, no registries,
   no callback dispatch, no hidden backfeeds, and no fixpoint machinery.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M90 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M89 handoff wording remains.
6. Evidence auditor: verify the implementation is supported by accepted
   M64-M89 typed facts and `array.tsl:105-111`, and does not claim support for
   broader corpus `value<backend>(uninit::array)` forms or broader array-body
   semantics.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M90 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M90
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M90 result

Record:

- M90 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering/backend-planning work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m90-planning-plus-review-prompt.md
```

The post-M90 prompt must focus on the next highest-value redesign step, use
read-only planning/review subagents, and must not implement M91 unless that
future prompt explicitly selects an executor task.

Do not start post-M90 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
