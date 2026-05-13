# Milestone 54 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 54.

Milestones 1 through 53 are accepted. Post-M53 planning is accepted and
selected:

```text
Milestone 54: Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 55.

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

M54 implements exactly one pipeline/lowering-input wiring slice:

- Build or expose the accepted M53 `ConcreteIntegerGenerationRuleSet` from typed
  catalog/type-group data before lowering evaluation.
- Thread that immutable rule set through the normal lowering-input path, such
  as `GenerationContext` / `LoweringRequest` construction or a focused
  pipeline/API adapter.
- Preserve the useful request-local default for unit tests only if normal
  pipeline-facing use has an explicit catalog-derived rule path.
- Prove selected lowering consumes an explicitly supplied catalog-derived rule
  set and does not hide missing or inconsistent explicit rule data behind the
  synthetic default.
- Preserve behavior exactly for:

  ```text
  type<generation>(base::in)
  type<generation>(base::signed_of(type<generation>(base::in)))
  type<generation>(base::unsigned_of(type<generation>(base::in)))
  ```

  and the exact M48/M51 signedness predicate branch forms.

- Preserve exactly these selected concrete tags:

  ```text
  si8, ui8, si16, ui16, si32, ui32, si64, ui64
  ```

- Preserve M52/M53 diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless an explicit catalog-derived
  rule-source diagnostic is required for missing or inconsistent rule data.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.
- Preserve M45/M46 backend translation limits: M54 must not expand suffix or
  type-spelling translation beyond accepted selected `si32`/`ui32` behavior.

## Out Of Scope

- Milestone 55 or any later milestone.
- New generation-time helper forms such as `type::size_bytes`.
- Backend suffix/type-spelling expansion beyond accepted M45/M46 `si32`/`ui32`
  behavior.
- C++ or Rust rendering.
- Generated C++ or Rust output.
- Generated test sources.
- CLI/reporting or writer behavior.
- Compiler execution or generated-test execution.
- Broad generic semantic-rule registries or plugin systems before a second rule
  family demonstrates the need.
- Treating wildcard or group selectors such as `?i?`, `?i64`, `si?`, `ui?`,
  `idqword`, `dword`, or `qword` as selected concrete type tags during
  lowering.
- Inferring broad integer semantics from regex, tag spelling, wildcard/group
  selectors, or concrete-looking unselected tags such as `si128`.
- Floats, masks, pointers, vector types, generic tags, backend-scoped type
  requests, vector/register metadata, vector length/alignment, generic lengths,
  aliases, casts, arrays, loops, calls, direct `intrin<...>`, `switch<compile>`,
  `if<compile>`, generalized plain `else`, broad TSIL parsing, and branch-body
  semantics.
- Lowering reading files, parsing raw TSL, querying the catalog during
  evaluation, or importing/executing `frozen/`.
- Renderer-side semantic inference or evaluation of generation-time helpers.
- Backend translation parsing raw generation helper text.

## Evidence

- `tsldata/detail/types.tsl:2-9` for concrete integer singleton tags.
- `tsldata/detail/types.tsl:10-16`, `:20-24`, and `:25-26` for wildcard/group
  selectors that must remain unsupported as selected concrete lowering tags.
- `tslgen/src/tslgen/domain/generation_rules.py` for typed M53 rule-source
  values and builder behavior.
- `tslgen/src/tslgen/domain/types.py` for typed `TypeGroup` values.
- `tslgen/src/tslgen/domain/catalog.py` for typed catalog lookup/indexing.
- `tslgen/src/tslgen/lowering/boundary.py` for `GenerationContext`,
  `LoweringRequest`, and lowering consumption of typed rule values.
- Current M52/M53 tests in `tslgen/tests/unit/test_lowering_boundary.py` and
  `tslgen/tests/unit/test_concrete_integer_generation_rules.py`.
- `frozen/` remains evidence only and is not needed for the selected M54 slice.

## Required Tests

- Focused unit tests proving catalog/type-group data can build the rule set and
  that repeated construction is deterministic.
- A lowering or pipeline-facing adapter test proving an explicitly
  catalog-derived `ConcreteIntegerGenerationRuleSet` is consumed by lowering.
- Negative tests proving missing singleton tags, missing companion pairs,
  inconsistent singleton/group data, wildcard/group selected tags, floats,
  pointers, masks, unknown tags, and concrete-looking unselected tags such as
  `si128` produce structured diagnostics without hidden default fallback.
- Regression tests proving all M52/M53 type-query and signedness branch
  behavior remains unchanged.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.

Golden fixtures required:

- None. M54 is a pipeline/lowering-input wiring slice and must not change
  generated C++ or Rust output.

## Phase 1: Executor

If M54 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M54 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M54 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M54 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M54 remains a pipeline/lowering-input wiring slice and does not leak
   into new helper semantics, backend translation expansion, backend rendering,
   generated output, generated test sources, Rust, CLI/reporting, writer
   behavior, compiler execution, generated-test execution, vector/register
   metadata, broad TSIL parsing, generalized plain `else`, branch-body
   semantics, renderer-side helper evaluation, backend parsing of raw helper
   text, lowering-time file/catalog/raw-TSL reads, or runtime reads from
   `frozen/`. Do not edit files.
4. Documentation auditor subagent:
   Check M54 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy,
   generation-time semantic lowering spec, target architecture, pipeline
   design, design decisions, open questions, and frozen parity baselines. Do
   not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for the selected catalog-derived rule
   wiring behavior and confirm `frozen/` remains evidence only. Do not edit
   files.

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
2. Mark accepted through Milestone 54.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 55 is already selected by an accepted planning result, create a
post-M54 planning-plus-review prompt. Do not start Milestone 55 from this
execution-review loop.

## Required Validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_concrete_integer_generation_rules.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Run the new focused pipeline/lowering-input wiring test command selected by the
executor. Use compileall, ruff, and mypy for changed Python files if
implementation or revision touched code/tests. If implementation discovers a
narrower or renamed targeted command, record the exact command and reason in
the review packet.

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
