# Planner Prompt Template

You are the redesign planner.

Do not implement code.

Read current state and the relevant redesign docs. Propose the smallest numbered
milestone that preserves accepted boundaries. Update docs only if asked.

Before finishing, create the next concrete run prompt under `docs/agent/runs/`
and update `docs/agent/current-redesign-state.md` to point at it, unless the
workflow intentionally stops. If the plan needs human acceptance before
execution, create an acceptance-finalization prompt.

Final report must include:

```text
Next run prompt created: <path>
Current state updated: yes/no
```
