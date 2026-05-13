# Redesign Documentation Auditor Skill

Use this skill for read-only redesign-doc consistency checks.

## Responsibilities

- Check roadmap, behavior, generation-time, testing, ADR, and open-question
  consistency.
- Identify stale wording and overclaims.
- Do not change docs unless explicitly assigned a revision task.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Use `AGENTS.md`, `PLANS.md`, and the active run prompt.
- Treat `frozen/` as evidence only.
- Do not introduce runtime dependencies on `frozen/`.
- Preserve typed semantic boundaries.
- Report concise structured results.
