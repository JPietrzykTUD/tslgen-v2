# M128 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M127:

```text
Milestone 128: Real TSIL Payload Envelope Body Intake Slice
```

Milestones 1 through 127 are accepted. M126 introduced the ADR-036 body model
boundary: implementation bodies are ordered source-owned body lines that may
later contain lowerable segments. M127 inventoried the real TSIL surface across
all current `tsldata/**/*.tsl` files and selected this implementation step as
a lowering-enabling prerequisite: admit real quoted `tsil` payload envelopes
into the clean body model before selecting semantic TSIL islands such as
`emit_return(...)`.

M128 is not semantic TSIL lowering. It should make real quoted `tsil` payloads
visible to the clean parser/catalog/body model as source-owned raw body lines.
Selected raw TSIL bodies must still produce unsupported-lowering diagnostics
instead of generated backend code.

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
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Extend the clean restart source-body intake so the existing narrow outer
fixture shape can use real quoted `tsil` payload envelopes as implementation
bodies:

```text
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "emit_return(left + right);"
```

and:

```text
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil """
      var<init_register>(result)
      emit_return(result);
    """
```

The payload content should become ordered raw `ImplementationBody` lines. Keep
the existing exact synthetic `body <operation>(...)` behavior stable.

## Required Executor Task

Run exactly one write-capable executor for M128. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep the existing `body <operation>(...)` parser/catalog/lowering path and
   accepted generated artifact bytes stable.
3. Add parser support for exact inline quoted `tsil "..."` implementation body
   payloads inside the current clean restart outer fixture shape.
4. Add parser support for exact multiline quoted `tsil """ ... """`
   implementation body payloads inside the current clean restart outer fixture
   shape.
5. Promote parsed quoted TSIL payloads into domain `ImplementationBody` values
   containing ordered `RawStringLine` values with source locations.
6. Keep selected raw TSIL bodies unsupported in lowering with structured
   diagnostics. Do not render raw TSIL as C++ or Rust.
7. Add focused tests for:
   - inline quoted `tsil` body intake;
   - multiline quoted `tsil` body intake and source-line order;
   - malformed or unterminated quoted `tsil` diagnostics;
   - existing synthetic `body ...` behavior and representative artifact bytes;
   - selected raw TSIL body unsupported-lowering behavior.
8. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- Parsing full current `tsldata/` primitive nesting under `impls:`.
- Supporting `tsil:` block entries; record as a future follow-up unless a later
  milestone selects it.
- Parsing or lowering `emit_return(...)`, `call<primitive=...>`,
  `call<primitive=@self[...]>(...)`, helpers, intrinsics, assignments, array
  access, declarations, operators, loops, `if<generation>`,
  `else if<generation>`, `else<generation>`, `if<compile>`, `else<compile>`,
  `if<runtime>`, `else<runtime>`, `switch<compile>`, casts, memory helpers, or
  I/O helpers.
- Rendering raw TSIL payload text as generated C++ or Rust code.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Building a complete TSIL grammar/parser, semantic validator, source repair
  mechanism, broad expression parser, target-language compiler, registry,
  dispatcher, callback map, plugin system, hidden backfeed, or fixpoint
  mechanism.
- Adding a new lowering IR category/request/result/worklist family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M128 remains a narrow TSIL payload-envelope
   intake slice and does not become semantic TSIL lowering or broad parser
   architecture.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, selection, lowering, parameter
   projection, or backend spellings.
3. Documentation auditor: verify behavior docs and roadmap accurately describe
   M128, including that raw TSIL bodies are unsupported for lowering and that
   M127 follow-ups (`else if<generation>`, `cast<...>`, `mem<...>`,
   `io<...>`) remain future work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/domain/catalog.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M128 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M128 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M128 is accepted. Select exactly one concrete M129 task focused on
lowering and grounded in the M127 inventory plus the M128 body intake result.
Do not create a separate post-M128 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 129 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
