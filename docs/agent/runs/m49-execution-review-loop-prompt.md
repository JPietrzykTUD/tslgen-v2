# Milestone 49 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 49.

Milestones 1 through 48 are accepted. Post-M48 planning is accepted and
selected:

```text
Milestone 49: Generated C++ Add I32 Test Source Parity Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 50.

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
- `docs/redesign/generation-time-semantic-lowering.md`

## Milestone Scope

M49 implements exactly one generated C++ test-source parity slice:

- Backend: C++ only.
- Selected case only: `add`, `add_i32_basic`, `si32`, scalar.
- Test-source rendering only.
- Artifact kind: `production_tests`.
- Logical path: `tests/add_i32_basic_test.cpp`.
- Golden fixture:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.cpp`.
- Provenance fixture:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.provenance.md`.
- Typed test inputs: `TestSourcePlan` / `PlannedTestCase`, or equivalent
  immutable typed test-plan values.
- Typed type-spelling input:
  `BackendTypeSpelling(backend_id="cpp", type_tag="si32",
  spelling="int32_t", source_ref_kind="base.in")`, or an equivalent immutable
  typed value from the M46 boundary.

The generated source must preserve semantic evidence for the test name,
selected primitive, two input vectors, expected vector, wrapper-call intent for
`tsl::add<Vec>(...)`, `using Vec = tsl::simd<int32_t, scalar>` from the typed
C++ type spelling, boolean test function shape, and legacy-style
`TEST(...){ ASSERT_TRUE(...) }` registration intent.

The renderer must consume typed test-plan and typed type-spelling values. It
must not rescan raw TSL text, infer `int32_t` from `si32`, or read/execute
legacy templates.

## Out Of Scope

- Milestone 50 or any later milestone.
- Compiling or running generated tests.
- Fetching, vendoring, configuring, or requiring `gtest`.
- Full legacy support headers, runtime aligned buffers, lane resizing,
  runtime-lane policy, mask support, or test-manifest policy.
- Broad generated-test parity beyond the selected scalar `add_i32_basic` case.
- `add_i32_edge`, `ui32`, floating, AVX2, vector, mask, load/store, shift, or
  conversion tests.
- Backend translation changes.
- Generation-time lowering changes.
- Generated C++ implementation output rendering changes.
- CLI/report/writer work, Rust work, output writing beyond existing artifact
  paths, and compiler/toolchain orchestration.
- Runtime dependency on `frozen/` or importing/executing legacy templates.

## Evidence

- `tsldata/primitives/arithmetic/fundamental.tsl:6` for `add_i32_basic` input
  and expected vectors.
- `frozen/jinja/cpp/test_file.j2:1-56` for include and `TEST(...)`
  registration structure.
- `frozen/jinja/cpp/partials/test_common.j2:1-13` for the boolean test
  function and `Vec` alias shape.
- `frozen/jinja/cpp/test_case.j2:51-63` for the binary test-case shape.
- `frozen/generator_specs/tests.yaml` for test-generation policy evidence.
- `docs/redesign/frozen-parity-baselines.md` `CPP-ADD-I32-TEST` entry for the
  selected baseline.

`frozen/` remains evidence only. Do not import or execute it.

## Required Tests

- Golden fixture and provenance tests for `add_i32_basic_test.cpp`.
- Determinism tests for repeated rendering.
- Unit tests proving rendering consumes `TestSourcePlan` / `PlannedTestCase`
  data and explicit typed C++ type-spelling input.
- Unit or regression tests proving the renderer does not read raw TSL text or
  `frozen/` templates at runtime.
- Diagnostic tests for unsupported backend, artifact kind, extension, type,
  case shape, extra metadata, malformed vector values, missing or ambiguous
  type spelling, and wrong selected-case cardinality.
- Regression test proving the existing metadata-style C++ production-test
  artifact remains stable.

## Phase 1: Executor

If M49 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M49 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M49 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M49 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M49 remains C++ test-source rendering only and does not leak into
   generation-time lowering, backend translation, generated implementation
   output rendering, CLI/report/writer, Rust, or compiler execution. Do not
   edit files.
4. Documentation auditor subagent:
   Check M49 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy, target
   architecture, pipeline design, design decisions, open questions, and frozen
   parity baselines. Do not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for `add_i32_basic` test-source parity and
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
2. Mark accepted through Milestone 49.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 50 is already selected by an accepted planning result, create a
post-M49 planning-plus-review prompt. Do not start Milestone 50 from this
execution-review loop.

## Required Validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_test_source_planning.py tslgen/tests/unit/test_cpp_production_test_rendering.py
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
