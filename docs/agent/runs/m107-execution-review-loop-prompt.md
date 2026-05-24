# M107 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M106:

```text
Milestone 107: Tiny Clean Restart Source-To-Artifact Vertical Slice
```

Milestones 1 through 106 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state and reserved a fresh
top-level `tslgen/` path for clean implementation. Do not start from old
`tslgenold/` modules.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`

## Goal

Prove the clean restart path on one tiny fixture:

```text
.tsl source document -> parse result -> minimal catalog -> selected implementation -> deterministic C++ and Rust artifact values
```

## Required Executor Task

Run exactly one write-capable executor for M107. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add only the minimal clean package/test structure under fresh `tslgen/`.
3. Load one explicit tiny `.tsl` source fixture through a source-loading
   boundary.
4. Parse only the documented source form needed by that fixture.
5. Build and validate a minimal typed catalog with one primitive and one
   implementation.
6. Select one implementation for explicit C++ and Rust target requests.
7. Emit one deterministic C++ artifact value and one deterministic Rust
   artifact value through typed backend emitters.
8. Exercise an artifact writer only as the explicit filesystem-write boundary
   if the slice writes files.
9. Add focused tests for the supported path, deterministic repeat runs, and at
   least one invalid-fixture diagnostic boundary.
10. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Broad `tsldata/` corpus parsing.
- Broad TSIL/body semantics.
- Dependency closure.
- Backend manifests.
- Hardware autodetection.
- CLI compatibility.
- Generated tests or generated-output parity.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old `tslgenold/`
  modules.
- New lowering IR taxonomies, worklists, registries, dispatchers, hidden
  backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code lives under fresh `tslgen/`, old
   state remains under `tslgenold/`, and no runtime imports depend on
   `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify the slice follows the KISS restart charter and
   keeps ownership simple.
3. Documentation auditor: verify behavior, decisions, roadmap, and workflow
   state remain coherent.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
```

Run the targeted clean-package tests added by M107 and the smallest supporting
compile/import checks needed for the new package surface. Do not run the old
`tslgenold` validation profile as proof of the clean product slice.

## Completion Rules

If M107 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M107 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 108 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
