# M92 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 92.

Milestones 1 through 91 are accepted. Post-M91 planning is accepted and
selected:

```text
Milestone 92: Exact Array Lowering Backend-Handoff Request Slice
```

Use the orchestrated executor-review loop in this prompt. M92 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M92 planning until M92 review returns
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
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline_results.py`
- `tslgen/src/tslgen/lowering/_array_body_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_array_body_completion_package.py`
- `tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py`
- `tslgen/src/tslgen/lowering/_array_body_package.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Create the typed lowering-side handoff request that lets future backend
planning consume the accepted M90 exact array lowering completion package
without reaching back through pipeline internals. M92 should bridge Stage 8
lowering completion to a future Stage 9 backend-planning boundary while
remaining request/provenance data only.

M92 must produce one concrete typed request for later backend planning. It must
not start backend planning, resolve backend values, translate backend text,
produce renderer-ready IR, or infer broader implementation-body semantics.

## Scope

- Add focused private ownership, such as
  `tslgen.lowering._array_body_backend_handoff`, for one exact array backend
  handoff request type and assembly function.
- Consume accepted typed `ExactArrayLoweringCompletionPackageIr` values,
  `array_lowering_completion_package` stage outputs, or narrowly validated
  sources carrying exactly one accepted completion package.
- Produce one typed exact array backend-handoff request carrying stable
  identity, source location/provenance, candidate id, target extension, source
  extension, selected type tag, branch-chain id, accepted completion-package
  reference, accepted M88/M89 package/inventory references, and explicit
  unresolved dependency request records.
- Preserve object identity/provenance for the accepted M90 completion package,
  accepted M89 inventory member, accepted M72 deferred backend-uninit value,
  and accepted M67 backend-value request record.
- Add one deterministic Stage 8 handoff stage after
  `array_lowering_completion_package`, such as
  `array_backend_handoff_request`.
- Preserve accepted M64-M91 diagnostics, source locations, public imports,
  stage names/order before the new stage, deterministic keys, selected-branch-
  only behavior, no-external-input boundaries, and pipeline snapshots.

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
- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad protocols, registries, callback maps, plugin systems, hidden
  backfeeds, fixpoint execution, raw-helper dispatch, or dispatch tables keyed
  by raw helper text/backend id/extension/type tag/corpus line number.
- Growing `boundary.py`, `_array_body_pipeline.py`,
  `_array_body_completion_package.py`, `_array_body_pipeline_results.py`, or
  `_array_body_stage_assembly.py` into broader catch-all modules.

## Required Inputs

- Accepted M90 `ExactArrayLoweringCompletionPackageIr`.
- Accepted M89 inventory and M88 structural package, reached by reference
  through the accepted M90 completion package.
- Accepted M72 deferred backend-uninit value and M67 backend-value request
  record, reached by reference through the accepted M90 unresolved dependency.
- Accepted M91 stable pipeline result/stage/snapshot ownership.
- Corpus evidence: `tsldata/primitives/load_store/array.tsl:105-111`.

## Expected Outputs

- A typed exact array backend-handoff request with stable identity,
  provenance, completion-package reference, unresolved dependency request
  records, and deterministic key behavior.
- A deterministic pipeline stage snapshot entry for the handoff-request stage
  after `array_lowering_completion_package`.
- Structured diagnostics for unsupported source, missing completion package,
  duplicate completion package, malformed runtime entries, context mismatch,
  source-location mismatch, wrong dependency set, wrong policy, and provenance
  mismatch.
- Stable public `tslgen.lowering` and `tslgen.lowering.boundary` imports.
- Focused private handoff ownership with one-way imports where practical and
  no replacement private monolith.

## Required Executor Task

Run exactly one write-capable executor for M92. The executor should:

1. Implement the smallest coherent exact array backend-handoff request slice
   described above.
2. Prefer focused private module ownership for handoff request data and
   assembly. If a module name other than
   `tslgen.lowering._array_body_backend_handoff` is chosen, document why it is
   the clearer ownership boundary and include it consistently in tests,
   validation, state updates, and the final report.
3. Consume accepted M90 completion package state and preserve M90/M89/M88/M72/
   M67 object identity and provenance rather than re-collecting or duplicating
   dependency facts.
4. Add the deterministic Stage 8 handoff stage after
   `array_lowering_completion_package` while preserving all prior accepted
   stage names, ordering, keys, output identity, diagnostics, and snapshots.
5. Add focused tests for positive request assembly, identity/provenance,
   diagnostics, pipeline stage order/snapshots, import boundaries, and
   out-of-scope negative assertions.
6. Avoid all out-of-scope backend, rendering, generated-output, source-repair,
   broad-body-semantics, broad-protocol, hidden-backfeed, fixpoint, and
   hardwiring behavior.
7. Run the required validation commands below.
8. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Tests

- Positive M92 tests for direct M90 completion package input, M90 stage-output
  input, and narrowly validated one-completion-package source input.
- Identity/provenance tests proving the handoff request references accepted
  M90/M89/M88/M72/M67 objects rather than duplicating or re-collecting them.
- Negative diagnostics for unsupported source, missing completion package,
  duplicate completion package, malformed runtime entries, context mismatch,
  source-location mismatch, wrong dependency set, wrong policy, and provenance
  mismatch.
- Pipeline tests proving the new handoff-request stage follows
  `array_lowering_completion_package` and preserves prior stage order, keys,
  output identity, selected-branch-only behavior, and pipeline snapshots.
- Import-boundary tests proving the focused handoff module does not import
  `boundary.py`, `tslgen.lowering`, `_array_body_pipeline.py`, backend
  modules, renderers, `tsldata`, or `frozen`.
- Negative assertions proving M92 does not read backend maps, resolve
  `uninit::array`, create Stage 9 plans, produce renderer-ready values, render
  output, infer declaration/store/return/SVE semantics, repair source text, or
  widen to generic backend-value evaluation.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_handoff.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_pipeline_results.py tslgen/src/tslgen/lowering/_array_body_stage_assembly.py tslgen/src/tslgen/lowering/_array_body_completion_package.py tslgen/src/tslgen/lowering/_array_body_backend_handoff.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m92 or backend_handoff or lowering_completion or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private module name, include that
file consistently in the line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M92 is Stage 8 lowering-side request/provenance
   work only and does not add backend resolution, backend maps/catalog reads,
   Stage 9 backend planning, backend translation, renderer-ready IR,
   rendering, generated output, broad TSIL, source-body repair, broad body
   semantics, broad protocols, hidden backfeeds, fixpoint behavior, or
   hardwiring.
3. Extensibility auditor: verify focused handoff ownership, one-way imports
   where practical, no replacement monolith, no broad dispatcher, no facade
   back-imports, no registry/callback/plugin machinery, and no catch-all
   growth in existing lowering modules.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M92 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M91 pending-acceptance wording remains.
6. Evidence auditor: verify the implementation is supported by accepted
   M64-M91 typed behavior and `tsldata/primitives/load_store/array.tsl:105-111`
   without claiming broader body, backend, SVE, or generated-output support.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M92 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M92
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M92 result

Record:

- M92 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m92-planning-plus-review-prompt.md
```

The post-M92 prompt must focus on the next highest-value redesign step, use
read-only planning/review subagents, and must not implement M93 unless that
future prompt explicitly selects an executor task.

Do not start post-M92 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
