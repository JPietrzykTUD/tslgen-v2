# Execution Review Loop Prompt Template

You are the Codex orchestrator for one implementation milestone.

Read `docs/agent/current-redesign-state.md` first.

## Required phases

1. Spawn one write-capable executor for the selected milestone.
2. Wait for the executor review packet.
3. Spawn read-only reviewer/auditor subagents:
   - reviewer
   - validation auditor
   - evidence auditor, when provenance or corpus evidence matters
   - documentation auditor
   - boundary auditor
4. Consolidate exactly one verdict.
5. If `Needs Revision`, spawn one focused revision executor for the blocking
   issues and run a focused re-review. Repeat only for local fixes.
6. If `Accept` or `Accept With Follow-Ups`, update state and create the next run
   prompt.
7. If `Return To Planner` or `Reject`, stop and create the appropriate planner
   or rollback prompt.

## Final report must include

```text
Executor completed: yes/no
Review verdict: <verdict>
Revision loop count: <n>
Next run prompt created: <path>
Current state updated: yes/no
```
