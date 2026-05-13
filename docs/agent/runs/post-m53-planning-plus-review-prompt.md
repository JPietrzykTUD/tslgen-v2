# Post-M53 Planning + Review Prompt

You are the Codex orchestrator for the clean-room `tslgen` redesign.

Milestones 1 through 53 have been reviewed and accepted. M53 returned
`Accept With Follow-Ups` after one focused documentation revision.

Your task is to plan the next numbered milestone after M53 and then run an
internal subagent review of that planning result before returning it.

Do not implement code.

## Current State

Read first:

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/next-run-prompt-protocol.md`
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

Produce a docs-only post-M53 planning update and internally review it with
subagents.

Select at most one next numbered milestone. If evidence does not support a
small next slice, explicitly defer implementation and record the stop or
planning condition.

## Phase 1: Planning Subagents

Spawn these read-only subagents and wait for all results.

### 1. Planner Subagent

Task:

- Propose the next numbered milestone after M53, or recommend explicit
  deferral.
- Consider deferred parity targets after M53, including catalog/pipeline wiring
  for generation rule sources, additional generation-time value/type lowering,
  backend modifier or type/value translation expansion, vector/register
  metadata, direct-intrinsic or semantic TSIL helper slices, broader generated
  test-source parity, CLI workflow compatibility, broader coverage/report
  parity, Rust output, and executable generated-test/toolchain orchestration.
- Treat M49-M53 non-blocking follow-ups as cleanup candidates, not automatic
  next-milestone scope.
- Define goal, scope, out of scope, inputs, outputs, tests, validation, review
  risks, and dependencies for any proposed milestone.

### 2. Evidence Auditor Subagent

Task:

- Verify evidence paths for plausible next slices.
- Check whether the evidence supports one thin milestone.
- Confirm `frozen/` remains evidence only for the proposed next slice.

### 3. Documentation Auditor Subagent

Task:

- Identify docs that must be updated for the post-M53 plan.
- Find stale post-M52/M53 wording.
- Check roadmap/state alignment and whether accepted follow-ups should be
  recorded for later cleanup rather than included in the next milestone.

### 4. Boundary Auditor Subagent

Task:

- Verify the proposed next milestone preserves M40-M53 boundaries.
- Confirm it does not combine generation-time lowering, backend translation,
  rendering, generated tests, CLI/reporting, Rust, and compiler execution
  unless the planning evidence explicitly justifies one narrow boundary.
- Confirm renderers stay non-evaluating and do not infer backend semantics.
- Confirm backend translation does not parse raw generation helper text.
- Confirm lowering rule-source work does not make lowering read files, parse
  raw TSL, or query the catalog at evaluation time.

## Phase 2: Planning Update

After Phase 1, update docs only if evidence supports a next milestone or an
explicit deferral state.

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

## Phase 3: Internal Review Subagents

After the planning update and `git diff --check`, spawn these read-only review
subagents.

### 5. Planning Reviewer Subagent

Task:

- Review the updated plan as if using a redesign-review prompt.
- Return one verdict:
  - `Accept`
  - `Accept With Follow-Ups`
  - `Needs Revision`
  - `Return To Planner`
  - `Reject`
- Focus on milestone clarity, evidence, docs consistency, and whether the next
  slice is small enough.

### 6. Boundary Reviewer Subagent

Task:

- Review only boundary preservation.
- Confirm the plan does not pull unrelated lowering, backend translation,
  rendering, output, generated tests, CLI/reporting, Rust, or compiler work
  into the next milestone.
- Return blocking and non-blocking issues.

### 7. Docs Consistency Reviewer Subagent

Task:

- Review only docs consistency.
- Check roadmap, behavioral spec, generation-time contract, testing strategy,
  ADRs, frozen parity baselines, open questions, and current state.
- Return stale wording or overclaim issues.

## Phase 4: Orchestrator Consolidation

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

- Do not implement code.
- Do not start a Milestone 54 executor.
- Do not select a broad TSIL parser, broad backend renderer, broad generated
  test framework, whole-report parity, or default compiler-execution milestone.
- Do not change generated output.
- Do not reopen accepted M40-M53 behavior unless evidence reveals a genuine
  design inconsistency.
- Do not import or execute `frozen/`.
- Do not let review subagents implement changes directly; the orchestrator owns
  any final docs-only corrections.

## Next Prompt Requirement

Before final response, create the next concrete prompt under `docs/agent/runs/`
according to `docs/agent/next-run-prompt-protocol.md`, unless the planning pass
intentionally records an explicit stop condition.

If the planning result requires human acceptance, create a post-M53 acceptance
finalization prompt instead of an executor prompt.

Update `docs/agent/current-redesign-state.md` to point at the next concrete
prompt or explicit stop condition.

## Final Response Format

Return:

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
12. Next run prompt created.
