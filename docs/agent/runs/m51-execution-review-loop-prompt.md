# Milestone 51 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 51.

Milestones 1 through 50 are accepted. Post-M50 planning is accepted and
selected:

```text
Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 52.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/executor.md`
- `docs/agent/subagents/reviewer.md`
- `docs/agent/subagents/validation-auditor.md`
- `docs/agent/subagents/boundary-auditor.md`
- `docs/agent/subagents/docs-auditor.md`
- `docs/agent/subagents/evidence-auditor.md`
- `docs/agent/subagents/next-prompt-generator.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Milestone Scope

M51 implements exactly one generation-time semantic lowering slice:

- Generation-time semantic lowering only.
- Exact signedness predicate branch form only:

  ```text
  if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
    ...
  } else {
    ...
  }
  ```

- Reuse M48 signedness predicate evaluation over typed M43
  `GenerationTypeRef(kind="base.in")` inputs.
- Reuse M42/M48 branch pruning, deterministic provenance, and
  selected-branch-only diagnostics.
- Treat plain `else` as equivalent to `else<generation>` only for this selected
  signedness predicate branch form.
- Preserve existing `else<generation>` signedness branch behavior.
- Use the selected M43 `si32` and `ui32` `base.in` inputs as the signed and
  unsigned coverage points.

The accepted representative evidence for the branch shape is
`tsldata/primitives/conversion/repr_change.tsl:1210-1217`. Its enclosing
`switch<compile>` and branch bodies remain out of scope.

## Out Of Scope

- Milestone 52 or any later milestone.
- Broad plain-`else` support for arbitrary generation branches.
- Primitive-attribute plain `else` support.
- Conversion or shift body parity.
- `switch<compile>`, `if<compile>`, direct `intrin<...>`, `let`, `var`, calls,
  vector transforms, loops, aliases, casts, arrays, generic lengths,
  immediates, vector/register metadata, broad TSIL parsing, or branch-body
  semantics.
- Signedness predicates beyond the selected M43 `si32`/`ui32` `base.in`
  inputs.
- Backend translation.
- Backend rendering.
- Generated C++ implementation output.
- Generated test sources.
- Rust output.
- CLI/reporting or writer behavior.
- Compiler execution or generated-test execution.
- Runtime dependency on `frozen/`, raw legacy TSL, or legacy generator logic.
- Renderer-side semantic inference or evaluation of generation-time helpers.
- Backend translation parsing raw generation helper text.

## Evidence

- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is the selected
  representative M51 branch-shape evidence.
- Broader `repr_change.tsl` ranges are supporting evidence only and do not
  expand M51 scope.
- Existing M48 signedness branch behavior and tests are the direct semantic
  baseline for predicate evaluation and branch pruning.
- M42 branch provenance behavior remains the provenance baseline.
- `frozen/tsl-gen/tsl_gen/tsil.lark:24` and
  `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:5039` may be used
  as evidence for historical branch forms only.

`frozen/` remains evidence only. Do not import, execute, or read it at runtime.

## Required Tests

- Plain-`else` signedness branch chooses the signed branch for `si32`.
- Plain-`else` signedness branch chooses the plain `else` branch for `ui32`.
- Existing `else<generation>` signedness branch tests continue to pass.
- Branch provenance remains deterministic and identifies the selected branch.
- Diagnostics are emitted only for the selected branch after pruning.
- Unselected-branch unresolved helpers remain ignored for this selected form.
- Malformed plain-`else` signedness branches produce explicit diagnostics.
- Unsupported predicates, nested type expressions, missing type context,
  unknown type tags, unsupported non-integer tags, and generalized plain-`else`
  forms are rejected or left unsupported with explicit diagnostics.
- Backend translation continues to reject raw generation helper text.
- Renderers continue not to evaluate generation-time helpers.
- Repeated lowering produces deterministic results and diagnostics.

## Phase 1: Executor

If M51 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M51 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M51 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M51 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M51 remains generation-time semantic lowering only and does not leak
   into broad plain-`else` support, primitive-attribute plain `else`, conversion
   or shift body parity, compile-time forms, backend translation, backend
   rendering, generated output, generated test sources, Rust, CLI/reporting,
   writer behavior, compiler execution, generated-test execution, broad TSIL
   parsing, renderer-side helper evaluation, or backend parsing of raw helper
   text. Do not edit files.
4. Documentation auditor subagent:
   Check M51 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy,
   generation-time semantic lowering spec, target architecture, pipeline
   design, design decisions, open questions, and frozen parity baselines. Do
   not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for the selected plain-`else` signedness
   branch shape and confirm `frozen/` remains evidence only. Do not edit files.

## Phase 3: Consolidated Verdict

The orchestrator consolidates the subagent results into one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

## Phase 4: Revision Loop If Needed

If the consolidated verdict is `Needs Revision`:

1. Identify only blocking issues.
2. Spawn exactly one focused revision executor subagent.
3. The revision executor may edit only files required to fix blocking issues.
4. Run focused validation.
5. Spawn read-only focused re-review subagents for the changed scope.
6. Repeat only if issues remain local and bounded.
7. Stop after two revision loops and return the remaining blocking issues if
   still unresolved.

If the verdict is `Return To Planner` or `Reject`, do not revise. Create the
appropriate planner, redesign, rollback, or stop prompt under
`docs/agent/runs/` and update `docs/agent/current-redesign-state.md`.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

1. Record follow-ups in `docs/agent/current-redesign-state.md` if needed.
2. Mark accepted through Milestone 51.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 52 is already selected by an accepted planning result, create a
post-M51 planning-plus-review prompt. Do not start Milestone 52 from this
execution-review loop.

## Required Validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Use compileall, ruff, and mypy for changed Python files if implementation or
revision touched code/tests. If implementation discovers a narrower or renamed
targeted command, record the exact command and reason in the review packet.

## Final Output Format

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
