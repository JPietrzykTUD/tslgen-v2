# Codex Redesign Workflow

This repository uses Codex with explicit planner, executor, reviewer, and audit
roles.

## State first

Every Codex task starts by reading:

```text
docs/agent/current-redesign-state.md
```

This file is the authoritative handoff. Chat history is not authoritative.

## Run prompts

Concrete task prompts live in:

```text
docs/agent/runs/
```

Reusable templates live in:

```text
docs/agent/prompt-templates/
```

Subagent role definitions live in:

```text
docs/agent/subagents/
```

## Subagent usage

Use subagents for bounded, parallel read-only work:

- planning comparison
- evidence audit
- documentation audit
- boundary audit
- validation audit
- review

Use only one write-capable executor per milestone/worktree.

## Milestone flow

```text
Plan -> Review plan -> Execute milestone -> Review milestone -> Revise if needed -> Accept -> Update current state
```

Or, with orchestrated planning:

```text
Planning subagents -> docs update -> review subagents -> local docs corrections -> human acceptance
```

## Drift controls

- Do not combine implementation across pipeline ownership boundaries.
- Do not let renderers infer semantics.
- Do not let backend translation parse raw generation helpers.
- Do not use `frozen/` as runtime input.
- Do not use ad-hoc dictionary mappings as semantic architecture.
