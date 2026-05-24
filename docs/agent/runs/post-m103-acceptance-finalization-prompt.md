# Post-M103 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M103 planning update.

Do not implement code.

## Accepted Result

The post-M103 planning update selected:

```text
Milestone 104: Worklist-Driven Backend Translation Result Expansion Slice
```

Internal planning review returned:

```text
Accept With Follow-Ups
```

The accepted planning result intentionally broadens the next lowering step, but
only as one documented boundary: M103 worklist entry to typed backend
translation expansion result. It may cover the accepted
`exact_array_backend_uninit_unresolved` and
`selected_body_direct_intrinsic_deferred` M103 classifications, but only through
explicit typed rule inputs over accepted concrete typed facts.

## Task

Update repository workflow state so the next action is M104 execution.

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
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_models.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_entries.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_boundary_worklist_validation.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`
- `tslgen/src/tslgen/lowering/boundary.py`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 103.
- Post-M103 planning accepted.
- Current action: execute Milestone 104.
- Active executor milestone:
  `Milestone 104: Worklist-Driven Backend Translation Result Expansion Slice`.
- Active run prompt:
  `docs/agent/runs/m104-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M104 is a Stage 8 lowering-owned typed backend translation expansion
    result boundary.
  - M104 is one documented gap: M103 worklist entry to typed translation
    expansion result.
  - M104 may consume only accepted concrete M103
    `Stage8BackendBoundaryWorklistInventoryIr` values.
  - M104 may handle only `exact_array_backend_uninit_unresolved` and
    `selected_body_direct_intrinsic_deferred` M103 classifications.
  - M103 worklist classifications may filter entries, but semantic behavior
    must come from concrete typed request/result facts plus explicit typed rule
    inputs.
  - M104 must produce typed resolved/deferred/unsupported result records, not
    renderer-ready IR or generated source.
  - M104 must not dispatch by `svptrue_b*`, extension id, type tag, byte size,
    primitive name, raw direct-intrinsic token text, source-location text, or
    hardware-looking tokens.
  - M104 must preserve M103/M99/M100 provenance and object identity.
  - M104 must keep ownership in new focused private modules and avoid growth in
    `boundary.py`, `_lowering_ir_contracts.py`, M99/M100 modules, and M103
    worklist modules.
  - M104 must not add backend-map/catalog/manifest reads during lowering,
    rendering, renderer-ready IR, generated output, Stage 9 backend planning,
    Rust rendering, source repair, raw source reparsing, operation scheduling,
    dependency closure, queues, scheduler/readiness behavior, registries,
    dispatchers, callbacks, plugins, hidden backfeeds, fixpoint machinery, or
    category-based semantic dispatch.

Create the M104 execution-review-loop prompt under:

```text
docs/agent/runs/m104-execution-review-loop-prompt.md
```

The M104 prompt must specify:

- one write-capable executor;
- read-only reviewer/auditor subagents;
- scope and out-of-scope boundaries from the M104 roadmap section;
- focused private modules such as:
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_models.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_sources.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_validation.py`
  - `tslgen/src/tslgen/lowering/_lowering_backend_translation_expansion_diagnostics.py`
- focused tests in a new file such as
  `tslgen/tests/unit/test_lowering_backend_translation_expansion.py`;
- positive tests for exact-array unresolved and selected-body direct-intrinsic
  deferred entries resolved by explicit typed rule input;
- missing-rule tests that produce typed deferred/unsupported state rather than
  guessed behavior;
- negative tests for rule mismatch, duplicate/conflicting rules, fake
  protocol-shaped objects, malformed source containers, malformed keys,
  provenance mismatch, and concrete-type rejection;
- direct-intrinsic negative tests proving no dispatch by `svptrue_b*`,
  extension id, type tag, byte size, primitive name, raw token text,
  source-location text, or hardware-looking tokens;
- import-boundary/source assertions proving no `boundary.py`, public facade,
  backend/rendering/planning imports, `tsldata`, `frozen`, backend maps/
  catalogs/manifests, raw parsing helpers, source repair, registry/
  dispatcher/callback/plugin/backfeed/fixpoint behavior, or category-based
  semantic dispatch;
- line-count checks for `boundary.py`, `_lowering_ir_contracts.py`, M99/M100
  modules, M103 worklist modules, and new M104 modules;
- required validation from the M104 roadmap section;
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
5. Whether the repo is ready to execute M104 after acceptance finalization.
