# M104 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 104.

Milestones 1 through 103 are accepted. Post-M103 planning is accepted and
selected:

```text
Milestone 104: Worklist-Driven Backend Translation Result Expansion Slice
```

Use the orchestrated executor-review loop in this prompt. M104 is an
implementation/documentation milestone; one write-capable executor may
implement the selected architecture slice. Do not start post-M104 planning
until M104 review returns `Accept` or `Accept With Follow-Ups`.

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
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py`
- `tslgen/tests/unit/test_lowering_backend_boundary_worklist.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`

## Goal

Create a typed, deterministic Stage 8 lowering result boundary that consumes
accepted M103 backend-boundary worklist entries and produces typed
resolved/deferred/unsupported backend translation expansion result records.

M104 is intentionally broader than a single literal M103 worklist
classification, but it is one coherent boundary:

```text
M103 worklist entry -> typed translation expansion result
```

It may cover only the accepted `exact_array_backend_uninit_unresolved` and
`selected_body_direct_intrinsic_deferred` classifications, and only when
explicit typed rule inputs are supplied. M103 worklist classifications may
filter candidate entries, but semantic behavior must come from concrete typed
request/result facts plus explicit typed rule inputs.

The M103 worklist remains static inventory/provenance input. M104 must not turn
it into a queue, scheduler, readiness oracle, dependency-closure plan,
completeness oracle, Stage 9 backend plan, renderer-ready IR, backend-map
evaluator, source scanner, registry, dispatcher, hidden backfeed, or fixpoint
mechanism.

## Taxonomy Fit

- The M103 worklist remains a lowering inventory.
- M104 may add typed translation result records, explicit typed rule input
  records, and local provenance values as needed.
- M104 must preserve object identity to accepted M103 worklist entries, M99
  request/no-request records, optional M100 result/deferred records, and
  earlier source facts.
- M104 must not introduce a new `work_item` taxonomy category.
- M102 protocol conformance may validate shape, but must not route semantics
  or accept arbitrary fake objects that merely satisfy a protocol.

## Scope

- Add focused private lowering modules for backend translation expansion, such
  as:
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_models.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_sources.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_validation.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_diagnostics.py`
- Consume only accepted concrete M103
  `Stage8BackendBoundaryWorklistInventoryIr` values.
- Accept only M103 entries classified as
  `exact_array_backend_uninit_unresolved` or
  `selected_body_direct_intrinsic_deferred`.
- Produce deterministic typed resolved/deferred/unsupported translation
  expansion result records.
- Resolve exact-array backend-uninit unresolved entries only from explicit
  typed rule inputs. This may extend beyond M100 only when the rule carries
  typed context M100 did not accept, such as the backend/type context required
  for a Rust or additional exact value result.
- Resolve selected-body direct-intrinsic deferred entries only from explicit
  typed rule inputs identity-bound to accepted typed request/worklist facts.
- Emit typed deferred/unsupported records with diagnostics when no explicit
  rule applies, when a rule is malformed, or when provenance/context does not
  match the accepted worklist entry.
- Preserve deterministic ordering, stable keys, source locations, candidate
  ids, source inventory/result keys, and object identities.
- Keep new M104-specific contracts local to focused M104 modules unless a
  later consolidation milestone accepts shared ownership.
- Add focused tests in a new test file such as
  `tslgen/tests/unit/test_lowering_backend_translation_expansion.py` rather
  than expanding the already-large `test_lowering_boundary.py`.

## Out Of Scope

- Rendering, renderer-ready IR, generated output, Stage 9 backend planning,
  artifact planning, wrapper planning, output/report/writer behavior, compiler
  execution, and host hardware dependency.
- Backend map/catalog/manifest reads during lowering, `tsldata/detail/lang`
  reads, generic backend helper evaluation, or raw helper text parsing.
- Calling existing translation lowerers to complete missing work.
- Source-body reparsing, source repair, source normalization, best-effort
  correction, broad TSIL/body parsing, or guessing the intended meaning of a
  malformed `.tsl` body.
- Dispatching by `svptrue_b*`, extension id, type tag, byte size, primitive
  name, raw direct-intrinsic token text, source-location text, or
  hardware-looking tokens.
- Direct-intrinsic/SVE semantic inference beyond explicit typed rule input.
- Rust rendering or broad Rust support. Rust exact-array uninit is allowed only
  if the typed rule input supplies the required typed backend/type context and
  the output remains a typed translation result.
- Operation scheduling, dependency closure, queues, scheduler/readiness
  behavior, registries, dispatchers, callbacks, plugins, hidden backfeeds,
  fixpoint mechanisms, or category-based semantic dispatch.
- Pipeline integration through `LoweredImplementation`, public facade exports,
  `_lower_input` orchestration, new `GenerationLoweringStageName` /
  `_stage_contracts.py` integration, or `boundary.py` growth.
- Growing `_lowering_ir_contracts.py`, M99/M100 modules, or M103 worklist
  modules for M104 ownership.

## Required Executor Task

Run exactly one write-capable executor for M104. The executor should:

1. Inspect accepted M99 request inventory, M100 exact-array translation result,
   M102 protocol surface, and M103 backend-boundary worklist modules.
2. Add the smallest focused private backend translation expansion module set
   needed to represent typed resolved/deferred/unsupported result records.
