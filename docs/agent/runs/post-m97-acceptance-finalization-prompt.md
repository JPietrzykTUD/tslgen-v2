# Post-M97 Acceptance Finalization Prompt

You are finalizing the accepted post-M97 planning result.

Do not implement code.

## Accepted Result

Post-M97 planning selected:

```text
Milestone 98: Stage 8 Lowering Stage-Assembly Ownership Extraction Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is behavior-preserving Stage 8 lowering architecture work.
It extracts accepted stage construction and per-candidate Stage 8 result
assembly from `boundary.py` into a focused private stage-assembly module while
preserving accepted M57-M97 semantics, diagnostics, stage names, stage order,
keys, object identities, and public facade behavior.

The non-blocking follow-up is that M98 must not become a generic coordinator,
registry, dispatcher, callback map, hidden backfeed, or fixpoint mechanism.

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
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_operation_package.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M98 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 97.
- Post-M97 planning accepted.
- Current action: execute Milestone 98.
- Active executor milestone:
  `Milestone 98: Stage 8 Lowering Stage-Assembly Ownership Extraction Slice`.
- Active run prompt:
  `docs/agent/runs/m98-execution-review-loop-prompt.md`.
- Next expected action: run the M98 execution-review loop.
- Boundary reminders:
  - M98 is behavior-preserving Stage 8 lowering architecture work only.
  - M98 extracts accepted stage construction and per-candidate Stage 8 result
    assembly into a focused private stage-assembly module, preferably
    `tslgen.lowering._lowering_stage_assembly`.
  - M98 keeps `boundary.py` as the public facade, request/result model owner,
    and `_lower_input` owner unless a smaller helper move is needed for the
    selected extraction.
  - M98 keeps `LoweringRequest`, `LoweredImplementation`, `LoweringPlan`,
    public imports, accepted diagnostics, accepted stage names, stage order,
    stage keys, output identities, and object identity behavior stable.
  - M98 must not modify `_operation_package_sources.py` or route more
    coordination through it.
  - M98 must not add new lowering semantics, new operation-package families,
    source-body parsing, source repair, backend translation, backend map/catalog
    reads, backend-uninit resolution, Stage 9 planning, operation scheduling,
    dependency closure, renderer-ready IR, rendering, generated output, Rust,
    CLI/report/writer behavior, compiler execution, registries, dispatchers,
    callback maps, hidden backfeeds, fixpoint machinery, or hardwiring.

Create:

```text
docs/agent/runs/m98-execution-review-loop-prompt.md
```

The M98 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M98 scope, out-of-scope items,
required inputs, expected outputs, tests, validation commands, revision loop,
and finalization rules.

Do not modify product code or tests.

## M98 Execution Prompt Requirements

The M98 execution-review-loop prompt must require:

- One write-capable executor only.
- Read-only reviewer, boundary auditor, extensibility auditor, validation
  auditor, and documentation auditor subagents after implementation.
- A focused private stage-assembly module, preferably
  `tslgen.lowering._lowering_stage_assembly`.
- Exact ownership for the new module:
  - accepted `GenerationLoweringStage` construction helpers;
  - per-candidate Stage 8 result assembly for the accepted operation-package,
    completion-manifest, and completion-gap-inventory tail;
  - no request/result public model ownership and no broad lowering source
    protocol ownership.
- `boundary.py` remains the public facade and keeps request/result models,
  `lower_candidates`, and `_lower_input` ownership unless a tiny helper move is
  explicitly necessary for the stage-assembly extraction.
- No edits to `_operation_package_sources.py`.
- Preservation of accepted M57-M97 diagnostics, stage names, stage ordering,
  stage keys, deterministic ordering, output identities, object identities,
  selected-branch-only diagnostics, public imports, and no-external-input
  boundaries.
- Tests for stage-construction parity, per-candidate completion-tail assembly,
  mini-TSIL and exact-array pipeline parity, object-identity preservation,
  deterministic keys/order, import boundaries, public import stability,
  line-count guardrails, and forbidden behaviors.
- Import-boundary tests proving the new module does not import `boundary.py`,
  the `tslgen.lowering` package facade, backend modules, renderers, `tsldata`,
  or `frozen`.
- Line-count guardrails requiring `boundary.py <= 1285`,
  `_operation_package_sources.py <= 819`, and the new stage-assembly module
  below the module-size guardrail.

Required validation for the execution prompt:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m98 or stage_assembly or completion_manifest or completion_gap_inventory or operation_package"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m97-acceptance-finalization-prompt.md docs/agent/runs/m98-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M98.
