# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 56 is accepted.

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

Post-M50 planning is accepted. It selected Milestone 51, and internal review
returned `Accept With Follow-Ups` after local planning-doc corrections.

The M51 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M51 planning is accepted. It selected Milestone 52, and internal review
returned `Accept With Follow-Ups` after a workflow handoff correction.

The M52 execution-review loop returned `Accept With Follow-Ups` after a
documentation wording cleanup.

Post-M52 planning is accepted. It selected Milestone 53, and internal review
returned `Accept With Follow-Ups` after a workflow handoff wording correction.

The M53 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M53 planning is accepted. It selected Milestone 54, and internal review
returned `Accept With Follow-Ups` after a workflow handoff correction.

The M54 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M54 planning is accepted. It selected Milestone 55, and internal review
returned `Accept With Follow-Ups` after local planning-doc updates.

The M55 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M55 planning is accepted. It selected Milestone 56, and internal review
returned `Accept With Follow-Ups` after local planning-doc corrections.

The M56 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

## Current Work State

Current required action:

```text
Run the post-M56 planning-plus-review prompt.
```

Active run prompt:

```text
docs/agent/runs/post-m56-planning-plus-review-prompt.md
```

Active executor milestone:

```text
None. Milestone 57 has not been selected. The active prompt is a docs-only
post-M56 planning pass.
```

Latest review verdict:

```text
M56 execution-review loop: Accept With Follow-Ups
```

Next expected action:

```text
Execute the active post-M56 planning-plus-review prompt. Do not implement code
unless a later accepted planning result explicitly selects an executor task.
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

Accepted post-M50 acceptance finalization prompt:

```text
docs/agent/runs/post-m50-acceptance-finalization-prompt.md
```

Accepted M51 execution prompt:

```text
docs/agent/runs/m51-execution-review-loop-prompt.md
```

Accepted post-M51 planning prompt:

```text
docs/agent/runs/post-m51-planning-plus-review-prompt.md
```

Accepted post-M51 acceptance finalization prompt:

```text
docs/agent/runs/post-m51-acceptance-finalization-prompt.md
```

Accepted M52 execution prompt:

```text
docs/agent/runs/m52-execution-review-loop-prompt.md
```

Accepted post-M52 planning prompt:

```text
docs/agent/runs/post-m52-planning-plus-review-prompt.md
```

Accepted post-M52 acceptance finalization prompt:

```text
docs/agent/runs/post-m52-acceptance-finalization-prompt.md
```

Accepted M53 execution prompt:

```text
docs/agent/runs/m53-execution-review-loop-prompt.md
```

Accepted post-M53 planning prompt:

```text
docs/agent/runs/post-m53-planning-plus-review-prompt.md
```

Accepted post-M53 acceptance finalization prompt:

```text
docs/agent/runs/post-m53-acceptance-finalization-prompt.md
```

Accepted M54 execution prompt:

```text
docs/agent/runs/m54-execution-review-loop-prompt.md
```

Accepted post-M54 planning prompt:

```text
docs/agent/runs/post-m54-planning-plus-review-prompt.md
```

Accepted post-M54 acceptance finalization prompt:

```text
docs/agent/runs/post-m54-acceptance-finalization-prompt.md
```

Accepted M55 execution prompt:

```text
docs/agent/runs/m55-execution-review-loop-prompt.md
```

Accepted post-M55 planning prompt:

```text
docs/agent/runs/post-m55-planning-plus-review-prompt.md
```

Accepted post-M55 acceptance finalization prompt:

```text
docs/agent/runs/post-m55-acceptance-finalization-prompt.md
```

Accepted M56 execution-review loop prompt:

```text
docs/agent/runs/m56-execution-review-loop-prompt.md
```

Active post-M56 planning prompt:

```text
docs/agent/runs/post-m56-planning-plus-review-prompt.md
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
- M51 is generation-time semantic lowering only.
- M51 accepts only the exact signedness predicate branch form
  `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
  with plain `else`.
- M51 reuses M48 signedness predicate evaluation over typed M43
  `GenerationTypeRef(kind="base.in")` inputs.
- M51 reuses M42/M48 branch pruning, deterministic provenance, and
  selected-branch-only diagnostics.
- M51 treats plain `else` as equivalent to `else<generation>` only for this
  selected signedness predicate branch form.
- M51 must preserve existing `else<generation>` signedness branch behavior.
- M51 must not add broad plain-`else` support for arbitrary generation
  branches.
- M51 must not add primitive-attribute plain `else` support.
- M51 must not add conversion or shift body parity.
- M51 must not add `switch<compile>`, `if<compile>`, direct `intrin<...>`,
  `let`, `var`, calls, vector transforms, loops, aliases, casts, arrays,
  generic lengths, immediates, vector/register metadata, backend translation,
  backend rendering, generated C++ output, generated test sources, Rust output,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, broad TSIL parsing, or branch-body semantics.
- M51 must not broaden signedness predicates beyond the selected M43
  `si32`/`ui32` `base.in` inputs.
- `tsldata/primitives/conversion/repr_change.tsl:1210-1217` is selected M51
  branch-shape evidence only. Its enclosing `switch<compile>` and branch
  bodies remain out of scope.
- `frozen/` remains evidence only.
- M52 is generation-time semantic lowering only.
- M52 extends only the accepted M43/M48/M51 concrete integer
  type/signedness semantics from `si32`/`ui32` to the selected concrete integer
  tags `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64`.
- M52 supports only the exact M43 type query forms
  `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`, and
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`.
- M52 supports only the exact M48/M51 signedness predicate branch forms
  over typed `GenerationTypeRef(kind="base.in")` inputs, with
  `else<generation>` or the M51 plain `else` spelling.
