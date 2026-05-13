# Post-M49 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M49 planning update.

Do not implement code.

## Prerequisite

Proceed only if the user has explicitly accepted the post-M49 planning update.
If acceptance is not explicit, stop and report that human acceptance is
required before M50 execution can be activated.

## Accepted Result

The post-M49 planning update selected:

```text
Milestone 50: Legacy Coverage JSON Adapter Row Slice
```

Internal Codex review returned:

```text
Accept With Follow-Ups after local planning-doc corrections
```

No blocking follow-up remains.

Non-blocking follow-ups remain recorded in
`docs/agent/current-redesign-state.md`.

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
- `docs/agent/runs/m50-execution-review-loop-prompt.md`

Create `docs/agent/runs/m50-execution-review-loop-prompt.md` as the next active
prompt. It must use the orchestrated executor-review loop pattern and include:

- exactly one write-capable executor if M50 is not already implemented;
- read-only reviewer/auditor subagents after execution;
- revision loop rules for `Needs Revision`;
- next-prompt creation rules for `Accept` / `Accept With Follow-Ups`;
- stop rules for `Return To Planner` / `Reject`;
- guardrail: do not start Milestone 51.

The M50 active prompt must constrain implementation to:

- Reporting adapter only.
- Selected row only: `add`, `avx2`, `cpp`, `f32`.
- Legacy coverage JSON selected-row adapter only.
- Golden fixture:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.json`.
- Provenance fixture:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.provenance.md`.
- Typed inputs:
  - accepted `PipelineCoverageReport` / primitive coverage DTOs or equivalent
    typed report data;
  - a new M50 typed adapter request and selected-row fact value carrying the
    exact selected legacy-row facts.

Boundary reminders for M50:

- M50 must not implement whole `primitive_coverage.json` parity, row-count
  parity, broad coverage matrix parity, coverage HTML/site parity, CLI workflow
  compatibility, new CLI flags, writer/report file writes, backend rendering,
  generation-time lowering, backend translation, generated C++ implementation
  output, test-source rendering, Rust output, compiler execution, or
  generated-test execution.
- M50 must not read `frozen/`, legacy report tools, raw legacy JSON, or raw TSL
  at runtime.
- M50 must not rerun parsing, selection, lowering, backend rendering, or test
  planning during adapter serialization.
- Legacy string-valued booleans are adapter/serialization output only; internal
  report values must remain typed.

Update `docs/agent/current-redesign-state.md` so it states:

- Accepted through: Milestone 49.
- Post-M49 planning accepted.
- Current action: run the Milestone 50 execution-review loop.
- Active run prompt:
  `docs/agent/runs/m50-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 50: Legacy Coverage JSON Adapter Row Slice`.
- The boundary reminders above.
- Non-blocking follow-ups remain recorded.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m50-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M50.
