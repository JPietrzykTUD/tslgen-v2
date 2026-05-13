# Post-M48 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M48 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M48 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M49 execution can be activated.

## Accepted Result

The post-M48 planning update selected:

```text
Milestone 49: Generated C++ Add I32 Test Source Parity Slice
```

Internal Codex review returned:

```text
Accept after local planning-doc revisions
```

No blocking follow-up remains.

The existing non-blocking follow-up remains:

```text
Older post-M34 wording around "do not define M35 yet" may be cleaned up later.
```

## Read First

- `docs/agent/current-redesign-state.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/frozen-parity-baselines.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/testing-strategy.md`

## Required Changes

Update only workflow docs/prompts:

- `docs/agent/current-redesign-state.md`
- `docs/agent/runs/m49-execution-review-loop-prompt.md`

Create `docs/agent/runs/m49-execution-review-loop-prompt.md` as the next active
prompt. It must use the orchestrated executor-review loop pattern and include:

- exactly one write-capable executor if M49 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 50.

The M49 active prompt must constrain implementation to:

- C++ only.
- Selected case only: `add`, `add_i32_basic`, `si32`, scalar.
- Test-source rendering only.
- Artifact kind `production_tests`.
- Logical path `tests/add_i32_basic_test.cpp`.
- Golden fixture:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.cpp`.
- Provenance fixture:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.provenance.md`.
- Typed inputs:
  - `TestSourcePlan` / `PlannedTestCase`;
  - explicit M46-style `BackendTypeSpelling(backend_id="cpp",
    type_tag="si32", spelling="int32_t", source_ref_kind="base.in")`.

Boundary reminders for M49:

- M49 must not compile or run generated tests.
- M49 must not fetch, vendor, configure, or require `gtest`.
- M49 must not read or execute legacy templates at runtime.
- M49 must not infer C++ type spelling locally.
- M49 must not broaden generated-test parity beyond `add_i32_basic`.
- M49 must not modify generation-time lowering, backend translation, generated
  C++ implementation output rendering, CLI/report/writer, Rust, or compiler
  execution behavior.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 48.
- Post-M48 planning accepted.
- Current action: run the Milestone 49 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m49-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 49: Generated C++ Add I32 Test Source Parity Slice`.
- The boundary reminders above.
- The non-blocking post-M34 wording cleanup follow-up remains recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m49-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M49.
