# M119 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M118:

```text
Milestone 119: Tiny Clean Unary Arithmetic Negation Type-Gated Lowering Slice
```

Milestones 1 through 118 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the tiny clean scalar type lowering table. M111 added the tiny clean
binary operation lowering table. M112 added the explicit return-statement body
boundary. M113 added the explicit function-signature boundary. M114 added the
explicit lowering stage-output boundary. M115-M117 broadened binary operation
lowering. M118 added the exact unary `bit_not(value)` source/catalog/lowering
shape. Do not start from old `tslgenold/` modules.

This milestone intentionally keeps the next task focused on lowering while
reusing the exact unary path and adding one small signedness/family
compatibility distinction.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- current clean implementation under `tslgen/src/tslgen/`

## Goal

Add unary arithmetic negation for the accepted one-parameter clean source
shape:

```text
prim<v:=(v)> neg(value):
  implementation scalar si32:
    body neg(value)
```

## Required Executor Task

Run exactly one write-capable executor for M119. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add `neg` to the existing lowering-owned unary operation descriptor table,
   preserving deterministic descriptor ordering after `bit_not`.
3. Reuse the M118 exact unary source/catalog/lowering shape: signature
   `v:=(v)`, parameter tuple `("value",)`, typed unary operation body, and
   lowered unary expression.
4. Extend the lowering-owned unary operation/type compatibility boundary so
   `neg` accepts currently supported signed integer and floating scalar
   descriptors (`si32`, `f32`, `f64`) and rejects unsigned scalar descriptors
   such as `ui32` with `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE`.
5. Keep unary descriptors backend-neutral. They must not contain C++ or Rust
   spelling, overflow/wrapping policy, unsigned-negation policy, floating
   special-value policy, constant-folding policy, or source repair policy.
6. Update C++ and Rust backends to render accepted `neg` lowered expressions
   through backend-owned unary spellings.
7. Preserve accepted binary operations, M118 `bit_not` behavior, M110 scalar
   descriptors, M112 body values, M113 signatures, M114 stage-output behavior,
   M116/M117/M118 compatibility behavior, diagnostics, logical paths, artifact
   ordering, and existing artifact bytes and digests.
8. Add focused tests for unary descriptor lookup/order, signed/floating lowerer
   acceptance, unsigned rejection with the existing operation/type diagnostic,
   backend spelling ownership, generator output for at least one `neg` source,
   M114 stage-output pass-through, and preservation of existing binary and
   `bit_not` behavior.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- New source syntax beyond the accepted M118 one-parameter unary form, broad
  TSIL parsing, arbitrary arity support, multiple statements, nested
  expressions, calls, variables, source repair, or generalized expression
  trees beyond the accepted binary and exact unary shapes.
- Runtime overflow/wrapping policy, unsigned negation semantics, floating
  special-value policy, constant folding, algebraic simplification, or broad
  arithmetic semantics.
- New scalar types, vector/SIMD shapes, hardware feature selection, branch
  pruning, generation-time helper evaluation, backend manifests, dependency
  closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  operation/lowering modules.
- Registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad expression/type framework.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify `neg` reuses the M118 unary path, the
   signed/floating type gate stays lowering-owned, backend spellings remain
   backend-owned, and lowering does not gain runtime negation policy,
   registries, dispatchers, broad arithmetic semantics, or broad expression
   frameworks.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M119 as new source syntax beyond the accepted
   unary form, source repair, runtime overflow/wrapping policy, broad
   arithmetic semantics, CLI, writer, backend manifest, or old migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
```

Run the smallest compile/import checks needed for the revised clean package
surface. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

## Completion Rules

If M119 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M119 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 120 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
