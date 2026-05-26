# M137 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M136:

```text
Milestone 137: Exact Primitive Call Dependency Diagnostic Boundary Slice
```

Milestones 1 through 136 are accepted. M135 gives recognized
`call<primitive=...>(...)` tokens structured selector data, and M136 adds
structured raw argument records. M133/M134 still lower only the exact
`call<primitive=add>(left, right)` case. Every other recognized primitive call
is still unsupported. M137 should make that unsupported boundary clearer and
more actionable without resolving or rendering calls.

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
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Unsupported recognized primitive-call tokens should produce a stable
diagnostic grounded in the structured M135/M136 representation. For example,
an unsupported call should report:

- target kind: `@self` or named primitive;
- selector source text;
- optional specialization payload;
- optional `attrs[...]` payload;
- raw argument count;
- opaque payload text;
- the explicit next missing semantic capability: primitive-call dependency
  resolution is not implemented yet.

The diagnostic remains a lowering boundary. It must not resolve primitive
references, expand `@self`, interpret attributes, interpret arguments, or emit
backend call text.

## Required Executor Task

Run exactly one write-capable executor for M137. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129/M130 directive classification, M132 call-island
   recognition, M134 emit-return payload-token behavior, M135 selector
   representation, M136 argument-list representation, and M133/M134 exact
   add-call lowering stable unless a focused test exposes a defect.
3. Refine the unsupported primitive-call diagnostic message to consume the
   structured selector and argument data when available. Keep legacy fallback
   text for any hand-constructed `LowerableDirective` that lacks
   `PrimitiveCall` data.
4. Keep diagnostic code `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` unless a
   focused test demonstrates a need for a narrower code.
5. Report structured context for both standalone primitive-call body tokens and
   `emit_return(...)` payload primitive-call tokens.
6. Preserve existing diagnostics for raw `emit_return(left)`,
   raw-plus-call payloads, malformed call selectors, malformed call arguments,
   non-call raw bodies, and non-call directives.
7. Add focused tests for:
   - named primitive calls;
   - `@self` calls;
   - specialization payloads;
   - `attrs[...]` payloads;
   - zero-argument calls;
   - nested raw argument payloads;
   - `emit_return(call<primitive=...>(...));` payload calls;
   - exact source locations;
   - exact add-call artifact stability;
   - existing M126-M136 diagnostics and artifact-byte stability.
8. Update redesign docs if diagnostic behavior or boundaries are clarified.

## Out Of Scope

- Primitive dependency closure; resolving named primitive references against
  the catalog; expanding `@self`; interpreting selector specialization or
  `attrs[...]`; resolving argument identifiers; recursively lowering argument
  expressions; expression parsing; backend call rendering; source repair;
  complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M137 changes only the unsupported
   primitive-call diagnostic boundary and preserves M133/M134 exact add-call
   lowering plus M135/M136 representation behavior. It must not introduce
   primitive resolution, dependency closure, `@self` expansion, expression
   parsing, recursive argument lowering, backend call rendering, renderer
   inference, or broad IR machinery.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used; verify structured diagnostic context remains diagnostic
   context only; verify selector and argument payloads remain opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M137 and preserve M128-M136 boundaries.
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

If M137 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M137 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M137 is accepted. Select exactly one concrete M138 task focused on
lowering from recognized TSIL body-token islands and grounded in the M127
inventory plus the M128-M137 body-intake/body-token/lowering results. Do not
create a separate post-M137 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 138 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
