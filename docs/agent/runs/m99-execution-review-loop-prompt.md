# M99 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 99.

Milestones 1 through 98 are accepted. Post-M98 planning is accepted and
selected:

```text
Milestone 99: Operation Package Backend-Translation Request Inventory Slice
```

Use the orchestrated executor-review loop in this prompt. M99 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M99 planning until M99 review returns
`Accept` or `Accept With Follow-Ups`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Create one typed, deterministic Stage 8 lowering-owned inventory of accepted
backend-scoped request facts visible from current operation packages,
completion manifests, and gap inventories.

For M99, "backend-translation request inventory" means typed
inventory/provenance over already accepted deferred/backend-scoped request
facts. It must not translate, resolve, evaluate, plan, schedule, or render
those facts.

## Scope

- Add focused private lowering ownership, preferably in
  `tslgen.lowering._lowering_backend_translation_request_inventory`, for typed
  inventory models, diagnostics, validation, deterministic keys, and assembly.
- Add one deterministic Stage 8 stage after accepted
  `lowering_completion_gap_inventory`, such as
  `lowering_backend_translation_request_inventory`.
- Consume only accepted typed Stage 8 facts: accepted M93-M95 operation
  packages, accepted M96 completion manifests, accepted M97 gap inventories,
  accepted M98 stage assembly outputs, and their preserved object references.
- Preserve source manifest, package record, package object, gap record,
  unresolved dependency record, and dependency request object identity.
- Produce typed deterministic inventory records for currently visible
  lowering-owned backend-scoped request states:
  - exact-array `value<backend>(uninit::array)` deferred backend-value request
    from accepted M92/M96/M97 facts;
  - selected-body direct-intrinsic package handoff as a later backend-owned
    body/direct-intrinsic request state, preserving accepted M62/M63/M95
    provenance without interpreting direct-intrinsic or SVE semantics;
  - explicit no-accepted-request / no-known-request inventory state for
    package families with no accepted backend-scoped request facts.
- Keep `boundary.py` as the public facade and request/result model owner.
- Keep `_operation_package_sources.py`, `_lowering_completion_manifest.py`,
  and `_lowering_completion_gap_inventory.py` from receiving request-inventory
  ownership.
- Use `_lowering_stage_assembly.py` only for narrow stage construction/result
  assembly integration if needed; do not broaden it into a coordinator.
- Keep `docs/redesign/missing-lowering-inventory.md` accurate if execution
  narrows, resolves, or newly discovers a lowering gap.

## Out Of Scope

- Backend translation, backend map/catalog/lang reads, backend manifest reads,
  `tsldata/detail/lang` reads, backend-uninit resolution, backend support
  decisions, Stage 9 backend planning, operation scheduling, primitive
  dependency closure, dependency solving, operation DAGs, wrapper planning,
  artifact planning, renderer-ready IR, rendering, generated C++ or Rust
  output, generated tests, CLI/report/writer behavior, compiler execution, or
  host hardware dependency.
- Generic `value<backend>(...)` or `type<backend>(...)` evaluation, intrinsic
  suffix/prefix/post/infix/immediate resolution, type spelling, vector/register
  metadata resolution, direct-intrinsic/SVE semantics, or byte-size-to-token
  inference.
- Raw `.tsl` source text parsing, source-body reparsing, source repair,
  source normalization, broad TSIL/body parsing, or best-effort correction.
- New operation-package source families, broad source protocols, registries,
  dispatchers, callback maps, plugin systems, hidden recursive backfeeds,
  fixpoint machinery, dependency-closure graphs, or lookup tables keyed by raw
  helper text, backend id, extension id, type tag, primitive name, source
  location, or direct-intrinsic token text.
- Treating `docs/redesign/missing-lowering-inventory.md` as runtime input,
  generated output, a source scanner, dependency-closure plan, completion
  oracle, or evidence by itself.

## Required Inputs

- Accepted M92 exact-array backend-handoff request behavior and unresolved
  backend-handoff dependency provenance.
- Accepted M93/M94 operation-package behavior and source-family distinction.
- Accepted M95 selected-body direct-intrinsic package behavior and provenance.
- Accepted M96 completion manifest and M97 gap inventory behavior, diagnostics,
  deterministic ordering, keys, and object-identity preservation.
- Accepted M98 stage-assembly behavior, public facade stability, and
  no-coordinator guardrails.
- Current pressure points after M98:
  - `boundary.py`: 1,241 physical lines.
  - `_operation_package_sources.py`: 819 physical lines.
  - `_lowering_completion_manifest.py`: 776 physical lines.
  - `_lowering_completion_gap_inventory.py`: 564 physical lines.
  - `_lowering_stage_assembly.py`: 189 physical lines.

## Expected Outputs

- One typed Stage 8 backend-translation request inventory value per selected
  candidate, or equivalent typed request-inventory value, with deterministic
  keys and record ordering.
- Inventory records that distinguish accepted backend-scoped request facts from
  explicit no-accepted-request states without inferring missing requests.
- Exact-array request records that preserve accepted M96/M97 unresolved
  dependency and dependency request object identity.
- Selected-body direct-intrinsic request/handoff records that preserve accepted
  M62/M63/M95 provenance without interpreting intrinsic token text.
