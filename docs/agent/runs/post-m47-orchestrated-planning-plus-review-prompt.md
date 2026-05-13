# Post-M47 Orchestrated Planning + Review Prompt

You are the Codex orchestrator for the clean-room `tslgen` redesign.

Milestones 1 through 47 have been reviewed and accepted.

Your task is to plan the next numbered milestone after M47 and then run an
internal subagent review of that planning result before returning it.

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

Produce a docs-only post-M47 planning update and internally review it with
subagents.

The expected candidate is a narrow generation-time signedness/type predicate
branch-pruning slice over typed M43 inputs, likely:

```text
if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
  ...
} else<generation> {
  ...
}
```

Codex must verify evidence and update the roadmap before any implementation.

## Phase 1: Planning subagents

Spawn these read-only subagents and wait for all results.

### 1. Planner subagent

Task:

- Propose the next numbered milestone after M47.
- Prefer a formal Milestone 48 only if evidence supports it.
- Define goal, scope, out of scope, inputs, outputs, tests, validation, review
  risks, and dependencies.

### 2. Evidence auditor subagent

Task:

- Verify evidence paths and line ranges for signedness/type predicate branch
  forms.
- Compare against alternative next slices.
- Confirm `frozen/` is evidence only.

### 3. Documentation auditor subagent

Task:

- Identify docs that must be updated.
- Find stale post-M47 wording.
- Check OQ-032/OQ-036 consistency.

### 4. Boundary auditor subagent

Task:

- Verify the proposed next milestone preserves M43/M45/M46/M47 boundaries.
- Confirm it does not combine lowering, backend translation, and rendering.
- Confirm renderers stay non-evaluating.

## Phase 2: Planning update

After Phase 1, update docs only if evidence supports a next milestone.

Likely files:

- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`
- `docs/agent/current-redesign-state.md`

Do not modify implementation code or tests.

Run:

```bash
git diff --check
```

## Phase 3: Internal review subagents

After the planning update and `git diff --check`, spawn these read-only review
subagents.

### 5. Planning reviewer subagent

Task:

- Review the updated plan as if using a redesign-review prompt.
- Return one verdict:
  - `Accept`
  - `Accept With Follow-Ups`
  - `Needs Revision`
  - `Return To Planner`
  - `Reject`
- Focus on milestone clarity, docs consistency, and whether the next slice is
  small enough.

### 6. Boundary reviewer subagent

Task:

- Review only boundary preservation.
- Confirm the plan does not pull backend translation, rendering, or broad TSIL
  parsing into the next milestone.
- Return blocking/non-blocking issues.

### 7. Docs consistency reviewer subagent

Task:

- Review only docs consistency.
- Check roadmap, behavioral spec, generation-time contract, OQ-032/OQ-036,
  testing strategy, and ADRs.
- Return stale wording or overclaim issues.

## Phase 4: Orchestrator consolidation

After all review subagents finish:

1. Summarize planning subagent results.
2. Summarize review subagent results.
3. If any review subagent finds blocking issues:
   - fix only docs/planning issues if local and clearly scoped;
   - rerun `git diff --check`;
   - summarize the fix.
4. If the issue is design-level, stop and return `Return To Planner`.
5. Produce a final consolidated planning review packet.

## Guardrails

Do not select a broad TSIL parser milestone.

Do not combine signedness branch pruning with backend suffix/type translation.

Do not change generated output.

Do not reopen accepted M45/M46/M47 behavior unless evidence reveals a genuine
design inconsistency.

Do not import or execute `frozen/`.

Do not let review subagents implement changes directly; the orchestrator owns
any final docs-only corrections.

## Final response format

1. Planning subagents spawned.
2. Review subagents spawned.
3. Candidate next slices considered.
4. Selected next milestone or explicit deferral.
5. Files changed.
6. Evidence used.
7. Boundary preservation summary.
8. Review verdict from internal subagents.
9. Blocking issues found and fixed, if any.
10. Validation command and exact result.
11. Whether the plan is ready for human acceptance.
12. Recommended next executor milestone.
