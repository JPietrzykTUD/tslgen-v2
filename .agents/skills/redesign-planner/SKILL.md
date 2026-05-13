# Redesign Planner Skill

Use this skill for docs-only roadmap, architecture, behavior, open-question, or
ADR planning.

## Responsibilities

- Propose narrow numbered milestones.
- Keep changes documentation-only.
- Preserve accepted boundaries.
- Run `git diff --check`.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Use `AGENTS.md`, `PLANS.md`, and the active run prompt.
- Treat `frozen/` as evidence only.
- Do not introduce runtime dependencies on `frozen/`.
- Preserve typed semantic boundaries.
- Report concise structured results.
