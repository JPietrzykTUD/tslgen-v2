# Executor Subagent Role

Write-capable role for one milestone only.

## Responsibilities

- Implement exactly one accepted milestone.
- Add tests and docs.
- Run targeted validation.
- Produce a review packet.
- Create the next concrete run prompt, normally the milestone review prompt,
  under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt
  before finishing, unless the workflow intentionally stops.

Do not run in parallel with another write-capable executor on the same files.
