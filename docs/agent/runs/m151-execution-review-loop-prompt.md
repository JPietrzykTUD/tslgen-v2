# M151 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M150:

```text
Milestone 151: Primitive-Call Lowering Consolidation Boundary
```

Milestones 1 through 150 are accepted. M150 added one reusable
`LoweredPrimitiveCallExpression` value for already recognized
`PrimitiveCall` tokens and proved it through the exact
`emit_return(call<primitive=...>(...));` consumer.

The accepted primitive-call path is now showing a complexity smell: the
milestone-shaped layers around selector payloads, target matching, argument
binding, expression lowering, inventory, closure, package assembly, and
diagnostics are starting to look like a small pipeline inside the lowering
pipeline. M151 must stop feature growth and consolidate that path before any
recursive call scanning, surrounding-context consumers, backend call rendering,
or dependency scheduling is added.

This is a simplification milestone. It should preserve accepted behavior while
making the primitive-call lowering concept smaller and easier to reason about.

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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_call_arguments.py`
- `tslgen/src/tslgen/lowering/primitive_call_closure.py`
- `tslgen/src/tslgen/lowering/primitive_call_diagnostics.py`
- `tslgen/src/tslgen/lowering/primitive_call_expression.py`
- `tslgen/src/tslgen/lowering/primitive_call_inventory.py`
- `tslgen/src/tslgen/lowering/primitive_call_targets.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m146_primitive_call_argument_binding.py`
- `tslgen/tests/test_m147_primitive_call_reference_inventory.py`
- `tslgen/tests/test_m148_primitive_call_dependency_closure.py`
- `tslgen/tests/test_m149_primitive_call_closure_lowering_package.py`
- `tslgen/tests/test_m150_primitive_call_expression.py`

## Goal

Consolidate primitive-call lowering into a small cohesive concept while
preserving all accepted M144-M150 behavior, diagnostics, deterministic order,
and public clean-restart behavior.

The desired direction is a simple primitive-call resolver/collector shape,
not a chain of milestone-named middleware. A concrete implementation may use
one focused module or a very small pair of modules, but it must make ownership
obvious:

```text
PrimitiveCallResolver
  resolve(selected, call, catalog, environment?) -> PrimitiveCallResolution

PrimitiveCallResolution
  call
  target selected implementation
  raw argument bindings
  source/provenance
  diagnostics

PrimitiveCallDependencyCollector
  collect(root selected implementation, catalog) -> compact closure/package facts
```

These names are a design sketch, not mandatory API. The executor should choose
the smallest shape that makes the accepted behavior simpler and keeps the code
easy to review.

## Required Executor Task

Run exactly one write-capable executor for M151. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Map the current primitive-call lowering modules and identify which layers
   are only milestone-shaped pass-throughs.
3. Consolidate selector-payload lowering, target matching, argument binding,
   expression creation, reference inventory, closure/package composition, and
   related diagnostics into a smaller cohesive lowering surface where that can
   be done without changing accepted behavior.
4. Preserve accepted domain values that still carry real meaning, especially
   source `PrimitiveCall`, matched selected implementation, raw argument
   bindings, source locations, diagnostics, closure order, and lowered
   primitive-call expression values.
5. Remove or collapse private modules whose only purpose is forwarding between
   adjacent primitive-call layers. Do not leave compatibility facades around
   poor internal abstractions unless an accepted public import truly requires
   them.
6. Keep public imports from `tslgen.lowering` and `Lowerer` methods stable
   where existing accepted tests rely on them, or update tests and docs only
   when the exposed surface was explicitly internal milestone scaffolding.
7. Add or update focused tests to prove behavior did not change:
   - M144 selector payload cases still pass;
   - M145 target matching cases still pass;
   - M146 raw argument binding cases still pass;
   - M147 inventory cases still pass;
   - M148 closure cases still pass;
   - M149 closure-lowering package cases still pass;
   - M150 primitive-call expression and exact emit-return consumer cases still
     pass;
   - a consolidation-specific test or assertion documents the new smaller
     ownership boundary if useful.
8. Update redesign docs to describe the consolidated primitive-call lowering
   ownership and remove wording that implies a durable chain of milestone
   middleware.

## Must Preserve

- The exact accepted M144-M150 diagnostics, including codes, severity, source
  location expectations, and actionable message intent.
- Raw source argument text as source truth.
- No parsing, validation, normalization, or repair of argument expressions.
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

1. Architecture reviewer: verify M151 reduces primitive-call lowering
   complexity and does not add new lowering semantics, renderer behavior,
   scheduling, recursive scanning, or surrounding-context consumers.
2. Boundary auditor: verify accepted M144-M150 behavior, diagnostics, raw
   argument preservation, deterministic order, and public clean-restart surface
   remain stable.
3. Simplification auditor: verify collapsed modules/classes really remove
   milestone-shaped middleware rather than merely renaming it or hiding it
   behind facades.
4. Documentation auditor: verify docs describe the consolidated ownership and
   no longer imply a durable primitive-call mini-pipeline.
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

If the executor decides a separate M151 test file is not needed because the
consolidation is fully covered by updated M144-M150 tests, it must update this
validation list in the state and roadmap during finalization and explain why.

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M151 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M151 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M151 is accepted. Do not start recursive primitive-call scanning,
var/let/assignment/loop/condition consumers, expression trees, backend call
rendering, or dependency scheduling until M151 is accepted and the next prompt
explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 152 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
