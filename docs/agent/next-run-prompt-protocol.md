# Next Run Prompt Protocol

`docs/agent/runs/` is the authoritative location for executable Codex prompts.
Chat may explain a task, but the repository must carry the next concrete prompt
before the current task is considered complete.

## Completion Rule

No Codex task is complete until it has written the next concrete prompt under
`docs/agent/runs/` and updated `docs/agent/current-redesign-state.md` to point
at it, unless the task intentionally ends the workflow and records an explicit
stop condition.

When Codex completes a task, it must decide the next workflow action and create
the corresponding prompt file under `docs/agent/runs/`. If the next action
depends on human acceptance, Codex must create a finalization prompt that
converts human acceptance into the next concrete run prompt.

Example:

```text
post-M47 planning ready for human acceptance
-> docs/agent/runs/post-m47-acceptance-finalization-prompt.md
-> docs/agent/runs/m48-executor-prompt.md after acceptance
```

## Required State Fields

`docs/agent/current-redesign-state.md` must include or clearly encode:

- accepted-through milestone
- current action
- active run prompt path
- next expected verdict or action
- boundary rules
- validation expectations
- known follow-ups
- stop condition, if no next prompt should be generated

## Transition Matrix

| Current result | Required next prompt under `docs/agent/runs/` |
| --- | --- |
| Planning accepted | Executor prompt for the selected milestone. |
| Planning needs revision | Docs revision prompt plus focused planning re-review prompt. |
| Executor finished | Review prompt for the implemented milestone. |
| Review accepted | Next planner/executor prompt based on roadmap state, or acceptance finalization prompt if human approval is required. |
| Review accepted with follow-ups | Next prompt plus recorded follow-ups in state. |
| Review needs revision | Narrow revision prompt plus focused re-review prompt. |
| Return to planner | Planner prompt for the design issue. |
| Reject | Rollback/redesign prompt or explicit stop-state. |
| Docs-only correction accepted | Next prompt from the restored workflow state. |
| End of phase | Next planning prompt or explicit stop-state. |

## Prompt Filename Rules

Prompt filenames must be stable and descriptive. Prefer milestone-prefixed
names when a task is tied to one milestone:

- `m48-executor-prompt.md`
- `m48-review-prompt.md`
- `m48-narrow-revision-prompt.md`
- `m48-focused-rereview-prompt.md`
- `post-m48-planning-plus-review-prompt.md`
- `post-m48-acceptance-finalization-prompt.md`

The active prompt path must be referenced in
`docs/agent/current-redesign-state.md`.

## Prompt Content Rules

Each concrete run prompt must include:

- accepted state
- selected milestone or planning target
- read-first files
- scope
- out-of-scope items
- required validation
- expected output format
- stop rule such as "Do not start Milestone N+1"
- required next prompt creation, unless the workflow intentionally stops

Focused revision prompts must name the exact blocking issue and exact files in
scope. Review prompts must be read-only unless explicitly marked as a revision
task. Orchestrated planning prompts must include internal review subagents
before returning a final result.

## Ownership

The orchestrator owns state transitions and next-run prompt generation.
Subagents return findings; they do not decide the final active prompt unless
the orchestrator delegates that explicitly.