- M52 must express signed/unsigned companion behavior as typed rules or typed
  evaluator functions, not raw text rewriting.
- M52 must keep wildcard/group selectors such as `?i?`, `?i64`, `si?`,
  `ui?`, and `idqword` unsupported as selected concrete type tags during
  lowering.
- M52 must not add backend translation expansion, including suffix or
  type-spelling expansion beyond accepted M45/M46 `si32`/`ui32` behavior.
- M52 must not add C++ or Rust rendering, generated output, generated
  test sources, CLI/reporting, writer behavior, compiler execution,
  generated-test execution, vector/register metadata, vector length/alignment,
  generic lengths, aliases, casts, arrays, loops, calls, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, generalized plain `else`, branch-body
  semantics, shift body parity, or conversion body parity.
- M53 is a semantic rule-source boundary slice only.
- M53 moves the accepted M52 concrete integer generation type/signedness
  semantics from a lowering-private table into typed domain/catalog rule values
  consumed by lowering.
- M53 must preserve behavior exactly for
  `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`,
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`, and the
  exact M48/M51 signedness predicate branch forms.
- M53 must preserve exactly the selected concrete tags `si8`, `ui8`, `si16`,
  `ui16`, `si32`, `ui32`, `si64`, and `ui64`.
- M53 must preserve M52 diagnostics, deterministic ordering, branch provenance,
  and selected-branch-only diagnostics unless a narrower rule-source diagnostic
  is required for missing or inconsistent rule data.
- M53 must preserve backend-translation rejection of raw unresolved generation
  helpers and renderer non-evaluation.
- M53 must preserve M45/M46 backend translation limits and must not expand
  suffix or type-spelling translation beyond accepted selected `si32`/`ui32`
  behavior.
- M53 must not infer broad integer semantics from regex or tag spelling alone.
- M53 must not treat wildcard/group selectors such as `?i?`, `?i64`, `si?`,
  `ui?`, and `idqword` as selected concrete type tags during lowering.
- M53 must not add new generation-time helper forms, backend translation
  expansion, C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, vector/register metadata, vector length/alignment, generic
  lengths, aliases, casts, arrays, loops, calls, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, generalized plain `else`, branch-body
  semantics, broad TSIL parsing, or runtime dependency on `frozen/`.
- M54 is a pipeline/lowering-input wiring slice only.
- M54 wires the accepted M53 `ConcreteIntegerGenerationRuleSet` through
  the normal catalog/lowering-input path for pipeline-facing use.
- M54 must build or expose concrete integer generation rules from typed
  catalog/type-group data before lowering evaluation.
- M54 must preserve all accepted M52/M53 type-query and signedness
  branch behavior, diagnostics, deterministic ordering, branch provenance, and
  selected-branch-only diagnostics unless an explicit catalog-derived
  rule-source diagnostic is required.
- M54 must prove explicit catalog-derived rule data is consumed by
  lowering and that missing or inconsistent explicit rule data is not hidden by
  a synthetic default fallback.
- M54 must preserve M45/M46 backend translation limits and must not
  expand suffix or type-spelling translation beyond accepted selected
  `si32`/`ui32` behavior.
- M54 must not add new generation-time helper forms, backend translation
  expansion, C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, vector/register metadata, vector length/alignment, generic
  lengths, aliases, casts, arrays, loops, calls, direct `intrin<...>`,
  `switch<compile>`, `if<compile>`, generalized plain `else`, branch-body
  semantics, broad TSIL parsing, broad generic semantic-rule registries, or
  runtime dependency on `frozen/`.
- M54 must not make lowering read files, parse raw TSL, query the
  catalog during evaluation, or infer broad integer semantics from regex, tag
  spelling, wildcard/group selectors, or concrete-looking unselected tags.
- M55 is generation-time semantic lowering only.
- M55 selects exactly
  `value<generation>(type::size_bytes(type<generation>(base::in)))`.
- M55 produces typed integer generation values for explicit selected
  scalar tags: `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, `ui64`,
  `f32`, and `f64`.
