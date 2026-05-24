# M102 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 102.

Milestones 1 through 101 are accepted. Post-M101 planning is accepted and
selected:

```text
Milestone 102: Lowering IR Category Protocol Surface Slice
```

Use the orchestrated executor-review loop in this prompt. M102 is an
implementation/documentation milestone; one write-capable executor may
implement the selected architecture slice. Do not start post-M102 planning
until M102 review returns `Accept` or `Accept With Follow-Ups`.

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
- `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Turn the M101 taxonomy from string/category labels into a small, explicit,
private lowering IR category surface that future milestones can target before
adding more feature-specific request/result/inventory families. M102 should
make the architecture easier to extend without introducing new lowering
semantics.

For M102, "IR category protocol surface" means typed, maintainable contracts
such as:

- `LoweringFact`: an accepted domain/semantic fact produced by lowering;
- `LoweringRequestIr`: a typed unresolved need for a later lowering/backend
  stage;
- `TranslationRequestIr`: a backend-translation-specific request category;
- `TranslationResultIr`: a typed fulfillment of a translation request from
  explicit facts/rules;
- `LoweringInventory`: a deterministic collection of accepted facts, not a
  readiness claim;
- `LoweringProvenance`: source/object identity needed for diagnostics,
  determinism, and traceability;
- `LoweringRuleInput`: explicit typed metadata supplied before evaluation;
- `LoweringStageOutput`: the typed output carried by a named stage envelope;
- `DiagnosticBoundary`: a typed boundary for malformed, unsupported, context,
  source-location, and provenance diagnostics.

The existing public `LoweringRequest` input/configuration bundle is not the
same concept as taxonomy-level request IR. M102 must not rename or break that
public API.

## Scope

- Add or refine private lowering contracts/protocols in the M101-owned
  contract area, likely `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
  or a focused sibling module.
- Keep the surface structural and typed, using small protocols, value objects,
  or helper predicates where useful. Do not impose a broad inheritance
  hierarchy on M57-M101 classes.
- Apply the protocol surface only to the accepted M99/M100 backend-translation
  request/result path as the first proof point.
- Preserve accepted M99/M100 keys, diagnostics, source locations, object
  identities, stage names, stage ordering, public imports, and deterministic
  behavior.
- Clarify in docs and tests that future feature-specific IR additions must
  first choose one of the stable category protocols.
- Keep `boundary.py` as a facade; do not add orchestration there.

## Out Of Scope

- New lowering semantics, new request families, new translation result
  families, C++ declaration/body assembly, Rust translation, generic
  `value<backend>(...)` or `type<backend>(...)` evaluation, backend
  map/catalog/manifest reads during lowering, backend support decisions,
  Stage 9 backend planning, rendering, generated output, operation scheduling,
  dependency closure, wrapper planning, artifact planning, CLI/report/writer
  behavior, compiler execution, or host hardware dependency.
- Raw `.tsl` source parsing, source-body reparsing, source repair,
  source normalization, best-effort correction, broad TSIL/body parsing,
  selected-body direct-intrinsic resolution, SVE/direct-intrinsic semantics,
  byte-size-to-token inference, or vector/register metadata expansion.
- Renaming the existing public `LoweringRequest`, rewriting all accepted
  M57-M101 IR to inherit from new base classes, introducing registries,
  dispatchers, callback maps, plugin mechanisms, hidden backfeeds, fixpoint
  machinery, or turning protocols into renderer/backend-planning APIs.
- Category-based semantic dispatch. The protocol surface may validate shape,
  category, key/provenance availability, or structural conformance, but it
  must not decide behavior, route requests, translate backend values, choose
  renderers, evaluate helpers, or act as a registry/dispatcher.

## Required Executor Task

Run exactly one write-capable executor for M102. The executor should:

1. Inspect the accepted M101 contract module and M99/M100 backend-translation
   request/result classes.
2. Add the smallest private category/protocol surface needed to make the M101
   taxonomy structurally usable.
3. Apply the surface only to the accepted M99/M100 backend-translation
   request/result path.
4. Preserve accepted keys, diagnostics, source locations, object identities,
   stage names, ordering, public imports, and deterministic behavior.
5. Add focused tests for positive category/protocol classification.
6. Add negative tests proving wrong, missing, or mismatched category/protocol
   conformance is caught as a structural contract failure.
