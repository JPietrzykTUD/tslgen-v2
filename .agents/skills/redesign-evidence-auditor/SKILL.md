# Redesign Evidence Auditor Skill

Use this skill for source/evidence/provenance inspection.

## Responsibilities

- Inspect `tsldata` and `frozen` only as evidence.
- Verify line ranges, fixture provenance, and parity claims.
- Do not import or execute `frozen`.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Use `AGENTS.md`, `PLANS.md`, and the active run prompt.
- Treat `frozen/` as evidence only.
- Do not introduce runtime dependencies on `frozen/`.
- Preserve typed semantic boundaries.
- Report concise structured results.
