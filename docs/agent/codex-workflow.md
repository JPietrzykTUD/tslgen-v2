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

`docs/agent/runs/` is the authoritative location for the next executable
Codex prompt. No planning, execution, review, revision, focused re-review, or
documentation-correction task is complete until it has written the next
concrete prompt under `docs/agent/runs/` and updated
`docs/agent/current-redesign-state.md` to point at it, unless the task
intentionally ends the workflow and records an explicit stop condition.

The full prompt-generation protocol, transition matrix, required state fields,
and filename rules live in:

```text
docs/agent/next-run-prompt-protocol.md
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

Every transition in this flow must leave a concrete active run prompt in
`docs/agent/runs/`. If the transition is waiting on human acceptance, the next
prompt should be a finalization prompt. After acceptance, the finalization
prompt creates the concrete executor, reviewer, planner, revision, or stop
prompt required by the workflow state.

## Orchestrated executor-review loop

Implementation milestones may use a single Codex run prompt that drives the full
executor -> reviewer -> revision -> next-prompt loop.

The active run prompt must explicitly name each subagent and whether it is
read-only or write-capable. Codex will not infer subagent use from role files
alone.

A typical implementation loop is:

```text
executor subagent writes the milestone
-> validation auditor runs checks
-> reviewer/evidence/docs/boundary auditors review
-> orchestrator consolidates verdict
-> focused revision executor runs only if needed
-> focused re-review runs only on the fix
-> next-prompt generator creates the next concrete run prompt
```

Executor-loop prompts are allowed to update `docs/agent/current-redesign-state.md`
and create next prompts under `docs/agent/runs/`. They must not start the next
implementation milestone.

## Drift controls

- Do not combine implementation across pipeline ownership boundaries.
- Do not let renderers infer semantics.
- Do not let backend translation parse raw generation helpers.
- Do not use `frozen/` as runtime input.
- Do not use ad-hoc dictionary mappings as semantic architecture.
