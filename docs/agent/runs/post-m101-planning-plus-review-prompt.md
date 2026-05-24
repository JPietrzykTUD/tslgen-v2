# Post-M101 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M101.

Milestones 1 through 101 are accepted. M101 accepted:

```text
Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice
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
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select exactly one next milestone that advances lowering toward completion
after M101's taxonomy/provenance consolidation.

Prefer a high-value lowering milestone that:

- builds on accepted typed M57-M101 lowering facts, requests, results,
  inventories, provenance contracts, rule inputs, and stage envelopes instead
  of raw source text;
- keeps semantic lowering typed, staged, composable, maintainable, and split
  across focused modules;
- uses the M101 IR taxonomy pressure check before adding any new request,
  result, inventory, package, or handoff object;
- preserves accepted diagnostics, stage names, ordering, keys, output
  identities, object identities, source locations, public imports, and
  deterministic behavior;
- avoids broad source repair, raw text rewriting, best-effort correction,
  backend map/catalog/manifest reads during lowering, and renderer inference;
- does not add rendering, generated output, Stage 9 planning, Rust translation,
  generic backend helper evaluation, operation scheduling, dependency closure,
  or direct-intrinsic/SVE semantics unless the selected scope explicitly and
  narrowly requires a typed boundary for that behavior;
- avoids adding more orchestration to `boundary.py` without extracting boundary
  request/result assembly.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M99 accepts typed Stage 8 backend-translation request inventory facts over
  accepted operation packages, manifests, and gap inventories.
- M100 accepts only the exact-array C++ `value_array_uninit`
  translation-result boundary from accepted M99
  `exact_array_backend_value_uninit_array` records and explicit typed C++ rule
  input.
- M101 accepts a private lowering IR taxonomy/provenance contract for the
  M99/M100 backend-translation request/result path. It did not add new
  lowering semantics, new request/result families, backend translation
  semantics, rendering/output, Stage 9 planning, Rust translation, generic
  backend helper evaluation, backend map/catalog/manifest reads, raw source
  parsing, source repair, selected-body direct-intrinsic resolution, SVE
  semantics, scheduling, dependency closure, a broad hierarchy, registry,
  dispatcher, hidden backfeed, or fixpoint mechanism.
- Future new IR classes should first fit the M101 taxonomy categories:
  semantic fact, request, result, inventory, provenance value, rule input, or
  stage envelope.
- Rust `value_array_uninit` remains deferred until typed type context and rule
  inputs are accepted.
- `docs/redesign/missing-lowering-inventory.md` is documentation only. It is
  not runtime input, generated output, a source scanner, a dependency-closure
  plan, or a completeness oracle.

## Required Subagents

Use read-only planning/review subagents:

1. Planner: propose one concrete next lowering milestone, with scope,
   out-of-scope boundaries, required tests, validation, and expected files.
2. Boundary auditor: check the proposal against lowering-stage, source-body
   integrity, backend/rendering, hardwiring, source-repair, and no-raw-helper
   boundaries.
3. Extensibility auditor: check module ownership, line-count pressure,
   composable pipeline fit, M101 taxonomy fit, and whether the plan avoids new
   monoliths and further `boundary.py` growth.
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
