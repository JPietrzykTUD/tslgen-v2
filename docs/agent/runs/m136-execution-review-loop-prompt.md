# M136 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M135:

```text
Milestone 136: Structured Primitive Call Argument List Boundary Slice
```

Milestones 1 through 135 are accepted. M135 gives recognized
`call<primitive=...>(...)` tokens a structured selector representation while
preserving the opaque selector text and opaque call payload. M136 should add
the next representation-only boundary for the explicit TSIL call keyword: an
ordered, source-owned argument list over the call payload.

This milestone must not resolve primitive calls or parse argument expressions.
Arguments remain raw source payload values. The boundary is only the top-level
comma structure of the TSIL `call<...>(...)` payload.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognized primitive-call tokens should preserve the original opaque call
payload and also expose deterministic argument payload records:

```text
call<primitive=add>(left, right)
```

should expose two raw argument values, `left` and `right`, with source
locations. A zero-argument call such as:

```text
call<primitive=set_zero[Vec]>()
```

should expose an empty argument tuple. Nested parentheses and square brackets
inside an argument must not be split as top-level commas.

## Required Executor Task

Run exactly one write-capable executor for M136. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129/M130 directive classification, M132 call-island
   recognition, M134 emit-return payload-token behavior, and M135 structured
   selector behavior stable unless a focused test exposes a defect.
3. Add the smallest typed representation for source-owned primitive-call
   arguments. Each argument should preserve its raw payload text and source
   location. Preserve the existing opaque `PrimitiveCall.payload` string.
4. Split only top-level commas in the call payload. The splitter must respect
   nested parentheses and square brackets so nested TSIL calls, helper-like
   calls, casts, and selector brackets in nested calls are not split
   internally.
5. Represent zero-argument calls as an empty argument tuple.
6. Populate structured argument lists for both standalone M132 call tokens and
   M134 `emit_return(...)` payload call tokens.
7. Preserve M133/M134 exact `call<primitive=add>(left, right)` lowering.
   Adapt the exact check to use or coexist with structured arguments without
   accepting swapped, missing, duplicate, extra, or expression-like arguments.
8. Preserve unsupported-call diagnostics for all recognized calls that are not
   the accepted exact add-call lowering case. Diagnostics may mention the
   structured argument count or raw argument payloads, but must not resolve or
   interpret them.
9. Add focused tests for:
   - zero-argument calls;
   - `call<primitive=add>(left, right)` two-argument structure and artifact
     stability;
   - nested call arguments such as
     `call<primitive=mov>(call<primitive=set_zero[Vec]>(), left)`;
   - helper/cast-like nested parentheses such as
     `call<primitive=set1>(cast<static>(type<generation>(base::in), factor))`;
   - source locations for arguments after whitespace;
   - the same argument structure inside
     `emit_return(call<primitive=...>(...));` payload tokens;
   - malformed argument delimiters preserving unsupported/malformed
     boundaries rather than source repair;
   - existing M126-M135 behavior, diagnostics, and artifact-byte stability.
10. Update redesign docs if the argument-list representation, diagnostics, or
    boundaries are clarified.

## Out Of Scope

- Primitive dependency closure; resolving named primitive references against
  the catalog; expanding `@self`; interpreting selector specialization or
  `attrs[...]`; resolving argument identifiers; parsing array access,
  assignment, operators, helpers, casts, or nested call semantics; recursively
  lowering argument expressions; backend call rendering; source repair;
  complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M136 adds only source-owned argument-list
   representation for recognized primitive calls and preserves M133/M134 exact
   add-call lowering. It must not introduce primitive resolution, `@self`
   expansion, expression parsing, recursive call lowering, backend call
   rendering, renderer inference, or broad IR machinery.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used; verify arguments remain raw payload values; verify nested
   calls/helpers/casts are not interpreted.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M136 and preserve M128-M135 boundaries.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M136 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M136 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M136 is accepted. Select exactly one concrete M137 task focused on
lowering from recognized TSIL body-token islands and grounded in the M127
inventory plus the M128-M136 body-intake/body-token/lowering results. Do not
create a separate post-M136 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 137 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
