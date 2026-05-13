# Redesign Orchestrator Skill

Use this skill when coordinating planner, executor, reviewer, validation,
evidence, documentation, or boundary subagents.

## Responsibilities

- Read current state first.
- Spawn only the subagents requested by the active run prompt.
- Keep write access single-owner per worktree.
- Consolidate subagent results.
- Apply only docs-only local corrections when explicitly allowed.
- Update `docs/agent/current-redesign-state.md` after accepted milestones or
  accepted planning.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Use `AGENTS.md`, `PLANS.md`, and the active run prompt.
- Treat `frozen/` as evidence only.
- Do not introduce runtime dependencies on `frozen/`.
- Preserve typed semantic boundaries.
- Report concise structured results.
