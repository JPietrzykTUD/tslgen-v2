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
Review the post-M47 planning packet. If accepted, execute Milestone 48.
```

Planning prompt used:

```text
docs/agent/runs/post-m47-orchestrated-planning-prompt.md
```

The post-M47 orchestrated planning pass selects a narrow
signedness/type-predicate generation-time branch-pruning slice over typed M43
values. The roadmap and supporting docs now contain a formal Milestone 48 plan.

## Current Boundary Rules

- `frozen/` is evidence only and must never become runtime input.
- M43 produces backend-neutral `GenerationTypeRef` values.
- M45 produces explicit intrinsic suffix modifier values such as `epi32`.
- M46 produces explicit backend type-spelling values such as `int32_t` and
  `uint32_t`.
- M47 consumes M45 and M46 translated values for the selected native integer add
  output.
- M48, if accepted for execution, evaluates only the exact
  `type::is_signed(type<generation>(base::in))` generation-time predicate over
  typed M43 `GenerationTypeRef(kind="base.in")` values and prunes the selected
  branch in semantic lowering.
- Renderers must not infer suffixes, type spellings, generation-time helper
  semantics, or backend modifier semantics.
- Backend translation must not parse raw `type<generation>(...)` text.
- Future semantic behavior must be expressed as typed rules or typed evaluator
  functions over explicit IR/domain values.

## Selected Next Milestone

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

The slice should remain generation-time semantic lowering only. It should not
combine branch pruning with backend modifier translation or output rendering.
It should not accept bare `else`, broaden to `type::is_same` or
`type::is_integral`, or render shift/conversion output without a later explicit
milestone.

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
