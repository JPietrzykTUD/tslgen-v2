# M132 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M131:

```text
Milestone 132: Tiny Clean Binary Declared-Parameter Lowering Slice
```

Milestones 1 through 131 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M131 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
deterministic source-set generation, exact binary/unary/comparison TSIL
emit-return body spellings, and exact binary operator TSIL body spellings.

M132 keeps the next task focused on lowering and removes the current
binary-fixture assumption that declared binary parameters must be exactly
`left, right`. Real corpus evidence uses binary parameter names such as
`data, shift`, `divident, divisor`, and `dividend, divisor`; this evidence
must not become a runtime semantic dependency.

This milestone is not broad `tsldata` parsing or parameter alias inference. It
recognizes declared binary parameter names only in the existing tiny clean
source-document shape. Declared binary parameters must be distinct, but
accepted body forms may reference either declared parameter in either operand
position, including repeated use. Operand order and repetition are
source-authored semantics and must be preserved exactly.

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

Allow binary clean source declarations of the form:

```text
prim<v:=(v,v)> add(lhs, rhs):
  implementation scalar si32:
    body add(lhs, rhs)
```

and the already accepted binary TSIL forms with matching declared parameters:

```text
prim<v:=(v,v)> add(lhs, rhs):
  implementation scalar si32:
    tsil "emit_return(add(lhs, rhs));"
```

```text
prim<v:=(v,v)> add(lhs, rhs):
  implementation scalar si32:
    tsil "emit_return(lhs + rhs);"
```

The selected implementation must preserve the declared parameter names through
typed catalog body values, lowered function signatures, lowered parameter
references, and generated C++/Rust artifacts while preserving M107-M131
behavior.

Source-authored operand order must be preserved. For example,
`body sub(rhs, lhs)` under `prim<v:=(v,v)> sub(lhs, rhs):` should lower to a
return expression equivalent to `rhs - lhs`, not be rejected or normalized.
Likewise, repeated declared operands such as `body add(lhs, lhs)` are accepted
when the source says so.

## Required Executor Task

Run exactly one write-capable executor for M132. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve the M125 exact source-document shape: one primitive header followed
   by one or more implementation/body pairs. Each implementation block remains
   exactly an implementation header immediately followed by one body line.
3. Allow the binary primitive header shape `prim<v:=(v,v)> name(param0,
   param1):` to use any two distinct valid identifier parameter names.
4. Keep comparison and unary primitive header parameter shapes unchanged.
5. Require accepted binary body operands to reference declared binary
   parameters, while preserving source-authored operand order and repetition:
   - synthetic `body <operation>(operand0, operand1)`;
   - M126 function-call-shaped `tsil "emit_return(<operation>(operand0,
     operand1));"`;
   - M131 exact operator spellings for `+`, `-`, `&`, `|`, and `^` over
     `operand0` and `operand1`.
   Here each operand must be one of the two declared binary parameters, but the
   operands may be swapped or repeated if that is what the `.tsl` source says.
6. Preserve declared binary parameter names in typed `BinaryOperationBody`,
   `LoweredFunctionSignature`, `LoweredBinaryOperationExpression`, generated
   C++ function parameters, generated Rust function parameters, and generated
   return expressions.
7. Preserve accepted primitive header shapes for comparison/unary,
   selected-implementation behavior, body argument shape rules, operation
   descriptors, scalar type descriptors, operation/type compatibility rules,
   and the `clean_restart_bootstrap_core` semantic-origin contract.
8. Keep target requests explicit. Selection should pick only the
   implementation matching the target extension and type tag; do not add
   target discovery, generate-all behavior, extension fallback, type groups, or
   implementation ranking.
9. Prove selected non-`left/right` binary parameters drive lowering by testing
   generated C++/Rust artifacts for representative synthetic, M126
   function-call-shaped TSIL, and M131 operator-shaped TSIL bodies.
10. Prove swapped and repeated declared body operands preserve source-authored
    semantics in generated C++/Rust instead of being rejected or normalized.
11. Prove undeclared body operands produce structured diagnostics and are not
    normalized.
12. Prove duplicate binary parameter declarations produce a structured diagnostic
    before generating artifacts.
13. Preserve M131 exact binary operator TSIL behavior, M130 ordered comparison
    TSIL behavior, M129 inequality TSIL behavior, M128 equality TSIL behavior,
    M127 unary TSIL behavior, M126 binary function-call TSIL behavior, M125
    multi-implementation behavior, M124 multi-source behavior, and
    deterministic artifact ordering.
14. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Broad `tsldata` syntax/layout parsing, nested implementation maps, multiple
  primitive blocks in one document, attributes, tests, descriptions,
  `requires` clauses, type groups, extension fallback, dependency closure, or
  target discovery.
- Broad TSIL parsing, primitive calls, intrinsics, casts, variables,
  immediates, multiple statements, multiline TSIL bodies, helper evaluation,
  branch pruning, source repair, or TSIL compiler behavior.
- Adding binary operator TSIL forms beyond already accepted M131 spellings,
  including `*`, `/`, `%`, `<<`, or `>>`.
- Broadening comparison or unary parameter names in this slice.
- Supporting signatures such as `v:=(v,sImm)`, mask signatures, immediate
  parameters, or actual shift source bodies such as `data << shift`.
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

1. Architecture reviewer: verify M132 is a binary declared-parameter lowering
   slice, remains KISS-compatible, and does not add broad TSIL parsing,
   arbitrary target-language operator modeling, broad `tsldata` parsing,
   parameter aliasing, target discovery, primitive aliasing, or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, parameter aliasing, compatibility evaluation, implementation
   selection, lowering, or backend spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M132 as broad TSIL
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

If M132 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M132 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M132 is accepted. Select exactly one concrete M133 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M132 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

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
