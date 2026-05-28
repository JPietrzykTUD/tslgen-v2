# M146 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M145:

```text
Milestone 146: Primitive-Call Argument Binding Boundary
```

Milestones 1 through 145 are accepted. M145 lowered already recognized
`call<primitive=...>(...)` selector payloads far enough to match one concrete
catalog primitive implementation candidate. It deliberately stopped before
binding call arguments, recursively lowering nested calls, selecting dependency
closure, lowering dependency bodies, or rendering backend call text.

M146 should take the next small lowering step: consume an already recognized
`PrimitiveCall`, the M144 typed selector payload, and the M145 target match,
then bind ordered raw source arguments positionally to the matched primitive's
formal parameters.

This is an argument binding boundary, not expression interpretation.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m144_selector_payload.py`
- `tslgen/tests/test_m145_primitive_call_target_matching.py`

## Goal

Add a small typed argument-binding boundary that turns:

- a recognized domain `PrimitiveCall`;
- an M144 `PrimitiveCallSelectorPayload`;
- an M145 `PrimitiveCallTargetMatch`;

into either:

- a typed primitive-call reference/binding that preserves the target match and
  pairs each matched primitive formal parameter with the corresponding raw
  source argument; or
- explicit diagnostics explaining why the binding is unsupported or invalid at
  this boundary.

Supported exact behavior:

- Bind arguments positionally to the matched target primitive's formal
  parameter names.
- Preserve each argument's raw text and source location from the existing
  `PrimitiveCallArgument` data.
- Preserve the M145 target match, selector payload, and source provenance.
- Accept any raw argument text when the argument count matches, including
  identifier-looking text, array-looking text, operator-looking text, helper
  calls, and nested `call<primitive=...>(...)` text. These remain raw
  argument values; they are not recursively lowered.
- Produce an explicit diagnostic when the number of source arguments differs
  from the matched primitive's formal parameter count.

The result should be a small typed value, for example
`PrimitiveCallArgumentBinding` entries plus a
`PrimitiveCallReference`/`PrimitiveCallArgumentBindingResult`. Prefer the
existing `PrimitiveCallArgument`, `PrimitiveCallTargetMatch`, and selected
implementation/context objects where that keeps ownership simple. Do not
introduce a registry, dispatcher, dependency worklist, dependency graph,
fixpoint mechanism, or broad selector/expression AST.

## Required Executor Task

Run exactly one write-capable executor for M146. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M145 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a focused typed argument-binding model in the existing lowering/domain
   ownership area. Prefer one or two obvious dataclasses and pure helper
   functions.
4. Add a lowerer entry point that consumes a selected implementation,
   catalog, recognized `PrimitiveCall`, M144 selector payload, and M145 target
   match, then returns an argument-binding result plus diagnostics.
5. Reuse M145 target matching results instead of rematching selector strings.
6. Bind formal parameters from the matched selected implementation/context,
   not from hardcoded names such as `left`, `right`, `lhs`, or `rhs`.
7. Treat duplicate formal names, swapped source argument names, arbitrary
   identifier text, nested calls, array indexing, operators, and helpers as raw
   source argument text for this boundary. Do not validate argument semantics.
8. Add focused positive tests for:
   - matched `@self[Vec]`;
   - named `sub[Vec]`;
   - a naked current-context named call such as `sub`;
   - attrs-only and specialization-plus-attrs calls already matched by M145;
   - arbitrary parameter names proving the binding is positional and not tied
     to `left`/`right`;
   - nested call-looking argument text that remains raw when arity is valid.
9. Add focused negative tests for:
   - too few arguments;
   - too many arguments;
   - a call with no arguments against a primitive with required parameters.
10. Update redesign docs if the argument-binding result ownership,
    diagnostics, or out-of-scope dependency/rendering boundary is clarified.

## Out Of Scope

Argument expression parsing; recursive nested-call lowering; resolving
argument identifiers; validating swapped or duplicate argument names; array
indexing semantics; assignment lowering; helper/operator/cast semantics;
dependency closure; dependency-body lowering; backend call rendering; backend
type text rendering; source repair; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; registries, dispatchers, dependency graphs, fixpoint
mechanisms, broad request/result/worklist families, or source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M146 adds only a typed argument-binding
   boundary and does not become expression parsing, dependency closure,
   dependency-body lowering, backend rendering, or broad machinery.
2. Boundary auditor: verify binding consumes recognized domain calls, M144
   selector payloads, M145 matches, selected context/catalog facts, and raw
   `PrimitiveCallArgument` values; raw argument text remains provenance/source
   truth only.
3. Evidence auditor: verify supported positive cases are grounded in observed
   selector/call forms from `tsldata/**/*.tsl` or accepted clean-restart tests,
   and unsupported arity cases are explicit diagnostics.
4. Documentation auditor: verify docs accurately describe argument binding and
   defer expression semantics, dependency closure, dependency-body lowering,
   and backend rendering.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py tslgen/tests/test_m146_primitive_call_argument_binding.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M146 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M146 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M146 is accepted. Do not start dependency closure,
dependency-body lowering, or backend call rendering until M146 is accepted and
the next prompt explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 147 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
