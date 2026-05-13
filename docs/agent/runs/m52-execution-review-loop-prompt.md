# Milestone 52 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 52.

Milestones 1 through 51 are accepted. Post-M51 planning is accepted and
selected:

```text
Milestone 52: Concrete Integer Generation Type Semantics Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 53.

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

M52 implements exactly one generation-time semantic lowering slice:

- Generation-time semantic lowering only.
- Existing exact M43 type query forms only:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

- Existing exact M48/M51 signedness predicate branch forms only:

  ```text
  if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) {
    ...
  } else<generation> {
    ...
  }
  ```

  and the same exact predicate with M51 plain `else`.

- Extend those accepted typed semantics from `si32`/`ui32` to only:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Express signed/unsigned companion behavior as typed rules or typed evaluator
  functions, not raw text rewriting:

  ```text
  si8  <-> ui8
  si16 <-> ui16
  si32 <-> ui32
  si64 <-> ui64
  ```

- Preserve M42/M48/M51 branch provenance, deterministic ordering, and
  selected-branch-only diagnostics.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.
- Preserve M45/M46 backend translation limits: M52 must not expand suffix or
  type-spelling translation beyond accepted selected `si32`/`ui32` behavior.

## Out Of Scope

- Milestone 53 or any later milestone.
- Backend translation expansion, including suffix, type-spelling, prefix, post,
  infix, or immediate modifier support for non-32-bit integer tags.
- C++ or Rust rendering.
- Generated C++ or Rust output.
- Generated test sources.
- CLI/reporting or writer behavior.
- Compiler execution or generated-test execution.
- Treating wildcard or group selectors such as `?i?`, `?i64`, `si?`, `ui?`, or
  `idqword` as selected concrete type tags during lowering.
- Floats, masks, pointers, vector types, generic tags, backend-scoped type
  requests, vector/register metadata, vector length/alignment, generic lengths,
  aliases, casts, arrays, loops, calls, direct `intrin<...>`, `switch<compile>`,
  `if<compile>`, generalized plain `else`, and branch-body semantics.
- Shift or conversion body parity. Evidence from shifts and conversions is
  type/signedness-helper evidence only.
- Runtime dependency on `frozen/`, raw legacy TSL, or legacy generator logic.
- Renderer-side semantic inference or evaluation of generation-time helpers.
- Backend translation parsing raw generation helper text.

## Evidence

- `tsldata/detail/types.tsl:2-16` for concrete integer tags and integer groups.
- `tsldata/primitives/arithmetic/fundamental.tsl:10-21` for accepted add tests
  over 8/16/64-bit signed and unsigned types.
- `tsldata/primitives/arithmetic/fundamental.tsl:47-90` for `?i?` intrinsic
  suffix helper evidence using base signed companion queries.
- `tsldata/primitives/bitwise/shifts.tsl:603-618` for shift tests over
  8/16/64-bit integer tags.
- `tsldata/primitives/bitwise/shifts.tsl:625-635` for exact signedness branch
  evidence over `?i?`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` for plain-`else`
  signedness evidence in a `?i64` context. Branch bodies remain out of scope.
- Legacy canonicalization and signedness evidence may be consulted in
  `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`, but `frozen/`
  remains evidence only.

## Required Tests

- Parameterized unit tests for `base::in`, `base::signed_of`, and
  `base::unsigned_of` across all selected concrete integer tags.
- Parameterized signedness branch pruning tests proving signed tags choose the
  true branch and unsigned tags choose the false branch for both
  `else<generation>` and plain `else`.
- Regression tests proving accepted `si32`/`ui32` behavior is unchanged.
- Diagnostic tests for `f32`, `f64`, `ptr`, mask tags, wildcard/group tags,
  unknown tags, shorthand forms, unsupported nested queries, and unresolved
  helpers in selected branches.
- Determinism tests for repeated type-query and signedness branch lowering.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M52 is a lowering slice and must not change generated C++ or Rust
  output.

## Phase 1: Executor

If M52 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M52 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M52 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M52 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M52 remains generation-time semantic lowering only and does not leak
   into backend translation expansion, backend rendering, generated output,
   generated test sources, Rust, CLI/reporting, writer behavior, compiler
   execution, generated-test execution, vector/register metadata, broad TSIL
   parsing, generalized plain `else`, branch-body semantics, shift/conversion
   body parity, renderer-side helper evaluation, or backend parsing of raw
   helper text. Do not edit files.
4. Documentation auditor subagent:
   Check M52 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy,
   generation-time semantic lowering spec, target architecture, pipeline
   design, design decisions, open questions, and frozen parity baselines. Do
   not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for the selected concrete integer
   type/signedness behavior and confirm `frozen/` remains evidence only. Do not
   edit files.

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
2. Mark accepted through Milestone 52.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 53 is already selected by an accepted planning result, create a
post-M52 planning-plus-review prompt. Do not start Milestone 53 from this
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