- Stage integration after `lowering_completion_gap_inventory` that preserves
  accepted M57-M98 diagnostics, stage names, stage ordering, stage keys,
  deterministic ordering, output identities, source locations, object
  identities, selected-branch-only diagnostics, public imports, and
  no-external-input boundaries.
- Import-boundary and line-count guardrails proving the new module is focused
  and pressure-point modules do not become replacement monoliths.

## Required Executor Task

Run exactly one write-capable executor for M99. The executor should:

1. Implement the Stage 8 backend-translation request inventory/provenance slice
   described above.
2. Add focused private ownership, preferably in
   `tslgen.lowering._lowering_backend_translation_request_inventory`.
3. Add the deterministic stage after `lowering_completion_gap_inventory`.
4. Consume only accepted typed M93-M98 facts and preserved object references.
5. Preserve accepted diagnostics, stage names, ordering, keys, deterministic
   ordering, output identities, source locations, object identities,
   selected-branch-only diagnostics, public imports, and no-external-input
   boundaries.
6. Add focused tests for request records, no-accepted-request states, mixed
   inventories, object-identity preservation, determinism, diagnostics,
   import boundaries, line-count guardrails, and forbidden behaviors.
7. Avoid all out-of-scope backend, rendering, output, source-repair, raw-body
   parsing, broad-body-semantics, broad-protocol, registry/dispatcher,
   scheduler, dependency-solver, hidden-backfeed, fixpoint, and hardwiring
   behavior.
8. Run the required validation commands below.
9. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Tests

- Positive tests for exact-array backend-value request inventory records,
  selected-body direct-intrinsic handoff/request records, mini-TSIL or other
  no-accepted-request states, and mixed per-candidate inventories.
- Tests proving request records preserve accepted source manifest, package
  record, package object, gap record, unresolved dependency record, and
  dependency request object identity where those references exist.
- Determinism tests for inventory keys, record ordering, repeated lowering,
  and reordered accepted inputs.
- Stage tests proving the new stage follows `lowering_completion_gap_inventory`
  without changing accepted M57-M98 stage names, ordering, keys, diagnostics,
  output identities, object identities, selected-branch-only behavior, public
  imports, or no-external-input boundaries.
- Negative diagnostics for unsupported source, missing manifest, missing gap
  inventory, multiple manifests/inventories, manifest/inventory mismatch,
  wrong stage/order, malformed entries, copied/equal-but-not-identical records,
  candidate/source-location mismatch, and provenance mismatch.
- Import-boundary tests proving the new module does not import `boundary.py`,
  the `tslgen.lowering` package facade, backend modules, renderers, `tsldata`,
  or `frozen`.
- Negative assertions proving M99 introduces no backend maps/catalog reads,
  backend translation, Stage 9 planning, renderer-ready IR, rendering/output,
  source repair, raw body parsing, registries, dispatchers, schedulers, hidden
  backfeeds, fixpoint behavior, dependency closure, operation scheduling, or
  hardwiring.
- Line-count tests or source assertions keeping `boundary.py`,
  `_operation_package_sources.py`, `_lowering_completion_manifest.py`,
  `_lowering_completion_gap_inventory.py`, `_lowering_stage_assembly.py`, and
  the new request-inventory module within module-size guardrails.

Prefer a new focused test file if adding all M99 coverage to
`test_lowering_boundary.py` would make that file harder to maintain. If a new
focused test file is added, include it in targeted validation and final
reporting.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or completion_gap_inventory or completion_manifest or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private module name, include that
file consistently in line-count, py-compile, import-boundary tests,
`docs/agent/current-redesign-state.md`, and final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M99 is Stage 8 inventory/provenance only and does
   not add raw body parsing, source repair, backend resolution, backend
   maps/catalog reads, Stage 9 planning, backend translation, renderer-ready
   IR, rendering, generated output, broad TSIL/body semantics,
   registries/dispatchers, hidden backfeeds, fixpoint behavior, scheduling,
   dependency solving, dependency closure, or hardwiring.
3. Extensibility auditor: verify the new module is cohesive and narrow, keeps
   one-way imports where practical, does not import `boundary.py` or the
   package facade, and does not grow `boundary.py`,
   `_operation_package_sources.py`, `_lowering_completion_manifest.py`,
   `_lowering_completion_gap_inventory.py`, or `_lowering_stage_assembly.py`
   into a coordinator/router.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M99 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs and
   `docs/redesign/missing-lowering-inventory.md` match the implemented result
   and no stale post-M98 pending-acceptance wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused revision executor for only
the blocking issues named by review, then run focused re-review. Repeat only
for tightly scoped local fixes.

If review returns `Return To Planner` or `Reject`, stop implementation and
create the appropriate planner, rollback, or redesign prompt under
`docs/agent/runs/`; update `docs/agent/current-redesign-state.md` with the
stop/next condition.

## Finalization Rules

If the consolidated verdict is `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- update relevant redesign docs, including
  `docs/redesign/missing-lowering-inventory.md` if M99 changes the missing
  lowering surface;
- create the next concrete prompt under `docs/agent/runs/`, normally
  `docs/agent/runs/post-m99-planning-plus-review-prompt.md`;
- record validation results and follow-ups.

Do not mark M99 accepted until review returns `Accept` or
`Accept With Follow-Ups`. Do not start post-M99 planning inside this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Validation commands and exact results.
4. Review/audit verdicts.
5. Follow-ups recorded, if any.
6. Next concrete run prompt created.
