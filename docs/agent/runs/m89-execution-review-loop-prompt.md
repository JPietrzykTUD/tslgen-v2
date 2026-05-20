# M89 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 89.

Milestones 1 through 88 are accepted. Post-M88 planning is accepted and
selected:

```text
Milestone 89: Exact Array Backend-Deferred Request Inventory Slice
```

Use the orchestrated executor-review loop in this prompt. M89 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M89 planning until M89 review returns
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
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Consume the accepted M88 exact array-body structural package and produce one
typed, source-ordered inventory of backend-deferred requests for the exact
selected `array.tsl:105-111` body.

The first and only supported inventory member is the accepted M72/M67
`value<backend>(uninit::array)` deferred backend-value boundary. M89 gives
later backend-planning work one stable typed handoff for deferred backend-value
facts without resolving those facts.

M89 is Stage 8 lowering inventory/provenance validation only. It must not
claim that backend uninit, array declarations, stores, returns, SVE operations,
or generated output are semantically lowered.

## Scope

- Add focused private ownership, such as
  `tslgen.lowering._array_body_backend_deferred_requests`, for exact array
  backend-deferred request inventory assembly, source selection, and
  inventory-specific diagnostics.
- Consume accepted M88 `ExactArrayBodyStructuralPackageIr` values, the
  `array_body_structural_package_assembly` stage output, or one narrowly
  validated package-only source carrying exactly one accepted M88 package.
- Produce a typed inventory value, such as
  `ExactArrayBackendDeferredRequestInventoryIr`, containing exactly one typed
  member for the accepted `value_backend_uninit_array` deferred backend-value
  fact.
- Preserve object identity/provenance from M88 package to M73 declaration
  shell, M72 `ExactArrayInitializationDeferredBackendUninitValue`, and the M67
  `ExactArrayInitializationHelperRequestRecord`.
- Validate candidate id, target extension, source extension, selected type
  tag, branch-chain id, variable token, slot identity, source location, request
  ordinal, request kind, helper leaf kind, source text provenance, and
  `deferred_backend_value` policy.
- Add one deterministic stage after `array_body_structural_package_assembly`,
  such as `array_backend_deferred_request_inventory`.
- Treat any protocol-shaped/runtime source entries as untrusted until concrete
  typed M88 package payloads are validated.
- Preserve accepted M64-M88 diagnostics, source locations, stage names/order,
  output identities, deterministic keys, selected-branch-only behavior, public
  imports, and pipeline snapshots.

## Out Of Scope

- Resolving, translating, normalizing, rendering, or otherwise interpreting
  `value<backend>(uninit::array)` beyond preserving the accepted deferred
  backend-value policy and typed provenance.
- Backend map reads, backend catalog reads, `tsldata/detail/lang` reads,
  backend translation, Stage 9 backend planning, renderer-ready IR, rendering,
  generated C++ or Rust output, generated tests, CLI/report/writer behavior,
  compiler execution, or Rust.
- Generic `value<backend>(...)`, `type<backend>(...)`, backend modifier, or
  backend helper evaluation.
- Declaration semantics, array semantics, allocation/lifetime, initializer
  behavior, variable scope, store semantics, return semantics, `tmp.data()`
  pointer semantics, SVE predicate/vector/register semantics, memory behavior,
  direct-intrinsic semantics, or broad body semantics.
- Inventorying generic backend-ish unresolved tokens such as `svst1`,
  `tmp.data()`, `svptrue_b*`, `emit_return`, or unrelated selected-body facts.
- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad TSIL parsing, raw helper dispatch, registries, callback maps, plugin
  systems, dispatch tables keyed by raw helper text/backend id/extension/type
  tag/corpus line number, reflection over package members, hidden backfeeds, or
  fixpoint execution.
- Growing `_array_body_models.py`, `_array_body_package.py`,
  `_array_body_pipeline.py`, or central facade modules into catch-all
  ownership.

## Required Inputs

- Accepted M88 `ExactArrayBodyStructuralPackageIr`.
- Accepted M72 `ExactArrayInitializationHelperSetCompletionIr`, including
  accepted `ExactArrayInitializationDeferredBackendUninitValue` with policy
  `deferred_backend_value`.
- Accepted M67 backend-value request record for
  `value<backend>(uninit::array)`.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:105-111`.

## Expected Outputs

- A typed exact array backend-deferred request inventory value carrying stable
  inventory identity, source location/provenance, candidate id, target
  extension, source extension, selected type tag, branch-chain id, source
  package identity, and the accepted M88 package reference.
- A typed inventory member carrying kind `value_backend_uninit_array`, request
  kind `backend_value`, policy `deferred_backend_value`, source location, and
  references to the accepted M72 deferred backend-uninit value and M67 request
  record.
- Deterministic key/provenance behavior matching accepted M64-M88 conventions.
- A pipeline stage snapshot entry for the inventory stage.
- Structured diagnostics for unsupported source, missing package, duplicate
  package, malformed package entry, context mismatch, missing/wrong
  backend-uninit boundary, wrong policy, source/provenance mismatch, and
  attempted non-exact backend-deferred member inventory.

## Required Executor Task

Run exactly one write-capable executor for M89. The executor should:

1. Implement the smallest coherent exact array backend-deferred request
   inventory slice described above.
2. Add focused M89 tests for positive inventory assembly, direct/stage/source
   inputs, identity/provenance preservation, malformed source diagnostics,
   wrong-policy/request/provenance diagnostics, deterministic stage order,
   selected-branch-only behavior, pipeline snapshots, and import boundaries.
3. Preserve all accepted M64-M88 diagnostics, source locations, stage
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
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m89 or backend_deferred or structural_package or exact_array_body_pipeline"
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
2. Boundary auditor: verify M89 stays Stage 8 inventory/provenance validation
   only, consumes accepted typed M88/M72/M67 facts, and does not add backend
   resolution, backend maps, Stage 9 backend planning, rendering/output,
   generic backend-value evaluation, source-body repair, broad protocols, or
   hardwiring.
3. Extensibility auditor: verify focused module ownership, one-way imports,
   package-consumer maintainability, no catch-all module growth, no registries,
   no callback dispatch, no hidden backfeeds, and no fixpoint machinery.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M89 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M88 handoff wording remains.
6. Evidence auditor: verify the implementation is supported by accepted
   M67/M72/M88 typed facts and `array.tsl:105-111`, and does not claim support
   for broader corpus `value<backend>(uninit::array)` forms.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M89 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M89
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M89 result

Record:

- M89 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering/backend-deferred work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m89-planning-plus-review-prompt.md
```

The post-M89 prompt must focus on lowering, use read-only planning/review
subagents, and must not implement M90 unless that future prompt explicitly
selects an executor task.

Do not start post-M89 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
