# Post-M100 Planning Acceptance Finalization Prompt

You are finalizing the accepted post-M100 planning update.

Do not implement code.

## Accepted Result

The post-M100 planning update selected:

```text
Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice
```

The selected plan responds to the architecture concern that lowering IR has
become too milestone-specific. M101 is a behavior-preserving consolidation
slice, not a new lowering feature.

## Task

Update repository workflow state so the next action is M101 execution.

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

## Required Changes

Update only if needed:

- `docs/agent/current-redesign-state.md`

It should state:

- Accepted through: Milestone 100.
- Post-M100 planning accepted.
- Current action: execute Milestone 101.
- Active executor milestone:
  `Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice`.
- Active run prompt:
  `docs/agent/runs/m101-execution-review-loop-prompt.md`.
- Boundary reminders:
  - M101 is behavior-preserving architecture/consolidation work.
  - M101 applies only to the accepted M99/M100 backend-translation
    request/result path.
  - M101 must preserve accepted M99/M100 stage names, ordering, keys,
    diagnostics, source locations, object identities where required, public
    imports, and deterministic behavior.
  - M101 may introduce a small shared contract/provenance module only if it
    reduces repeated request/result/provenance shape without becoming a
    registry, dispatcher, callback system, plugin mechanism, broad hierarchy,
    hidden backfeed, or fixpoint mechanism.
  - M101 must not add new backend translation semantics, new request families,
    new result families, rendering, generated output, Stage 9 planning, Rust
    translation, generic backend helper evaluation, backend map/catalog/
    manifest reads during lowering, raw source parsing, source repair,
    selected-body direct-intrinsic resolution, SVE semantics, scheduling, or
    dependency closure.
- Follow-up: if M101 cannot consolidate the M99/M100 path without semantic
  risk, record the blocker in `docs/redesign/open-questions.md` and stop
  before speculative abstraction.

Create the M101 execution-review-loop prompt under:

```text
docs/agent/runs/m101-execution-review-loop-prompt.md
```

The M101 prompt must specify:

- one write-capable executor;
- read-only reviewer/auditor subagents;
- scope and out-of-scope boundaries from the M101 roadmap section;
- required validation from the M101 roadmap section;
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
5. Whether the repo is ready to execute M101 after acceptance finalization.
