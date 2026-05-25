# M135 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M134:

```text
Milestone 135: Tiny Clean Exact Indexed Binary Assignment Body Lowering Boundary Slice
```

Milestones 1 through 134 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M134 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, exact TSIL emit-return body
spellings, declared binary parameter preservation, remaining binary operator
TSIL spellings, and explicit scalar width descriptors.

M135 keeps the next task focused on lowering. It starts the array/body path by
recognizing exactly one indexed assignment body shape and carrying it as typed
source-owned semantics through parser, catalog, and lowering boundaries. This
is a boundary slice, not generated loop support. Backends may reject the new
lowered body with a structured unsupported diagnostic until a later milestone
defines array signatures, result storage, loop envelopes, and rendering.

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
- current clean parser/catalog/selection/lowering/backend implementation under
  `tslgen/src/tslgen/`
- current tiny-pipeline tests in `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognize this exact single-line body shape under the existing tiny binary
source shape:

```text
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "result[i] = left[i] + right[i];"
```

and promote it into typed body/lowering values that preserve:

- assignment target name `result`;
- index name `i`;
- source-authored declared operand names and order;
- existing binary operation descriptor semantics;
- scalar type descriptor from M134;
- source location for diagnostics.

The selected implementation should not be silently converted into an
`emit_return(...)` body, repaired, or rendered by rescanning the raw TSIL text.

## Required Executor Task

Run exactly one write-capable executor for M135. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add parser recognition for only the exact indexed binary assignment TSIL
   shape:

   ```text
       tsil "result[i] = operand0[i] <operator> operand1[i];"
   ```

   where `<operator>` is one of the already accepted binary operator spellings
   from M131/M133 and `operand0`/`operand1` are identifier tokens.
3. Promote accepted forms into a typed catalog body value before selection,
   lowering, or backend emission. Preserve source-authored operand order and
   repetition exactly as M132 does for return-expression binary bodies.
4. Validate that indexed assignment operands reference declared binary
   primitive parameters. Undeclared operands must produce structured catalog or
   lowering diagnostics and must not be aliased or normalized.
5. Preserve the exact assignment target/index boundary for this slice:
   accepted forms use `result[i]` as the target and use the same index token
   `i` on both RHS operands. Different targets, missing indexes, different
   index tokens, nested indexes, extra whitespace-sensitive source repairs, or
   arbitrary index expressions are unsupported.
6. Lower accepted indexed assignment bodies into typed backend-neutral lowering
   values that carry the operation descriptor, scalar type descriptor, target
   name, index name, and indexed parameter references. Keep this as a small
   body/lowering concept, not a new request/result/worklist family.
7. Make backend behavior explicit for the new lowered body. It is acceptable
   for C++ and Rust backends to return a structured unsupported-body diagnostic
   and no artifact in M135, because array/result signatures and loop rendering
   are out of scope. The diagnostic must come from typed lowered values, not
   raw source rescanning.
8. Add positive tests proving exact indexed assignment bodies reach typed
   catalog/lowering values for representative binary operations, including a
   swapped or repeated declared-operand case.
9. Add generator-path tests proving selected indexed assignment bodies produce
   deterministic structured unsupported-backend diagnostics and no artifacts
   until rendering support exists.
10. Add negative tests for nearby malformed or unsupported forms, including:
    undeclared operands, non-`result` assignment targets, mismatched RHS index
    tokens, missing indexes, nested or arithmetic index expressions, helper
    calls such as `details::arith_mul(left[i], right[i])`, primitive calls,
    casts, multiple statements, and attempts to combine assignment with
    `emit_return(...)`.
11. Preserve all M107-M134 accepted behavior, including exact emit-return
    bodies, declared binary parameter semantics, operation/type compatibility,
    backend-owned operator/type spellings, deterministic artifact ordering,
    and representative artifact bytes for existing return-expression cases.
12. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Full TSIL parsing, statement lists, multiline bodies, loop envelopes,
  variable declarations, temporary variables, scopes, result allocation,
  vector length, lane counts, array type descriptors, pointer/reference type
  spellings, mask values, or generated loop artifacts.
- Backend rendering for indexed assignment bodies, C++ array/span/pointer
  signature design, Rust slice signature design, mutable result parameters,
  result ownership, aliasing policy, bounds checks, loop unrolling, or compiler
  execution of generated indexed bodies.
- Helper substitution for `details::arith_mul`, `details::arith_rem`, or
  `details::arith_add`; primitive calls; `call<primitive=...>`; casts;
  `type<generation>(...)`; `type<backend>(...)`; direct intrinsics; pointer
  helpers such as `ptr_add`; ternaries; conditionals; or general expression
  parsing.
- Broad `tsldata` syntax/layout parsing, nested implementation maps, multiple
  primitive blocks in one document, attributes, tests, descriptions,
  `requires` clauses, type groups, extension fallback, dependency closure, or
  target discovery.
- Adding operation ids, scalar type tags, backend operator spellings,
  primitive aliases, scalar shift-count signatures, backend manifests,
  registries, dispatchers, callback maps, plugin systems, hidden backfeeds,
  fixpoint mechanisms, broad operation frameworks, or new lowering IR
  request/result/worklist families.
- Loading operation semantics, compatibility rules, type aliases, source-body
  rewrites, or backend spellings from `tsldata/`, backend manifests, YAML,
  `frozen`, `tslgenold`, plugins, or environment configuration at runtime.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M135 is a focused exact indexed-assignment
   body/lowering boundary slice and does not add broad TSIL parsing, loops,
   array signatures, backend rendering, helper substitution, corpus loading,
   target discovery, aliases, backend manifests, source repair, or IR
   ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for indexed body
   recognition, operation lookup, type lookup, compatibility evaluation,
   lowering, backend spellings, or diagnostics.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M135 as broad TSIL
   parsing, loop lowering, array signature/rendering support, helper
   substitution, backend manifest loading, CLI/writer work, vector/SIMD
   support, source repair, or old migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/model.py tslgen/src/tslgen/lowering/lowerer.py tslgen/src/tslgen/backends/cpp/backend.py tslgen/src/tslgen/backends/rust/backend.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

## Completion Rules

If M135 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M135 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M135 is accepted. Select exactly one concrete M136 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M135 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 136 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
