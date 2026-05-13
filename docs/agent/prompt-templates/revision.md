# Revision Prompt Template

You are revising a milestone after `Needs Revision`.

Fix only the blocking issues. Do not start later milestones. Run focused
validation and produce a revision report.

Before finishing, create the next concrete run prompt under `docs/agent/runs/`
and update `docs/agent/current-redesign-state.md` to point at it, unless the
workflow intentionally stops. For a focused revision, the next prompt is
normally the focused re-review prompt.

Final report must include:

```text
Next run prompt created: <path>
Current state updated: yes/no
```
