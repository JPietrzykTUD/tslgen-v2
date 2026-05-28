# M147 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M146:

```text
Milestone 147: Primitive-Call Reference Inventory Boundary
```

Milestones 1 through 146 are accepted. M144 lowers recognized primitive-call
selectors into typed selector payloads. M145 matches those payloads to one
catalog primitive implementation candidate. M146 binds raw call arguments
positionally to the matched primitive's formal parameters. M146 deliberately
stopped before walking selected bodies, dependency closure, dependency-body
lowering, recursive nested-call lowering, or backend rendering.

M147 should take the next small lowering step: walk a selected implementation
body in source order, find already recognized primitive-call tokens, and
compose the accepted M144, M145, and M146 boundaries into a typed
source-ordered inventory of primitive-call references.

This is an inventory boundary, not a dependency solver.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`
- `tslgen/tests/test_m146_primitive_call_argument_binding.py`

## Goal

Add a small typed inventory boundary that turns one selected implementation
plus catalog facts into either:

- a deterministic tuple of typed `PrimitiveCallReference` values for
  recognized primitive-call tokens; and
- accumulated diagnostics from selector-payload lowering, target matching, and
  argument binding.

Supported exact behavior:

- Walk the selected implementation's `ImplementationBody.tokens` in source
  order.
- Include standalone `LowerableDirective` tokens that carry a `PrimitiveCall`.
- Include already recognized primitive-call payload tokens inside supported
  directive payload token streams such as `emit_return(...)`, preserving
  source order relative to the containing directive.
- For each recognized call, run M144 selector-payload lowering, then M145
  target matching, then M146 argument binding.
- Keep successful references in source order.
- Accumulate diagnostics and continue with later recognized calls when a call
  fails at selector, target, or arity boundaries.
- Preserve raw argument text and source provenance from the original
  `PrimitiveCallArgument` values.

Resolve the M146 follow-up before broader call-lowering code depends on it:
either narrow the public lowerer argument-binding API so it no longer accepts
redundant `selected`, `selector_payload`, and `catalog` parameters, or add a
small explicit consistency check for the redundant values that stays within
the M146 boundary. Prefer the smallest coherent API.

The result should be a small typed value, for example
`PrimitiveCallReferenceInventory` with `references` and `diagnostics`. Do not
introduce a dependency graph, dependency worklist, scheduler, registry,
dispatcher, fixpoint mechanism, or broad selector/expression AST.

## Required Executor Task

Run exactly one write-capable executor for M147. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M146 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a focused typed primitive-call reference inventory model in the existing
   lowering/domain ownership area.
4. Add a lowerer entry point that consumes a selected implementation and
   catalog, then returns the primitive-call reference inventory plus
   diagnostics.
5. Compose the accepted M144, M145, and M146 helpers; do not duplicate
   selector parsing, target matching, attribute matching, or arity logic.
6. Resolve the M146 API follow-up narrowly if the inventory uses that public
   method.
7. Add focused positive tests for:
   - one standalone primitive-call token;
   - one `emit_return(...)` payload primitive-call token;
   - multiple recognized calls returned in source order;
   - raw nested call-looking argument text remaining inside one inventory
     reference without recursive lowering.
8. Add focused diagnostic tests for:
   - unsupported selector payload diagnostics;
   - unknown or missing target diagnostics from M145;
   - arity mismatch diagnostics from M146;
   - mixed success and failure continuing to later calls.
9. Update redesign docs if the inventory ownership, ordering, diagnostics, or
   out-of-scope dependency/rendering boundary is clarified.

## Out Of Scope

Dependency closure; dependency scheduling; selecting transitive dependency
sets; lowering dependency bodies; recursively lowering nested calls inside
arguments; parsing raw argument expressions; resolving argument identifiers;
array/index/operator/helper/cast semantics; rendering backend call text;
rendering backend type text; replacing existing scalar operation lowering;
source repair; runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
registries, dispatchers, dependency graphs, fixpoint mechanisms, broad
request/result/worklist families, or source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M147 adds only a typed primitive-call
   reference inventory boundary and does not become dependency closure,
   dependency-body lowering, recursive call lowering, backend rendering, or
   broad machinery.
2. Boundary auditor: verify the inventory composes M144, M145, and M146 typed
   boundaries and keeps raw argument text/provenance as source truth only.
3. Evidence auditor: verify supported call-token inventory cases are grounded
   in observed `tsldata/**/*.tsl` forms or accepted clean-restart tests, and
   unsupported cases are explicit diagnostics.
4. Documentation auditor: verify docs accurately describe the inventory
   boundary and defer dependency closure, dependency-body lowering, recursive
   nested-call lowering, and backend rendering.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M147 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M147 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M147 is accepted. Do not start dependency closure,
dependency-body lowering, or backend call rendering until M147 is accepted and
the next prompt explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 148 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
