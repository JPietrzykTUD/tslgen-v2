# Post-M99 Planning Plus Review Prompt

You are planning the next redesign milestone after accepted M99.

Milestones 1 through 99 are accepted. M99 accepted:

```text
Milestone 99: Operation Package Backend-Translation Request Inventory Slice
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
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Planning Goal

Select exactly one next milestone that advances the lowering redesign toward
completion while respecting the accepted M99 boundary.

Prefer a high-value lowering milestone that:

- builds on accepted typed Stage 8 package/manifest/gap/request-inventory
  facts instead of raw source text;
- keeps semantic lowering typed, staged, composable, and maintainable;
- preserves accepted M57-M99 diagnostics, stage names, ordering, keys, output
  identities, object identities, and public imports;
- avoids broad source repair, raw text rewriting, and best-effort correction;
- preserves small-module guardrails and avoids new catch-all files;
- does not add backend translation, rendering, generated output, or Stage 9
  planning unless the selected scope explicitly and narrowly requires it.

## Current Boundary Reminders

- `frozen/` is evidence only and must never become runtime input.
- M99 is accepted Stage 8 lowering inventory/provenance work only.
- M99 added the deterministic `lowering_backend_translation_request_inventory`
  stage after `lowering_completion_gap_inventory`.
- M99 ownership is split across focused private inventory, source-adapter, and
  diagnostics modules.
- M99 consumes only accepted typed M93-M98 operation-package, manifest,
  gap-inventory, and stage-assembly facts plus their preserved object
  references.
- M99 records exact-array backend-value request, selected-body direct-intrinsic
  handoff, and no-accepted-request inventory states. It does not translate,
  resolve, evaluate, plan, schedule, or render those facts.
- M99 did not parse raw `.tsl` source text, repair source bodies, infer package
  requests, read backend maps/catalogs/manifests, evaluate generic
  `value<backend>(...)` or `type<backend>(...)`, infer direct-intrinsic/SVE
  semantics, create Stage 9 plans, produce renderer-ready IR, render output,
  schedule operations, solve dependencies, or perform dependency closure.
- `docs/redesign/missing-lowering-inventory.md` is documentation only. It is
  not runtime input, generated output, a source scanner, a dependency-closure
  plan, or a completeness oracle.

## Required Subagents

Use read-only planning/review subagents:

1. Planner: propose one concrete next lowering milestone, with scope,
   out-of-scope boundaries, required tests, validation, and expected files.
2. Boundary auditor: check the proposal against lowering-stage, source-body
   integrity, backend/rendering, hardwiring, and no-repair boundaries.
3. Extensibility auditor: check module ownership, line-count pressure,
   composable pipeline fit, and whether the plan avoids new monoliths.
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
