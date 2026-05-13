# Redesign Next Prompt Generator Skill

Use this skill after the orchestrator has selected the next workflow action.

## Responsibilities

- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at that prompt.
- Preserve accepted-through milestone state and boundary rules.
- Do not implement product code.

## Shared rules

- Read `docs/agent/current-redesign-state.md` first.
- Follow `docs/agent/next-run-prompt-protocol.md`.
- Use stable descriptive prompt filenames.
- Run `git diff --check` for changed workflow files.
