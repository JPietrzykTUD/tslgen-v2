# Milestone 53 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 53.

Milestones 1 through 52 are accepted. Post-M52 planning is accepted and
selected:

```text
Milestone 53: Catalog-Validated Concrete Integer Generation Rule Source Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 54.

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

M53 implements exactly one semantic rule-source boundary slice:

- Move the accepted M52 concrete integer generation type/signedness semantics
  from a lowering-private table into typed domain/catalog rule values consumed
  by lowering.
- Introduce a typed concrete integer generation rule model outside
  `tslgen.lowering.boundary` for exactly:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Validate or construct that rule source from typed catalog/type-group data
  such as `TypeGroup` entries from `tsldata/detail/types.tsl`, while preserving
  the exact accepted M52 rule set:

  ```text
  si8  <-> ui8
  si16 <-> ui16
  si32 <-> ui32
  si64 <-> ui64
  ```

- Make generation-time lowering consume the typed rule source instead of owning
  the private concrete-integer rule table.
- Preserve behavior exactly for:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

  and the exact M48/M51 signedness predicate branch forms.

- Preserve M52 diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless a narrower rule-source diagnostic is
  required for missing or inconsistent rule data.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.
- Preserve M45/M46 backend translation limits: M53 must not expand suffix or
  type-spelling translation beyond accepted selected `si32`/`ui32` behavior.

## Out Of Scope

- Milestone 54 or any later milestone.
- New generation-time helper forms such as `type::size_bytes`.
- Inferring broad integer semantics from regex, tag spelling, or generic
  integer-looking names.
- Treating wildcard or group selectors such as `?i?`, `?i64`, `si?`, `ui?`, or
  `idqword` as selected concrete type tags during lowering.
- Regex-derived acceptance of concrete-looking unselected tags such as `si128`.
- Backend translation expansion, including suffix, type-spelling, prefix, post,
  infix, or immediate modifier support for non-32-bit integer tags.
- C++ or Rust rendering.
- Generated C++ or Rust output.
- Generated test sources.
- CLI/reporting or writer behavior.
- Compiler execution or generated-test execution.
- Floats, masks, pointers, vector types, generic tags, backend-scoped type
  requests, vector/register metadata, vector length/alignment, generic lengths,
  aliases, casts, arrays, loops, calls, direct `intrin<...>`, `switch<compile>`,
  `if<compile>`, generalized plain `else`, broad TSIL parsing, and branch-body
  semantics.
- Runtime dependency on `frozen/`, raw legacy TSL, or legacy generator logic.
- Lowering reading files, parsing raw TSL, or querying the catalog directly at
  evaluation time instead of consuming typed rule values prepared at the
  domain/catalog/lowering-input boundary.
- Renderer-side semantic inference or evaluation of generation-time helpers.
- Backend translation parsing raw generation helper text.

## Evidence

- `tsldata/detail/types.tsl:2-9` for concrete integer singleton tags.
- `tsldata/detail/types.tsl:10-16` and `:20-24` for wildcard/group selectors
  that must remain unsupported as selected concrete lowering tags.
- `tslgen/src/tslgen/domain/types.py` for typed `TypeGroup` values.
- `tslgen/src/tslgen/domain/catalog.py` for typed catalog lookup/indexing.
- Current M52 tests in `tslgen/tests/unit/test_lowering_boundary.py` for the
  accepted behavior contract.
- Legacy canonicalization and signedness evidence may be consulted in
  `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py`, but `frozen/`
  remains evidence only.

## Required Tests

- Focused unit tests for the new typed rule source, including deterministic
  rule ordering.
- Rule-source validation tests for missing singleton tags, missing companion
  pairs, inconsistent singleton/group data, wildcard/group selectors, floats,
  pointers, masks, unknown tags, and concrete-looking unselected tags such as
  `si128`.
- Regression tests proving all M52 type-query and signedness branch behavior
  remains unchanged.
- Diagnostic tests proving unsupported selected tags keep structured
  diagnostics unless a narrower rule-source diagnostic is required for missing
  or inconsistent rule data.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M53 is a semantic rule-source boundary slice and must not change
  generated C++ or Rust output.

## Phase 1: Executor

If M53 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M53 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M53 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M53 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M53 remains a semantic rule-source boundary slice and does not leak
   into backend translation expansion, backend rendering, generated output,
   generated test sources, Rust, CLI/reporting, writer behavior, compiler
   execution, generated-test execution, vector/register metadata, broad TSIL
   parsing, generalized plain `else`, branch-body semantics, renderer-side
   helper evaluation, backend parsing of raw helper text, or runtime reads from
   `frozen/`. Do not edit files.
4. Documentation auditor subagent:
   Check M53 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy,
   generation-time semantic lowering spec, target architecture, pipeline
   design, design decisions, open questions, and frozen parity baselines. Do
   not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for the selected concrete integer
   rule-source behavior and confirm `frozen/` remains evidence only. Do not
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
2. Mark accepted through Milestone 53.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 54 is already selected by an accepted planning result, create a
post-M53 planning-plus-review prompt. Do not start Milestone 54 from this
execution-review loop.

## Required Validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Run the new focused rule-source test command selected by the executor. Use
compileall, ruff, and mypy for changed Python files if implementation or
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
