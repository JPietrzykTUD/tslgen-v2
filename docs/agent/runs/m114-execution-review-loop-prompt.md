# M114 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M113:

```text
Milestone 114: Tiny Clean Lowering Stage Output Boundary Slice
```

Milestones 1 through 113 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the first tiny clean scalar type lowering table. M111 added the
first tiny clean binary operation lowering table. M112 added the explicit
return-statement body boundary. M113 added the explicit function-signature
boundary. Do not start from old `tslgenold/` modules.

This milestone intentionally keeps the next task focused on lowering.

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

Make the lowering stage output explicit before backend emission:

```text
selected implementations -> ordered lowered function set plus diagnostics
```

## Required Executor Task

Run exactly one write-capable executor for M114. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a small lowering-owned stage-output value for the current tiny clean
   slice, such as `LoweredFunctionSet`, carrying an ordered tuple of accepted
   `LoweredFunction` values.
3. Add a small lowering-stage result for batch lowering of selected
   implementations, carrying the lowered function set plus accumulated
   lowering diagnostics.
4. Keep the existing single-selected lowering semantics intact. M114 may
   factor that path into the batch output, but must not change the accepted
   M110/M111/M112/M113 scalar descriptor, binary operation expression, return
   body, or function signature values.
5. Update the generator to lower the selected implementations for a target
   into the explicit lowering stage output before backend emission, then emit
   only from the output's ordered lowered functions.
6. Preserve current C++ and Rust artifact bytes, logical paths, metadata,
   ordering, diagnostics, and digests.
7. Add focused tests for ordered stage-output functions, diagnostic
   accumulation for unsupported selected implementations, generator use of the
   stage output, byte-stable existing `add` output, and at least one
   non-`add`/non-`si32` path still passing through the stage output.
8. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- New `.tsl` source syntax, parser/catalog source-form changes,
  source-body repair, broad TSIL parsing, `emit_return(...)` recognition,
  additional body shapes, or additional arities/parameter names.
- New scalar types, new operations, vector/SIMD shapes, hardware feature
  selection, branch pruning, generation-time helper evaluation, backend
  manifests, dependency closure, or old generator maps.
- Module/package planning, function overloading policy, include planning,
  artifact layout changes, artifact-plan values, renderer-ready IR, or backend
  emission inside lowering.
- Cross-target coordination, schedulers, readiness oracles, queues,
  registries, dispatchers, plugin systems, hidden backfeeds, fixpoint
  mechanisms, or a broad IR/stage framework.
- CLI integration, writer changes, generated test execution, CMake/Cargo
  scaffolding, runtime imports from `frozen/` or `tslgenold/`, or porting old
  lowering-stage modules.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify the lowering stage output is a small typed
   lowering-owned boundary, not a scheduler, artifact plan, backend emission
   layer, module/package planner, registry, dispatcher, or broad IR framework.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M114 as parser/source syntax, CLI, writer,
   artifact planning, backend emission, module/package planning, or broad
   stage framework work.
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

If M114 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M114 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 115 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
