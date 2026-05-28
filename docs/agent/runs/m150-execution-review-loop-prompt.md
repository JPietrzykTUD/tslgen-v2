# M150 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M149:

```text
Milestone 150: Primitive-Call Expression Lowering Boundary With Exact Emit-Return Consumer
```

Milestones 1 through 149 are accepted. M149 composes the accepted M148
primitive-call dependency closure with the existing selected-function lowerer
and returns a compact package containing the closure, lowerable functions, and
diagnostics. M149 deliberately stopped before making primitive-call bodies
lowerable as function return expressions.

M150 should take the next small lowering step: lower an already recognized
`PrimitiveCall` token into a reusable typed primitive-call expression value,
then prove that expression through the first exact consumer:
`emit_return(call<primitive=...>(...));`.

This is a primitive-call expression-lowering boundary with one exact
`emit_return(...)` consumer, not a renderer, scheduler, nested expression
parser, or general call language. Do not implement separate per-context
primitive-call lowering; future expression slots should consume the same
primitive-call expression value when their surrounding construct is selected.

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
- `tslgen/tests/test_m149_primitive_call_closure_lowering_package.py`

## Goal

Add one reusable typed primitive-call expression value for recognized
`PrimitiveCall` tokens, then use it only in the exact selected return-body
consumer where:

- the selected implementation body contains exactly one `emit_return`
  directive token;
- the `emit_return` payload token stream contains exactly one recognized
  `PrimitiveCall` token;
- existing M144 selector-payload lowering, M145 target matching, and M146
  argument binding succeed for that call.

Supported exact behavior:

- A focused helper or method may lower one already recognized `PrimitiveCall`
  token into a typed primitive-call expression by composing existing
  primitive-call reference lowering behavior.
- `Lowerer.lower(...)` may return a `LoweredFunction` whose return expression
  is a typed primitive-call expression for the accepted exact form.
- The primitive-call expression should preserve the accepted
  `PrimitiveCallReference`, including target match, raw source arguments,
  bindings, and source provenance.
- The existing M149 closure-lowering package should then include such a root
  function when its exact `emit_return(call<primitive=...>(...));` body lowers.
- Diagnostics from unsupported selectors, missing targets, and argument-count
  mismatches must come from the accepted M144-M146/M147 behavior rather than
  new duplicate matching code.
- Nearby forms remain unsupported diagnostics: standalone `call<...>(...)`
  bodies, primitive calls embedded in `var`, `let`, assignment, loop, or
  condition payloads, raw `emit_return(left)`, mixed raw-plus-call payloads,
  malformed calls, and multi-token payloads.

## Required Executor Task

Run exactly one write-capable executor for M150. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M149 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a focused typed lowered primitive-call expression value in the existing
   lowering model.
4. Add the smallest reusable primitive-call expression lowering helper needed
   for one already recognized `PrimitiveCall` token.
5. Teach selected-function lowering to consume that helper only for the exact
   `emit_return` payload-call form described above.
6. Compose existing primitive-call reference lowering behavior; do not
   duplicate selector parsing, target matching, argument binding, inventory
   walking, closure traversal, or package lowering logic.
7. Preserve raw argument text and provenance as source truth. Do not parse,
   validate, normalize, or repair argument expressions.
8. Add focused positive tests for:
   - lowering a recognized `PrimitiveCall` token into the reusable typed
     primitive-call expression;
   - exact `emit_return(call<primitive=sub[Vec]>(left, right));` lowering to a
     function return that consumes the typed primitive-call expression;
   - swapped or arbitrary raw argument text being preserved in bindings when
     arity matches;
   - M149 package including a root function whose exact return-call body now
     lowers.
9. Add focused diagnostic/boundary tests for:
   - missing target or unsupported selector diagnostics flowing through the
     accepted call-reference boundary;
   - standalone `call<...>(...)` body remaining unsupported as a function
     return body;
   - primitive calls in unselected contexts such as `var`, `let`, assignment,
     loop, or condition payloads remaining unsupported by surrounding-context
     lowering;
   - raw-only or mixed `emit_return(...)` payloads remaining unsupported.
10. Update redesign docs if the expression ownership, exact accepted consumer,
   diagnostics, or out-of-scope rendering boundary is clarified.

## Out Of Scope

Standalone primitive-call statement semantics; primitive-call consumers other
than the exact `emit_return(...)` form selected above; dependency scheduling;
topological sorting for rendering; backend call rendering; backend type
rendering; resolving call arguments into backend expressions; recursively
lowering nested calls inside arguments; parsing raw argument expressions;
resolving argument identifiers; array/index/operator/helper/cast semantics;
lowering arbitrary `emit_return(...)` expressions; lowering var/let/loop/if
payload semantics; source repair; runtime `tsldata`, `frozen`, or `tslgenold`
dependencies; public dependency graphs, schedulers, registries, dispatchers,
fixpoint mechanisms, broad request/result/worklist families, or source-data
repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M150 adds one reusable typed primitive-call
   expression boundary and only one exact `emit_return(...)` consumer, and
   does not become rendering, scheduling, nested expression parsing, or broad
   call-language machinery.
2. Boundary auditor: verify M150 composes M144-M147 behavior and M149 package
   behavior without duplicating selector parsing, target matching, argument
   binding, inventory walking, closure traversal, or package lowering.
3. Evidence auditor: verify recognized primitive-call expression forms and the
   exact `emit_return(call<primitive=...>(...));` consumer are grounded in
   `tsldata/**/*.tsl` or accepted clean-restart fixtures, and unsupported
   nearby surrounding contexts remain explicit diagnostics.
4. Documentation auditor: verify docs accurately describe reusable
   primitive-call expression lowering plus the exact accepted `emit_return`
   consumer, and defer other surrounding contexts, standalone call semantics,
   nested expression parsing, backend call rendering, and scheduling.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py tslgen/tests/test_m147_primitive_call_reference_inventory.py tslgen/tests/test_m148_primitive_call_dependency_closure.py tslgen/tests/test_m149_primitive_call_closure_lowering_package.py tslgen/tests/test_m150_primitive_call_expression.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M150 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M150 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M150 is accepted. Do not start backend call rendering,
standalone call semantics, other surrounding-context consumers, nested
expression parsing, or dependency scheduling until M150 is accepted and the
next prompt explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 151 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
