# Post-M47 Orchestrated Planning Prompt

You are the Codex orchestrator for the clean-room `tslgen` redesign.

Milestones 1 through 47 have been reviewed and accepted.

Your task is to plan the next numbered milestone after M47 using subagents.

Do not implement code.

## Current state

Read first:

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Objective

Decide and document the next numbered milestone after M47.

The expected candidate is a narrow generation-time signedness/type predicate
branch-pruning slice over typed M43 inputs, likely:

```text
if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { ... } else<generation> { ... }
```

Codex must verify the evidence and write the plan before any implementation.

## Subagents to spawn

Spawn these read-only subagents and wait for all results.

### 1. Planner subagent

Use:

```text
docs/agent/runs/post-m47-planner-subagent-prompt.md
```

Task: propose the next numbered milestone and required doc updates.

### 2. Evidence auditor subagent

Use:

```text
docs/agent/runs/post-m47-evidence-auditor-subagent-prompt.md
```

Task: verify evidence paths and line ranges for signedness/type predicate branch
forms and compare against possible alternative next slices.

### 3. Documentation auditor subagent

Use:

```text
docs/agent/runs/post-m47-docs-auditor-subagent-prompt.md
```

Task: check current roadmap/open questions/design docs for stale post-M47 wording
and identify exact sections to update.

### 4. Boundary auditor subagent

Use:

```text
docs/agent/runs/post-m47-boundary-auditor-subagent-prompt.md
```

Task: verify that the proposed next milestone preserves M43/M45/M46/M47
boundaries and does not combine lowering, backend translation, and rendering.

## Orchestrator output

After all subagents finish:

1. Summarize each subagent result.
2. Decide whether to add a formal Milestone 48.
3. If yes, update the relevant docs.
4. Keep changes documentation-only.
5. Run:

   ```bash
   git diff --check
   ```

6. Produce a planning review packet.

## Required docs if Milestone 48 is added

Update as needed:

- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`

Do not modify implementation code or tests.

## Guardrails

Do not select a broad TSIL parser milestone.

Do not combine signedness branch pruning with backend suffix/type translation.

Do not change generated output.

Do not reopen accepted M45/M46/M47 behavior unless evidence reveals a genuine
design inconsistency.

Do not import or execute `frozen/`.

## Final response format

1. Subagents spawned.
2. Candidate next slices considered.
3. Selected next milestone or explicit deferral.
4. Files changed.
5. Evidence used.
6. Boundary preservation summary.
7. Validation command and exact result.
8. Whether the post-M47 plan is ready for redesign review.
9. Recommended next executor milestone.
