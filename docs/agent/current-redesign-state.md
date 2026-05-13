# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 47 is accepted.

## Current Work State

Current required action:

```text
Human review/acceptance of the formal M48 planning pass. Do not implement M48
until the plan is accepted.
```

Primary prompt:

```text
docs/agent/runs/post-m47-orchestrated-planning-plus-review-prompt.md
```

This prompt has been run as the planning source for M48.

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
- Planned M48 consumes typed M43 `GenerationTypeRef(kind="base.in")` values for
  signedness predicate branch pruning and remains generation-time semantic
  lowering only.

## Selected Next Milestone Candidate

The post-M47 planning pass selected:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

The slice remains generation-time semantic lowering only. It evaluates the
exact
`if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
plus `else<generation>` form over typed M43 `base.in` values. It does not
combine branch pruning with backend modifier translation, output rendering,
plain `else` conversion syntax, or broad shift/conversion body lowering.

## Known Follow-Ups

- Human acceptance is still required before execution.
- The retried evidence audit confirmed additional exact shift evidence ranges:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is predicate
  evidence only because it uses plain `else`, not `else<generation>`.

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
