# Redesign Reviewer Skill

Use this skill when reviewing a redesign implementation change.

## Workflow

1. Read `docs/agent/review-checklist.md`.
2. Identify the milestone or slice being reviewed.
3. Check architecture boundaries before style.
4. Look for accidental legacy leakage.
5. Verify tests cover behavior, diagnostics, determinism, and side effects.
6. Confirm docs were updated when requirements or decisions changed.
7. Report findings first, ordered by severity, with file and line references.

## Rules

- Review behavior and architecture, not legacy similarity.
- Do not request a port of old modules.
- Prefer concrete, testable findings.
- Call out unresolved questions that should block implementation.
