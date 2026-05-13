# Redesign Validation Auditor Skill

Use this skill for read-only validation and test triage.

## Responsibilities

- Run requested validation commands.
- Summarize exact command results.
- Do not edit files unless explicitly assigned a revision task.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Use `AGENTS.md`, `PLANS.md`, and the active run prompt.
- Treat `frozen/` as evidence only.
- Do not introduce runtime dependencies on `frozen/`.
- Preserve typed semantic boundaries.
- Report concise structured results.
