# M132 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M131:

```text
Milestone 132: Exact TSIL Primitive-Call Body-Token Island Boundary Slice
```

Milestones 1 through 131 are accepted. M131 made `ImplementationBody.tokens`
the canonical source-owned body model. Parser-owned line records remain
adapter details only. M132 is the first lowerable-island slice on top of that
token stream.

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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/pipeline/_tsil_directives.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognize exact TSIL primitive-call keyword islands in raw body-token text:

```text
call<primitive=selector>(opaque-payload)
```

Classify only the call span as a lowerable body token and preserve raw
source-authored prefix/suffix text as `RawStringToken` values. Selector and
payload text are opaque source data. This is keyword-envelope recognition, not
primitive semantics.

## Required Executor Task

Run exactly one write-capable executor for M132. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Consume the M131 `ImplementationBody.tokens` stream as the canonical body
   model.
3. Recognize only exact `call<primitive=...>(...)` islands inside raw token
   text from parser-recognized TSIL payloads.
4. Preserve raw prefix/suffix text around the call island, including
   assignment text, array access, braces, semicolons, whitespace, and other
   target-like text.
5. Keep selector text after `primitive=` and before the matching outer `>`
   opaque. Delimiter matching must be sufficient for current corpus selectors
   with nested angle-looking text inside brackets, such as
   `@self[type<backend>(vector::as_extension(scalar))]`.
6. Keep payload text between the outer `(` and matching `)` opaque. Payload
   text may be empty.
7. Support matching across contiguous raw body tokens so the outer selector
   and payload delimiters may be found even when the current parser emits one
   raw token per source line.
8. Do not classify calls inside existing `emit_return`, `var`, `let`, `loop`,
   `if`, `switch`, or `else` directive payload arguments in this milestone.
9. Keep selected bodies containing primitive-call islands unsupported for
   backend rendering until a later milestone defines semantic call lowering.
10. Add focused tests for:
    - assignment-like raw prefix/suffix preservation around
      `call<primitive=@self[type<backend>(...)]>(left[i], right[i])`;
    - `call<primitive=set_zero[Vec]>()` with an empty payload;
    - cross-line raw-token delimiter matching for one primitive-call island;
    - malformed call envelopes and unsupported nearby call-like names
      remaining unsupported;
    - direct primitive-looking names such as `sub(left, right)` remaining
      unsupported;
    - existing M129/M130 directive payloads containing `call<primitive=...>`
      remaining opaque and not segmented;
    - existing M126-M131 behavior and artifact-byte stability remaining intact.
11. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- Primitive resolution; dependency closure; `@self` resolution; type-argument
  parsing; call argument splitting; expression parsing; helper/operator
  lowering; assignment lowering; array access lowering; directive-payload
  segmentation; generation/backend query evaluation; backend rendering; source
  repair; complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
  `tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
  fixpoint mechanisms; or new lowering IR category/request/result/worklist
  families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M132 is an exact primitive-call island
   classification slice over the M131 body-token stream and does not introduce
   broad parser architecture, new IR machinery, runtime legacy dependencies,
   expression lowering, assignment lowering, directive-payload segmentation, or
   renderer inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for primitive lookup, dependency closure, `@self`
   resolution, type inference, query evaluation, argument projection, backend
   spellings, or source repair; verify selector and payload text stay opaque.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M132 and preserve M128-M131 boundaries.
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

If M132 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M132 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M132 is accepted. Select exactly one concrete M133 task focused on
lowering from recognized body-token islands and grounded in the M127 inventory
plus the M128-M132 body-intake/body-token results. Do not create a separate
post-M132 planning prompt unless review returns `Return To Planner`, `Reject`,
or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 133 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