- M55 must use explicit scalar size-byte rule/value records and must
  not reuse or mutate `ConcreteIntegerGenerationRuleSet` for float size
  semantics.
- M55 accepts `f32` and `f64` only for the exact size-bytes value query
  and must not broaden standalone `type<generation>(base::in)` or
  signed/unsigned companion behavior to floats.
- M55 must not infer sizes from regex, tag spelling, wildcard/group
  selectors, or unselected concrete-looking tags such as `si128`.
- M55 must not add arithmetic or comparisons over generation values,
  branch pruning from size values, enclosing body lowering, backend
  translation expansion, rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, Rust, compiler execution, generated-test
  execution, vector/register metadata, loops, casts, calls, direct
  `intrin<...>`, broad TSIL parsing, or runtime dependency on `frozen/`.
- M55 must not make lowering read files, parse raw TSL, or query the
  catalog during evaluation.
- M56 is generation-time semantic lowering only.
- M56 selects exactly
  `value<generation>(type::size_bytes(type<generation>(base::in))) * 8`.
- M56 consumes the M55 typed `GenerationValue(kind="type.size_bytes")`
  behavior and explicit scalar size-byte rules to produce typed scalar
  bit-width generation values.
- M56 must not add general arithmetic, operators other than the exact
  selected `* 8` expression, reversed operands, arbitrary literals,
  comparisons such as `== 2`, branch pruning, `else if<generation>`,
  branch-chain syntax, surrounding body lowering, backend translation,
  rendering, generated output, generated test sources, CLI/reporting, writer
  behavior, Rust, compiler execution, generated-test execution,
  vector/register metadata, broad TSIL parsing, or runtime dependency on
  `frozen/`.
- M56 must not make lowering read files, parse raw TSL, or query the
  catalog during evaluation.

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

## Accepted Milestone 51

The Milestone 51 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 51: Plain-Else Signedness Generation Branch Lowering Slice
```

The slice is generation-time semantic lowering only. It extends the accepted
M48 signedness predicate branch pruning behavior to the documented plain
`else` form for the exact M48 predicate over typed M43 `base.in` values.
`PrunedGenerationBranch` records the accepted else syntax, and existing
`else<generation>` signedness branch behavior remains supported. Backend
translation, rendering, output generation, CLI/report/writer behavior, Rust,
compiler execution, generated-test execution, conversion body lowering, and
broader TSIL/plain-`else` support remain out of scope.

## Accepted Milestone 52

The Milestone 52 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 52: Concrete Integer Generation Type Semantics Slice
```

The slice is generation-time semantic lowering only. It extends the accepted
M43/M48/M51 concrete integer type and signedness semantics from `si32`/`ui32`
to `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64` for the
existing exact M43 type query forms and the existing exact M48/M51 signedness
predicate branch forms. Signed/unsigned companion behavior is expressed through
typed concrete-integer rules. Wildcard/group selectors remain unsupported as
selected concrete type tags. Backend suffix/type-spelling translation remains
limited to accepted M45/M46 `si32`/`ui32` behavior, and M52 adds no rendering,
generated output, generated test sources, CLI/reporting, writer behavior, Rust,
compiler execution, vector/register metadata, branch-body semantics, or broad
TSIL parsing.

