# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 50 is accepted.

Post-M47 planning is accepted. The accepted planning result selected
Milestone 48, and the M48 execution-review loop returned `Accept`.

Post-M48 planning is accepted. It selected Milestone 49, and internal review
accepted the plan after local planning-doc revisions.

The M49 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M49 planning is accepted. It selected Milestone 50, and internal review
returned `Accept With Follow-Ups` after local planning-doc corrections.

The M50 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

## Current Work State

Current required action:

```text
Await human acceptance of the post-M50 planning update.
```

Active run prompt:

```text
docs/agent/runs/post-m50-acceptance-finalization-prompt.md
```

Active planning target:

```text
Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice
```

Next expected action:

```text
After explicit human acceptance, the finalization prompt creates
docs/agent/runs/m51-execution-review-loop-prompt.md and updates this state file
to make M51 execution active.
```

Accepted planning prompt:

```text
docs/agent/runs/post-m47-orchestrated-planning-plus-review-prompt.md
```

Accepted post-M48 planning prompt:

```text
docs/agent/runs/post-m48-planning-plus-review-prompt.md
```

Accepted M49 execution prompt:

```text
docs/agent/runs/m49-execution-review-loop-prompt.md
```

Accepted post-M49 planning prompt:

```text
docs/agent/runs/post-m49-planning-plus-review-prompt.md
```

Accepted post-M49 acceptance finalization prompt:

```text
docs/agent/runs/post-m49-acceptance-finalization-prompt.md
```

Accepted M50 execution prompt:

```text
docs/agent/runs/m50-execution-review-loop-prompt.md
```

Accepted post-M50 planning prompt:

```text
docs/agent/runs/post-m50-planning-plus-review-prompt.md
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
- M49 is generated C++ test-source rendering only. It consumes typed
  `TestSourcePlan` / `PlannedTestCase` values for the selected scalar
  `add_i32_basic` case plus explicit typed C++ type-spelling input for
  `si32 -> int32_t`.
- M49 must not compile or run generated tests, fetch or require `gtest`, read
  legacy templates at runtime, infer type spellings locally, broaden
  generated-test parity, or modify generation-time lowering, backend
  translation, generated implementation output rendering, CLI/report/writer,
  Rust, or compiler execution behavior.
- M50 is reporting-adapter work only.
- M50 is selected-row only: primitive `add`, extension `avx2`, language `cpp`,
  and type `f32`.
- M50 produces only the selected legacy coverage JSON row adapter.
- M50 consumes accepted `PipelineCoverageReport` / primitive coverage DTOs or
  equivalent typed report data, plus a new M50 typed adapter request and
  selected-row fact value carrying the exact selected legacy-row facts.
- Legacy string-valued booleans are adapter/serialization output only; internal
  report values must remain typed.
- M50 must not implement whole `primitive_coverage.json` parity, row-count
  parity, broad coverage matrix parity, coverage HTML/site parity, CLI workflow
  compatibility, new CLI flags, writer/report file writes, backend rendering,
  generation-time lowering, backend translation, generated C++ implementation
  output, test-source rendering, Rust output, compiler execution, or
  generated-test execution.
- M50 must not read `frozen/`, legacy report tools, raw legacy JSON, or raw TSL
  at runtime.
- M50 must not rerun parsing, selection, lowering, backend rendering, or test
  planning during adapter serialization.
- Planned M51 is generation-time semantic lowering only.
- Planned M51 accepts only the exact signedness predicate branch form
  `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
  with plain `else`.
- Planned M51 reuses M48 signedness predicate evaluation, M42 branch provenance,
  and typed M43 `GenerationTypeRef(kind="base.in")` inputs.
- Planned M51 treats `tsldata/primitives/conversion/repr_change.tsl:1210-1217`
  as branch-shape evidence only. Conversion body lowering remains out of scope.
