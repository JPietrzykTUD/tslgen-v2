# M149 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M148:

```text
Milestone 149: Primitive-Call Closure Function Lowering Package Boundary
```

Milestones 1 through 148 are accepted. M148 computes a compact typed
primitive-call dependency closure by repeatedly applying the accepted M147
primitive-call reference inventory to a root selected implementation and newly
discovered target implementations. M148 deliberately stopped before dependency
scheduling, dependency-body rendering, primitive-call invocation rendering, or
expression parsing.

M149 should take the next small lowering step: compose the M148 closure with
the existing selected-function lowering for the selected implementations in
that closure. The result should be an inspectable package that says which
selected dependency bodies are already lowerable by the tiny lowerer, while
preserving closure references and diagnostics.

This is a lowering package boundary, not a scheduler, renderer, call renderer,
or graph subsystem.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/requirements.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/tsil-type-query-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_call_inventory.py`
- `tslgen/src/tslgen/lowering/primitive_call_closure.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m146_primitive_call_argument_binding.py`
- `tslgen/tests/test_m147_primitive_call_reference_inventory.py`
- `tslgen/tests/test_m148_primitive_call_dependency_closure.py`

## Goal

Add a small typed closure-lowering package boundary that turns one root
selected implementation plus catalog facts into:

- the M148 primitive-call dependency closure;
- lowered functions for selected implementations in closure selected order,
  using only the existing selected-function lowerer;
- accumulated diagnostics from closure discovery and selected-function
  lowering.

Supported exact behavior:

- Start from one `SelectedImplementation`.
- Run M148 dependency closure for the root.
- For each selected implementation in closure `selected` order, run the
  existing selected-function lowering behavior.
- Include successful lowered functions in deterministic closure order.
- Accumulate selected-function lowering diagnostics even when one selected
  implementation fails to lower.
- Preserve the M148 closure references and selected implementation list
  unchanged in the package result.

The result should be a compact typed value, for example
`PrimitiveCallClosureLoweringPackage` with `closure`, `lowered_functions`, and
`diagnostics`. A small helper function is fine; do not expose a dependency
graph, scheduler, registry, dispatcher, fixpoint engine, or broad worklist
family.

## Required Executor Task

Run exactly one write-capable executor for M149. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M148 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a focused typed closure-lowering package model in the existing
   lowering ownership area.
4. Add a lowerer entry point that consumes a root selected implementation and
   catalog, then returns the closure-lowering package.
5. Compose the accepted M148 closure helper and existing selected-function
   lowering; do not duplicate primitive-call inventory, selector parsing,
   target matching, argument binding, or selected-function lowering logic.
6. Preserve deterministic ordering from M148 closure selected order.
7. Add focused positive tests for:
   - root plus one lowerable dependency lowering both supported operation
     bodies;
   - deterministic lowered-function order matching closure selected order.
8. Add focused diagnostic tests for:
   - a dependency whose body is unsupported by selected-function lowering;
   - closure diagnostics and selected-function lowering diagnostics both
     appearing in the package diagnostics.
9. Update redesign docs if package ownership, ordering, diagnostics, or the
   out-of-scope scheduling/rendering boundary is clarified.

## Out Of Scope

Dependency scheduling; topological sorting for rendering; backend call
rendering; lowering primitive-call references into invocation text; resolving
call arguments into backend expressions; recursively lowering nested calls
inside arguments; parsing raw argument expressions; resolving argument
identifiers; array/index/operator/helper/cast semantics; rendering backend
type text; replacing existing scalar operation lowering; source repair;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; public dependency
graphs, schedulers, registries, dispatchers, fixpoint mechanisms, broad
request/result/worklist families, or source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M149 adds only a compact typed lowering
   package boundary and does not become scheduling, dependency-body rendering,
   primitive-call invocation rendering, expression parsing, or broad
   graph/worklist machinery.
2. Boundary auditor: verify the package composes M148 closure and existing
   selected-function lowering without duplicating M144-M148 logic.
3. Evidence auditor: verify tests are grounded in accepted clean-restart
   primitive-call dependency and selected-function lowering behavior, and that
   unsupported cases remain explicit diagnostics.
4. Documentation auditor: verify docs accurately describe the package
   boundary and defer scheduling, call rendering, expression parsing, and
   backend rendering.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M149 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M149 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M149 is accepted. Do not start dependency scheduling,
primitive-call invocation rendering, or backend rendering until M149 is
accepted and the next prompt explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 150 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
