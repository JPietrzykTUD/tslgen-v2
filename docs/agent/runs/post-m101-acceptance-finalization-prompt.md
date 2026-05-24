# Post-M101 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M101 planning update.

Do not implement code.

## Accepted Result

The post-M101 planning update selected:

```text
Milestone 102: Lowering IR Category Protocol Surface Slice
```

The selected plan responds to the user concern that M101 added category labels
and contract attachments, but not a stable reusable typed IR category surface.
M102 is a behavior-preserving architecture slice, not a new lowering feature.

## Task

Update repository workflow state so the next action is M102 execution.

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
- `tslgen/src/tslgen/lowering/_lowering_ir_contracts.py`

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 101.
- Post-M101 planning accepted.
- Current action: execute Milestone 102.
- Active executor milestone:
  `Milestone 102: Lowering IR Category Protocol Surface Slice`.
- Active run prompt:
  `docs/agent/runs/m102-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M102 is behavior-preserving architecture/protocol-surface work.
  - M102 turns M101 taxonomy labels into a small private typed category
    surface.
  - M102 applies first to the accepted M99/M100 backend-translation
    request/result path.
  - M102 must preserve accepted keys, diagnostics, source locations, object
    identities, stage names, stage ordering, public imports, and deterministic
    behavior.
  - M102 must keep the existing public `LoweringRequest` input bundle distinct
    from taxonomy-level request IR such as `LoweringRequestIr` or
    `TranslationRequestIr`.
  - M102 must not add new lowering semantics, new request/result families,
    backend translation semantics, rendering, generated output, Stage 9
    planning, Rust translation, generic backend helper evaluation, backend
    map/catalog/manifest reads during lowering, raw source parsing, source
    repair, selected-body direct-intrinsic resolution, SVE semantics,
    scheduling, dependency closure, broad inheritance, registry, dispatcher,
    callback system, plugin mechanism, hidden backfeed, or fixpoint mechanism.

Create the M102 execution-review-loop prompt under:

```text
docs/agent/runs/m102-execution-review-loop-prompt.md
```

The M102 prompt must specify:

- one write-capable executor;
- read-only reviewer/auditor subagents;
- scope and out-of-scope boundaries from the M102 roadmap section;
- required tests proving wrong, missing, or mismatched category/protocol
  conformance is caught;
- import-boundary tests proving no backend/rendering imports, no
  `tsldata`/`frozen` dependency, no raw parsing helpers, and no category-based
  semantic dispatch;
- an explicit boundary that the protocol surface may validate shape but must
  not decide semantic behavior, route requests, translate backend values, or
  act as a registry/dispatcher;
- required validation from the M102 roadmap section;
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
3. Follow-up recorded, if any.
4. Validation command and exact result.
5. Whether the repo is ready to execute M102 after acceptance finalization.
