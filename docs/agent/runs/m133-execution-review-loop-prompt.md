# M133 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M132:

```text
Milestone 133: Tiny Clean Remaining Binary Operator TSIL Lowering Slice
```

Milestones 1 through 132 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M132 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
deterministic source-set generation, exact binary/unary/comparison TSIL
emit-return body spellings, exact binary operator TSIL body spellings, and
declared binary parameter preservation.

M133 keeps the next task focused on lowering. It completes the currently
modeled binary operator-shaped TSIL bridge by adding exact selected-body
recognition for the remaining already-supported binary operations whose
backend spellings and lowering descriptors already exist: `mul`, `div`, `mod`,
`shift_left`, and `shift_right`.

This milestone is not arbitrary C, C++, Rust, or TSIL expression parsing. It
recognizes only exact `tsil "emit_return(operand0 OP operand1);"` forms for
`*`, `/`, `%`, `<<`, and `>>` under the existing tiny clean binary document
shape. Operands must be declared binary parameters. Operand order and
repetition are source-authored semantics and must be preserved exactly.
Legacy helper-shaped bodies such as `details::arith_mul(...)` are backend
evidence from `frozen/`, not clean source semantics. The clean source form for
the modeled operation is the exact operator spelling, for example
`factor1 * factor2`; any future backend helper choice belongs after typed
lowering, inside backend translation/rendering.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- current clean parser/catalog/selection/lowering implementation under
  `tslgen/src/tslgen/`
- current tiny-pipeline tests in `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Allow exact binary TSIL operator bodies such as:

```text
prim<v:=(v,v)> div(divident, divisor):
  implementation scalar si32:
    tsil "emit_return(divident / divisor);"
```

```text
prim<v:=(v,v)> shift_left(data, shift):
  implementation scalar si32:
    tsil "emit_return(data << shift);"
```

The selected implementation must promote the exact source spelling into the
existing typed `BinaryOperationBody` operation ids before lowering, preserve
declared parameter names and source-authored operand references through
lowered values, and generate deterministic C++/Rust artifacts from typed
lowering results.

## Required Executor Task

Run exactly one write-capable executor for M133. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve the M125 exact source-document shape: one primitive header followed
   by one or more implementation/body pairs. Each implementation block remains
   exactly an implementation header immediately followed by one body line.
3. Preserve M132 binary parameter behavior: `prim<v:=(v,v)> name(param0,
   param1):` may use any two distinct valid identifier parameter names, and
   accepted binary body operands must reference declared parameters while
   preserving source-authored order and repetition.
4. Add exact operator-shaped TSIL body recognition for the remaining
   already-modeled binary operations:
   - `operand0 * operand1` -> `mul`;
   - `operand0 / operand1` -> `div`;
   - `operand0 % operand1` -> `mod`;
   - `operand0 << operand1` -> `shift_left`;
   - `operand0 >> operand1` -> `shift_right`.
5. Preserve accepted M131 exact operator-shaped TSIL bodies for `+`, `-`, `&`,
   `|`, and `^`.
6. Promote accepted M133 operator-shaped TSIL bodies into typed
   `BinaryOperationBody` values before selection, lowering, and backend
   emission. Do not render by rescanning raw TSIL text.
7. Preserve declared binary parameter names and source-authored operand order
   and repetition in `BinaryOperationBody`, `LoweredFunctionSignature`,
   `LoweredBinaryOperationExpression`, generated C++ parameters/returns, and
   generated Rust parameters/returns.
8. Prove selected M133 operator-shaped TSIL bodies drive generated C++/Rust
   artifacts for `mul`, `div`, `mod`, `shift_left`, and `shift_right`.
9. Prove at least representative non-`left/right` corpus-like parameter names
   drive lowering, including `divident, divisor` for `/`, `dividend, divisor`
   for `%`, and `data, shift` for `<<` or `>>`.
10. Prove swapped and repeated declared operands preserve source-authored
    semantics for at least one M133 operator.
11. Prove undeclared operands in M133 operator-shaped TSIL bodies produce
    structured diagnostics and are not normalized.
12. Prove selected mismatched M133 operator-shaped TSIL bodies, such as
    `data << shift` under `shift_right`, produce the existing structured
    lowering mismatch diagnostic.
13. Prove malformed nearby M133 operator forms, such as missing required
    spaces, unsupported logical operators, nested expressions, casts, or
    missing semicolons, produce structured diagnostics rather than source
    repair, target-language parsing, renderer inference, or silent fallback.
14. Preserve M132 declared-parameter behavior, M131 exact binary operator TSIL
    behavior, M130 ordered comparison TSIL behavior, M129 inequality TSIL
    behavior, M128 equality TSIL behavior, M127 unary TSIL behavior, M126
    binary function-call TSIL behavior, M125 multi-implementation behavior,
    M124 multi-source behavior, explicit target selection, compatibility
    diagnostics, and deterministic artifact ordering.
15. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Broad `tsldata` syntax/layout parsing, nested implementation maps, multiple
  primitive blocks in one document, attributes, tests, descriptions,
  `requires` clauses, type groups, extension fallback, dependency closure, or
  target discovery.
- Broad TSIL parsing, primitive calls, intrinsics, helper calls such as
  `details::arith_mul(...)`, casts, variables, immediates, multiple statements,
  multiline TSIL bodies, helper evaluation, branch pruning, source repair, or
  TSIL compiler behavior. Treat `details::arith_mul(...)` and similar helper
  calls as legacy/backend evidence, not accepted clean source forms.
- Adding operation ids, backend spellings, scalar type support, compatibility
  rules, or semantic rules beyond operations already modeled before this
  milestone.
- Supporting signatures such as `v:=(v,s)`, `v:=(v,sImm)`, mask signatures,
  immediate parameters, scalar shift-count source forms, or actual broad
  corpus implementation maps.
- Adding primitive aliases such as current corpus `binary_and` names for the
  accepted clean operation id `bit_and`.
- Loading operation semantics, compatibility rules, parameter aliases, or
  backend spellings from `tsldata/`, backend manifests, YAML, `frozen`,
  `tslgenold`, plugins, or environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M133 is an exact remaining binary operator
   TSIL lowering slice, remains KISS-compatible, and does not add broad TSIL
   parsing, arbitrary target-language operator modeling, broad `tsldata`
   parsing, parameter aliasing, target discovery, primitive aliasing, backend
   manifest loading, source repair, or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, parameter aliasing, compatibility evaluation, implementation
   selection, lowering, or backend spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M133 as broad TSIL
   parsing, broad `tsldata` parsing, arbitrary target-language operator
   modeling, corpus ingestion, backend manifest loading, source repair, target
   discovery, CLI, writer, primitive aliasing, parameter aliasing, or old
   migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

## Completion Rules

If M133 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M133 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M133 is accepted. Select exactly one concrete M134 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M133 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

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