## Accepted Milestone 53

The Milestone 53 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 53: Catalog-Validated Concrete Integer Generation Rule Source Slice
```

The slice is a semantic rule-source boundary only. It moves the accepted M52
concrete integer generation type/signedness semantics from a lowering-private
table into typed `ConcreteIntegerGenerationRuleSet` / rule values in the domain
layer, consumed by lowering through `GenerationContext`. It preserves M52
`GenerationTypeRef` outputs, signedness branch pruning, diagnostics,
deterministic ordering, branch provenance, and selected-branch-only diagnostics
for `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64`.
Wildcard/group selectors and concrete-looking unselected tags remain
unsupported. M53 adds no new generation-time helper forms, backend translation
expansion, rendering, generated output, generated test sources, CLI/reporting,
writer behavior, Rust, compiler execution, broad TSIL parsing, or runtime
dependency on `frozen/`.

## Accepted Milestone 54

The Milestone 54 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 54: Catalog-Derived Concrete Integer Generation Rule Pipeline Wiring Slice
```

The slice wires the accepted M53
`ConcreteIntegerGenerationRuleSet` through a normal catalog/lowering-input path
for pipeline-facing use. It exposes catalog-derived rule construction from
typed `Catalog.type_groups` and builds `LoweringRequest` values carrying those
immutable rules before lowering evaluation. It preserves M52/M53 type-query and
signedness-branch behavior, diagnostics, deterministic ordering, branch
provenance, selected-branch-only diagnostics, backend raw-helper rejection, and
renderer non-evaluation. M54 adds no new helper forms, backend translation
expansion, rendering, generated output, CLI/reporting/writer behavior, Rust,
compiler execution, broad TSIL parsing, or runtime dependency on `frozen/`.

## Accepted Milestone 55

The Milestone 55 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 55: Base Scalar Size-Bytes Generation Value Query Slice
```

The slice is generation-time semantic lowering only. It resolves exactly
`value<generation>(type::size_bytes(type<generation>(base::in)))` to typed
`GenerationValue(kind="type.size_bytes", value=<bytes>, type_tag=<tag>)`
values for selected scalar tags `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`,
`si64`, `ui64`, `f32`, and `f64`. The accepted byte values are
`si8`/`ui8 -> 1`, `si16`/`ui16 -> 2`, `si32`/`ui32`/`f32 -> 4`, and
`si64`/`ui64`/`f64 -> 8`.

M55 uses explicit scalar size-byte rule/value records derived from typed
catalog/type-group data before lowering evaluation. It preserves standalone
`type<generation>(base::in)` and signed/unsigned companion behavior as
integer-only; `f32` and `f64` are accepted only for the exact size-bytes value
query. The focused revision tightened exact-query parsing so
`value<generation>(type::size_bytes(type<generation>(base::in),))` is rejected
with a stable arity diagnostic. M55 adds no generation-value arithmetic or
comparisons, branch pruning from size values, enclosing body lowering, backend
translation expansion, rendering, generated output, generated test sources,
CLI/reporting/writer behavior, Rust, compiler execution, generated-test
execution, broad TSIL parsing, or runtime dependency on `frozen/`.

## Accepted Milestone 56

The Milestone 56 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 56: Size-Bytes Times-Eight Generation Value Arithmetic Slice
```

The slice is generation-time semantic lowering only. It resolves exactly
`value<generation>(type::size_bytes(type<generation>(base::in))) * 8` to typed
`GenerationValue(kind="type.size_bits", value=<bits>, type_tag=<tag>)` values
by reusing the accepted M55 `type.size_bytes` value and explicit scalar
size-byte rules. The accepted bit values are `si8`/`ui8 -> 8`,
`si16`/`ui16 -> 16`, `si32`/`ui32`/`f32 -> 32`, and
`si64`/`ui64`/`f64 -> 64`.

