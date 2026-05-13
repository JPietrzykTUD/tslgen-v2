# Executor Prompt Template

You are the redesign executor.

Implement exactly the selected milestone. Do not start later milestones.

Add tests and docs, run validation, and produce the PLANS.md review packet.

Before finishing, create the next concrete run prompt under `docs/agent/runs/`
and update `docs/agent/current-redesign-state.md` to point at it, unless the
workflow intentionally stops. For a completed executor milestone, the next
prompt is normally the milestone review prompt.

Final report must include:

```text
Next run prompt created: <path>
Current state updated: yes/no
```
