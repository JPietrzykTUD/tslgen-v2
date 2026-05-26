# M130 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M129:

```text
Milestone 130: Exact TSIL Var Directive Boundary Slice
```

Milestones 1 through 129 are accepted. M128 admitted exact quoted `tsil`
payload envelopes into the clean body model as raw `ImplementationBody` lines.
M129 classified exact `emit_return(...)` directive envelopes from those raw
payload lines into typed directive values while keeping the directive payload
opaque and blocking backend rendering.

M130 continues the keyword/directive-first lowering path. It must recognize
exact `var<...>(...)` TSIL directive envelopes and keep modifier/payload text
opaque. It must not become variable semantics, type inference,
expression/operator/helper/call lowering, or target-language passthrough.

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

- `tsldata/primitives/arithmetic/fundamental.tsl:36`:
  `var<init_register>(result)`
- `tsldata/primitives/bitwise/bit_ops.tsl:37-38`:
  `var<const_infer>(ua, call<primitive=reinterpret[...]>(left));` and
  `var<const_infer>(ub, call<primitive=reinterpret[...]>(right));`
- Many multiline payloads combine `var<...>(...)` directive lines with loops,
  assignments, helper calls, primitive calls, and `emit_return(...)`.

These lines are evidence that `var` is a TSIL directive boundary. They are not
evidence that M130 should parse initializer expressions, infer types, resolve
calls, or render backend code. Do not load operation semantics or backend
spellings from `tsldata` at runtime.

## Goal

When an M128 raw TSIL body line contains an exact `var` directive envelope:

```text
var<modifier>(opaque-payload)
var<modifier>(opaque-payload);
```

classify it as a typed directive value such as:

```text
LowerableDirective(name="var", arguments=(<modifier>, <opaque-payload>))
```

or an equally narrow typed directive value if implementation evidence shows the
existing domain value is insufficient. Modifier and payload text are
source-owned and opaque. Do not split initializer arguments, parse operators,
resolve helper calls, resolve primitive calls, infer storage semantics, or map
the directive to backend code in this milestone.

## Required Executor Task

Run exactly one write-capable executor for M130. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve M128 quoted-TSIL intake, M129 `emit_return` directive
   classification, and existing synthetic `body <operation>(...)` artifact
   bytes.
3. Recognize only `var<...>(...)` directive envelopes from parser-recognized
   TSIL payload bodies.
4. Preserve the modifier text between `var<` and the matching `>` and the
   payload text between the outer `(` and its matching `)`.
5. Use delimiter matching for the directive envelope only. Nested parentheses
   and bracket/angle-like source text inside the payload remain opaque.
6. Match leading/trailing payload-line indentation introduced by quoted
   multiline TSIL only for finding the directive boundary. Do not normalize the
   modifier or payload text.
7. Keep selected bodies containing `var` directives unsupported for backend
   rendering unless a later milestone defines complete statement/body
   lowering.
8. Add focused tests for:
   - `var<init_register>(result)` directive classification;
   - `var<const_infer>(ua, call<primitive=...>(left));` payload preservation;
   - malformed var envelopes and unsupported nearby directive names remaining
     unsupported;
   - multiline ordered coexistence with an already classified `emit_return`
     line;
   - existing M128/M129 behavior and artifact-byte stability remaining intact.
9. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- Variable declaration semantics, storage initialization, type inference,
  expression parsing, helper/call/operator lowering, assignment lowering,
  loops, generation/backend control, backend rendering, source repair,
  complete TSIL grammar, runtime `tsldata` semantic lookup, `frozen` or
  `tslgenold` runtime dependency, registries, dispatchers, hidden backfeeds,
  fixpoint mechanisms, or new lowering IR category/request/result/worklist
  families.
- Supporting `let<...>`, `loop<...>`, `if<...>`, `call<...>`, `intrin`,
  `intrin_compose`, `cast<...>`, `mem<...>`, `io<...>`, assignments, array
  access, or any keyword/directive not explicitly selected here.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M130 remains an exact TSIL `var`
   directive-boundary slice and does not introduce broad parser architecture,
   new IR machinery, runtime legacy dependencies, expression lowering, or
   renderer inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for operation lookup, compatibility, source repair,
   parameter projection, type inference, or backend spellings; verify helpers,
   calls, operators, and target-looking payload text stay opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M130 and preserve M127-M129 follow-ups.
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

If M130 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M130 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M130 is accepted. Select exactly one concrete M131 task focused on
keyword/directive lowering and grounded in the M127 inventory plus the
M128-M130 body-intake and directive-boundary results. Do not create a separate
post-M130 planning prompt unless review returns `Return To Planner`, `Reject`,
or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 131 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
