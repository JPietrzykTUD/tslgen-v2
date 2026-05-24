# M103 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 103.

Milestones 1 through 102 are accepted. Post-M102 planning is accepted and
selected:

```text
Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice
```

Use the orchestrated executor-review loop in this prompt. M103 is an
implementation/documentation milestone; one write-capable executor may
implement the selected architecture slice. Do not start post-M103 planning
until M103 review returns `Accept` or `Accept With Follow-Ups`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Create a typed, deterministic Stage 8 backend-translation boundary worklist
inventory over already accepted backend-boundary facts.

For M103, "worklist" means a static lowering-owned inventory/provenance view,
not an executable queue, scheduler, dependency-closure plan, readiness oracle,
Stage 9 backend plan, renderer-ready IR, completeness oracle, source scanner,
backend-map evaluator, registry, dispatcher, hidden backfeed, or fixpoint
mechanism.

The milestone should make the Stage 8-to-backend frontier visible in one
maintainable typed shape before adding another feature-specific backend-result
or direct-intrinsic semantic slice.

## M102 Taxonomy Fit

- The aggregate worklist is a lowering inventory.
- Entries preserve provenance and object identity for accepted concrete M99
  `TranslationRequestIr` records and accepted concrete M100
  `TranslationResultIr` records.
- M103 must not introduce a new `work_item` taxonomy category.
- M102 protocol conformance may validate shape, but must not route semantics
  or accept arbitrary fake objects that merely satisfy a protocol.

## Scope

- Add a focused private lowering module such as
  `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`, with
  optional focused source/diagnostic siblings only if the implementation
  justifies the split.
- Consume only accepted typed M99
  `Stage8BackendTranslationRequestInventoryIr` values and optional accepted
  typed M100 `ExactArrayBackendUninitTranslationResultIr` values.
- Produce a deterministic per-candidate backend-boundary worklist inventory
  that preserves object identity to M99 request/no-request records and M100
  result/deferred records.
- Classify only accepted concrete states, such as accepted exact-array
  backend-uninit translation results, accepted exact-array translation
  requests that are still unresolved, accepted selected-body direct-intrinsic
  handoff requests that remain deferred, and explicit no-accepted-backend-
  boundary-fact records.
- Validate candidate id, source location, source inventory identity, M100
  result/inventory consistency, duplicate/conflicting entries, deterministic
  ordering, and malformed source containers with explicit diagnostics.
- Keep new worklist-specific contracts local to the new focused module unless
  a separate consolidation milestone later accepts shared ownership.
- Add focused tests in a new test file rather than expanding the already-large
  `test_lowering_boundary.py`.

## Out Of Scope

- Calling existing translation/result lowerers to complete missing work.
- Inferring new requests, duplicating request records by key, or resolving
  direct-intrinsic/SVE meaning.
- Pipeline integration through `LoweredImplementation`, public facade exports,
  `_lower_input` orchestration, new `GenerationLoweringStageName` /
  `_stage_contracts.py` integration, or `boundary.py` growth.
- Growing `_lowering_ir_contracts.py` into a registry of feature-specific
  contracts.
- New lowering semantics, new request/result families, backend translation
  semantics, Rust translation, generic backend helper evaluation, backend
  map/catalog/manifest reads during lowering, `tsldata/detail/lang` reads,
  runtime `frozen/` use, Stage 9 backend planning, renderer-ready IR,
  rendering, generated output, operation scheduling, dependency closure,
  wrapper planning, artifact planning, CLI/report/writer behavior, compiler
  execution, or host hardware dependency.
- Raw `.tsl` source parsing, source-body reparsing, source repair, source
  normalization, best-effort correction, broad TSIL/body parsing, token-to-
  intrinsic inference, byte-size-to-token inference, vector/register metadata
  expansion, category-based semantic dispatch, registries, dispatchers,
  callback maps, plugin mechanisms, hidden backfeeds, or fixpoint machinery.

## Required Executor Task

Run exactly one write-capable executor for M103. The executor should:

1. Inspect the accepted M99 request inventory, M100 exact-array translation
   result, and M102 protocol surface.
2. Add the smallest focused private worklist module needed to represent a
   static Stage 8 backend-boundary inventory/provenance view.
3. Consume only concrete accepted M99 inventories plus optional concrete
   accepted M100 results.
4. Preserve object identity to accepted M99 request/no-request records and
   M100 result/deferred records.
5. Reject arbitrary fake objects that merely satisfy M102 protocols.
6. Avoid `boundary.py`, `LoweredImplementation`, public facade, `_lower_input`,
   `GenerationLoweringStageName`, `_stage_contracts.py`, M99/M100 module, and
   `_lowering_ir_contracts.py` growth.
