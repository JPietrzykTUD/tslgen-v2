# M148 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M147:

```text
Milestone 148: Primitive-Call Dependency Closure Boundary
```

Milestones 1 through 147 are accepted. M147 walks a selected implementation
body in source order and composes M144 selector-payload lowering, M145 target
matching, and M146 argument binding into a typed source-ordered inventory of
primitive-call references. M147 deliberately stopped before dependency
closure, dependency scheduling, dependency-body lowering, recursive nested-call
lowering, or backend rendering.

M148 should take the next small lowering step: compute the dependency closure
over selected implementations by repeatedly applying the accepted M147
primitive-call reference inventory to a root selected implementation and newly
discovered target implementations.

This is a dependency closure boundary, not a scheduler, renderer, or graph
subsystem.

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
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/src/tslgen/lowering/primitive_call_targets.py`
- `tslgen/src/tslgen/lowering/primitive_call_arguments.py`
- `tslgen/src/tslgen/lowering/primitive_call_inventory.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m146_primitive_call_argument_binding.py`
- `tslgen/tests/test_m147_primitive_call_reference_inventory.py`

## Goal

Add a small typed dependency-closure boundary that turns one root selected
implementation plus catalog facts into:

- the root and all transitively referenced selected implementations in
  deterministic first-discovery order;
- the primitive-call references that caused discovery, also in deterministic
  discovery order;
- accumulated diagnostics from each M147 inventory.

Supported exact behavior:

- Start from one `SelectedImplementation`.
- Run M147 reference inventory for the root.
- Treat each successful `PrimitiveCallReference.target_match.selected` as a
  dependency selected implementation.
- Recursively run M147 reference inventory for newly discovered selected
  implementations.
- De-duplicate selected implementations by a stable selected target identity,
  so self-recursion, cycles, and shared dependencies terminate deterministically.
- Continue collecting successful references and later dependencies when one
  selected implementation inventory reports diagnostics.

The result should be a compact typed value, for example
`PrimitiveCallDependencyClosure` with selected implementations, references,
and diagnostics. A small internal queue or loop is fine; do not expose a
dependency graph, scheduler, registry, dispatcher, fixpoint engine, or broad
worklist family.

## Required Executor Task

Run exactly one write-capable executor for M148. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M147 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a focused typed dependency-closure model in the existing
   lowering/domain ownership area.
4. Add a lowerer entry point that consumes a root selected implementation and
   catalog, then returns the dependency closure plus diagnostics.
5. Compose the accepted M147 inventory helper; do not duplicate selector
   parsing, target matching, argument binding, or raw call walking.
6. Use deterministic selected-implementation identity derived from the target
   fields and primitive attributes already available on `SelectedImplementation`.
7. Add focused positive tests for:
   - one-hop closure;
   - transitive closure;
   - shared dependency de-duplication;
   - self-recursive or cyclic calls terminating without duplicate selected
     implementations.
8. Add focused diagnostic tests for:
   - diagnostics from a root inventory;
   - diagnostics from a dependency inventory;
   - mixed success and failure continuing to collect later dependencies.
9. Update redesign docs if closure ownership, ordering, diagnostics, or the
   out-of-scope scheduling/rendering boundary is clarified.

## Out Of Scope

Dependency scheduling; topological sorting for rendering; lowering dependency
bodies into renderable code; recursively lowering nested calls inside
arguments; parsing raw argument expressions; resolving argument identifiers;
array/index/operator/helper/cast semantics; rendering backend call text;
rendering backend type text; replacing existing scalar operation lowering;
source repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
public dependency graphs, schedulers, registries, dispatchers, fixpoint
mechanisms, broad request/result/worklist families, or source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M148 adds only a typed dependency-closure
   boundary and does not become scheduling, dependency-body lowering, backend
   rendering, expression parsing, or broad graph/worklist machinery.
2. Boundary auditor: verify the closure composes M147 inventories and keeps raw
   argument text/provenance as source truth only; no M144-M146 logic is
   duplicated.
3. Evidence auditor: verify closure test cases are grounded in observed
   primitive-call dependency forms from `tsldata/**/*.tsl` or accepted
   clean-restart tests, and unsupported cases are explicit diagnostics.
4. Documentation auditor: verify docs accurately describe dependency closure
   and defer scheduling, dependency-body lowering, recursive nested-call
   lowering, expression parsing, and backend rendering.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M148 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M148 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M148 is accepted. Do not start dependency scheduling,
dependency-body rendering, or backend call rendering until M148 is accepted and
the next prompt explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 149 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
