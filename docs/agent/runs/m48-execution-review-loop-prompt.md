# Milestone 48 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 48.

Milestones 1 through 47 are accepted. Post-M47 planning selected:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 49.

## Read first

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
- `docs/agent/review-checklist.md`

## Milestone scope

M48 implements exactly the generation-time signedness branch-pruning slice:

```text
if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
  ...
} else<generation> {
  ...
}
```

The predicate consumes typed M43 `GenerationTypeRef(kind="base.in")` values.
`si32` selects the true branch. `ui32` selects the `else<generation>` branch.

M48 is lowering-only. It must not modify backend translation, rendering,
generated output, CLI/API, writer/report behavior, Rust output, or compiler
execution.

## Phase 1: Executor

If M48 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it using
`docs/agent/runs/m48-executor-prompt.md` as the implementation scope.

If M48 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a PLANS.md review packet and run required validation.

## Phase 2: Review/audit subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M48 implementation using the scope in `docs/agent/runs/m48-review-prompt.md`.
   Return exactly one verdict.

2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.

3. Boundary auditor subagent:
   Verify M48 remains generation-time lowering only and does not leak into
   backend translation or rendering. Do not edit files.

4. Documentation auditor subagent:
   Check M48 docs/state for stale wording or overclaims. Do not edit files.

5. Evidence auditor subagent:
   Check evidence/provenance claims for signedness branches. Do not edit files.

## Phase 3: Consolidated verdict

The orchestrator consolidates the subagent results into one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

## Phase 4: Revision loop if needed

If the consolidated verdict is `Needs Revision`:

1. Identify only blocking issues.
2. Spawn exactly one focused revision executor subagent.
3. The revision executor may edit only files required to fix blocking issues.
4. Run focused validation.
5. Spawn read-only focused re-review subagents.
6. Repeat only if issues remain local and bounded.
7. Stop after two revision loops and return the remaining blocking issues if
   still unresolved.

If the verdict is `Return To Planner` or `Reject`, do not revise. Create the
appropriate planner/rollback prompt under `docs/agent/runs/` and update state.

## Phase 5: Next prompt generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

1. Record follow-ups in `docs/agent/current-redesign-state.md` if needed.
2. Mark accepted through Milestone 48.
3. Decide the next workflow action from `docs/redesign/implementation-roadmap.md`.
4. Spawn or perform the next-prompt generator task to create the next prompt
   under `docs/agent/runs/`.
5. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no next milestone is defined, create a post-M48 planning-plus-review prompt.

## Required validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_cpp_backend_vertical_slice.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_backend_metadata_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Use compileall, ruff, and mypy for changed Python files if implementation or
revision touched code/tests.

## Final output format

Return:

1. Executor status.
2. Review subagents spawned.
3. Consolidated verdict.
4. Revision loop count.
5. Files changed.
6. Validation commands and exact results.
7. Follow-ups recorded.
8. Next run prompt created.
9. Current state updated: yes/no.
10. Recommendation for next action.