7. Keep any worklist-specific contract constants in the new focused module,
   not `_lowering_ir_contracts.py`.
8. Add focused tests in a new test file.
9. Run the required validation commands below.
10. Return a concise implementation summary, files changed, validation
    results, line counts, review verdicts, and follow-ups.

If the executor discovers that M103 cannot be implemented as a static
inventory/provenance view without adding queue/scheduler/readiness/Stage 9 or
semantic-dispatch behavior, stop implementation, record the blocker in
`docs/redesign/open-questions.md`, and return `Return To Planner` with a
planning-revision prompt.

## Required Tests

- Positive tests over M99 request inventories with exact-array request,
  selected-body direct-intrinsic request, and no-request records.
- Positive tests over an M99 inventory plus matching M100 exact-array
  translation result, preserving source object identities.
- Negative tests for arbitrary M102-conformant fake objects, not only wrong
  concrete classes.
- Negative tests for mismatched M100 result inventory/candidate/source
  location, duplicate/conflicting worklist entries, missing source inventory,
  unsupported source containers, and malformed keys.
- Import-boundary/source assertions proving no `boundary.py`, public
  `tslgen.lowering` facade, backend modules, renderers, backend planners,
  `tsldata`, `frozen`, backend maps/catalogs/manifests, raw parsing helpers,
  source repair, registry/dispatcher/callback/plugin/backfeed/fixpoint, or
  category-based semantic dispatch.
- Line-count tests or source assertions proving M103 does not grow
  `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, or the new
  worklist module into a replacement monolith. Tests must prove `boundary.py`
  remains unchanged and below its current guardrail, `_lowering_ir_contracts.py`
  remains below its current guardrail, and the new worklist module stays below
  a focused ceiling such as 400 lines unless a reviewed split justifies a
  different limit.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_boundary_worklist.py tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

If implementation creates focused source/diagnostic sibling modules, include
them in line-count, py-compile, pytest/source assertions, mypy, and final
reporting.

Run broader validation if shared lowering behavior changes beyond the private
M103 worklist module:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
```

## Required Subagents

After the executor completes, use read-only subagents:

1. Reviewer: review the implementation against this prompt, `AGENTS.md`,
   `PLANS.md`, `docs/agent/review-checklist.md`, and the roadmap. Return
   `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`,
   or `Reject`.
2. Boundary auditor: verify no queue/scheduler/readiness oracle, Stage 9
   backend planning, renderer-ready IR, rendering/output, backend translation
   semantics, Rust translation, direct-intrinsic/SVE resolution, backend
   map/catalog/manifest reads, raw helper parsing, source repair, or
   category-based semantic dispatch.
3. Extensibility auditor: verify ownership stays in a focused private module,
   `boundary.py` and `_lowering_ir_contracts.py` do not grow, no broad
   inheritance/registry/dispatcher/callback/plugin/backfeed/fixpoint mechanism
   appears, and new tests enforce line-count ceilings.
4. Validation auditor: verify tests and validation results, including
   M99/M100 positives, arbitrary protocol-fake negatives, identity
   preservation, diagnostics, import boundaries, forbidden behavior, line
   counts, and mypy.
5. Documentation auditor: verify roadmap/state/design docs and
   `docs/redesign/missing-lowering-inventory.md` reflect accepted M103
   behavior and remaining deferred backend work accurately.

## Review Loop

The main thread is the orchestrator.

- If all reviews return `Accept`, mark M103 accepted, update
  `docs/agent/current-redesign-state.md`, update any needed redesign docs, and
  create `docs/agent/runs/post-m103-planning-plus-review-prompt.md`.
- If reviews return `Accept With Follow-Ups`, record non-blocking follow-ups,
  mark M103 accepted, update state/docs, and create the post-M103 planning
  prompt.
- If any review returns `Needs Revision`, run one focused write-capable
  revision executor limited to the blocking issues, then run focused re-review.
- If any review returns `Return To Planner`, stop implementation, update state,
  and create an appropriate post-M103 planning-revision prompt.
- If any review returns `Reject`, stop implementation, update state, and create
  an appropriate rollback/redesign prompt.

Only one write-capable executor or revision executor may modify a worktree at
a time. Review and audit subagents are read-only unless the orchestrator later
creates a focused revision task.

## Finalization Rules

On `Accept` or `Accept With Follow-Ups`, before finishing:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record accepted M103 behavior and validation;
- update `docs/redesign/missing-lowering-inventory.md` if M103 narrows or
  resolves backend-boundary lowering gaps;
- create the next concrete run prompt under `docs/agent/runs/`;
- run the final `git diff --check`.

Do not start Milestone 104 or post-M103 implementation work.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
