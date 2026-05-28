# M152 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M151:

```text
Milestone 152: Lowerer Primitive-Call Facade Reduction Boundary
```

Milestones 1 through 151 are accepted. M151 collapsed the primitive-call
middleware modules into `tslgen/src/tslgen/lowering/primitive_calls.py`, with
`PrimitiveCallResolver` owning call resolution and
`PrimitiveCallDependencyCollector` owning inventory and closure collection.
M151 deliberately preserved the existing `Lowerer` primitive-call helper
methods because accepted tests relied on that historical milestone surface.

M152 should remove that remaining visible scaffolding where it is only a
compatibility-shaped facade. This is still consolidation work, not new
primitive-call semantics.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m146_primitive_call_argument_binding.py`
- `tslgen/tests/test_m147_primitive_call_reference_inventory.py`
- `tslgen/tests/test_m148_primitive_call_dependency_closure.py`
- `tslgen/tests/test_m149_primitive_call_closure_lowering_package.py`
- `tslgen/tests/test_m150_primitive_call_expression.py`
- `tslgen/tests/test_m151_primitive_call_consolidation.py`

## Goal

Shrink `Lowerer` back toward selected-function/type lowering by moving
primitive-call substep tests and callers to the consolidated M151 resolver and
collector surface.

Accepted direction:

- Tests that exercise selector payload, target matching, argument binding,
  primitive-call expression creation, reference inventory, or dependency
  closure should call the focused resolver/collector/helper surface directly
  instead of preserving old `Lowerer.lower_primitive_call_*` milestone
  facades.
- Remove `Lowerer` primitive-call helper methods whose only job is delegating
  to `PrimitiveCallResolver`, `PrimitiveCallDependencyCollector`, or
  `selector_payload`.
- Keep selected-function lowering behavior and the exact M150
  `emit_return(call<primitive=...>(...));` consumer stable.
- Keep `Lowerer.lower_primitive_call_closure_lowering_package(...)` only if it
  remains the smallest place to compose closure collection with
  `Lowerer.lower_all(...)`. If a cleaner package composition belongs in
  `primitive_calls.py`, move it without adding rendering or scheduling.

## Required Executor Task

Run exactly one write-capable executor for M152. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Identify `Lowerer` primitive-call helper methods that are pure facades over
   M151 resolver/collector behavior.
3. Update focused M144-M151 tests to use `PrimitiveCallResolver`,
   `PrimitiveCallDependencyCollector`, and/or `selector_payload` helpers
   directly where those tests intentionally exercise primitive-call internals.
4. Remove facade methods from `Lowerer` when no accepted test or product path
   needs them.
5. Preserve selected-function lowering and public generator behavior.
6. Preserve accepted diagnostics, source locations, deterministic order, raw
   argument preservation, and exact return-call consumer behavior.
7. Add a small M152 regression test only if needed to document that `Lowerer`
   no longer exposes primitive-call substep facades.
8. Update redesign docs to describe the smaller `Lowerer` surface and the
   resolver/collector ownership.

## Must Preserve

- M144-M151 accepted behavior and diagnostics.
- Raw source argument text as source truth.
- Deterministic reference/closure/function ordering.
- M150's exact `emit_return(call<primitive=...>(...));` consumer boundary.
- Renderer behavior: primitive-call expressions remain backend-unsupported
  until a later backend milestone explicitly selects call rendering.

## Out Of Scope

New primitive-call semantics; recursive primitive-call scanning; primitive-call
discovery in additional surrounding contexts; `var`, `let`, assignment, loop,
`if`, `switch`, cast, intrinsic, operator, helper, array/index, or
name-reference lowering; expression trees; replacing raw argument text with
lowered argument expressions; backend call rendering; backend type rendering;
dependency scheduling or topological output sorting; source repair; runtime
`tsldata`, `frozen`, or `tslgenold` dependencies; public dependency graphs,
schedulers, registries, dispatchers, fixpoint mechanisms, broad
request/result/worklist families, or source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M152 shrinks the `Lowerer` primitive-call
   facade and does not add new semantics, rendering, scheduling, recursive
   scanning, or surrounding-context consumers.
2. Boundary auditor: verify M144-M151 behavior, diagnostics, raw argument
   preservation, deterministic order, exact return-call behavior, and public
   generator behavior remain stable.
3. Simplification auditor: verify the removed `Lowerer` methods were truly
   facade scaffolding and that tests now exercise the appropriate
   resolver/collector ownership directly.
4. Documentation auditor: verify docs describe the smaller `Lowerer` surface
   and the resolver/collector ownership accurately.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds a focused M152 test file, include it in the compileall
and pytest commands and update this prompt, the roadmap, and current state
during finalization.

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M152 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M152 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M152 is accepted. Do not start recursive primitive-call scanning,
var/let/assignment/loop/condition consumers, expression trees, backend call
rendering, or dependency scheduling until M152 is accepted and the next prompt
explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 153 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
