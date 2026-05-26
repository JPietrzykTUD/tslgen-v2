# M131 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M130:

```text
Milestone 131: Source-Owned Body Token Stream Consolidation Slice
```

Milestones 1 through 130 are accepted. M128 admitted exact quoted `tsil`
payload envelopes into the clean body model as raw body content. M129
classified exact `emit_return(...)` directive envelopes. M130 classified exact
selected directive envelopes: `var<...>(...)`, `let<...>(...)`,
`loop<...>(...)`, `if<...>(...)`, `switch<...>(...)`, and `else<...>`.

M131 responds to the design correction that `RawStringLine | SegmentedLine` is
too line-centered for future lowerable islands that may span source lines. It
must consolidate the canonical domain implementation body into a source-owned
token stream, preserving current behavior exactly and adding no new TSIL
lowering semantics.

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

## Design Grounding

ADR-036 states that implementation bodies are source-owned and should be
modeled as raw source text plus documented lowerable islands. M128-M130 proved
the line-container version of that idea, but the next real concern is that
lowerable islands such as future `call<primitive=...>(...)` may span source
lines. A line-as-primary domain model would force either single-line-only
matching or a premature TSIL parser.

M131 should therefore make the domain body model token-first:

```text
ImplementationBody
  tokens: tuple[BodyToken, ...]

BodyToken =
  RawStringToken
  LowerableOperationFragment
  LowerableDirective
```

Raw string tokens may contain newlines, indentation, braces, assignments,
semicolons, and any target-like text. Lowerable tokens keep the opaque
arguments and source locations accepted by M126-M130.

Parser output may remain line-oriented as an adapter detail if that keeps the
slice small. The domain catalog and lowering boundary should consume the token
stream as canonical.

## Goal

Replace the canonical domain implementation-body shape based on
`RawStringLine | SegmentedLine` with a deterministic source-owned token stream.
Preserve accepted M126-M130 behavior, diagnostics, source locations, and
artifact bytes. Do not recognize any new lowerable TSIL form in this milestone.

Existing line container values such as `RawStringLine`, `SegmentedLine`, and
`BodyLine` should be removed from the canonical domain model or reduced to
private/parser-side compatibility only if removing them completely would make
the slice unnecessarily risky.

## Required Executor Task

Run exactly one write-capable executor for M131. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve M126 synthetic `body <operation>(...)` lowering behavior and
   existing generated artifact bytes.
3. Preserve M128 quoted-TSIL intake semantics: inline and multiline payloads
   remain source-owned raw text in deterministic order.
4. Preserve M129 `emit_return(...)` directive classification and unsupported
   opaque-return diagnostics.
5. Preserve M130 directive-envelope classification, raw prefix/suffix
   preservation, and unsupported selected-body behavior.
6. Make `ImplementationBody` expose a canonical `tokens` sequence containing
   `RawStringToken`, `LowerableOperationFragment`, and `LowerableDirective`
   values, or an equally small equivalent justified by implementation
   evidence.
7. Update catalog promotion, lowering, and tests to consume the token stream
   rather than line containers.
8. Preserve source locations for diagnostics. If raw text spans multiple
   lines, keep enough source identity for future cross-line island matching and
   diagnostics.
9. Add focused tests proving:
   - `body add(left, right)` becomes one `LowerableOperationFragment` token;
   - inline quoted `tsil` becomes raw token data;
   - multiline quoted `tsil` preserves order and newline/text boundaries;
   - M129 `emit_return(...)` becomes one directive token;
   - M130 `} else<compile> {` becomes raw/directive/raw tokens in order;
   - selected unsupported TSIL bodies still diagnose without rendering raw
     text;
   - existing accepted artifact bytes remain stable.
10. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- New TSIL syntax recognition; `call<primitive=...>` island matching;
  primitive resolution; dependency closure; `@self` resolution; type-argument
  parsing; argument splitting; expression parsing; helper/operator lowering;
  assignment lowering; array access lowering; directive-payload segmentation;
  multiline call matching; generation/backend query evaluation; backend
  rendering; source repair; complete TSIL grammar; runtime `tsldata` semantic
  lookup; `frozen` or `tslgenold` runtime dependency; registries;
  dispatchers; hidden backfeeds; fixpoint mechanisms; or new lowering IR
  category/request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M131 is a behavior-preserving body-model
   consolidation and does not introduce broad parser architecture, new IR
   machinery, runtime legacy dependencies, expression lowering, primitive-call
   matching, assignment lowering, directive-payload segmentation, or renderer
   inference.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used for primitive lookup, dependency closure, type inference,
   query evaluation, argument projection, backend spellings, or source repair.
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
lowering from recognized body-token islands and grounded in the M127 inventory
plus the M128-M131 body-intake and body-token-stream results. Do not create a
separate post-M131 planning prompt unless review returns `Return To Planner`,
`Reject`, or an explicit stop condition is recorded.

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
