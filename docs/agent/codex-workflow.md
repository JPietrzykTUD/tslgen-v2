# Codex Redesign Workflow

This workflow moves milestone execution/review from chat into the repository so
Codex can inspect the active tree and use subagents without losing state.

## Persistent State

Always read first:

```text
docs/agent/current-redesign-state.md
```

Concrete run prompts live under:

```text
docs/agent/runs/
```

Reusable templates live under:

```text
docs/agent/prompt-templates/
```

## Orchestrator Rules

The main Codex thread is the orchestrator.

It may spawn subagents for bounded tasks, but it owns:

- final verdict consolidation
- final next-action decision
- updates to `docs/agent/current-redesign-state.md`
- ensuring only one write-capable executor edits a given worktree at a time

## Safe Parallelism

Safe to parallelize:

- architecture review
- validation audits
- evidence/provenance audits
- documentation consistency checks
- planning research

Unsafe to parallelize in the same worktree:

- two implementation agents editing the same files
- implementation and documentation revision touching the same docs
- reviewer and executor both modifying code

## Standard Milestone Loop

1. Planner defines or selects exactly one milestone.
2. Executor implements one milestone.
3. Orchestrator runs parallel review/audit subagents.
4. Orchestrator consolidates one verdict.
5. If `Needs Revision`, one focused executor fixes only the blocking issues.
6. A focused reviewer checks only the fix.
7. Orchestrator updates current state after acceptance.

## Drift Controls

- Use typed semantic rules/evaluators, not ad-hoc dictionary semantics.
- Keep renderers as formatting layers over translated values.
- Keep `frozen/` as evidence only.
- Keep generated output changes narrow and golden-tested.
- Stop and return to planner for design-level inconsistencies.
