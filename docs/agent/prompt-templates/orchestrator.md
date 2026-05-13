# Orchestrator Prompt Template

Read `docs/agent/current-redesign-state.md` first.

Use the active run prompt under `docs/agent/runs/`.

Spawn only the subagents named in that run prompt. Wait for all subagent
results, consolidate them, and produce the requested output.

Do not implement code unless the run prompt explicitly selects an executor task.

The orchestrator owns state transitions and next-run prompt generation. Before
finishing, create the next concrete run prompt under `docs/agent/runs/` and
update `docs/agent/current-redesign-state.md` to point at it, unless the
workflow intentionally stops.

Final report must include:

```text
Next run prompt created: <path>
Current state updated: yes/no
```
