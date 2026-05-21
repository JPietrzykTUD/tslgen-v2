# Post-M96 Acceptance Finalization Prompt

You are finalizing the accepted post-M96 planning result.

Do not implement code.

## Accepted Result

Post-M96 planning selected:

```text
Milestone 97: Lowering Completion Gap Inventory Slice
```

Planning review returned:

```text
Accept With Follow-Ups
```

The accepted plan is a Stage 8 lowering-only gap inventory slice. It consumes
accepted M96 `Stage8LoweringCompletionManifestIr` values and records only
lowering-observed gaps visible from accepted manifest facts. The initial gap
category is accepted unresolved backend-handoff dependency records; manifests
without unresolved dependencies produce a deterministic no-known-gap inventory
state.

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
- `tslgen/src/tslgen/lowering/_lowering_completion_manifest.py`
- `tslgen/src/tslgen/lowering/_operation_package_sources.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Task

Update repository workflow state so the next action is M97 execution.

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 96.
- Post-M96 planning accepted.
- Current action: execute Milestone 97.
- Active executor milestone:
  `Milestone 97: Lowering Completion Gap Inventory Slice`.
- Active run prompt:
  `docs/agent/runs/m97-execution-review-loop-prompt.md`.
- Next expected action: run the M97 execution-review loop.
- Boundary reminders:
  - M97 is Stage 8 lowering gap-inventory work only.
  - M97 consumes accepted M96 `Stage8LoweringCompletionManifestIr` values,
    `lowering_completion_manifest` stages, or a narrow one-manifest container.
  - M97 "gap" means a lowering-observed deferred or unsupported fact visible
    from accepted M96 manifest facts only.
  - The first supported gap category is accepted unresolved backend-handoff
    dependency records; manifests without such records produce a deterministic
    no-known-gap state.
  - M97 preserves source manifest, package record, package object, unresolved
    dependency record, and source dependency request object identity.
  - M97 keeps ownership in a focused private gap-inventory module.
  - M97 must not grow `_operation_package_sources.py`.
  - If stage integration would grow `boundary.py` beyond 1,300 lines, the
    executor must first extract existing coordination or keep M97 module-only
    and record stage integration as a follow-up.
  - M97 must not infer semantic body completion, backend readiness, renderer
    readiness, dependency closure, operation scheduling, backend support,
    backend value resolution, or output readiness.
  - No backend translation, backend map/catalog reads, backend-uninit
    resolution, Stage 9 backend planning, operation scheduling, primitive
    dependency closure, dependency solving, renderer-ready IR, rendering,
    generated output, source repair, raw body parsing, registries,
    dispatchers, hidden backfeeds, fixpoint machinery, Rust,
    CLI/report/writer, or compiler execution work is in M97.

Create:

```text
docs/agent/runs/m97-execution-review-loop-prompt.md
```

The M97 execution prompt must use the orchestrated executor-review loop with
exactly one write-capable executor followed by read-only review/audit
subagents. It must include the selected M97 scope, out-of-scope items,
required inputs, expected outputs, tests, validation commands, revision loop,
and finalization rules.

Do not modify product code or tests.

## M97 Execution Prompt Requirements

The M97 execution-review-loop prompt must require:

- One write-capable executor only.
- Read-only reviewer, boundary auditor, extensibility auditor, validation
  auditor, and documentation auditor subagents after implementation.
- Focused private gap-inventory ownership, such as
  `tslgen.lowering._lowering_completion_gap_inventory`.
- A narrowly named output model such as
  `Stage8LoweringCompletionGapInventoryIr`.
- Consumption of accepted M96 `Stage8LoweringCompletionManifestIr` values as
  the primary input, not raw source text, operation-package source adapters, or
  backend/rendering concepts.
- Support only for current accepted M96 manifest facts: no-known-gap manifests
  and accepted unresolved backend-handoff dependency records.
- Preservation of source manifest, package record, package object, unresolved
  dependency record, source dependency request, candidate id, source locations,
  and deterministic keys by object identity where identity is the contract.
- No changes to accepted M86/M92/M95 package behavior or accepted M96 manifest
  behavior.
- No edits to `_operation_package_sources.py`.
- No growth in `boundary.py` beyond the current 1,300-line guardrail. If stage
  integration cannot preserve that guardrail, the executor must perform a
  behavior-preserving extraction first or keep M97 module-only and report
  stage integration as a follow-up.
- Tests for no-known-gap inventories, unresolved dependency gap records,
  deterministic keys/order, object identity/provenance preservation,
  unsupported/missing/multiple/wrong-stage/malformed/context/location/copied
  record diagnostics, stage placement after `lowering_completion_manifest` if
  integrated, import boundaries, line counts, and forbidden behaviors.

Required validation for the execution prompt:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_operation_package_sources.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_completion_manifest.py tslgen/src/tslgen/lowering/_lowering_completion_gap_inventory.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m97 or completion_gap_inventory or completion_manifest"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Validation

Run:

```bash
git diff --check -- docs/agent/current-redesign-state.md docs/agent/runs/post-m96-acceptance-finalization-prompt.md docs/agent/runs/m97-execution-review-loop-prompt.md
```

If other docs are changed, include them in the diff-check.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M97.