- Planned M51 must not add backend translation, rendering, generated output,
  shift/conversion body parity, `switch<compile>`, `if<compile>`, direct
  `intrin<...>`, `let`, `var`, calls, vector transforms, loops, generic
  lengths, vector/register metadata, Rust, CLI/reporting, compiler execution,
  generated-test execution, broad TSIL parsing, or broad plain-`else` support.

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

## Accepted Milestone 49

The Milestone 49 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 49: Generated C++ Add I32 Test Source Parity Slice
```

The slice renders exactly one deterministic C++ `production_tests` artifact for
`add_i32_basic` at logical path `tests/add_i32_basic_test.cpp`. It consumes
typed `TestSourcePlan` / `PlannedTestCase` data plus explicit typed C++
type-spelling input for `si32 -> int32_t`; the renderer does not infer type
spellings, rescan raw TSL text, read or execute legacy templates, compile or run
generated tests, fetch or require `gtest`, or broaden generated-test parity.

## Accepted Milestone 50

The Milestone 50 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 50: Legacy Coverage JSON Adapter Row Slice
```

The slice renders exactly one deterministic legacy-style coverage JSON adapter
row for `add` / `avx2` / `cpp` / `f32`. It consumes typed
`PipelineCoverageReport` / `PrimitiveCoverageRow` data plus a selected typed
adapter request, produces a typed `LegacyCoverageSelectedRowFact`, and emits
legacy string-valued booleans only at the JSON serialization boundary. It
rejects aggregate primitive rows that would infer a selected row by cross
product and rejects unsupported direct row-fact serialization.

M50 remains reporting-adapter work only. It does not implement whole
`primitive_coverage.json` parity, row-count parity, broad coverage matrix
parity, HTML/site parity, CLI/report writing, backend rendering,
generation-time lowering, backend translation, generated C++ implementation
output, test-source rendering, Rust output, compiler execution, generated-test
execution, or runtime reads from `frozen/`, raw legacy JSON, or raw TSL.

## Known Follow-Ups

- Older post-M34 wording around "do not define M35 yet" may be cleaned up
  later. This is non-blocking for current planning.
- The retried evidence audit confirmed additional exact shift evidence ranges:
  `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`,
  `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is selected M51
  branch-shape evidence only because it uses the M48 signedness predicate with
  plain `else`. Its enclosing `switch<compile>` and branch bodies remain
  out-of-scope conversion evidence.
- M49 review follow-up: harden the no-file-read regression so it also catches
  `pathlib.Path.read_text()` style reads; source inspection found the renderer
  pure/in-memory, so this is non-blocking.
- M49 review follow-up: consider deduplicating descriptor diagnostics for
  malformed descriptor cardinality in C++ test-source rendering.
- M49 docs follow-up: consider syncing `testing-strategy.md` with the full M49
  diagnostic list, including wrong selected-case cardinality and unsupported
  legacy-test features.
- M49 docs follow-up: clarify behavioral-spec wording that slightly conflates
  rendered artifact logical path with committed golden fixture path.
- M49 evidence follow-up: consider extending the `test_common.j2` evidence
  range if a future doc wants to claim the full macro closing shape.
- M50 review follow-up: harden the no-file-read regression so it wraps the full
  `selected_legacy_coverage_row_to_json(...)` adapter path, not only direct
  row-fact serialization. Source inspection and focused boundary review found
  the adapter pure/in-memory, so this is non-blocking.
- M50 evidence follow-up: consider adding an explicit active source/report data
  note to `add_avx2_f32_coverage_row.provenance.md`. Existing selected legacy
  row, field-construction evidence, and redesign baseline citations were
  accepted for M50.
- M51 planning follow-up: before execution, clarify whether
  `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is the canonical
  fixture and the broader `repr_change.tsl` ranges are supporting evidence
  only. This is non-blocking for human acceptance.
- M51 docs follow-up: tighten `generation-time-semantic-lowering.md` wording
  that says "report parity" remains deferred so it clearly means broad report
  parity beyond the accepted M50 selected row.

## Stop Condition

No stop condition is active. The workflow proceeds with the active post-M50
acceptance finalization prompt after human acceptance.

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
