# M121 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M120:

```text
Milestone 121: Tiny Clean Scalar Compare Result Lowering Shape Slice
```

Milestones 1 through 120 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the tiny clean scalar type lowering table. M111-M120 broadened the
clean lowering path for scalar binary and unary operations while keeping
backend spelling owned by backends. Do not start from old `tslgenold/`
modules.

This milestone intentionally keeps the next task focused on lowering while
adding the first exact scalar comparison result boundary.

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

Add exact scalar equality comparison lowering for the documented compare source
shape:

```text
prim<m:=(v,v)> equal(left, right):
  implementation scalar si32:
    body equal(left, right)
```

## Required Executor Task

Run exactly one write-capable executor for M121. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add parser/catalog support only for the exact compare source shape:
   signature `m:=(v,v)`, parameter tuple `("left", "right")`, one scalar
   implementation, and body argument tuple `("left", "right")`.
3. Model the accepted compare source body as typed catalog data rather than
   forcing it through arithmetic/bitwise binary operation semantics.
4. Add a small backend-neutral comparison operation descriptor for `equal` and
   a lowered comparison expression paired with the existing lowered
   return-statement/function structure.
5. Introduce the smallest explicit lowered result-type boundary needed for a
   scalar comparison result. The accepted backend result spelling is `bool` in
   C++ and Rust, owned by the backend layer, not by lowering descriptors.
6. Allow currently supported scalar descriptors (`si32`, `ui32`, `f32`, `f64`)
   as the left/right input scalar type for `equal(left, right)`.
7. Update C++ and Rust backends to render accepted `equal` lowered expressions
   through backend-owned result-type and operator spelling rules.
8. Preserve accepted binary and unary operation behavior, M110 scalar
   descriptors, M112 body values, M113 signatures, M114 stage-output behavior,
   M116-M120 compatibility behavior, diagnostics, logical paths, artifact
   ordering, and existing artifact bytes and digests.
9. Add focused tests for parsing/cataloging the exact compare form, rejecting
   nearby malformed compare forms, descriptor lookup/order, lowerer acceptance
   for representative integer and floating scalar descriptors, backend result
   and operator spelling ownership, generator output for one `equal` source,
   M114 stage-output pass-through, and preservation of existing binary/unary
   behavior.
10. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Compare operations beyond `equal`, broad mask modeling, vector/SIMD compare
  results, mask lane types, boolean scalar inputs, mask composition, predicate
  paths, or backend mask ABI decisions.
- New source syntax beyond the exact compare form, broad TSIL parsing,
  arbitrary arity support, multiple statements, nested expressions, calls,
  variables, source repair, or generalized expression trees beyond the
  accepted binary, unary, and exact comparison shapes.
- Floating NaN/special-value policy, signed ordering policy, runtime comparison
  semantics beyond emitting the backend-owned equality operator for accepted
  lowered values, constant folding, algebraic simplification, or broad
  comparison semantics.
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
2. Architecture reviewer: verify `equal` uses an explicit comparison path, the
   scalar comparison result boundary remains minimal, backend result/operator
   spellings remain backend-owned, and lowering does not gain broad mask IR,
   vector/SIMD comparison semantics, runtime floating policy, registries,
   dispatchers, or broad expression frameworks.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M121 as broad mask modeling, broad comparison
   families, source repair, runtime floating policy, CLI, writer, backend
   manifest, or old migration work.
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

If M121 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M121 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 122 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
