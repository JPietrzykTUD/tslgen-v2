# Orchestrator Prompt Template

Read `docs/agent/current-redesign-state.md` first.

Use the active run prompt under `docs/agent/runs/`.

Spawn only the subagents named in that run prompt. Wait for all subagent
results, consolidate them, and produce the requested output.

Do not implement code unless the run prompt explicitly selects an executor task.
