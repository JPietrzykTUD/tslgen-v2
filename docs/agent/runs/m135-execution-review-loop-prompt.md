# M135 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M134:

```text
Milestone 135: Structured Primitive Call Representation Boundary Slice
```

Milestones 1 through 134 are accepted. M132 recognizes exact
`call<primitive=...>(...)` islands as lowerable call tokens, but the selector
is still opaque text. M133 and M134 use only the tiny exact
`call<primitive=add>(left, right)` case for accepted add lowering, while
unsupported recognized calls produce precise diagnostics. M135 must strengthen
the representation of the TSIL `call<primitive=...>` keyword without resolving
or executing those calls.

This milestone replaces the previously planned raw
`emit_return(<selected-parameter>)` idea. Raw return payload identifiers remain
unsupported; do not add name resolution for `left`, `right`, `result`, or any
other target-language-looking payload text.

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

Represent the `primitive=` selector of recognized TSIL primitive calls in typed
source-owned form. The selector target may be the `@self` keyword, meaning the
currently selected primitive, or an arbitrary named primitive reference such as
`add`, `binary_and`, `reinterpret`, or `set_zero`.

Accepted selector forms for this slice are:

```text
call<primitive=@self>(...)
call<primitive=@self[...]>(...)
call<primitive=@self attrs[...]>(...)
call<primitive=@self[...] attrs[...]>(...)
call<primitive=<primitive-name>>(...)
call<primitive=<primitive-name>[...]>(...)
call<primitive=<primitive-name> attrs[...]>(...)
call<primitive=<primitive-name>[...] attrs[...]>(...)
```

`<primitive-name>` is documentation notation for an arbitrary primitive name
token. It is not the literal source spelling `_NAME_`.

The bracket payloads and call argument payload remain opaque source text. The
milestone should make selector structure visible to lowering and diagnostics,
not resolve catalog dependencies or interpret call arguments.

## Required Executor Task

Run exactly one write-capable executor for M135. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129/M130 directive classification, M132 call-island
   recognition, M133 exact add-call lowering, and M134 emit-return payload-token
   behavior stable unless a focused test exposes a defect.
3. Add the smallest typed representation for a recognized primitive-call
   selector. It should distinguish:
   - self target: `@self`;
   - named target: `<primitive-name>`;
   - optional specialization payload from `[...]`;
   - optional attrs payload from `attrs[...]`;
   - original selector source text and source location for diagnostics.
4. Preserve the existing opaque call argument payload exactly. Do not split
   arguments, parse nested calls, parse expressions, or evaluate attributes.
5. Populate the structured selector for both standalone M132 call tokens and
   call tokens found inside M134 `emit_return(...)` payload tokens.
6. Preserve M133/M134 exact add-call lowering behavior. If the existing
   lowering check consumes the old opaque arguments, adapt it to use or coexist
   with the new selector representation without broadening semantics.
7. Preserve unsupported-call diagnostics for all recognized calls that are not
   the accepted exact add-call lowering case. Diagnostics may include the
   structured target kind/name as context, but must not resolve the call.
8. Add focused tests for structured representation of:
   - `call<primitive=@self>(left, right)`;
   - `call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left, right)`;
   - `call<primitive=add>(left, right)`;
   - `call<primitive=reinterpret[Vec, Vec<si64>]>(left)`;
   - `call<primitive=mov attrs[mask=zero]>(left, right)`;
   - `call<primitive=mul[Vec] attrs[mask=pass_through]>(left, right)`;
   - the same structured selector availability for an
     `emit_return(call<primitive=...>(...));` payload token.
9. Add negative tests for malformed selector brackets or malformed
   `attrs[...]` forms proving they remain unsupported/malformed boundaries
   rather than source repair.
10. Update redesign docs if the selector representation, diagnostics, or
    boundaries are clarified.

## Out Of Scope

- Raw `emit_return(left)` or `emit_return(result)` name resolution; primitive
  dependency closure; resolving named primitive references against the catalog;
  expanding `@self`; interpreting specialization payloads; interpreting
  `attrs[...]`; splitting call arguments; recursive primitive-call trees;
  expression parsing; helper/operator lowering; assignment lowering; array
  access lowering; generation/backend query evaluation; backend call
  rendering; source repair; complete TSIL grammar; runtime `tsldata` semantic
  lookup; `frozen` or `tslgenold` runtime dependency; registries; dispatchers;
  hidden backfeeds; fixpoint mechanisms; or new request/result/worklist
  families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M135 adds only structured source
   representation for the `call<primitive=...>` selector and preserves the
   accepted exact add-call lowering boundary. It must not introduce raw
   return-payload name resolution, dependency closure, `@self` expansion,
   argument splitting, expression parsing, backend call rendering, renderer
   inference, or broad IR machinery.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used; verify named primitive references and `@self` are
   represented but not resolved; verify specialization and attrs payloads stay
   opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M135 and preserve M128-M134 boundaries, especially that `_NAME_` is not a
   literal source form and raw `emit_return(left)` is still unsupported.
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

If M135 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M135 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M135 is accepted. Select exactly one concrete M136 task focused on
lowering from recognized TSIL body-token islands and grounded in the M127
inventory plus the M128-M135 body-intake/body-token/lowering results. Do not
create a separate post-M135 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 136 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
