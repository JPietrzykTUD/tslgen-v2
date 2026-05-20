# Post-M88 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M88 planning update.

Do not implement code.

## Accepted Result

The post-M88 planning update selected:

```text
Milestone 89: Exact Array Backend-Deferred Request Inventory Slice
```

Internal planning/audit returned:

```text
Recommend With Follow-Ups
```

The selected M89 scope is a Stage 8 lowering inventory/provenance slice. It
consumes the accepted M88 `ExactArrayBodyStructuralPackageIr` and inventories
only the accepted M72/M67 `value<backend>(uninit::array)` deferred
backend-value boundary as a typed inventory member. It does not resolve backend
uninit, read backend maps, translate backend text, create renderer-ready IR,
render output, or implement declaration/array/store/return/SVE semantics.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/agent/runs/post-m88-planning-plus-review-prompt.md`

## Task

Update repository workflow state so the next action is M89 execution, then
create the concrete M89 execution-review loop prompt.

Update:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 88.
- Post-M88 planning accepted.
- Current action: execute Milestone 89.
- Active run prompt:
  `docs/agent/runs/m89-execution-review-loop-prompt.md`.
- Active executor milestone:
  `Milestone 89: Exact Array Backend-Deferred Request Inventory Slice`.
- Boundary reminders:
  - M89 is Stage 8 lowering inventory/provenance validation only.
  - M89 consumes accepted M88 exact array-body structural package values.
  - M89 inventories only the accepted M72/M67
    `value<backend>(uninit::array)` deferred backend-value boundary as the
    first supported typed inventory member.
  - M89 must preserve object identity/provenance for the accepted M88 package,
    M72 deferred backend-uninit value, and M67 backend-value request record.
  - Runtime/protocol-shaped sources must be treated as untrusted until their
    typed package payload is validated.
  - M89 must not resolve backend uninit, read backend maps/catalogs,
    translate backend text, create Stage 9 backend plans, create
    renderer-ready IR, render output, generate artifacts, evaluate generic
    `value<backend>(...)`, repair source bodies, infer declaration/array/store/
    return/SVE semantics, or add broad protocols/registries/hidden backfeeds.

Do not modify implementation code or tests.

## Required M89 Execution Prompt

Create:

```text
docs/agent/runs/m89-execution-review-loop-prompt.md
```

The M89 execution prompt must:

- Use the orchestrated executor-review loop.
- Permit exactly one write-capable executor for M89.
- Require read-only reviewer, boundary auditor, extensibility auditor,
  validation auditor, documentation auditor, and evidence auditor after the
  executor.
- Include a focused revision loop for `Needs Revision`.
- Stop and create a planner/rollback prompt for `Return To Planner` or
  `Reject`.
- Require finalization to update state/docs and create the next concrete prompt
  after M89 review accepts.
- Explicitly forbid post-M89 planning until M89 review returns `Accept` or
  `Accept With Follow-Ups`.

The M89 execution prompt must include scope and out-of-scope wording from the
accepted M89 roadmap section. It should require focused private ownership,
such as `tslgen.lowering._array_body_backend_deferred_requests`, and should
avoid growing `_array_body_models.py`, `_array_body_package.py`,
`_array_body_pipeline.py`, or `boundary.py` into catch-all files.

## M89 Validation Commands

The M89 execution prompt must require:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_backend_deferred_requests.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m89 or backend_deferred or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If the implementation chooses a different focused private module name, include
that file consistently in the line-count, py-compile, import-boundary tests,
state file, and final report.

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/m89-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. M89 execution prompt path created.
4. Boundary reminders recorded.
5. Validation command and exact result.
6. Whether the repo is ready to execute M89.
