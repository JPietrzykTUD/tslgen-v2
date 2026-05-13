# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 48 is accepted.

Post-M47 planning is accepted. The accepted planning result selected
Milestone 48, and the M48 execution-review loop returned `Accept`.

No Milestone 49 is selected yet.

## Current Work State

Current required action:

```text
Run post-M48 planning plus review.
```

Active run prompt:

```text
docs/agent/runs/post-m48-planning-plus-review-prompt.md
```

Active planning target:

```text
Select the next numbered milestone after Milestone 48, or explicitly defer.
```

Next expected action:

```text
The post-M48 planning-plus-review prompt proposes the next milestone, runs
internal planning review subagents, and records the accepted planning result
or a focused planning revision prompt.
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

## Accepted Milestone 48

The Milestone 48 execution-review loop accepted:

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
  later. This is non-blocking for post-M48 planning.
- The retried evidence audit confirmed additional exact shift evidence ranges:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is predicate
  evidence only because it uses plain `else`, not `else<generation>`.

## Stop Condition

No stop condition is active. The workflow proceeds with the active post-M48
planning-plus-review prompt.

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
