# Redesign Orchestrator Skill

Use this skill when coordinating Codex subagents for the TSL generator redesign.

## Workflow

1. Read `docs/agent/current-redesign-state.md` first.
2. Identify the current milestone, verdict state, and next required action.
3. Spawn only the subagents needed for the task.
4. Keep write-capable work single-owner per branch/worktree.
5. Wait for all subagent summaries.
6. Consolidate results into one verdict, revision request, or next prompt.
7. Update `docs/agent/current-redesign-state.md` only after an accepted
   milestone, accepted focused correction, or accepted planning pass.

## Rules

- Do not let two write-capable subagents edit the same files concurrently.
- Reviewers and auditors are read-only unless explicitly assigned a focused
  revision task.
- Prefer parallel review/validation/evidence audits over parallel
  implementation.
- Preserve the clean-redesign boundary and one-milestone rule.
