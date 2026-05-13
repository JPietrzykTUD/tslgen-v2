# Redesign Evidence Auditor Skill

Use this skill when checking source evidence, frozen evidence, fixture
provenance, or golden-file boundaries.

## Workflow

1. Read the current milestone prompt and provenance expectations.
2. Inspect `tsldata/` and `frozen/` only as evidence.
3. Verify cited paths/ranges and fixture provenance where available.
4. Confirm tests do not require `frozen/` at runtime.
5. Do not modify files.

## Rules

- Never treat `frozen/` as architecture.
- Never import or execute `frozen/` code.
- Report missing or stale provenance as focused findings.
