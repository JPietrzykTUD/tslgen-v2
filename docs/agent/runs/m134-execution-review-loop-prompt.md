# M134 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M133:

```text
Milestone 134: Exact Emit-Return Primitive-Call Payload Lowering Slice
```

Milestones 1 through 133 are accepted. M129 recognizes exact
`emit_return(...)` directive envelopes as `LowerableDirective` tokens with one
opaque payload argument. M132 recognizes standalone
`call<primitive=...>(...)` islands in raw body-token text. M133 lowers only the
exact self-contained selected `call<primitive=add>(left, right)` body and
diagnoses other selected primitive-call body tokens. M134 must compose only the
exact `emit_return(call<primitive=add>(left, right));` shape without turning
`emit_return` payloads into a general expression language.

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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/_tsil_directives.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

When a selected implementation body is exactly this M129 emit-return token:

```text
LowerableDirective(
    name="emit_return",
    arguments=("call<primitive=add>(left, right)",),
)
```

and the selected primitive is the already supported scalar `add(left, right)`
shape, lowering should resolve it through the same accepted typed add-operation
path used by `body add(left, right)` and M133's self-contained
`call<primitive=add>(left, right)` body.

Every other selected `emit_return(...)` body should preserve the existing
opaque return-expression diagnostic boundary unless this milestone explicitly
selects that exact payload form.

## Required Executor Task

Run exactly one write-capable executor for M134. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep the M129 directive classifier, M132 primitive-call classifier, and
   domain body-token representation unchanged unless a focused test exposes a
   defect.
3. Add lowerer detection for the exact single-token M129 emit-return shape:
   `LowerableDirective(name="emit_return", arguments=(payload,))`.
4. Lower only the exact payload text
   `call<primitive=add>(left, right)` when the selected primitive is the
   already supported scalar `add(left, right)` shape and the selected body has
   no raw prefix/suffix tokens.
5. Reuse the existing typed add-operation lowering path. Do not add backend
   call rendering or renderer-side semantic inference.
6. Preserve `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION` for all other
   `emit_return(...)` payloads, including operators, identifiers, helper calls,
   malformed primitive-call payloads, non-add primitive-call payloads, `@self`
   primitive-call payloads, extra statements, and payloads with raw prefix or
   suffix text.
7. Add the nonblocking M133 follow-up as explicit test coverage: a selected
   direct M132 `call<primitive=@self[...]>(...)` body must produce
   `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` without interpreting `@self`.
8. Add focused tests for:
   - exact `emit_return(call<primitive=add>(left, right));` lowering producing
     the same generated artifact bytes as `body add(left, right)` and M133's
     self-contained exact add call;
   - `emit_return(call<primitive=sub>(left, right));` preserving the opaque
     return-expression diagnostic;
   - `emit_return(call<primitive=@self[...]>(...));` preserving the opaque
     return-expression diagnostic;
   - direct selected M133 `@self` primitive-call diagnostics;
   - malformed/nearby emit-return payloads preserving existing diagnostics;
   - existing M126-M133 behavior and artifact-byte stability.
9. Update redesign docs if lowering behavior, diagnostic behavior, or
   boundaries are clarified.

## Out Of Scope

- General `emit_return` expression lowering; directive-payload segmentation;
  general primitive resolution; dependency closure; `@self` interpretation;
  type-argument parsing; call argument splitting; expression parsing;
  helper/operator lowering; assignment lowering; array access lowering;
  generation/backend query evaluation; new backend call rendering; source
  repair; complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new lowering IR category/request/result/worklist
  families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M134 composes only the exact
   `emit_return(call<primitive=add>(left, right));` boundary with the existing
   typed add-operation path. It must not introduce general emit-return
   expression parsing, directive-payload segmentation, semantic call lowering,
   dependency closure, broad parser architecture, new IR machinery, runtime
   legacy dependencies, assignment lowering, or renderer inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for primitive lookup, dependency closure, `@self`
   resolution, type inference, query evaluation, argument projection, backend
   spellings, or source repair; verify non-selected payloads stay opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M134 and preserve M128-M133 boundaries.
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

If M134 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M134 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M134 is accepted. Select exactly one concrete M135 task focused on
lowering from recognized body-token islands and grounded in the M127 inventory
plus the M128-M134 body-intake/body-token/lowering results. Do not create a
separate post-M134 planning prompt unless review returns `Return To Planner`,
`Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 135 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
