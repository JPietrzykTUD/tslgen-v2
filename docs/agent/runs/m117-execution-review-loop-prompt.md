# M117 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M116:

```text
Milestone 117: Tiny Clean Integer Bitwise Binary Operations Type-Gated Lowering Slice
```

Milestones 1 through 116 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the tiny clean scalar type lowering table. M111 added the tiny clean
binary operation lowering table for `add`/`sub`/`mul`. M112 added the explicit
return-statement body boundary. M113 added the explicit function-signature
boundary. M114 added the explicit lowering stage-output boundary. M115 added
binary division through the existing backend-neutral descriptor path. M116
added integer-only `mod` through a small lowering-owned operation/type
compatibility boundary. Do not start from old `tslgenold/` modules.

This milestone intentionally keeps the next task focused on lowering while
broadening the tiny operation surface by one coherent integer-only family.

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

Add integer-only bitwise binary operations to the existing tiny clean
binary-operation lowering path:

```text
bit_and(left, right) / bit_or(left, right) / bit_xor(left, right)
over integer scalar descriptors
-> LoweredBinaryOperationExpression(operation="bit_*")
```

## Required Executor Task

Run exactly one write-capable executor for M117. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add `bit_and`, `bit_or`, and `bit_xor` to the existing lowering-owned
   binary operation descriptor table, preserving deterministic descriptor order
   after `mod`.
3. Reuse and minimally extend the M116 operation/type compatibility boundary
   so the bitwise operations lower only for currently supported integer scalar
   descriptors.
4. Reject floating scalar descriptors for the bitwise operations with the
   accepted M116 `TSL-LOWER-UNSUPPORTED-OPERATION-TYPE` diagnostic shape.
5. Keep descriptors backend-neutral. They must not contain C++ or Rust
   spelling, logical-boolean policy, mask policy, signedness runtime policy,
   overflow policy, or source repair policy.
6. Update C++ and Rust backends to spell only the accepted bitwise descriptors
   via backend-owned operator spelling tables.
7. Preserve accepted `add`/`sub`/`mul`/`div`/`mod` behavior, M110 scalar
   descriptors, M112 body values, M113 signatures, M114 lowering stage-output
   behavior, M116 compatibility behavior, diagnostics, logical paths, artifact
   ordering, and existing artifact bytes and digests.
8. Add focused tests for descriptor lookup/order, integer lowerer acceptance,
   floating-type rejection with the M116 diagnostic, backend spelling
   ownership, generator output for at least one integer bitwise source, M114
   stage-output pass-through, and the unsupported-operation diagnostic
   boundary.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- New `.tsl` source syntax, parser/catalog source-form changes,
  source-body repair, broad TSIL parsing, additional arities/parameter names,
  or additional body shapes.
- Logical boolean semantics, boolean scalar types, masks, shifts, rotates,
  bit-width promotion, signedness runtime policy, constant folding, algebraic
  simplification, or broad bitwise/arithmetic semantics.
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
  mechanisms, or a broad operation/type framework.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify bitwise operations extend the existing typed
   binary operation descriptor path, the M116 type-gating remains a tiny
   lowering-owned compatibility boundary, and lowering does not gain backend
   spelling, runtime bitwise policy, registries, dispatchers, or broad
   frameworks.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M117 as parser/source syntax, logical boolean
   semantics, shifts/rotates, broad arithmetic semantics, CLI, writer, backend
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

If M117 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M117 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 118 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
