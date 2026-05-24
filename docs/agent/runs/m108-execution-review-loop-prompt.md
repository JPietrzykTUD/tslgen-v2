# M108 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M107:

```text
Milestone 108: Minimal Clean Body Lowering Boundary Slice
```

Milestones 1 through 107 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107 created the
first tiny clean restart source-to-artifact slice under the fresh `tslgen/`
path. Do not start from old `tslgenold/` modules.

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

Introduce the first deliberately small lowering boundary in the clean restart
path:

```text
selected typed implementation -> backend-neutral lowered function -> C++ and Rust artifact values
```

## Required Executor Task

Run exactly one write-capable executor for M108. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused `tslgen/src/tslgen/lowering/` module for the exact M107
   `add(left, right)` / `scalar` / `si32` body only.
3. Lower the selected M107 implementation into a small backend-neutral typed
   function value with deterministic name, parameters, scalar type tag, and
   binary-add expression.
4. Make C++ and Rust emitters consume the lowered function value rather than
   reading the catalog body directly.
5. Preserve M107 generated C++ and Rust artifact content, logical paths,
   diagnostics, and deterministic ordering.
6. Add focused tests for the lowering value, pipeline determinism, backend
   consumption of lowered values, and at least one unsupported-lowering
   diagnostic boundary.
7. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- Broad TSIL/body semantics.
- Expression parsing beyond the accepted exact M107 binary-add body.
- Generation-time branch pruning.
- Dependency closure.
- Backend manifests.
- Type maps beyond `si32`.
- Hardware autodetection.
- CLI compatibility.
- Generated tests or generated-output parity.
- Artifact writing.
- Corpus-wide `tsldata/` parsing.
- Runtime imports from `frozen/` or `tslgenold/`.
- Porting, adapting, compatibility-wrapping, or migrating old `tslgenold/`
  lowering modules.
- Lowering IR taxonomies, worklists, inventories, registries, dispatchers,
  plugin systems, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify clean code stays under fresh `tslgen/`, old
   state remains evidence-only under `tslgenold/`, and no runtime imports
   depend on `tslgenold/` or `frozen/`.
2. Architecture reviewer: verify the lowering boundary follows the KISS restart
   charter and makes backend ownership simpler without introducing broad
   lowering machinery.
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

If M108 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M108 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 109 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
