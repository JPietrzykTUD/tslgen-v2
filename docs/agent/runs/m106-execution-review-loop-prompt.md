# M106 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 106 after M105
finalization.

Milestones 1 through 105 are accepted. M105 created the KISS generator restart
charter and selected the next structural restart milestone:

```text
Milestone 106: Old Implementation Quarantine Layout Reset Slice
```

Use the orchestrated executor-review loop in this prompt. M106 is a repository
layout milestone only. Do not implement parser, catalog, generator, backend,
renderer, writer, CLI, fixture, test, or generated-output product code.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`

## Goal

Separate old accepted/exploratory implementation state from the clean restart
package path:

```text
old state: tslgen/ -> tslgenold/
clean restart path: fresh tslgen/
```

After M106, `tslgenold/` is evidence-only, like `frozen/`, and must not become
a runtime dependency of the clean generator. The fresh top-level `tslgen/` path
is reserved for later restart product code, but M106 must not add that product
code.

## Required Executor Task

Run exactly one write-capable executor for M106. The executor should:

1. Inspect dirty worktree state before moving anything.
2. If unrelated edits exist, preserve them and do not revert them.
3. Move the current top-level `tslgen/` tree wholesale to `tslgenold/`.
4. Reserve or create a fresh top-level `tslgen/` path without adding product
   implementation. A minimal placeholder or README is acceptable only to make
   the clean path explicit.
5. Update only documentation, workflow state, and lightweight validation/import
   path references needed for the layout reset to be coherent.
6. Keep `frozen/` unchanged and evidence-only.
7. Run required validation.
8. Return a concise review packet with files changed, scope confirmation,
   follow-ups, and validation results.

If the move is unsafe because `tslgen/` contains overlapping dirty changes that
cannot be preserved clearly, stop before moving files. Record the blocker and
create the appropriate narrow follow-up prompt instead of starting product
implementation.

## Out Of Scope

- New clean generator product code under `tslgen/`.
- Porting, adapting, or compatibility-wrapping old `tslgen/` modules.
- Creating parser, catalog, selection, backend, renderer, artifact writer, CLI,
  fixture, test, or generated-output implementation.
- Updating generated artifacts.
- Treating `tslgenold/` or `frozen/` as runtime inputs for the clean generator.
- Broad repository cleanup, formatting churn, dependency upgrades, or unrelated
  validation-profile redesign.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Layout/boundary auditor: verify old state moved to `tslgenold/`, fresh
   `tslgen/` is clean/reserved, and no product code was added.
2. Architecture reviewer: verify the move follows the KISS restart charter and
   does not create legacy compatibility architecture.
3. Documentation auditor: verify roadmap, state, architecture, testing, and
   open-question docs remain coherent.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Review Verdict

Consolidate the executor and subagent results into one verdict:

```text
Accept
Accept With Follow-Ups
Needs Revision
Return To Planner
Reject
```

If the verdict is `Needs Revision`, run one focused layout/documentation
revision and then a focused re-review. If the verdict is `Return To Planner` or
`Reject`, stop and create the appropriate planning/rollback prompt.

## Required Validation

Run:

```bash
git diff --check
```

If documentation or lightweight path checks change, run the smallest additional
validation needed to prove the layout reset is coherent. Do not run broad
product-code tests unless M106 explicitly changes a maintained validation
surface that still exists after the move.

## Completion Rules

If M106 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M106 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

The next prompt should select the first clean restart product slice only after
the layout reset is accepted. Do not start that slice in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Layout result.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
