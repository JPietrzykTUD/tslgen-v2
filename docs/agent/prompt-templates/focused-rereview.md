# Focused Re-Review Prompt Template

You are re-reviewing after a focused revision.

Review only the previously blocking issue and any files changed to fix it.
Return exactly one verdict.

Before finishing, ensure the next concrete run prompt under `docs/agent/runs/`
matches the verdict and update `docs/agent/current-redesign-state.md` to point
at it, unless the workflow intentionally stops.

Final report must include:

```text
Next run prompt created: <path>
Current state updated: yes/no
```
