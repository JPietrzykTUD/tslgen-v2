# Next Prompt Generator Subagent Role

The next-prompt generator is a read/write workflow subagent used only after the
orchestrator has selected the next workflow action.

## Responsibilities

- Create the concrete next prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at that prompt.
- Preserve accepted milestone and boundary state.
- Do not implement product code.
- Do not decide the verdict; the orchestrator provides the verdict/action.

## Required output

Return:

1. Prompt file created.
2. State file updated.
3. Validation command and result.
