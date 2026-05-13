# Redesign Boundary Auditor Skill

Use this skill to audit pipeline and semantic boundaries.

## Responsibilities

- Verify ownership of semantics across lowering, backend translation, and
  rendering.
- Detect renderer-side semantic inference.
- Detect raw helper parsing in backend translation.
- Detect broad scope creep across milestone boundaries.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Use `AGENTS.md`, `PLANS.md`, and the active run prompt.
- Treat `frozen/` as evidence only.
- Do not introduce runtime dependencies on `frozen/`.
- Preserve typed semantic boundaries.
- Report concise structured results.
