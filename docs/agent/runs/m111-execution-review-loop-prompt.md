# M111 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M110:

```text
Milestone 111: Tiny Clean Binary Operation Lowering Table Slice
```

Milestones 1 through 110 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary.
M110 added the first tiny clean scalar type lowering table. Do not start from
old `tslgenold/` modules.

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

Broaden the tiny clean lowering path from one hard-coded binary operation to a
small typed binary-operation descriptor table:

```text
selected scalar binary implementation -> lowered function with scalar type and binary operation descriptors
```

## Required Executor Task

Run exactly one write-capable executor for M111. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a small lowering-owned binary operation descriptor model and typed
   descriptor table for the clean restart operation set selected for this
   slice: `add`, `sub`, and `mul`.
3. Keep operation descriptors backend-neutral: operation id, arity/category,
   expected source body operation name, and stable semantic name are lowering
   facts; C++ and Rust operator spellings remain backend-owned.
4. Replace the lowerer's one-off `add` primitive/body check with lookup
   through this typed operation descriptor table, while preserving exact binary
   `left, right` parameter handling.
5. Allow the exact tiny scalar source form to use the supported operation names
   as primitive name and body operation, for example `sub(left, right)` in a
   `sub` primitive. Nearby shapes remain diagnostic boundaries.
6. Update C++ and Rust backends only as consumers of the lowered operation
   descriptor, with small backend-owned operator spelling maps.
7. Preserve the existing `add`/`si32` artifact bytes, logical paths, and
   digests.
8. Add focused tests for operation descriptor lookup, successful lowering for
   supported operations, at least one non-`add` end-to-end clean source,
   unsupported operation diagnostics, operation/body mismatch diagnostics,
   backend-owned operator spelling, and byte-stable existing `add` output.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- CLI integration or legacy CLI compatibility.
- Writer changes beyond preserving M109 behavior.
- New arities, parameter names, templates beyond the exact binary scalar form,
  extensions beyond `scalar`, vector/SIMD shapes, hardware feature selection,
  branch pruning, generation-time helper evaluation, broad TSIL parsing, or
  division/modulo semantics.
- Type metadata or operation metadata loaded from `tsldata`, backend manifests,
  or old generator maps.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old operation,
  parser, backend, or lowering modules.
- Dependency closure, registries, dispatchers, plugin systems, hidden
  backfeeds, fixpoint mechanisms, or a broad expression/type framework.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify the operation table is a small typed
   lowering-owned descriptor boundary, not a broad expression framework, and
   that backend operator spelling remains backend-owned.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M111 as CLI, writer, broad parser, or broad
   expression work.
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

If M111 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M111 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 112 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
