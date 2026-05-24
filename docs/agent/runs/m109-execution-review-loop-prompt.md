# M109 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M108:

```text
Milestone 109: Tiny Clean Artifact Writer Boundary Slice
```

Milestones 1 through 108 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean source-to-artifact slice. M108 inserted the first tiny clean
lowering boundary. Do not start from old `tslgenold/` modules.

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

## Goal

Add the first explicit filesystem-write boundary for the clean restart path:

```text
artifact values -> deterministic checked write report
```

## Required Executor Task

Run exactly one write-capable executor for M109. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused clean artifact writer under `tslgen/src/tslgen/io/`.
3. Write only existing in-memory `ArtifactSet` values to an explicit output
   root supplied by the caller.
4. Keep path handling deterministic and safe: reject absolute logical paths,
   parent-directory escapes, duplicate logical paths, and directory/file
   collisions with structured diagnostics.
5. Return a typed write report with stable written-path and digest data.
6. Add tests that generate the M108 artifact set, write it to a temporary
   output root, assert file contents/digests/report ordering, and cover at
   least one unsafe-path diagnostic boundary.
7. Keep the existing pure source-to-artifact API usable without writing files.
8. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- CLI integration.
- Generated test execution.
- CMake/Cargo/project scaffolding.
- Broad output tree parity.
- Cleaning output roots.
- Watch/incremental behavior.
- Formatting or compiling generated C++/Rust.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old writer modules.
- New lowering semantics.
- Backend manifests.
- Dependency closure.
- Registries, dispatchers, plugin systems, hidden backfeeds, or fixpoint
  mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify the writer is the only filesystem-write owner
   for generated artifact values and does not hide writes in pure stages.
3. Documentation auditor: verify behavior, roadmap, and workflow state remain
   coherent.
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

If M109 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M109 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 110 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
