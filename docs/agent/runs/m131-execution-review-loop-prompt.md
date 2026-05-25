# M131 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M130:

```text
Milestone 131: Tiny Clean Exact TSIL Emit-Return Binary Operator Body Lowering Slice
```

Milestones 1 through 130 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M130 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
deterministic source-set generation, and exact binary/unary/comparison TSIL
emit-return body spellings.

M131 keeps the next task focused on lowering and adds the next
corpus-observed exact scalar binary TSIL emit-return body spellings. Selected
binary scalar implementations may use exact TSIL-like body lines for `+`,
`-`, `&`, `|`, and `^` instead of only the synthetic clean-restart
`body ...` fixture line or the accepted M126 function-call-shaped binary TSIL
form. Corpus evidence exists at
`tsldata/primitives/arithmetic/fundamental.tsl:31`,
`tsldata/primitives/arithmetic/fundamental.tsl:328`,
`tsldata/primitives/bitwise/bit_ops.tsl:31`,
`tsldata/primitives/bitwise/bit_ops.tsl:312`, and
`tsldata/primitives/bitwise/bit_ops.tsl:462`; this evidence must not become a
runtime semantic dependency.

This milestone is not target-language operator modeling. It recognizes only
exact documented source spellings that map to existing typed TSL binary
operation ids.

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

Allow these exact selected binary scalar implementation body lines:

```text
    tsil "emit_return(left + right);"
    tsil "emit_return(left - right);"
    tsil "emit_return(left & right);"
    tsil "emit_return(left | right);"
    tsil "emit_return(left ^ right);"
```

to produce the same typed backend-neutral binary operation bodies as the
accepted fixture forms:

```text
    body add(left, right)
    body sub(left, right)
    body bit_and(left, right)
    body bit_or(left, right)
    body bit_xor(left, right)
```

The selected implementation must lower through the existing typed
selected-implementation path and preserve M107-M130 behavior.

## Required Executor Task

Run exactly one write-capable executor for M131. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve the M125 exact source-document shape: one primitive header followed
   by one or more implementation/body pairs. Each implementation block remains
   exactly an implementation header immediately followed by one body line.
3. Add exact recognition for binary scalar TSIL emit-return body lines under
   the accepted binary primitive header form
   `prim<v:=(v,v)> name(left, right):`. The exact source spellings and typed
   operation ids are:
   - `tsil "emit_return(left + right);"` -> `add`
   - `tsil "emit_return(left - right);"` -> `sub`
   - `tsil "emit_return(left & right);"` -> `bit_and`
   - `tsil "emit_return(left | right);"` -> `bit_or`
   - `tsil "emit_return(left ^ right);"` -> `bit_xor`
4. Keep the accepted synthetic binary `body <operation>(left, right)` line
   working byte-for-byte for existing tests and artifacts.
5. Keep the accepted M126 binary function-call-shaped TSIL emit-return body
   form working byte-for-byte for existing tests and artifacts.
6. Keep the accepted M127 unary TSIL, M128 equality TSIL, M129 inequality TSIL,
   and M130 ordered-comparison TSIL emit-return body forms working
   byte-for-byte for existing tests and artifacts.
7. Promote exact binary operator TSIL emit-return bodies into typed operation
   body data before lowering/backend emission. Downstream lowering and
   emitters must not rescan raw TSIL text or render from raw TSIL text.
8. Preserve accepted primitive header shapes, selected-implementation
   behavior, body argument shape rules, operation descriptors, scalar type
   descriptors, operation/type compatibility rules, and the
   `clean_restart_bootstrap_core` semantic-origin contract.
9. Keep target requests explicit. Selection should pick only the implementation
   matching the target extension and type tag; do not add target discovery,
   generate-all behavior, extension fallback, type groups, or implementation
   ranking.
10. Prove that each selected exact binary operator TSIL emit-return body drives
    lowering by testing generated C++/Rust artifacts for `add`, `sub`,
    `bit_and`, `bit_or`, and `bit_xor`.
11. Prove that unselected exact binary operator TSIL emit-return bodies are not
    lowered by adding focused multi-implementation coverage where an unselected
    exact binary operator TSIL body would be an operation/primitive mismatch if
    selected, while the selected implementation still generates successfully.
12. Add negative tests showing selected mismatched binary operator TSIL
    emit-return bodies, such as using `left + right` for a non-`add` binary
    primitive, and malformed nearby binary operator TSIL forms produce
    structured diagnostics, not source repair, renderer inference, or silent
    fallback.
13. Preserve M130 ordered comparison TSIL behavior, M129 inequality TSIL
    behavior, M128 equality TSIL behavior, M127 unary TSIL behavior, M126
    binary function-call TSIL behavior, M125 multi-implementation behavior,
    M124 multi-source behavior, and deterministic artifact ordering.
14. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Parsing broad TSIL strings, nested calls, primitive calls, intrinsics, casts,
  variables, immediates, multiple statements, multiline TSIL bodies, helper
  evaluation, branch pruning, source repair, or TSIL compiler behavior.
- Adding binary operator TSIL forms beyond the five exact spellings listed in
  this milestone, including `*`, `/`, `%`, `<<`, or `>>`.
- Adding new unary or comparison TSIL forms in this slice.
- Modeling arbitrary C, C++, or Rust operators, precedence, associativity,
  casts, temporaries, mixed expressions, or target-language passthrough.
- Adding primitive aliases such as current corpus `binary_and` names for the
  accepted clean operation id `bit_and`.
- Parsing multiple primitive blocks inside one `.tsl` document, loading broad
  `tsldata/`, parsing broad TSL syntax, adding new operation ids, scalar
  types, templates, type groups, extension fallback, dependency closure,
  backend manifests, target discovery, generated-test execution, CLI behavior,
  writer behavior, or output tree parity.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M131 is an exact selected-body lowering slice,
   remains KISS-compatible, and does not add broad TSIL parsing, arbitrary
   target-language operator modeling, corpus loading, target discovery,
   primitive aliasing, or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, implementation selection, lowering, or
   backend spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M131 as broad TSIL
   parsing, arbitrary target-language operator modeling, corpus ingestion,
   backend manifest loading, source repair, target discovery, CLI, writer,
   primitive aliasing, or old migration work.
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

If M131 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M131 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M131 is accepted. Select exactly one concrete M132 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M131 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

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
