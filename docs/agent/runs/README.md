# Codex Run Prompts

Concrete prompts for active or historical Codex tasks live here.

This directory is the authoritative location for the next executable Codex
prompt. The active run prompt is recorded in
`docs/agent/current-redesign-state.md`.

Each run prompt should specify:

- accepted state
- selected task
- subagents to spawn, if any
- files to read
- scope and out-of-scope boundaries
- validation commands
- expected output format
- stop rule, such as "Do not start Milestone N+1"
- the next prompt this task must create before completion, unless it records an
  explicit workflow stop condition

Stable, descriptive filenames are preferred, for example:

- `m48-executor-prompt.md`
- `m48-review-prompt.md`
- `m48-narrow-revision-prompt.md`
- `m48-focused-rereview-prompt.md`
- `post-m48-planning-plus-review-prompt.md`
- `post-m48-acceptance-finalization-prompt.md`

See `docs/agent/next-run-prompt-protocol.md` for the required transition
matrix and prompt-generation rules.


## Execution-review loop prompts

Implementation milestones may use a combined execution-review loop prompt named
like:

```text
m48-execution-review-loop-prompt.md
```

Such prompts must explicitly spawn one write-capable executor, read-only review
and audit subagents, a focused revision executor only if needed, and a next
prompt generator after acceptance.