7. Add import-boundary and forbidden-behavior tests proving no backend/
   rendering imports, no `tsldata`/`frozen` dependency, no raw parsing helpers,
   and no category-based semantic dispatch.
8. Avoid all out-of-scope backend, rendering, Stage 9, Rust, raw parsing,
   source repair, registry/dispatcher, broad hierarchy, hidden-backfeed,
   fixpoint, semantic-routing, and `boundary.py` growth.
9. Run the required validation commands below.
10. Return a concise implementation summary, files changed, validation
    results, line counts, review verdicts, and follow-ups.

If the executor discovers that the M101 taxonomy cannot be represented as a
small private structural surface without semantic risk, stop implementation,
record the blocker in `docs/redesign/open-questions.md`, and return
`Return To Planner` with a planning-revision prompt.

## Required Tests

- Focused contract/protocol tests for the new category surface.
- Negative tests proving wrong, missing, or mismatched category/protocol
  conformance is caught.
- Regression tests proving M99 backend-translation request inventory and M100
  exact-array backend-uninit translation result behavior remain unchanged.
- Diagnostic tests covering the existing malformed/source/container,
  provenance mismatch, context mismatch, source-location mismatch,
  missing/duplicate/conflicting rule, unsupported backend, and wrong
  request-kind cases.
- Import-boundary tests proving the category/protocol module does not import
  `boundary.py`, the `tslgen.lowering` facade, backend modules, renderers,
  backend planners, `tsldata`, or `frozen`.
- Source assertions proving the protocol surface does not contain or introduce
  category-based semantic dispatch, registry, dispatcher, callback, plugin,
  hidden backfeed, fixpoint, renderer selection, backend value translation,
  helper evaluation, raw parsing, or source repair behavior.
- Line-count tests or source assertions proving the protocol surface does not
  grow `boundary.py`, `_lowering_stage_assembly.py`, M99/M100 modules, or the
  contract module into a new monolith.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_ir_contracts.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or exact_array_backend_uninit_translation_result or m100 or m101 or m102"
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

If implementation creates a new category/protocol test file or module, include
it in line-count, py-compile, pytest, mypy, import-boundary tests, and final
reporting.

Run broader validation if shared lowering behavior changes beyond the M99/M100
path:

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
2. Boundary auditor: verify no new lowering semantics, backend translation
   semantics, backend map/catalog/manifest reads during lowering, raw helper
   parsing, source repair, renderer inference, Stage 9 planning,
   rendering/output, Rust translation, generic backend helper evaluation,
   direct-intrinsic/SVE semantics, generated output, or category-based
   semantic dispatch.
3. Extensibility auditor: verify the category/protocol surface is small,
   private, structural, and applied first to M99/M100 without creating broad
   inheritance, registry, dispatcher, callback system, plugin mechanism,
   hidden backfeed, fixpoint system, or replacement monolith.
4. Validation auditor: verify tests and validation results, including
   conformance positives/negatives, diagnostics, determinism, object identity,
   import boundaries, forbidden behavior, line counts, and mypy.
5. Documentation auditor: verify roadmap/state/design docs and
   `docs/redesign/missing-lowering-inventory.md` reflect M102 accurately.

## Review Loop

The main thread is the orchestrator.

- If all reviews return `Accept`, mark M102 accepted, update
  `docs/agent/current-redesign-state.md`, update any needed redesign docs, and
  create `docs/agent/runs/post-m102-planning-plus-review-prompt.md`.
- If reviews return `Accept With Follow-Ups`, record non-blocking follow-ups,
  mark M102 accepted, update state/docs, and create the post-M102 planning
  prompt.
- If any review returns `Needs Revision`, run one focused write-capable
  revision executor limited to the blocking issues, then run focused re-review.
- If any review returns `Return To Planner`, stop implementation, update state,
  and create an appropriate post-M102 planning-revision prompt.
- If any review returns `Reject`, stop implementation, update state, and create
  an appropriate rollback/redesign prompt.

Only one write-capable executor or revision executor may modify a worktree at
a time. Review and audit subagents are read-only unless the orchestrator later
creates a focused revision task.

## Finalization Rules

On `Accept` or `Accept With Follow-Ups`, before finishing:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record accepted M102 behavior and validation;
- update `docs/redesign/missing-lowering-inventory.md` if M102 narrows or
  resolves the category/protocol-surface gap;
- create the next concrete run prompt under `docs/agent/runs/`;
- run the final `git diff --check`.

Do not start Milestone 103 or post-M102 implementation work.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
