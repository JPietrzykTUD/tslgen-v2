# Post-M102 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M102 planning update.

Do not implement code.

## Accepted Result

The post-M102 planning update selected:

```text
Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

The accepted planning result intentionally narrows the earlier broad worklist
idea. For M103, "worklist" means a static typed Stage 8
inventory/provenance view over accepted concrete M99/M100 facts. It is not an
executable queue, scheduler, dependency-closure plan, readiness oracle, Stage
9 backend plan, renderer-ready IR, completeness oracle, source scanner,
backend-map evaluator, registry, dispatcher, hidden backfeed, or fixpoint
mechanism.

## Task

Update repository workflow state so the next action is M103 execution.

Read first:

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
- `tslgen/src/tslgen/lowering/boundary.py`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 102.
- Post-M102 planning accepted.
- Current action: execute Milestone 103.
- Active executor milestone:
  `Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice`.
- Active run prompt:
  `docs/agent/runs/m103-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M103 is a Stage 8 static inventory/provenance slice.
  - M103 consumes only accepted concrete M99
    `Stage8BackendTranslationRequestInventoryIr` values and optional accepted
    concrete M100 `ExactArrayBackendUninitTranslationResultIr` values.
  - M103 must preserve object identity to accepted request, no-request,
    result, and deferred records.
  - M103 must reject arbitrary fake objects that merely satisfy M102
    protocols.
  - M103 must keep ownership in a focused private module and avoid
    `boundary.py`, `LoweredImplementation`, public facade, `_lower_input`,
    M99/M100 module, and `_lowering_ir_contracts.py` growth.
  - M103 must not add new `GenerationLoweringStageName` values or
    `_stage_contracts.py` integration.
  - M103 worklist-specific contract constants must stay in the new focused
    module, not `_lowering_ir_contracts.py`.
  - M103 must not call translation lowerers to complete missing work.
  - M103 must not add backend translation semantics, Rust translation, direct-
    intrinsic/SVE resolution, Stage 9 planning, renderer-ready IR, rendering,
    generated output, scheduling, dependency closure, backend map/catalog/
    manifest reads, raw source parsing, source repair, registries,
    dispatchers, callbacks, plugins, hidden backfeeds, fixpoint behavior, or
    category-based semantic dispatch.

Create the M103 execution-review-loop prompt under:

```text
docs/agent/runs/m103-execution-review-loop-prompt.md
```

The M103 prompt must specify:

- one write-capable executor;
- read-only reviewer/auditor subagents;
- scope and out-of-scope boundaries from the M103 roadmap section;
- a focused private worklist module such as
  `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`;
- focused tests in a new test file rather than expanding
  `tslgen/tests/unit/test_lowering_boundary.py`;
- positive tests over M99 request/no-request records and optional matching
  M100 exact-array translation results;
- negative tests for fake M102-protocol objects, mismatched M100 result
  inventory/candidate/source location, duplicate/conflicting entries,
  unsupported source containers, malformed keys, and missing source inventory;
- explicit negative tests for arbitrary M102-conformant fake objects, not only
  wrong concrete classes;
- import-boundary/source assertions proving no `boundary.py`, public facade,
  backend/rendering/planning imports, `tsldata`, `frozen`, backend maps/
  catalogs/manifests, raw parsing helpers, source repair, registry/
  dispatcher/callback/plugin/backfeed/fixpoint behavior, or category-based
  semantic dispatch;
- line-count checks for `boundary.py`, `_lowering_ir_contracts.py`, M99/M100
  modules, and the new worklist module, including an explicit ceiling for the
  new module and proof that `boundary.py` remains unchanged;
- required validation from the M103 roadmap section;
- finalization rules to update state/docs and create the next prompt.

Do not modify implementation code or tests.

## Validation

Run:

```bash
git diff --check
```

If other docs are changed, include them in the diff-check by running the same
repository-wide command.

## Final Report

Report:

1. Files changed.
2. State transition made.
3. Follow-ups recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M103 after acceptance finalization.
