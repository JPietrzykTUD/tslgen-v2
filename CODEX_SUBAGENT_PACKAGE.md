# Codex Subagent Transition Package

This package moves the redesign workflow into Codex with subagents.

## Current State

Accepted through: Milestone 47.

Current action: post-M47 planning with internal subagent review.

Primary prompt:

```text
docs/agent/runs/m48-execution-review-loop-prompt.md
```

## Included workflow files

- `AGENTS.md`
- `PLANS.md`
- `.agents/skills/redesign-*/SKILL.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/subagents/*.md`
- `docs/agent/prompt-templates/*.md`
- `docs/agent/runs/post-m47-orchestrated-planning-plus-review-prompt.md`

## Use

Extract this archive into the repository root after reverting to the accepted M47
state. Then ask Codex to read `docs/agent/current-redesign-state.md` and run the
active prompt.

## Executor Review Loop

The package now includes `docs/agent/runs/m48-execution-review-loop-prompt.md`, which drives executor, reviewer/auditor subagents, focused revision, and next-prompt generation.
