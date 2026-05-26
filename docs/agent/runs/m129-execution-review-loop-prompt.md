# M129 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M128:

```text
Milestone 129: Exact Inline TSIL Emit-Return Operator Lowering Slice
```

Milestones 1 through 128 are accepted. M126 introduced the ADR-036 body model
boundary: implementation bodies are ordered source-owned body lines that may
later contain lowerable segments. M127 inventoried the real TSIL surface across
all current `tsldata/**/*.tsl` files. M128 admitted exact quoted `tsil`
payload envelopes into the clean body model as raw `ImplementationBody` lines,
while selected raw TSIL bodies still produce unsupported-lowering diagnostics.

M129 is the first semantic lowering slice over M128 raw TSIL payload content.
It must remain an exact `emit_return` operator-island lowering slice, not a
general TSIL parser or target-language passthrough.

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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/binary_operations.py`
- `tslgen/src/tslgen/lowering/comparison_operations.py`
- `tslgen/src/tslgen/backends/cpp/backend.py`
- `tslgen/src/tslgen/backends/rust/backend.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Corpus Grounding

Use current `.tsl` source data as evidence for the selected exact forms:

- `tsldata/primitives/arithmetic/fundamental.tsl:31`:
  `tsil "emit_return(left + right);"`
- `tsldata/primitives/arithmetic/fundamental.tsl:328`:
  `tsil "emit_return(left - right);"`
- `tsldata/primitives/comparison/fundamental.tsl:33`,
  `:192`, `:344`, `:539`, `:734`, and `:900`:
  exact scalar comparison returns for `==`, `!=`, `<`, `>`, `<=`, and `>=`.

These source lines are evidence for this milestone. Do not load operation
semantics or backend spellings from `tsldata/` at runtime.

## Goal

When a selected implementation body contains exactly one M128 raw TSIL line
matching one of these forms:

```text
emit_return(<identifier> + <identifier>);
emit_return(<identifier> - <identifier>);
emit_return(<identifier> == <identifier>);
emit_return(<identifier> != <identifier>);
emit_return(<identifier> < <identifier>);
emit_return(<identifier> > <identifier>);
emit_return(<identifier> <= <identifier>);
emit_return(<identifier> >= <identifier>);
```

lower it to the existing typed `LoweredBinaryOperationExpression` or
`LoweredComparisonOperationExpression` for the selected primitive operation.
The operation meaning comes from the selected primitive and the exact accepted
operator spelling together. Backends must still render C++ and Rust from typed
lowered values; raw TSIL text must not be rendered.

Operand names are source-owned identifier tokens. Carry operand order into
`LoweredParameterRef` exactly as written when the operands refer to declared
primitive parameters. Do not normalize swapped operands, reject duplicate
operands merely because they are duplicated, or repair malformed source text.

## Required Executor Task

Run exactly one write-capable executor for M129. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep the existing synthetic `body <operation>(...)` parser/catalog/lowering
   path and accepted generated artifact bytes stable.
3. Add exact raw-TSIL lowering for the one-line M128 body shape:
   `emit_return(<identifier> <operator> <identifier>);`.
4. Support only:
   - `add` with `+`;
   - `sub` with `-`;
   - `equal` with `==`;
   - `nequal` with `!=`;
   - `less_than` with `<`;
   - `greater_than` with `>`;
   - `less_than_or_equal` with `<=`;
   - `greater_than_or_equal` with `>=`.
5. Reuse the existing lowering-owned operation descriptors and existing
   lowered expression model. Do not add a new lowering IR
   category/request/result/worklist family.
6. Keep operand order source-owned. If the exact body says
   `emit_return(right - left);`, the lowered expression should refer to
   `right` then `left`, provided those names are declared primitive
   parameters. Unknown operands must diagnose unsupported lowering.
7. Diagnose unsupported or malformed raw TSIL bodies with structured lowering
   diagnostics. Negative cases must include at least:
   - primitive/operator mismatch, such as `add` with `-`;
   - unsupported operator such as `*` in this milestone;
   - helper calls such as `details::arith_mul(...)`;
   - primitive calls such as `call<primitive=add>(...)`;
   - multiline raw TSIL bodies;
   - missing semicolon or extra expression structure.
8. Add focused tests for:
   - raw TSIL `emit_return(left + right);` lowering and C++/Rust artifact
     equality with the synthetic `body add(left, right)` path;
   - raw TSIL `emit_return(left - right);` lowering and C++/Rust artifact
     equality with the synthetic `body sub(left, right)` path;
   - all six raw TSIL comparison operator forms lowering to existing typed
     comparison expressions/artifacts;
   - source-owned operand order;
   - each required negative boundary above;
   - existing M128 raw intake and unsupported-lowering tests remaining stable
     where the payload is outside the M129 exact forms.
9. Update redesign docs if behavior or diagnostic boundaries are clarified.

## Out Of Scope

- Full TSIL parsing, expression precedence, nested expressions, parentheses
  beyond the exact accepted envelope, literals, constants, member access, array
  access, assignments, declarations, loops, block structure, comments inside
  expressions, semicolon repair, whitespace normalization beyond the exact
  accepted forms, or multiline semantic lowering.
- Lowering `details::arith_mul`, `details::arith_rem`,
  `details::arith_add`, `call<primitive=...>`,
  `call<primitive=@self[...]>(...)`, `intrin`, `intrin_compose`, `cast<...>`,
  `type<generation>`, `type<backend>`, `value<generation>`,
  `value<backend>`, `if<generation>`, `else if<generation>`,
  `else<generation>`, `if<compile>`, `else<compile>`, `if<runtime>`,
  `else<runtime>`, `mem<...>`, or `io<...>`.
- Parsing full current `tsldata/` primitive nesting under `impls:`.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Raw TSIL backend rendering, renderer-side semantic inference, source repair,
  a complete TSIL grammar, a target-language parser, registry, dispatcher,
  callback map, plugin system, hidden backfeed, or fixpoint mechanism.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M129 remains an exact lowering island over
   M128 raw TSIL and does not introduce broad parser architecture, new IR
   machinery, runtime legacy dependencies, or renderer inference.
2. Boundary auditor: verify no `frozen/`, `tslgenold/`, or runtime `tsldata/`
   shortcut is used for operation lookup, compatibility, source repair,
   parameter projection, or backend spellings; verify unsupported helpers and
   calls stay unsupported.
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
lowering and grounded in the M127 inventory plus the M128/M129 body-intake and
return-island results. Do not create a separate post-M129 planning prompt
unless review returns `Return To Planner`, `Reject`, or an explicit stop
condition is recorded.

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
