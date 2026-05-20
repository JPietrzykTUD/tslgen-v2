# Post-M94 Acceptance Finalization Prompt

You are finalizing the accepted post-M94 planning result.

Do not implement code.

## Accepted Result

Post-M94 planning selected:

```text
Milestone 95: Selected-Body Direct-Intrinsic Operation Package Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is a Stage 8 lowering-only operation-package family slice.
It packages already accepted M63 selected-body envelopes and the enclosed
accepted M62 selected assignment/direct-intrinsic body IR as typed provenance.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_operation_package_models.py`
- `tslgen/src/tslgen/lowering/_operation_package_diagnostics.py`
- `tslgen/src/tslgen/lowering/_selected_body_models.py`
- `tslgen/src/tslgen/lowering/_selected_body_lowering.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M95 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 94.
- Post-M94 planning accepted.
- Current action: execute Milestone 95.
- Active executor milestone:
  `Milestone 95: Selected-Body Direct-Intrinsic Operation Package Slice`.
- Active run prompt:
  `docs/agent/runs/m95-execution-review-loop-prompt.md`.
- Next expected action: run the M95 execution-review loop.
- Boundary reminders:
  - M95 is Stage 8 lowering operation-package work only.
  - M95 consumes only accepted M63 `SelectedBodyEnvelopeIr` values and the
    enclosed accepted M62 `SelectedAssignmentDirectIntrinsicBodyIr`.
  - M95 must not parse raw selected-body text.
  - `svptrue_b16`, `svptrue_b32`, `svptrue_b64`, `pg`, selected literals,
    selected type tags, branch ids, extension ids, primitive names, backend
    ids, and source locations are provenance fields only, not semantic
    dispatch keys.
  - M95 must not infer byte size, vector width, predicate meaning, backend
    support, or SVE/direct-intrinsic semantics from direct-intrinsic tokens.
  - No package is produced for `NoSelectedBodyEnvelopeIr` except a diagnostic
    when a selected-body direct-intrinsic package is explicitly requested.
  - Selected-body package validation and entry ownership must live in a
    focused module such as `_operation_package_selected_body.py`.
  - `_operation_package_sources.py` may receive only narrow explicit
    integration and must not become a generic source protocol, callback map,
    registry, or dispatcher.
  - No backend translation, backend map/catalog reads, backend-uninit
    resolution, Stage 9 planning, renderer-ready IR, rendering, generated
    output, source repair, broad TSIL/body semantics, registries, dispatchers,
    hidden backfeeds, fixpoint machinery, hardwiring, Rust, CLI/report/writer,
    or compiler execution work is in M95.

Create:

```text
docs/agent/runs/m95-execution-review-loop-prompt.md
```

The M95 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M95 scope, out-of-scope items,
required inputs, expected outputs, tests, validation commands, revision loop,
and finalization rules.

Do not modify product code or tests.

## M95 Execution Prompt Requirements

The M95 execution-review-loop prompt must require:

- One write-capable executor only.
- Read-only reviewer, boundary auditor, extensibility auditor, validation
  auditor, and documentation auditor subagents after implementation.
- A focused new selected-body package module such as
  `_operation_package_selected_body.py`.
- Preservation of existing M86 mini-TSIL leaf-return and M92 exact-array
  backend-handoff package behavior.
- Positive tests for accepted direct M63 envelope input, accepted stage input,
  and narrow container input where applicable.
- Diagnostic tests for unsupported source, wrong source family, no selected
  body, malformed/non-singleton selected-body envelope state, context/source
  location mismatch, and M62/M63 provenance mismatch.
- Determinism tests for package keys and reordered typed inputs.
- Pipeline/stage tests proving selected-body packages append after
  `selected_body_envelope_lowering` without changing existing package
  behavior.
- Import-boundary and line-count tests proving no operation-package private
  module becomes a replacement monolith and no private operation-package module
  imports `boundary.py`, the `tslgen.lowering` package facade, backend modules,
  renderers, `tsldata`, or `frozen`.

Required validation for the execution prompt:

```bash
wc -l tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package.py tslgen/src/tslgen/lowering/_operation_package_*.py tslgen/src/tslgen/lowering/_selected_body_models.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_pipeline.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m95 or operation_package or selected_body"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m94-acceptance-finalization-prompt.md docs/agent/runs/m95-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M95.
