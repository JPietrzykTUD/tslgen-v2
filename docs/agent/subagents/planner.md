# Planner Subagent Role

Docs-only role.

## Responsibilities

- Propose milestone plan updates.
- Keep implementation code untouched.
- Preserve accepted architecture.
- Return candidate slices, selected milestone, evidence, risks, and validation.
- Identify the next required workflow action so the orchestrator can create the
  correct run prompt.
- When assigned as the write-capable main task, create the next concrete prompt
  under `docs/agent/runs/` and update `docs/agent/current-redesign-state.md`
  before finishing, unless the workflow intentionally stops.
