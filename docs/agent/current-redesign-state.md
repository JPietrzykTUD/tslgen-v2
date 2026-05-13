# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 47 is accepted.

Post-M47 planning is accepted. The accepted planning result selected
Milestone 48 as the next executor milestone.

Milestone 48 execution is complete and awaiting review.

## Current Work State

Current required action:

```text
Review Milestone 48.
```

Active run prompt:

```text
docs/agent/runs/m48-review-prompt.md
```

Active review milestone:

```text
Milestone 48: Signedness Type-Predicate Branch Pruning Slice
```

Next expected action:

```text
Milestone 48 reviewer returns a verdict, creates the next concrete run prompt
under docs/agent/runs/, and updates this state file according to the verdict.
```

Accepted planning prompt:

```text
docs/agent/runs/post-m47-orchestrated-planning-plus-review-prompt.md
```

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
- Renderers must not evaluate generation-time helpers.
- Backend translation must not parse raw generation helper text.
- Future semantic behavior must be expressed as typed rules or typed evaluator
  functions over explicit IR/domain values.
- M48 is generation-time semantic lowering only.
- M48 consumes typed M43 `GenerationTypeRef(kind="base.in")` values for
  signedness predicate branch pruning.
- M48 includes no backend translation, rendering, generated output,
  CLI/report/writer, Rust, or compiler execution work.

## Active Review Milestone

The Milestone 48 executor implemented:

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

- Older post-M34 wording around "do not define M35 yet" may be cleaned up
  later. This is non-blocking for M48 review and acceptance.
- The retried evidence audit confirmed additional exact shift evidence ranges:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is predicate
  evidence only because it uses plain `else`, not `else<generation>`.

## Stop Condition

No stop condition is active. The workflow proceeds with the active M48 review
prompt.

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
