# Milestone 50 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 50.

Milestones 1 through 49 are accepted. Post-M49 planning is accepted and
selected:

```text
Milestone 50: Legacy Coverage JSON Adapter Row Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 51.

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
- `docs/redesign/frozen-parity-baselines.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`

## Milestone Scope

M50 implements exactly one legacy coverage JSON adapter row slice:

- Reporting adapter only.
- Selected row only: primitive `add`, extension `avx2`, language `cpp`, type
  `f32`.
- Legacy coverage JSON selected-row adapter only.
- Golden fixture:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.json`.
- Provenance fixture:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.provenance.md`.
- Typed report input: accepted `PipelineCoverageReport` / primitive coverage
  DTOs, or equivalent immutable typed report data.
- Typed adapter input: a new M50 typed adapter request and selected-row fact
  value carrying the exact selected legacy-row facts for `add` / `avx2` /
  `cpp` / `f32`.

The selected adapter row must produce these fields in stable order:

```text
effective_present
extension
has_intrinsic
has_lang_block
has_tsil
language
missing_effective
missing_intrinsic
missing_lang_block
missing_tsil
primitive
primitive_class
template
type
```

The selected row facts include primitive class `fundamental`, template
`v:=(v,v)`, `has_tsil=true`, `has_intrinsic=false`, `has_lang_block=false`,
and `effective_present=true`.

Legacy string-valued booleans are adapter/serialization output only. Internal
reporting values must remain typed.

## Out Of Scope

- Milestone 51 or any later milestone.
- Whole `primitive_coverage.json` parity, row-count parity, or broad coverage
  matrix parity.
- Coverage HTML, MkDocs/site output, or documentation-report parity.
- CLI workflow compatibility, new CLI flags, stdout/stderr behavior changes,
  or writer/report file writes.
- Backend rendering.
- Generation-time lowering.
- Backend translation.
- Generated C++ implementation output.
- Test-source rendering.
- Rust output.
- Compiler execution or generated-test execution.
- Runtime dependency on `frozen/`, legacy report tools, raw legacy JSON, or raw
  TSL.
- Rerunning parsing, selection, lowering, backend rendering, or test planning
  during adapter serialization.
- Untyped dictionaries as the adapter model past parser/catalog or test
  fixture boundaries.

## Evidence

- `frozen/out/reports/primitive_coverage.json:57762-57777` for the selected
  legacy row.
- `frozen/tools/report_primitive_coverage.py:242-266` for legacy row field
  construction and string-valued boolean evidence.
- `docs/redesign/frozen-parity-baselines.md` `COVERAGE-ADD-AVX2-F32-ROW`
  entry for the selected baseline.
- `docs/redesign/implementation-roadmap.md` Milestone 50 entry for accepted
  scope, tests, diagnostics, and boundaries.

`frozen/` remains evidence only. Do not import, execute, or read it at runtime.

## Required Tests

- Golden fixture and provenance tests for
  `add_avx2_f32_coverage_row.json`.
- Determinism tests for repeated adapter serialization.
- Unit tests proving the adapter consumes accepted typed coverage/report DTOs
  rather than raw legacy JSON or fresh parser/selection/lowering/rendering
  runs.
- Field mapping tests for selected `add`, `avx2`, `cpp`, `f32`,
  `fundamental`, `v:=(v,v)`, `has_tsil=true`, `has_intrinsic=false`,
  `has_lang_block=false`, `effective_present=true`, and derived
  missing/effective fields.
- Diagnostic tests for unsupported adapter request, missing selected row,
  ambiguous selected row, missing required typed report fields, unavailable
  primitive class/template metadata, and attempts to serialize from raw legacy
  evidence instead of accepted report DTOs.
- Regression tests proving existing redesign coverage JSON and HTML reports
  remain stable.
- Unit or regression tests proving serialization does not read from `frozen/`,
  raw legacy JSON, raw TSL, or legacy report tools at runtime.

## Phase 1: Executor

If M50 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M50 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M50 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M50 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M50 remains reporting-adapter only and does not leak into whole-report
   parity, HTML/site parity, CLI/report writing, backend rendering,
   generation-time lowering, backend translation, generated C++ implementation
   output, test-source rendering, Rust, compiler execution, generated-test
   execution, or runtime legacy reads. Do not edit files.
4. Documentation auditor subagent:
   Check M50 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy, target
   architecture, pipeline design, design decisions, open questions, and frozen
   parity baselines. Do not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for the selected legacy coverage row and
   confirm `frozen/` remains evidence only. Do not edit files.

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
2. Mark accepted through Milestone 50.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 51 is already selected by an accepted planning result, create a
post-M50 planning-plus-review prompt. Do not start Milestone 51 from this
execution-review loop.

## Required Validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_coverage_reporting.py
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
