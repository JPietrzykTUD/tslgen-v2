# Post-M103 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M103.

Milestones 1 through 103 are accepted. M103 accepted:

```text
Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice
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
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py`
- `tslgen/tests/unit/test_lowering_backend_boundary_worklist.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`

## Planning Goal

Select exactly one next milestone that advances lowering toward completion
after M103's static Stage 8 backend-boundary worklist inventory.

Prefer a high-value lowering milestone that:

- selects exactly one M103 worklist row/classification or one documented
  missing-lowering inventory gap as the next focused implementation target;
- consumes accepted typed facts, requests, results, inventories, provenance,
  rule inputs, and diagnostic boundaries instead of raw source text;
- keeps the Stage 8 worklist a static inventory/provenance view and does not
  turn it into a queue, scheduler, readiness oracle, dependency closure,
  completeness oracle, Stage 9 backend plan, or renderer-ready IR;
- uses typed rule inputs or typed evaluator functions for semantic behavior;
- preserves accepted diagnostics, stage names, ordering, keys, output
  identities, object identities, source locations, public imports, and
  deterministic behavior;
- keeps ownership in focused private modules and avoids further growth in
  `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, and M103
  worklist modules unless the plan explicitly extracts a cohesive module;
- avoids source repair, raw text rewriting, best-effort correction,
  backend-map/catalog/manifest reads during lowering, category-based semantic
  dispatch, broad registries/dispatchers, hidden backfeeds, fixpoint
  mechanisms, and renderer inference.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M99 accepts typed Stage 8 backend-translation request inventory facts over
  accepted operation packages, manifests, and gap inventories.
- M100 accepts only the exact-array C++ `value_array_uninit`
  translation-result boundary from accepted M99
  `exact_array_backend_value_uninit_array` records and explicit typed C++ rule
  input.
- M101/M102 accept private lowering IR taxonomy, provenance, and category
  protocol surfaces for the M99/M100 path. They must not become a semantic
  dispatcher or broad public hierarchy.
- M103 accepts a private typed Stage 8 backend-boundary worklist inventory over
  accepted concrete M99 request inventories and optional concrete M100
  exact-array backend-uninit translation results.
- M103 classifications are:
  `exact_array_backend_uninit_translated`,
  `exact_array_backend_uninit_unresolved`,
  `selected_body_direct_intrinsic_deferred`, and
  `no_accepted_backend_boundary_fact`.
- M103 rejects arbitrary protocol-shaped fake objects and malformed source
  containers with diagnostics.
- M103 did not add pipeline/facade integration, `GenerationLoweringStageName`
  values, `_stage_contracts.py` entries, Stage 9 planning, rendering,
  generated output, backend map/catalog/manifest reads, translation lowerer
  calls, direct-intrinsic/SVE resolution, source repair, or category-based
  semantic dispatch.
- Rust `value_array_uninit`, scalar/vector backend type spelling, backend
  modifiers, direct-intrinsic resolution, renderer-ready exact-array body IR,
  primitive calls/dependencies, broader body structure, and broad backend
  support decisions remain deferred unless the selected milestone narrows one
  of them into a typed lowering slice.
- `docs/redesign/missing-lowering-inventory.md` is documentation only. It is
  not runtime input, generated output, a source scanner, dependency-closure
  plan, or completeness oracle.

## Required Subagents

Use read-only planning/review subagents:

1. Planner: propose one concrete next lowering milestone, with scope,
   out-of-scope boundaries, required tests, validation, expected files, and the
   M103 worklist classification or missing-inventory gap it advances.
2. Boundary auditor: check the proposal against lowering-stage,
   source-body-integrity, backend/rendering, hardwiring, source-repair,
   no-raw-helper, and no category-based semantic-dispatch boundaries.
3. Extensibility auditor: check module ownership, line-count pressure,
   composable pipeline fit, M101/M102 taxonomy/protocol fit, M103 worklist
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