M56 preserves M55 context precedence and the M52-M55 generation-time lowering
boundaries. It adds no general arithmetic engine, operators beyond the exact
selected `* 8` form, reversed operands, arbitrary literals, comparisons,
branch pruning, `else if<generation>`, branch-chain syntax, surrounding body
lowering, backend translation, rendering, generated output, generated test
sources, CLI/reporting/writer behavior, Rust, compiler execution,
generated-test execution, vector/register metadata, broad TSIL parsing, or
runtime dependency on `frozen/`.

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
- M51 review follow-up: consider gating plain `else` earlier in the lowering
  parser for an even tighter boundary. Current behavior accepts plain `else`
  only after the condition resolves to the supported typed signedness predicate
  and rejects primitive-attribute or arbitrary plain-`else` forms, so this is
  non-blocking.
- M52 planning follow-up: the active M52 execution prompt explicitly preserves
  M45/M46 `si32`/`ui32` backend translation limits while M52 expands only
  generation-time lowering semantics.
- M52 review follow-up: consider adding location assertions for the new and
  expanded M52 diagnostic cases; current tests assert code/severity/message but
  mostly not path, line, and column.
- M53 planning follow-up: addressed in
  `docs/agent/runs/m53-execution-review-loop-prompt.md`, which explicitly
  repeats the broad TSIL parsing prohibition while moving only concrete integer
  rule-source ownership.
- M53 review follow-up addressed by M54: catalog-derived concrete integer
  generation rules are now wired through a normal catalog/lowering-input path,
  with focused tests proving lowering consumes explicit catalog-built rules
  instead of hiding bad explicit rule data behind the synthetic default.
- M53 review follow-up: consider enforcing the exact selected-tag and
  companion-pair invariants in `ConcreteIntegerGenerationRuleSet` construction
  or making validated construction the only supported path.
- M53 review follow-up: add available source locations to
  `TSL-DOMAIN-GEN-RULE-*` diagnostics when `TypeGroup` source spans are
  available, especially unsupported selected-tag diagnostics.
- M53 docs/evidence follow-up: sync broader redesign docs from selected-plan
  wording to accepted/implemented M53 wording, and consider widening
  unsupported group-selector evidence beyond `tsldata/detail/types.tsl:20-24`
  if `dword` and `qword` remain part of known unsupported group classification.
- Repo-wide evidence follow-up: `tslgen/tests/unit/test_backend_artifact_model.py`
  still reads representative legacy backend manifest YAML from `frozen/` at
  unit-test runtime. This predates M52 and M52 lowering code has no `frozen/`
  runtime dependency, but a future cleanup may replace those reads with
  redesign-owned fixtures if the strict no-`frozen/` test-runtime policy is
  applied broadly.
- M54 review follow-up: add explicit negative test subcases for `dword` and
  `qword` selected tags. The implementation already classifies them as
  unsupported group selectors; the extra tests would tighten traceability to
  `tsldata/detail/types.tsl:25-26`.
- M55 review follow-up: consider tightening the shared generation-call
  argument splitter so earlier helper families also reject empty/trailing
  arguments consistently. M55 fixed the selected value-query path with a strict
  parser and regression test.
- M55 evidence follow-up: the already-used M55 execution prompt's IO evidence
  citation can be tightened later to name `tsldata/primitives/io/out.tsl:22`
  for the float test; the roadmap citation has been corrected.
- Post-M55 planning follow-up: exact size-byte equality branch pruning over
  `== 2`, `== 4`, and `== 8` remains a strong future lowering candidate, but
  it is deferred from M56 because it also opens `else if<generation>` branch
  chain syntax and selected-branch pruning policy.
- M56 docs/evidence follow-up: normalize remaining pre-acceptance wording in
  `docs/redesign/implementation-roadmap.md`,
  `docs/redesign/behavioral-spec.md`,
  `docs/redesign/frozen-parity-baselines.md`, and related
  `docs/redesign/open-questions.md` M56 mentions.
- M56 docs follow-up: add or update the helper inventory entry for the exact
  M56 `type.size_bytes * 8` bit-width expression.
- M56 review follow-up: consider tightening the arithmetic probe so a
  non-arithmetic value query with an unmatched closing parenthesis keeps M55
  malformed-query diagnostics separate from M56 arithmetic diagnostics.
- M56 test follow-up: add an explicit chained/mixed arithmetic rejection case,
  such as a `* 8 * 2` expression after the selected size-bytes value query.

## Stop Condition

No stop condition is active. The workflow proceeds with the active post-M56
planning-plus-review prompt. Do not start Milestone 57 until that planning
prompt has selected a next milestone and the selected plan has been accepted.

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
