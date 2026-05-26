# M133 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M132:

```text
Milestone 133: Exact TSIL Primitive-Call Lowering Boundary Slice
```

Milestones 1 through 132 are accepted. M132 recognizes exact
`call<primitive=...>(...)` islands in raw body-token text as existing
`LowerableDirective` tokens named `call` with opaque arguments
`(primitive, selector, payload)`. M133 must keep unresolved calls opaque, emit
a precise unsupported diagnostic for them, and lower only one tiny
self-contained call case.

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
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

When a selected implementation body is exactly this M132 primitive-call token:

```text
LowerableDirective(name="call", arguments=("primitive", "add", "left, right"))
```

and the selected primitive is the already supported scalar `add(left, right)`
shape, lowering should resolve it through the existing accepted add-operation
path.

For every other selected M132 primitive-call token, lowering should emit a
precise unsupported primitive-call diagnostic at the call token source.
Selector and payload text may appear in the message as opaque source context,
but lowering must not interpret unresolved calls.

## Required Executor Task

Run exactly one write-capable executor for M133. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep the M132 primitive-call classifier representation unchanged unless a
   focused test exposes a defect.
3. Add lowerer detection for the exact M132 primitive-call token shape:
   `LowerableDirective(name="call", arguments=("primitive", selector, payload))`.
4. Lower only the exact self-contained selected add case:
   `LowerableDirective(name="call", arguments=("primitive", "add", "left, right"))`
   when the selected primitive is the already supported scalar `add(left, right)`
   shape and the body contains no raw prefix/suffix tokens.
5. Emit a stable diagnostic such as `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` at
   the call token source for selected bodies containing primitive-call tokens
   outside that exact self-contained case.
6. Preserve existing generic `TSL-LOWER-UNSUPPORTED-BODY` diagnostics for
   raw-only bodies, malformed nearby call-like source, direct primitive-looking
   names such as `sub(left, right)`, and non-call directives.
7. Preserve existing `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION` diagnostics for
   `emit_return(call<primitive=...>(...));`; do not segment directive payloads.
8. Add focused tests for:
   - exact `call<primitive=add>(left, right)` lowering producing the same
     generated artifact bytes as the accepted synthetic
     `body add(left, right)` path;
   - selected assignment-like primitive-call body diagnostic;
   - selected zero-argument primitive-call body diagnostic;
   - selected body with multiple already-classified primitive-call tokens, if
     M132 currently classifies that shape;
   - malformed/nearby raw calls remaining generic unsupported bodies;
   - direct primitive-looking names remaining generic unsupported bodies;
   - directive payload calls remaining opaque return/directive diagnostics;
   - existing M126-M132 behavior and artifact-byte stability.
9. Update redesign docs if lowering behavior, diagnostic behavior, or
   boundaries are clarified.

## Out Of Scope

- General primitive resolution beyond the exact `add(left, right)` case;
  dependency closure; `@self` resolution; type-argument parsing; call argument
  splitting; expression parsing; helper/operator lowering; assignment
  lowering; array access lowering; directive-payload segmentation;
  generation/backend query evaluation; new backend call rendering; source
  repair; complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new lowering IR category/request/result/worklist
  families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M133 is only the exact
   `call<primitive=add>(left, right)` lowering boundary plus precise
   unsupported diagnostics for other M132 primitive-call tokens. It must not
   introduce general semantic call lowering, dependency closure, broad parser
   architecture, new IR machinery, runtime legacy dependencies, expression
   lowering, assignment lowering, directive-payload segmentation, or renderer
   inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for primitive lookup, dependency closure, `@self`
   resolution, type inference, query evaluation, argument projection, backend
   spellings, or source repair; verify selector and payload text stay opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M133 and preserve M128-M132 boundaries.
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

If M133 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M133 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M133 is accepted. Select exactly one concrete M134 task focused on
lowering from recognized body-token islands and grounded in the M127 inventory
plus the M128-M133 body-intake/body-token results. Do not create a separate
post-M133 planning prompt unless review returns `Return To Planner`, `Reject`,
or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 134 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
