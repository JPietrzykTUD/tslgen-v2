# M131 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M130:

```text
Milestone 131: Exact TSIL Primitive-Call Island Boundary Slice
```

Milestones 1 through 130 are accepted. M128 admitted exact quoted `tsil`
payload envelopes into the clean body model as raw `ImplementationBody` lines.
M129 classified exact `emit_return(...)` directive envelopes from those raw
payload lines. M130 classified exact selected directive envelopes:
`var<...>(...)`, `let<...>(...)`, `loop<...>(...)`, `if<...>(...)`,
`switch<...>(...)`, and `else<...>`.

M131 continues the source-owned body-line direction. It must recognize exact
single-line `call<primitive=...>(...)` islands only in TSIL raw body lines that
remain raw after M129-M130 directive classification. It must not parse
assignments, array access, expressions, directive payloads, primitive
semantics, dependency closure, or backend rendering.

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
- `tslgen/src/tslgen/pipeline/_tsil_directives.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Corpus Grounding

Use current `.tsl` source data as evidence for the selected call-island
boundary:

- `tsldata/primitives/arithmetic/fundamental.tsl:43`:
  `result[i] = call<primitive=@self[type<backend>(vector::as_extension(scalar))]>(left[i], right[i]);`
- `tsldata/primitives/bitwise/shifts.tsl:52`:
  `result[i] = call<primitive=@self[type<backend>(vector::as_extension(scalar)), shift]>(data[i]);`
- `tsldata/primitives/arithmetic/fundamental.tsl:130`:
  `emit_return(call<primitive=set_zero[Vec]>());`
- `tsldata/primitives/bitwise/bit_ops.tsl:36-37`:
  `var<const_infer>(ua, call<primitive=reinterpret[...]>(left));`

The first two lines are M131 scope because the call appears in a raw
assignment-like body line. The latter two are evidence for future
directive-payload segmentation; M131 must leave already classified directive
payloads opaque.

## Goal

When an M128 raw TSIL body line still remains a `RawStringLine` after M130 and
contains one exact single-line primitive-call island:

```text
call<primitive=selector>(opaque-payload)
```

classify only that call span as a lowerable segment. Preserve raw source text
before and after the call as `RawStringToken` segments. Selector and payload
text are source-owned and opaque. A zero-argument payload such as
`call<primitive=set_zero[Vec]>()` is accepted.

Use the existing source-body model if sufficient, for example a
`LowerableDirective` named `call` with arguments such as
`("primitive", selector, payload)`, or an equally narrow typed segment value if
implementation evidence shows the existing value is insufficient. Do not add a
new IR category/request/result/worklist family.

## Required Executor Task

Run exactly one write-capable executor for M131. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve M128 quoted-TSIL intake, M129 `emit_return` classification, M130
   directive-envelope classification, and existing synthetic
   `body <operation>(...)` artifact bytes.
3. Recognize only `call<primitive=...>(...)` islands from parser-recognized
   TSIL payload lines that remain raw after M130.
4. Preserve selector text after `primitive=` and before the matching outer `>`.
   Delimiter matching must be sufficient for current corpus selectors with
   nested angle-looking text inside brackets, such as
   `@self[type<backend>(vector::as_extension(scalar))]`.
5. Preserve payload text between the outer `(` and matching `)`. Payload text
   remains opaque and may be empty.
6. Preserve raw prefix/suffix text around the call island; do not interpret
   assignment, array access, semicolon, operators, braces, or target-like text.
7. Do not classify calls inside existing `emit_return`, `var`, `let`, `loop`,
   `if`, `switch`, or `else` directive payload arguments in this milestone.
8. Keep selected bodies containing primitive-call islands unsupported for
   backend rendering unless a later milestone defines semantic call lowering.
9. Add focused tests for:
   - assignment-like raw prefix/suffix preservation around
     `call<primitive=@self[type<backend>(...)]>(left[i], right[i])`;
   - `call<primitive=set_zero[Vec]>()` with an empty payload;
   - malformed call envelopes and unsupported nearby call-like names remaining
     unsupported;
   - direct primitive-looking names such as `sub(left, right)` remaining
     unsupported;
   - existing M129/M130 directive payloads containing `call<primitive=...>`
     remaining opaque and not segmented;
   - existing M128-M130 behavior and artifact-byte stability remaining intact.
10. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- Primitive resolution, dependency closure, `@self` resolution, type-argument
  parsing, argument splitting, expression parsing, helper/operator lowering,
  assignment lowering, array access lowering, directive-payload segmentation,
  multiline call matching, generation/backend query evaluation, backend
  rendering, source repair, complete TSIL grammar, runtime `tsldata` semantic
  lookup, `frozen` or `tslgenold` runtime dependency, registries,
  dispatchers, hidden backfeeds, fixpoint mechanisms, or new lowering IR
  category/request/result/worklist families.
- Supporting `call<intrin=...>`, `call<...>` selectors other than
  `primitive=`, direct primitive-looking calls, helper calls, `intrin`,
  `intrin_compose`, `cast<...>`, `mem<...>`, `io<...>`, `type<...>`,
  `value<...>`, assignments, array access, or any unselected keyword.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M131 remains an exact primitive-call island
   classification slice over raw TSIL body lines and does not introduce broad
   parser architecture, new IR machinery, runtime legacy dependencies,
   expression lowering, assignment lowering, directive-payload segmentation, or
   renderer inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for primitive lookup, dependency closure, `@self`
   resolution, type inference, query evaluation, argument projection, or
   backend spellings; verify selector and payload text stay opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M131 and preserve M128-M130 boundaries.
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

If M131 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M131 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M131 is accepted. Select exactly one concrete M132 task focused on
lowering from recognized directive/body islands and grounded in the M127
inventory plus the M128-M131 body-intake and lowerable-island results. Do not
create a separate post-M131 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 132 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
