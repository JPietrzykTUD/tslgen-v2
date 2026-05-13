# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 47 is accepted.

Latest accepted slice:

- Milestone 47: Native Integer Add Parity Slice.
- M47 renders the selected C++ AVX2 integer `binary/add` output only by
  consuming explicit M45 suffix and M46 type-spelling translated values.
- M47 must not be used as a pattern for broad native rendering.

## Current Work State

Current required action:

```text
Plan the next numbered milestone after M47.
```

Use:

```text
docs/agent/runs/post-m47-orchestrated-planning-prompt.md
```

The likely next milestone is a narrow signedness/type-predicate generation-time
branch-pruning slice over typed M43 values, but Codex must confirm the evidence
and update the roadmap before any implementation begins.

## Current Boundary Rules

- `frozen/` is evidence only and must never become runtime input.
- M43 produces backend-neutral `GenerationTypeRef` values.
- M45 produces explicit intrinsic suffix modifier values such as `epi32`.
- M46 produces explicit backend type-spelling values such as `int32_t` and
  `uint32_t`.
- M47 consumes M45 and M46 translated values for the selected native integer add
  output.
- Renderers must not infer suffixes, type spellings, generation-time helper
  semantics, or backend modifier semantics.
- Backend translation must not parse raw `type<generation>(...)` text.
- Future semantic behavior must be expressed as typed rules or typed evaluator
  functions over explicit IR/domain values.

## Next Planning Goal

Create a formal Milestone 48 section or an explicitly justified alternative.

The expected candidate is:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

The slice should remain generation-time semantic lowering only. It should not
combine branch pruning with backend modifier translation or output rendering.

## Validation Expectations

For docs-only planning tasks:

```bash
git diff --check
```

For implementation milestones, run the milestone-specific targeted tests plus:

```bash
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

## Repository-State Note

Some handoff archives intentionally omit `frozen/` and TSL corpus file contents.
Docs may still cite those paths as evidence, but implementation and tests must
not require `frozen/` as runtime input.
