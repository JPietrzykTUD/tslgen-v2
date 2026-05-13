# Orchestrator Subagent Role

The orchestrator owns coordination and final synthesis.

The orchestrator owns state transitions and next-run prompt generation.
Subagents return findings; they do not decide the final active prompt unless
the orchestrator delegates that explicitly.

## Rules

- Read `docs/agent/current-redesign-state.md` first.
- Spawn only the subagents required by the active run prompt.
- Keep all write-capable work single-owner.
- Consolidate subagent results into one final packet.
- Update state only after accepted milestones, accepted planning, accepted
  documentation corrections, or explicit workflow transitions.
- Before finishing, create the next concrete prompt under `docs/agent/runs/`
  and update `docs/agent/current-redesign-state.md` to point at it, unless the
  workflow intentionally stops.