3. Consume only concrete accepted M103 worklist inventories.
4. Preserve object identity to M103 worklist entries, M99 request/no-request
   records, optional M100 result/deferred records, and earlier provenance.
5. Reject arbitrary fake objects that merely satisfy M102 protocols.
6. Use explicit typed rule inputs only; do not infer semantics from worklist
   classification, direct-intrinsic token text, SVE-looking strings, extension
   ids, type tags, byte sizes, primitive names, source locations, or hardware-
   looking tokens.
7. Avoid `boundary.py`, `LoweredImplementation`, public facade, `_lower_input`,
   `GenerationLoweringStageName`, `_stage_contracts.py`, M99/M100 modules,
   M103 worklist modules, and `_lowering_ir_contracts.py` growth.
8. Keep M104-specific contract constants in focused M104 modules.
9. Add focused tests in a new test file.
10. Run the required validation commands below.
11. Return a concise implementation summary, files changed, validation
    results, line counts, review verdicts, and follow-ups.

If the executor discovers that M104 cannot be implemented as a typed
rule-input-driven result expansion without adding generic dispatcher,
scheduler/readiness, Stage 9, rendering, backend-map reads, source repair, or
hardwired token semantics, stop implementation, record the blocker in
`docs/redesign/open-questions.md`, and return `Return To Planner` with a
planning-revision prompt.

## Required Tests

- Positive exact-array unresolved entry resolved by explicit typed rule input.
- Positive selected-body direct-intrinsic deferred entry resolved by explicit
  typed rule input.
- Missing rule produces typed deferred or unsupported state, not guessed
  behavior.
- Negative tests for rule mismatch, duplicate/conflicting rules, fake
  protocol-shaped worklist/rule/result objects, malformed source containers,
  malformed keys, and provenance mismatch.
- Direct-intrinsic negative tests proving no dispatch by `svptrue_b*`,
  extension id, type tag, byte size, primitive name, raw token text,
  source-location text, or hardware-looking tokens.
- Determinism tests for ordering and repeat-run equality.
- Import-boundary/source assertions proving no `boundary.py`, public
  `tslgen.lowering` facade, backend modules, renderers, backend planners,
  `tsldata`, `frozen`, backend maps/catalogs/manifests, raw parsing helpers,
  source repair, registry/dispatcher/callback/plugin/backfeed/fixpoint, or
  category-based semantic dispatch.
- Line-count tests or source assertions proving M104 does not grow
  `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, M103 worklist
  modules, or new M104 modules into replacement monoliths.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py tslgen/tests/unit/test_lowering_backend_translation_expansion.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py tslgen/tests/unit/test_lowering_backend_translation_expansion.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_expansion.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_boundary_worklist.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_translation_expansion.py tslgen/tests/unit/test_lowering_backend_boundary_worklist.py tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

If implementation creates focused model/source/validation/diagnostic sibling
modules, include them in line-count, py-compile, pytest/source assertions,
mypy, and final reporting.

Run broader validation if shared lowering behavior changes beyond the private
M104 translation expansion module set:

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
2. Boundary auditor: verify no scheduler/readiness behavior, Stage 9 backend
   planning, renderer-ready IR, rendering/output, backend map/catalog/manifest
   reads, raw helper parsing, source repair, generic backend dispatcher,
   category-based semantic dispatch, or direct-intrinsic/SVE hardwiring.
3. Extensibility auditor: verify ownership stays in focused private modules,
   `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, and M103
   modules do not grow, no broad inheritance/registry/dispatcher/callback/
   plugin/backfeed/fixpoint mechanism appears, and tests enforce line-count
   ceilings/import boundaries.
4. Validation auditor: verify tests and validation results, including
   explicit typed rule positives, missing-rule deferred/unsupported behavior,
   fake protocol-shaped object negatives, no-hardwiring negatives,
   determinism, identity preservation, diagnostics, import boundaries, and
   mypy.
5. Documentation auditor: verify roadmap/state/design docs and
   `docs/redesign/missing-lowering-inventory.md` reflect accepted M104
   behavior and remaining deferred backend/rendering work accurately.

## Review Loop

The main thread is the orchestrator.

- If all reviews return `Accept`, mark M104 accepted, update
  `docs/agent/current-redesign-state.md`, update any needed redesign docs, and
  create `docs/agent/runs/post-m104-planning-plus-review-prompt.md`.
- If reviews return `Accept With Follow-Ups`, record non-blocking follow-ups,
  mark M104 accepted, update state/docs, and create the post-M104 planning
  prompt.
- If any review returns `Needs Revision`, run one focused write-capable
  revision executor limited to the blocking issues, then run focused re-review.
- If any review returns `Return To Planner`, stop implementation, update state,
  and create an appropriate post-M104 planning-revision prompt.
- If any review returns `Reject`, stop implementation, update state, and
  create an appropriate rollback/redesign prompt.

Only one write-capable executor or revision executor may modify a worktree at
a time. Review and audit subagents are read-only unless the orchestrator later
creates a focused revision task.

## Finalization Rules

On `Accept` or `Accept With Follow-Ups`, before finishing:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record accepted M104 behavior and validation;
- update `docs/redesign/missing-lowering-inventory.md` if M104 narrows or
  resolves backend-boundary lowering gaps;
- create the next concrete run prompt under `docs/agent/runs/`;
- run the final `git diff --check`.

Do not start Milestone 105 or post-M104 implementation work.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
