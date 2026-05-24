# Post-M104 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M104.

Milestones 1 through 104 are accepted. M104 accepted:

```text
Milestone 104: Worklist-Driven Backend Translation Result Expansion Slice
```

The next task should focus on lowering. Do not implement code unless this
prompt explicitly selects an executor task; this prompt is planning and review
only.

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
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_models.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_validation.py`
- `tslgen/tests/unit/test_lowering_backend_translation_expansion.py`
- `tslgen/tests/unit/test_lowering_backend_boundary_worklist.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`

## Planning Goal

Select exactly one next milestone that advances lowering toward completion
after M104's typed worklist-driven backend translation expansion result
boundary.

Prefer a high-value lowering milestone that:

- builds on accepted M99-M104 typed request, result, worklist, expansion,
  provenance, rule-input, and diagnostic boundaries;
- chooses one coherent boundary rather than a generic backend dispatcher;
- moves the pipeline closer to renderer-ready body/value IR, additional typed
  backend value/type results, direct-intrinsic result broadening, primitive
  call/dependency facts, or another documented lowering gap;
- keeps semantic behavior driven by explicit typed facts, typed context, typed
  rule inputs, or typed evaluator functions;
- preserves accepted diagnostics, stage names, ordering, keys, output
  identities, object identities, source locations, public imports, and
  deterministic behavior;
- keeps ownership in focused private modules and avoids further growth in
  `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, M103 worklist
  modules, and M104 expansion modules unless the plan explicitly extracts a
  cohesive module;
- avoids source repair, raw text rewriting, best-effort correction,
  backend-map/catalog/manifest reads during lowering, category-based semantic
  dispatch, broad registries/dispatchers, hidden backfeeds, fixpoint
  mechanisms, scheduler/readiness behavior, Stage 9 planning, rendering, and
  renderer inference.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M99 accepts typed Stage 8 backend-translation request inventory facts.
- M100 accepts only the exact-array C++ `value_array_uninit`
  translation-result boundary from accepted M99 exact-array request records and
  explicit typed C++ rule input.
- M101/M102 accept private lowering IR taxonomy, provenance, and category
  protocol surfaces for the M99/M100 path. They must not become a semantic
  dispatcher or broad public hierarchy.
- M103 accepts a private typed Stage 8 backend-boundary worklist inventory over
  accepted concrete M99 request inventories and optional concrete M100
  exact-array backend-uninit translation results.
- M104 accepts private typed backend translation expansion results over
  concrete M103 worklist inventories. It consumes only the
  `exact_array_backend_uninit_unresolved` and
  `selected_body_direct_intrinsic_deferred` classifications.
- M104 missing rules produce typed deferred records. M104 mismatched,
  duplicate, or conflicting explicit rules for accepted entries produce typed
  unsupported records. Malformed fake inputs and malformed containers fail at
  the boundary with diagnostics.
- M104 does not infer from `svptrue_b*`, extension id, type tag, byte size,
  primitive name, raw direct-intrinsic token text, source-location text, or
  hardware-looking tokens.
- M104 did not add pipeline/facade integration, `GenerationLoweringStageName`
  values, `_stage_contracts.py` entries, Stage 9 planning, rendering,
  generated output, backend map/catalog/manifest reads, source repair,
  scheduler/readiness behavior, dependency closure, registry/dispatcher/plugin
  behavior, hidden backfeeds, fixpoint machinery, or category-based semantic
  dispatch.
- Remaining lowering gaps include broad backend value/type translation,
  explicit Rust/type context, renderer-ready body IR, primitive calls and
  dependencies, modifiers, broader direct-intrinsic families, broader body
  structure, and output integration after typed lowering/backend results.
- `docs/redesign/missing-lowering-inventory.md` is documentation only. It is
  not runtime input, generated output, a source scanner, dependency-closure
  plan, or completeness oracle.

## Required Subagents

Use read-only planning/review subagents:

1. Planner: propose one concrete next lowering milestone, with scope,
   out-of-scope boundaries, required tests, validation, expected files, and the
   accepted M104 result surface or missing-inventory gap it advances.
2. Boundary auditor: check the proposal against lowering-stage,
   source-body-integrity, backend/rendering, hardwiring, source-repair,
   no-raw-helper, no category-based semantic-dispatch, no scheduler/readiness,
   and no Stage 9 boundaries.
3. Extensibility auditor: check module ownership, line-count pressure,
   composable pipeline fit, M101/M102 taxonomy/protocol fit, M103/M104
   ownership, and whether the plan avoids new monoliths and further
   `boundary.py` growth.
4. Documentation auditor: check whether roadmap/state/design docs and
   `docs/redesign/missing-lowering-inventory.md` would remain coherent after
   accepting the plan.

The main thread is the orchestrator. Consolidate the subagent results into one
planning verdict:

```text
Accept
Accept With Follow-Ups
Needs Revision
Return To Planner
Reject
```

If the plan needs local planning-doc corrections, make only documentation
changes. Do not modify implementation code or tests.

## Required Output

If the selected plan is accepted or accepted with follow-ups:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record the selected next milestone;
- update `docs/redesign/missing-lowering-inventory.md` if the selected plan
  resolves, narrows, or newly discovers lowering gaps;
- create the next concrete run prompt under `docs/agent/runs/`.

If human acceptance is required before execution, create an acceptance
finalization prompt. If local policy permits direct execution next, create the
executor or execution-review-loop prompt. In both cases, point
`docs/agent/current-redesign-state.md` at the new prompt.

If the result is `Needs Revision`, create a focused planning-revision prompt.
If the result is `Return To Planner` or `Reject`, create the appropriate
planner/rollback prompt and record the stop/next condition.

## Validation

Run:

```bash
git diff --check
```

If other docs are changed, include them in the diff-check by running the same
repository-wide command.

## Final Report

Report:

1. Selected next milestone or stop condition.
2. Planning verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command and exact result.
