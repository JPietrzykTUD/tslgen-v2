# M115 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M114:

```text
Milestone 115: Tiny Clean Binary Division Operation Lowering Slice
```

Milestones 1 through 114 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the first tiny clean scalar type lowering table. M111 added the
first tiny clean binary operation lowering table for `add`/`sub`/`mul`. M112
added the explicit return-statement body boundary. M113 added the explicit
function-signature boundary. M114 added the explicit lowering stage-output
boundary. Do not start from old `tslgenold/` modules.

This milestone intentionally keeps the next task focused on lowering while
taking a small functional step.

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

Add binary division to the existing tiny clean binary-operation lowering path:

```text
div(left, right) -> LoweredBinaryOperationExpression(operation="div")
```

## Required Executor Task

Run exactly one write-capable executor for M115. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add `div` to the existing lowering-owned binary operation descriptor table,
   preserving deterministic descriptor ordering.
3. Keep the descriptor backend-neutral. It must not contain C++ or Rust
   spelling, divide-by-zero policy, overflow policy, floating special-value
   policy, or source repair policy.
4. Update C++ and Rust backends to spell only the accepted `div` descriptor via
   backend-owned operator spelling tables.
5. Preserve M110 scalar descriptors, M112 body values, M113 signatures, M114
   lowering stage-output behavior, diagnostics, logical paths, artifact
   ordering, and existing `add`/`sub`/`mul` artifact bytes and digests.
6. Add focused tests for descriptor lookup/order, lowerer acceptance, backend
   spelling ownership, generator output for at least one `div` source, M114
   stage-output pass-through for `div`, and the updated unsupported-operation
   diagnostic boundary.
7. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- New `.tsl` source syntax, parser/catalog source-form changes,
  source-body repair, broad TSIL parsing, additional arities/parameter names,
  or additional body shapes.
- Modulo/remainder semantics, division-by-zero diagnostics, integer overflow
  policy, floating special-value policy, constant folding, algebraic
  simplification, or broad arithmetic semantics.
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
2. Architecture reviewer: verify `div` extends the existing typed binary
   operation descriptor path without putting backend spelling or runtime
   arithmetic policy into lowering and without adding broad operation/type
   framework behavior.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M115 as parser/source syntax, modulo,
   broad arithmetic semantics, CLI, writer, backend manifest, or old migration
   work.
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

If M115 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M115 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 116 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
