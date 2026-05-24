# M122 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M121:

```text
Milestone 122: Tiny Clean Scalar Comparison Operator Family Lowering Slice
```

Milestones 1 through 121 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the tiny clean scalar type lowering table. M111-M120 broadened the
clean lowering path for scalar binary and unary operations while keeping
backend spelling owned by backends. M121 added the first exact scalar
comparison result boundary for `equal(left, right)` over the documented
`m:=(v,v)` shape. Do not start from old `tslgenold/` modules.

This milestone intentionally keeps the next task focused on lowering while
broadening the accepted M121 same-shape scalar comparison path to a small
evidence-backed comparison operator family.

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

Add exact scalar comparison lowering for the documented compare source shape:

```text
prim<m:=(v,v)> nequal(left, right):
  implementation scalar si32:
    body nequal(left, right)
```

and the same exact source/catalog/lowering shape for:

- `less_than(left, right)`
- `greater_than(left, right)`
- `less_than_or_equal(left, right)`
- `greater_than_or_equal(left, right)`

## Required Executor Task

Run exactly one write-capable executor for M122. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add `nequal`, `less_than`, `greater_than`, `less_than_or_equal`, and
   `greater_than_or_equal` to the existing lowering-owned comparison operation
   descriptor table, preserving deterministic descriptor ordering after
   `equal`.
3. Reuse the accepted M121 exact compare source/catalog/lowering shape:
   signature `m:=(v,v)`, parameter tuple `("left", "right")`, one scalar
   implementation, typed comparison operation body, lowered comparison
   expression, explicit scalar-comparison result boundary, and M114
   stage-output boundary.
4. Allow the currently supported scalar descriptors (`si32`, `ui32`, `f32`,
   `f64`) as the left/right input scalar type for each accepted comparison
   operation.
5. Keep comparison descriptors backend-neutral. They must not contain C++ or
   Rust result-type spelling, backend operator spelling, runtime
   NaN/special-value policy, signed ordering policy, mask ABI policy,
   constant-folding policy, or source repair policy.
6. Update C++ and Rust backends to render accepted comparison lowered
   expressions through backend-owned result-type spellings and backend-owned
   operator spellings: `!=`, `<`, `>`, `<=`, and `>=`.
7. Preserve accepted `equal` behavior, binary and unary operation behavior,
   M110 scalar descriptors, M112 body values, M113 signatures, M114
   stage-output behavior, M116-M121 compatibility behavior, diagnostics,
   logical paths, artifact ordering, and existing artifact bytes and digests.
8. Add focused tests for comparison descriptor lookup/order, parser/catalog
   acceptance for the exact compare family form, the M121 malformed
   body-argument follow-up case such as `equal(value, right)`, lowerer
   acceptance for representative integer and floating scalar descriptors,
   backend result/operator spelling ownership, generator output for at least
   one new comparison source, M114 stage-output pass-through, and preservation
   of existing binary, unary, and `equal` behavior.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- New compare source syntax beyond the accepted M121 same-shape compare form,
  broad TSIL parsing, arbitrary arity support, compare-zero forms, range
  comparisons, special predicates, multiple statements, nested expressions,
  calls, variables, source repair, or generalized expression trees beyond the
  accepted binary, unary, and exact comparison shapes.
- Broad mask modeling, vector/SIMD compare results, mask lane types, boolean
  scalar inputs, mask composition, predicate paths, or backend mask ABI
  decisions.
- Floating NaN/special-value policy, signed ordering policy beyond emitting
  backend-owned operators for accepted lowered values, constant folding,
  algebraic simplification, or broad comparison semantics.
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
2. Architecture reviewer: verify the comparison family reuses the explicit M121
   comparison path, the scalar comparison result boundary remains minimal,
   backend result/operator spellings remain backend-owned, and lowering does
   not gain broad mask IR, vector/SIMD comparison semantics, runtime floating
   policy, signed-ordering policy, registries, dispatchers, or broad
   expression frameworks.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M122 as broad mask modeling, vector/SIMD
   comparison semantics, source repair, runtime floating policy, signed
   ordering policy, CLI, writer, backend manifest, or old migration work.
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

If M122 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M122 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 123 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
