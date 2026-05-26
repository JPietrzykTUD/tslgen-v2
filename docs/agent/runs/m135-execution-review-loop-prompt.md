# M135 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M134:

```text
Milestone 135: Exact Emit-Return Parameter Payload Lowering Slice
```

Milestones 1 through 134 are accepted. M134 gives `emit_return(...)`
directives a narrow payload-token boundary: the original opaque payload text
is preserved in directive arguments, and exact lowerable payload islands are
available as source-owned payload tokens. M135 lowers only one additional
payload-token form: an exact raw token naming a selected primitive parameter.

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
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/backends/cpp/backend.py`
- `tslgen/src/tslgen/backends/rust/backend.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

When a selected implementation body is exactly one `emit_return(...)`
directive whose M134 payload-token stream contains exactly one raw token:

```text
emit_return(left);
```

and that raw token exactly matches a selected primitive parameter, lowering
should produce a typed lowered value-reference expression and the C++/Rust
backends should render a direct return of that parameter.

This is not general expression parsing. It is exact selected-parameter return
lowering over the M134 payload-token boundary.

## Required Executor Task

Run exactly one write-capable executor for M135. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129/M130 directive classification, M132 primitive-call
   classification, M133 standalone call lowering, and M134 payload-token
   classification stable unless a focused test exposes a defect.
3. Add the smallest typed lowered expression needed to represent returning a
   named selected parameter. Prefer a clear value-reference expression over
   broad expression machinery.
4. Teach C++ and Rust backends to render only that typed value-reference
   expression directly as the parameter name.
5. Lower only a selected `emit_return(...)` directive whose payload-token
   stream is exactly one `RawStringToken` and whose text exactly equals one of
   `selected.primitive.parameters`.
6. Emit a stable unsupported return-value diagnostic for a single raw
   identifier payload that does not match a selected primitive parameter, such
   as `emit_return(result);`.
7. Preserve existing `TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION` for raw payloads
   that are not exact single identifiers, including `left + right`, helper
   calls, raw-plus-call payloads, empty payloads, and malformed nearby forms.
8. Preserve M134 primitive-call payload behavior:
   - exact `emit_return(call<primitive=add>(left, right));` still lowers
     through M133;
   - unsupported recognized call payloads still produce
     `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL`.
9. Add focused tests for:
   - `emit_return(left);` and `emit_return(right);` C++/Rust artifact rendering;
   - exact source locations for parameter-return lowering;
   - unknown identifier diagnostics such as `emit_return(result);`;
   - non-identifier raw payload diagnostics such as `emit_return(left + right);`;
   - preserved M134 primitive-call payload behavior;
   - existing M126-M134 behavior and artifact-byte stability.
10. Update redesign docs if lowering behavior, diagnostic behavior, or
    boundaries are clarified.

## Out Of Scope

- General `emit_return` expression parsing; variable declarations or lookup;
  assignment lowering; array access; primitive-call dependency closure; `@self`
  interpretation; type-argument parsing; call argument splitting;
  helper/operator lowering; generation/backend query evaluation; backend call
  rendering; source repair; complete TSIL grammar; runtime `tsldata` semantic
  lookup; `frozen` or `tslgenold` runtime dependency; registries; dispatchers;
  hidden backfeeds; fixpoint mechanisms; or new lowering IR
  category/request/result/worklist families beyond the single value-reference
  expression needed by this slice.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M135 lowers only exact selected-parameter
   `emit_return` payloads through a small typed value-reference expression. It
   must not introduce general expression parsing, variables, assignment/array
   lowering, dependency closure, backend call rendering, renderer inference, or
   broad IR machinery.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used; verify unknown identifiers are diagnostics, not guessed
   variables; verify M134 primitive-call payload boundaries are preserved.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M135 and preserve M128-M134 boundaries.
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
lowering from recognized body-token islands and grounded in the M127 inventory
plus the M128-M135 body-intake/body-token/lowering results. Do not create a
separate post-M135 planning prompt unless review returns `Return To Planner`,
`Reject`, or an explicit stop condition is recorded.

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
