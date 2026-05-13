# Codex Subagent Transition Package

This package moves the redesign workflow into Codex with subagents.

## Current State

Accepted through: Milestone 47.

Current action: post-M47 planning for the next numbered milestone.

Primary prompt:

```text
docs/agent/runs/post-m47-orchestrated-planning-prompt.md
```

## Subagent Model

The orchestrator may spawn read-only subagents for:

- planning
- evidence audit
- documentation audit
- boundary audit
- validation audit, when implementation exists

Only one write-capable executor should edit a worktree at a time.

## Current Expected Next Slice

The likely next slice is signedness/type predicate branch pruning over typed M43
inputs. Codex must verify evidence and add the formal next milestone before any
implementation starts.
