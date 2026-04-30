# Redesign Executor Skill

Use this skill when implementing one milestone from the TSL generator redesign.

## Workflow

1. Confirm the selected milestone and scope.
2. Read the relevant docs under `docs/redesign/`.
3. Inspect only the evidence needed for the selected behavior.
4. Implement the smallest usable slice.
5. Add tests required by the milestone.
6. Run targeted tests.
7. Update redesign docs for new evidence, decisions, or blockers.
8. Summarize changed files and validation.

## Rules

- Keep side effects at documented boundaries.
- Use typed domain/configuration objects.
- Return structured diagnostics from validation logic.
- Preserve deterministic ordering.
- Do not add runtime dependencies on `frozen/`.
- Do not silently preserve legacy quirks.
