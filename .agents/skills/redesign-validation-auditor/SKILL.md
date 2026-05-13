# Redesign Validation Auditor Skill

Use this skill when running tests and validation for a redesign milestone.

## Workflow

1. Read the current milestone prompt and `docs/agent/current-redesign-state.md`.
2. Run only the validation commands requested by the milestone/review prompt.
3. Capture exact commands, exit codes, and concise outputs.
4. Do not modify files.
5. Report failures with enough context for a focused revision.

## Rules

- Do not run legacy workflows unless the prompt explicitly requests them.
- Do not invoke compilers unless the milestone explicitly permits it.
- Do not install tools unless the task explicitly permits it.
- Keep summaries structured and concise.
