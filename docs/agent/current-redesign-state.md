# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 48 is accepted.

Post-M47 planning is accepted. The accepted planning result selected
Milestone 48, and the M48 execution-review loop returned `Accept`.

Post-M48 planning selected Milestone 49 and internal review accepted the plan
after local planning-doc revisions.

Post-M48 planning is awaiting human acceptance before M49 execution is
activated.

## Current Work State

Current required action:

```text
Finalize human acceptance of the post-M48 planning update.
```

Active run prompt:

```text
docs/agent/runs/post-m48-acceptance-finalization-prompt.md
```

Active planning target:

```text
Milestone 49: Generated C++ Add I32 Test Source Parity Slice
```

Next expected action:

```text
After explicit human acceptance, the finalization prompt creates
docs/agent/runs/m49-execution-review-loop-prompt.md and updates this state file
to make M49 execution active.
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
- Planned M49 is generated C++ test-source rendering only. It consumes typed
  `TestSourcePlan` / `PlannedTestCase` values for the selected scalar
  `add_i32_basic` case plus explicit typed C++ type-spelling input for
  `si32 -> int32_t`.
- Planned M49 must not compile or run generated tests, fetch or require `gtest`,
  read legacy templates at runtime, infer type spellings locally, broaden
  generated-test parity, or modify generation-time lowering, backend
  translation, generated implementation output rendering, CLI/report/writer,
  Rust, or compiler execution behavior.

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
- Post-M48 planning human acceptance is required before executor work begins.

## Stop Condition

No stop condition is active. The workflow proceeds with the active post-M48
acceptance finalization prompt.

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
