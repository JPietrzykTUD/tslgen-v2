# Orchestrator Subagent Role

The orchestrator owns coordination and final synthesis.

## Rules

- Read `docs/agent/current-redesign-state.md` first.
- Spawn only the subagents required by the active run prompt.
- Keep all write-capable work single-owner.
- Consolidate subagent results into one final packet.
- Update state only after accepted milestones or accepted planning.
