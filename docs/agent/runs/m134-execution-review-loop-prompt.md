# M134 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M133:

```text
Milestone 134: Exact Lowerable Directive Payload Token Boundary Slice
```

Milestones 1 through 133 are accepted. M129 recognizes exact
`emit_return(...)` directive envelopes as `LowerableDirective` tokens with one
opaque payload argument. M132 recognizes standalone
`call<primitive=...>(...)` islands in raw body-token text. M133 lowers only the
exact self-contained selected `call<primitive=add>(left, right)` body and
diagnoses other selected primitive-call body tokens. M134 must stop treating
all directive payloads as indivisible strings by adding the first narrow
payload-token boundary for `emit_return(...)`.

This milestone must not hardcode the combined source string
`emit_return(call<primitive=add>(left, right));`. The point is to let an
`emit_return` payload carry raw text plus lowerable islands, so already
accepted lowerable tokens can compose naturally.

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

When an M129 `emit_return(...)` directive payload contains an exact M132
primitive-call island:

```text
emit_return(call<primitive=add>(left, right));
```

the `emit_return` directive should retain the original opaque payload text for
diagnostics and also expose a payload-token stream containing the already
recognized primitive-call token. Lowering may then compose accepted
boundaries:

- `emit_return` supplies the return context.
- The payload lowers only if its token stream contains exactly one payload
  token that is already accepted by the M133 exact
  `call<primitive=add>(left, right)` boundary.

Every other selected `emit_return(...)` body should keep a precise unsupported
boundary: recognized but unsupported primitive-call payload tokens should use
the M133 primitive-call diagnostic, while raw-only or mixed raw payloads should
preserve the existing opaque return-expression diagnostic.

## Required Executor Task

Run exactly one write-capable executor for M134. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129 directive-envelope classification, standalone M132
   primitive-call classification, and existing M133 standalone call lowering
   stable unless a focused test exposes a defect.
3. Introduce the smallest durable payload-token representation needed for
   lowerable directive payloads. The first accepted producer is
   `emit_return(...)`; `var`, `let`, `loop`, `if`, `switch`, and `else`
   payloads remain opaque unless a later milestone explicitly selects them.
4. Preserve each directive's original opaque payload text for diagnostics while
   exposing ordered payload tokens for exact lowerable islands. Raw
   prefix/suffix payload text must remain raw payload-token data.
5. Classify only exact `call<primitive=...>(...)` islands inside the
   `emit_return` payload using the M132 call-envelope rules. Selector and
   payload text inside the call must remain opaque.
6. Lower an `emit_return` directive only when its payload-token stream contains
   exactly one payload token that can already lower through the M133 exact
   `call<primitive=add>(left, right)` boundary for the accepted scalar add
   shape.
7. Emit `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` at the call token source when an
   `emit_return` payload contains a recognized primitive-call token that cannot
   lower through the M133 boundary.
8. Preserve `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION` for raw-only,
   raw-plus-call, malformed nearby call-like, helper/operator/identifier, and
   other unsupported `emit_return` payloads.
9. Add the nonblocking M133 follow-up as explicit test coverage: a selected
   direct M132 `call<primitive=@self[...]>(...)` body must produce
   `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` without interpreting `@self`.
10. Add focused tests for:
    - payload-token representation of
      `emit_return(call<primitive=add>(left, right));`;
    - exact composed lowering producing the same generated artifact bytes as
      `body add(left, right)` and M133's self-contained exact add call;
    - `emit_return(call<primitive=sub>(left, right));` producing the primitive
      call diagnostic at the call token source;
    - `emit_return(call<primitive=@self[...]>(...));` producing the primitive
      call diagnostic without interpreting `@self`;
    - direct selected M133 `@self` primitive-call diagnostics;
    - raw-plus-call payloads preserving the return-expression diagnostic;
    - malformed/nearby emit-return payloads preserving existing diagnostics;
    - existing M126-M133 behavior and artifact-byte stability.
11. Update redesign docs if payload-token behavior, diagnostic behavior, or
    boundaries are clarified.

## Out Of Scope

- General directive-payload segmentation; recursive payload parsing; broad
  `emit_return` expression lowering; general primitive resolution; dependency
  closure; `@self` interpretation; type-argument parsing; call argument
  splitting; expression parsing; helper/operator lowering; assignment
  lowering; array access lowering; generation/backend query evaluation; new
  backend call rendering; source repair; complete TSIL grammar; runtime
  `tsldata` semantic lookup; `frozen` or `tslgenold` runtime dependency;
  registries; dispatchers; hidden backfeeds; fixpoint mechanisms; or new
  lowering IR category/request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M134 creates only the narrow directive
   payload-token boundary needed for exact `emit_return(...)` payload islands
   and composes with the existing M133 add-call boundary. It must not hardcode
   the combined `emit_return(call<primitive=add>(left, right));` source string,
   introduce general emit-return expression parsing, recursive directive
   payload parsing, semantic call lowering, dependency closure, broad parser
   architecture, new request/result/worklist machinery, runtime legacy
   dependencies, assignment lowering, or renderer inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for primitive lookup, dependency closure, `@self`
   resolution, type inference, query evaluation, argument projection, backend
   spellings, or source repair; verify selector and call payload text remain
   opaque.
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
