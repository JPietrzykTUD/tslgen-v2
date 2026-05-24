# M110 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M109:

```text
Milestone 110: Tiny Clean Scalar Type Lowering Table Slice
```

Milestones 1 through 109 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. M109 added the first explicit artifact writer boundary. Do
not start from old `tslgenold/` modules.

This milestone intentionally follows the current user direction to focus the
next task on lowering.

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

Broaden the tiny clean lowering path from one hard-coded scalar type to a small
typed scalar-type lowering table:

```text
selected scalar add implementation -> lowered function with typed scalar type descriptor
```

## Required Executor Task

Run exactly one write-capable executor for M110. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a small lowering-owned scalar type descriptor model and typed descriptor
   table for the clean restart scalar types selected for this slice.
3. Keep the descriptor backend-neutral: tags, kind/family, bit width, and
   signedness/floating classification are lowering facts; C++ and Rust spelling
   remain backend-owned.
4. Replace the M108 lowerer's single `si32` type constant with lookup through
   this typed descriptor table.
5. Allow the exact existing `scalar` / `add(left, right)` clean source form to
   use the supported scalar type tags, while malformed or unsupported tags
   remain diagnostic boundaries.
6. Update C++ and Rust backends only as consumers of the lowered scalar type
   descriptor, with small backend-owned spelling maps, so supported scalar tags
   can be emitted deterministically.
7. Preserve the existing M107/M108 `si32` artifact bytes and logical paths.
8. Add focused tests for descriptor lookup, successful lowering for the
   supported tags, unsupported-type diagnostics, byte-stable `si32` output, and
   at least one non-`si32` end-to-end clean fixture or generated temporary
   source.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- CLI integration or legacy CLI compatibility.
- Writer changes beyond preserving M109 behavior.
- New primitive names, templates, arities, extensions, vector/SIMD shapes,
  hardware feature selection, branch pruning, generation-time helper
  evaluation, or broad TSIL parsing.
- Type metadata loaded from `tsldata`, backend manifests, or old generator
  maps.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old type/lowering
  modules.
- Dependency closure, registries, dispatchers, plugin systems, hidden
  backfeeds, fixpoint mechanisms, or a broad type-system framework.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify the new scalar type table is a small typed
   lowering-owned descriptor boundary, not a broad type-system framework, and
   that backend spelling policy remains backend-owned.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent and do not describe M110 as CLI work.
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

If M110 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M110 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 111 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
