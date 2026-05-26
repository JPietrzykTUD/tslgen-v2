# M129 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M128:

```text
Milestone 129: Exact TSIL Emit-Return Directive Boundary Slice
```

Milestones 1 through 128 are accepted. M126 introduced the ADR-036 body model
boundary: implementation bodies are ordered source-owned body lines that may
later contain lowerable segments. M127 inventoried the real TSIL surface across
all current `tsldata/**/*.tsl` files. M128 admitted exact quoted `tsil`
payload envelopes into the clean body model as raw `ImplementationBody` lines,
while selected raw TSIL bodies still produce unsupported-lowering diagnostics.

M129 is the first keyword-level lowering slice over M128 raw TSIL payload
content. It must recognize the `emit_return` directive boundary and keep its
payload opaque. It must not become expression/operator/helper/call lowering, a
general TSIL parser, or target-language passthrough.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Corpus Grounding

Use current `.tsl` source data as evidence for the selected keyword boundary:

- `tsldata/primitives/arithmetic/fundamental.tsl:31`:
  `tsil "emit_return(left + right);"`
- `tsldata/primitives/arithmetic/fundamental.tsl:328`:
  `tsil "emit_return(left - right);"`
- `tsldata/primitives/comparison/fundamental.tsl:33`,
  `:192`, `:344`, `:539`, `:734`, and `:900`:
  exact scalar comparison returns for `==`, `!=`, `<`, `>`, `<=`, and `>=`.
- Many multiline payloads use indented `emit_return(...)` statements whose
  payloads are `result`, `call<primitive=...>(...)`, `details::...`,
  `intrin_compose<...>(...)`, casts, array access, and generation/backend
  queries.

These lines are evidence that `emit_return` is a TSIL directive boundary.
They are not evidence that M129 should parse the expression inside
`emit_return(...)`. Do not load operation semantics or backend spellings from
`tsldata/` at runtime.

## Goal

When an M128 raw TSIL body line contains an exact `emit_return` statement
envelope:

```text
emit_return(<opaque-source-payload>);
emit_return(<opaque-source-payload>) ;
```

classify it as the existing typed directive concept:

```text
LowerableDirective(name="emit_return", arguments=(<opaque-source-payload>,))
```

or an equally narrow typed directive value if implementation evidence shows the
existing domain value is insufficient. The payload is source-owned opaque text.
Do not split it into operands, parse operators, resolve helper calls, or map it
to a backend expression in this milestone.

## Required Executor Task

Run exactly one write-capable executor for M129. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep the existing synthetic `body <operation>(...)` parser/catalog/lowering
   path and accepted generated artifact bytes stable.
3. Recognize only the `emit_return` keyword/directive envelope from M128 raw
   TSIL payload lines.
4. Preserve the directive payload exactly as source text between the outer
   `emit_return(` and its matching close parenthesis.
5. Match leading/trailing payload-line indentation introduced by quoted
   multiline TSIL only for finding the directive boundary. Do not normalize the
   directive payload.
6. Handle nested parentheses while finding the matching close parenthesis for
   the outer directive call. This is delimiter matching for the keyword
   envelope, not expression parsing.
7. Promote exact `emit_return` directive lines into typed body/directive values
   that later expression/call/helper/query milestones can consume.
8. Keep selected bodies containing only an `emit_return` directive with opaque
   payload blocked before backend rendering with a structured unsupported
   return-expression diagnostic unless the existing synthetic `body ...` path
   is in use.
9. Diagnose unsupported or malformed raw TSIL bodies with structured
   diagnostics. Negative cases must include at least:
   - missing semicolon;
   - unbalanced outer directive parentheses;
   - extra statement text after the directive;
   - unsupported directive keyword;
   - non-directive raw line;
   - helper/call/operator payloads remaining opaque and not rendered.
10. Add focused tests for:
   - inline `emit_return(left + right);` directive classification with opaque
     payload `left + right`;
   - multiline raw TSIL payload lines with indentation, including
     `emit_return(result);`;
   - nested-parenthesis payload preservation, such as
     `emit_return(call<primitive=add>(left, right));`;
   - helper/operator payloads remaining opaque and not semantically lowered;
   - selected `emit_return` directive bodies producing unsupported
     return-expression diagnostics and no artifacts;
   - existing M128 raw intake tests and synthetic `body ...` artifact-byte
     stability remaining intact.
11. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- Full TSIL parsing, expression precedence, operator/operand parsing,
  expression semantic lowering, literals, constants, member access, array
  access, assignments, declarations, loops, block structure, comments inside
  expressions, semicolon repair, or whitespace normalization beyond exact
  directive-envelope matching.
- Lowering `details::arith_mul`, `details::arith_rem`,
  `details::arith_add`, operators such as `+`, `-`, `==`, `<`, `>`, `<=`,
  `>=`, `!=`, `call<primitive=...>`, `call<primitive=@self[...]>(...)`,
  `intrin`, `intrin_compose`, `cast<...>`, `type<generation>`,
  `type<backend>`, `value<generation>`, `value<backend>`, `if<generation>`,
  `else if<generation>`, `else<generation>`, `if<compile>`,
  `else<compile>`, `if<runtime>`, `else<runtime>`, `mem<...>`, or `io<...>`.
- Parsing full current `tsldata/` primitive nesting under `impls:`.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Raw TSIL backend rendering, renderer-side semantic inference, source repair,
  a complete TSIL grammar, a target-language parser, registry, dispatcher,
  callback map, plugin system, hidden backfeed, or fixpoint mechanism.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M129 remains an exact TSIL directive-boundary
   slice and does not introduce broad parser architecture, new IR machinery,
   runtime legacy dependencies, expression lowering, or renderer inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for operation lookup, compatibility, source repair,
   parameter projection, or backend spellings; verify helpers, calls, and
   operators stay opaque inside the directive payload.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M129 and preserve M127/M128 follow-ups.
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

If M129 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M129 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M129 is accepted. Select exactly one concrete M130 task focused on
keyword/directive lowering and grounded in the M127 inventory plus the
M128/M129 body-intake and directive-boundary results. Do not create a separate
post-M129 planning prompt unless review returns `Return To Planner`, `Reject`,
or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 130 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
