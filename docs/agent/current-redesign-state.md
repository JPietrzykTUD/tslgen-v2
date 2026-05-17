# Current Redesign State

This file is the handoff state for Codex tasks. It is intentionally concise and
must be updated after accepted milestones, accepted documentation corrections,
or accepted planning passes.

## Accepted Through

Milestone 65 is accepted.

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

Post-M56 planning is accepted after user-requested revision. It selected
`Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice`. The
roadmap also records draft staged-lowering follow-on candidates for a stage
pipeline boundary, branch-chain pruning, and opaque selected-body handoff; they
are not active for execution.

The M57 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M57 planning is accepted. It selected
`Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice`, and
internal review returned `Accept With Follow-Ups` after local state wording
corrections.

A user-requested workflow correction sharpened the M58 handoff: the generated
M58 execution prompt must require an extendable, maintainable typed lowering
stage contract, not a cosmetic wrapper or broad central string evaluator.

The M58 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M58 planning selected
`Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice`, and
internal review returned `Needs Revision` only for workflow handoff wording
that was corrected locally.

Post-M58 planning is accepted. It selected
`Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice`.

The M59 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M59 planning selected
`Milestone 60: Opaque Selected Branch Body Handoff Slice`, and internal review
returned `Accept With Follow-Ups` after workflow handoff corrections.

Post-M59 planning is accepted. It selected
`Milestone 60: Opaque Selected Branch Body Handoff Slice`.

The M60 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M60 planning is accepted. It selected
`Milestone 61: Selected Branch Body Assignment Form Recognition Slice`, and
internal review returned `Accept With Follow-Ups` after local state wording
corrections.

The M61 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M61 planning selected
`Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice`, and
internal review returned `Accept With Follow-Ups` after local planning-doc
updates.

Post-M61 planning is accepted. It selected
`Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice`.

The M62 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

Post-M62 planning selected
`Milestone 63: Backend-Neutral Selected Body Envelope IR Slice`, and internal
review returned `Accept With Follow-Ups` after local planning-doc updates.

Post-M62 planning is accepted. It selected
`Milestone 63: Backend-Neutral Selected Body Envelope IR Slice`.

The M63 execution-review loop returned `Accept With Follow-Ups` with no
blocking implementation issues and no focused revision.

Post-M63 planning selected
`Milestone 64: Exact Array Body Envelope Slot Assembly Slice`, and internal
review returned `Accept With Follow-Ups` after local planning-doc updates.

Post-M63 planning is accepted. It selected
`Milestone 64: Exact Array Body Envelope Slot Assembly Slice`.

The M64 execution-review loop returned `Accept With Follow-Ups` after one
focused revision.

Post-M64 planning selected
`Milestone 65: Exact Array Body Envelope Pipeline Integration Slice`, and
internal review returned `Accept With Follow-Ups` after a focused workflow
handoff correction.

Post-M64 planning is accepted. It selected
`Milestone 65: Exact Array Body Envelope Pipeline Integration Slice`.

The M65 execution-review loop returned `Accept With Follow-Ups` after one
focused documentation revision.

## Current Work State

Current required action:

```text
Plan the next lowering-focused milestone after Milestone 65.
```

Active run prompt:

```text
docs/agent/runs/post-m65-planning-plus-review-prompt.md
```

Active executor milestone:

```text
None. Current task is post-M65 planning.
```

Latest review verdict:

```text
The M65 execution-review loop returned Accept With Follow-Ups after a focused
documentation revision. M65 is accepted.
```

Next expected action:

```text
Run the active post-M65 planning-plus-review prompt. Focus the next task on
lowering. Use the specified planning/review subagents, do not implement code,
and do not start M66 execution.
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

Accepted post-M56 planning prompt:

```text
docs/agent/runs/post-m56-planning-plus-review-prompt.md
```

Accepted post-M56 acceptance finalization prompt:

```text
docs/agent/runs/post-m56-acceptance-finalization-prompt.md
```

Accepted M57 execution-review loop prompt:

```text
docs/agent/runs/m57-execution-review-loop-prompt.md
```

Accepted post-M57 planning prompt:

```text
docs/agent/runs/post-m57-planning-plus-review-prompt.md
```

Accepted post-M57 acceptance finalization prompt:

```text
docs/agent/runs/post-m57-acceptance-finalization-prompt.md
```

Accepted M58 execution-review loop prompt:

```text
docs/agent/runs/m58-execution-review-loop-prompt.md
```

Accepted post-M58 planning prompt:

```text
docs/agent/runs/post-m58-planning-plus-review-prompt.md
```

Accepted post-M58 acceptance finalization prompt:

```text
docs/agent/runs/post-m58-acceptance-finalization-prompt.md
```

Accepted M59 execution-review loop prompt:

```text
docs/agent/runs/m59-execution-review-loop-prompt.md
```

Accepted post-M59 planning prompt:

```text
docs/agent/runs/post-m59-planning-plus-review-prompt.md
```

Accepted post-M59 acceptance finalization prompt:

```text
docs/agent/runs/post-m59-acceptance-finalization-prompt.md
```

Accepted M60 execution-review loop prompt:

```text
docs/agent/runs/m60-execution-review-loop-prompt.md
```

Accepted post-M60 planning prompt:

```text
docs/agent/runs/post-m60-planning-plus-review-prompt.md
```

Accepted post-M60 acceptance finalization prompt:

```text
docs/agent/runs/post-m60-acceptance-finalization-prompt.md
```

Accepted M61 execution-review loop prompt:

```text
docs/agent/runs/m61-execution-review-loop-prompt.md
```

Completed post-M61 planning prompt:

```text
docs/agent/runs/post-m61-planning-plus-review-prompt.md
```

Accepted post-M61 acceptance finalization prompt:

```text
docs/agent/runs/post-m61-acceptance-finalization-prompt.md
```

Accepted M62 execution-review loop prompt:

```text
docs/agent/runs/m62-execution-review-loop-prompt.md
```

Completed post-M62 planning prompt:

```text
docs/agent/runs/post-m62-planning-plus-review-prompt.md
```

Accepted post-M62 acceptance finalization prompt:

```text
docs/agent/runs/post-m62-acceptance-finalization-prompt.md
```

Accepted M63 execution-review loop prompt:

```text
docs/agent/runs/m63-execution-review-loop-prompt.md
```

Completed post-M63 planning prompt:

```text
docs/agent/runs/post-m63-planning-plus-review-prompt.md
```

Accepted post-M63 acceptance finalization prompt:

```text
docs/agent/runs/post-m63-acceptance-finalization-prompt.md
```

Accepted M64 execution-review loop prompt:

```text
docs/agent/runs/m64-execution-review-loop-prompt.md
```

Completed post-M64 planning prompt:

```text
docs/agent/runs/post-m64-planning-plus-review-prompt.md
```

Accepted post-M64 acceptance finalization prompt:

```text
docs/agent/runs/post-m64-acceptance-finalization-prompt.md
```

Accepted M65 execution-review loop prompt:

```text
docs/agent/runs/m65-execution-review-loop-prompt.md
```

Active post-M65 planning prompt:

```text
docs/agent/runs/post-m65-planning-plus-review-prompt.md
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
- M57 is generation-time semantic lowering only.
- M57 selects exactly the size-byte equality generation predicates
  `value<generation>(type::size_bytes(type<generation>(base::in))) == 2`,
  `== 4`, and `== 8`.
- M57 consumes the M55 typed
  `GenerationValue(kind="type.size_bytes")` behavior and explicit scalar
  size-byte rules to produce typed boolean generation predicate values.
- M57 treats `si8`/`ui8` byte size `1` as `false` for all selected
  predicates and must not introduce branch-chain no-match policy.
- M57 must not add branch pruning, `if<generation>` parsing,
  `else if<generation>`, selected-arm/no-match provenance, direct
  `intrin<...>` calls, assignments, SVE array/load-store bodies, vector
  metadata, backend translation, rendering, generated output, generated test
  sources, CLI/reporting, writer behavior, Rust, compiler execution,
  generated-test execution, broad TSIL parsing, or runtime dependency on
  `frozen/`.
- M57 must not add standalone comparison forms outside the exact
  selected predicates, general comparison parsing, final `else`, broad
  no-final-else branch policy, or branch-body semantics.
- M57 must not make lowering read files, parse raw TSL, or query the
  catalog during evaluation.
- M58 is generation-time semantic lowering stage-boundary work only.
- M58 must introduce a genuinely extendable and maintainable typed staged
  lowering contract, not merely rename or wrap current functions and not create
  a broad central string-matching or `if`/`elif` evaluator.
- M58 must give introduced or refined stage boundaries explicit typed inputs
  and outputs suitable for future stages.
- M58 organizes the accepted M55 `GenerationValue(kind="type.size_bytes")`,
  M56 `GenerationValue(kind="type.size_bits")`, and M57
  `GenerationPredicate(kind="type.size_bytes.equals")` results so later
  control-flow pruning can consume typed results without backend/rendering
  changes or raw helper re-evaluation.
- M58 must preserve accepted M55/M56/M57 observable lowered outputs exactly and
  preserve accepted M42/M48/M51 generation branch-pruning behavior exactly.
- M58 must not add new generation-time helper semantics, new arithmetic,
  comparison, or predicate semantics, size-byte equality branch-chain pruning,
  `else if<generation>` support, no-match provenance, selected branch body
  handoff, direct `intrin<...>` / SVE body lowering, vector/register metadata,
  backend translation expansion, rendering, generated output, generated test
  sources, CLI/reporting, writer behavior, Rust, compiler execution, broad
  TSIL parsing, or runtime dependency on `frozen/`.
- M58 must not make lowering read files, parse raw TSL, or query the catalog
  during evaluation; catalog-derived rule construction must remain before
  evaluation.
- M59 is generation-time semantic lowering control-flow pruning only.
- M59 must consume typed M57/M58 predicate and stage outputs instead of
  re-evaluating raw generation helper text.
- M59 selects only the exact no-final-else SVE size-byte chain from
  `tsldata/primitives/load_store/array.tsl:107-109`, with documented
  `== 2`, `== 4`, and `== 8` arm order.
- M59 selects matching arms for byte sizes `2`, `4`, and `8`.
- M59 records explicit no-match provenance for byte size `1` without
  synthesizing a final `else`.
- M59 keeps all branch bodies opaque and must not introduce the M60 selected
  body handoff contract.
- M59 may include only the smallest typed reuse cleanup needed to avoid
  duplicating private staged-predicate assembly or re-evaluating raw helper
  text.
- M59 must preserve accepted M55/M57/M58 value, predicate, and stage outputs,
  backend raw-helper rejection, and renderer non-evaluation.
- M59 must not add broad `else if<generation>` syntax beyond the exact
  selected chain shape, final `else`, reordered chains, missing arms, duplicate
  arms, nested branches, broad no-final-else policy, standalone comparison
  evaluation, general comparison parsing, M60 opaque selected branch body
  handoff, direct `intrin<...>` / SVE body lowering, assignments, variables,
  arrays, calls, casts, loops, vector/register metadata,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting, writer
  behavior, Rust, compiler execution, broad TSIL parsing, or runtime
  dependency on `frozen/`.
- M59 must not make lowering read files, parse raw TSL, or query the catalog
  during evaluation.
- M60 is generation-time semantic lowering only.
- M60 consumes accepted typed M59 branch-chain pruning/stage output.
- M60 introduces a distinct typed opaque selected-body handoff value or
  equivalent typed stage output.
- M60 must keep branch bodies opaque.
- M60 must not parse or lower selected or unselected body semantics.
- M60 must not synthesize a selected body for byte-size `1` no-match cases.
- M60 must not invoke mini TSIL lowering or produce direct-intrinsic/SVE
  `TsilStatement` values for the branch-chain path.
- M60 must preserve backend raw-helper rejection and renderer non-evaluation.
- M60 must not add direct `intrin<...>` / SVE body lowering, assignments,
  variables, arrays, calls, casts, loops, vector/register metadata,
  `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting/writer
  behavior, Rust, compiler execution, broad TSIL parsing, runtime dependency
  on `frozen/`, lowering-time file reads, raw TSL parsing, or catalog queries
  during evaluation.
- M61 is generation-time lowering form-recognition work only.
- M61 must consume accepted typed M60 selected-body handoff outputs, not raw
  branch-chain text, raw TSL, catalog data, or `frozen/` runtime input.
- M61 may recognize only the exact selected single-statement assignment form
  from `tsldata/primitives/load_store/array.tsl:107-109`:
  `pg = intrin<svptrue_b16>();`, `pg = intrin<svptrue_b32>();`, and
  `pg = intrin<svptrue_b64>();`.
- M61 output must be typed/provenanced form metadata only, preserving target
  text, opaque RHS/direct-intrinsic token text, original body text, and
  M60 handoff identity.
- M61 must not lower assignment semantics, validate direct intrinsics, infer
  SVE predicate meaning, map byte-size literals to intrinsic suffixes, inspect
  unselected branch bodies, or synthesize a body/form for `si8`/`ui8`
  no-match cases.
- M61 must not add direct `intrin<...>` / SVE body lowering, declarations,
  variables, arrays, calls, casts, loops, multi-statement bodies,
  vector/register metadata, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting/writer
  behavior, Rust, compiler execution, broad TSIL parsing, runtime dependency
  on `frozen/`, lowering-time file reads, raw TSL parsing, or catalog queries
  during evaluation.
- M62 is accepted as generation-time lowering body-IR work only.
- M62 must consume accepted typed M61 `selected_body_form_recognition`
  outputs, not raw selected body text except as preserved provenance.
- M62 may produce unresolved typed selected assignment/direct-intrinsic body IR
  only for the exact M61-recognized single-statement form
  `pg = intrin<svptrue_b16|svptrue_b32|svptrue_b64>();`.
- M62 must expose a distinct post-form-recognition stage or typed value, such
  as `selected_body_ir_lowering`, rather than stretching M60 handoff or M61
  form-recognition metadata into a mixed dispatcher.
- M62 must preserve target text, direct-intrinsic token text, original RHS/body
  text, selected type/literal, and provenance as typed IR facts.
- M62 must not validate intrinsic names, infer SVE predicate meaning, prove
  `pg` scope/type, map byte-size literals to `svptrue_b*` tokens, create
  backend intrinsic IR, create backend translation requests, feed renderers, or
  emit generated output.
- M62 must not add broad assignment semantics, broad direct `intrin<...>`
  lowering, non-zero-argument calls, declarations, variables, arrays, stores,
  casts, loops, multi-statement bodies, `emit_return`, vector/register
  metadata, `value<generation>(vector::length)`,
  `value<generation>(vector::alignment)`, backend uninit values, backend
  translation, rendering, output, generated tests, CLI/reporting/writer
  behavior, Rust, compiler execution, broad TSIL parsing, runtime dependency
  on `frozen/`, lowering-time file reads, raw TSL parsing, or catalog queries
  during evaluation.
- M63 is generation-time lowering/body-envelope IR work only.
- M63 must consume only accepted typed M62 `selected_body_ir_lowering` outputs
  or equivalent typed M62 values: `SelectedAssignmentDirectIntrinsicBodyIr`
  and `NoSelectedAssignmentDirectIntrinsicBodyIr`.
- M63 must expose a distinct post-M62 stage or typed value, such as
  `selected_body_envelope_lowering`, rather than stretching M62 body IR into a
  mixed dispatcher.
- M63 must produce a backend-neutral selected-body envelope with deterministic
  ordering. For selected cases, the typed sequence is exact and singleton,
  wrapping only the existing M62 selected assignment/direct-intrinsic body IR.
- M63 must produce an explicit no-body envelope for M62 no-body-IR cases
  without synthesizing statements or body text.
- M63 may preserve M62 target text, direct-intrinsic token text, explicit
  empty argument list, original RHS/body text, selected type/literal, source
  location, branch identity, and provenance as typed facts.
- SVE-looking corpus text is evidence only. M63 must not make `svptrue_b*`,
  `pg`, `svbool_t`, `svst1`, vector metadata, backend uninit values, or
  `emit_return` architectural concepts or semantic rules.
- M63 must not parse preserved body text to derive semantics, validate direct
  intrinsics, infer SVE predicate/vector semantics, map byte sizes to
  intrinsic tokens, add assignment binding, declaration handling, variable
  scope, array/store/return lowering, vector length/alignment, backend
  translation, rendering, output, generated tests, CLI/report/writer behavior,
  Rust, compiler execution, broad TSIL parsing, lowering-time file reads, raw
  TSL parsing, catalog queries, runtime `frozen/` use, dictionaries/raw string
  keys as downstream semantic models, or backend-specific branches in the
  envelope stage.
- M64 is generation-time lowering/body-envelope slot assembly work only.
- M64 must consume accepted typed M63 `selected_body_envelope_lowering`
  outputs or equivalent typed M63 envelope values:
  `SelectedBodyEnvelopeIr` and `NoSelectedBodyEnvelopeIr`.
- M64 may assemble only the exact ordered structural array-body skeleton
  evidenced by `tsldata/primitives/load_store/array.tsl:105-111`.
- M64 must produce deterministic typed opaque slots around one selected-body
  slot that references the M63 envelope. Slot labels are structural/
  provenance labels only, not semantic statement kinds.
- M64 must not loosen M63's singleton selected-body envelope invariant or
  synthesize selected branch text for `si8`/`ui8` no-body cases.
- SVE-looking corpus text is evidence only. M64 must not make `svbool_t`,
  `pg`, `svptrue_b*`, `svst1`, `tmp.data()`, vector metadata, backend uninit
  values, or `emit_return` architectural concepts or semantic rules.
- M64 must not add declaration semantics, assignment binding, variable scope,
  array semantics, direct-intrinsic semantics, SVE predicate/vector semantics,
  byte-size-to-token inference, store semantics, return semantics, vector
  length/alignment evaluation, backend uninit semantics, backend translation,
  rendering, output, generated tests, CLI/report/writer behavior, Rust,
  compiler execution, broad TSIL parsing, lowering-time file reads, raw TSL
  parsing, catalog queries, runtime `frozen/` use, dictionaries/raw string keys
  as downstream semantic models, or backend-specific branches.
- M65 is generation-time lowering pipeline-integration work only.
- M65 must consume accepted M63 selected/no-body envelopes and accepted M64
  `ExactArrayBodyEnvelopeSkeleton` values supplied in memory.
- M65 must key skeleton lookup by typed candidate id, selected type tag, and
  branch-chain identity, not by raw body text.
- M65 must call the accepted M64 `assemble_exact_array_body_envelope` boundary,
  populate `LoweredImplementation.array_body_envelopes`, and append the
  `array_body_envelope_slot_assembly` stage after
  `selected_body_envelope_lowering`.
- M65 must make the skeleton-required policy concrete: no-skeleton input
  preserves existing M63-only behavior unless a candidate is explicitly marked
  as requiring a skeleton.
- M65 must diagnose missing required skeleton input, duplicate/conflicting
  skeletons, skeletons supplied for candidates without M63 envelopes, and
  skeleton/envelope provenance mismatches.
- M65 must not produce or recognize skeletons from raw payload text, parse
  broad TSIL or `array.tsl` during lowering evaluation, lower slot-specific
  semantics, treat M64 slot labels as semantic statement kinds, or add
  declaration, assignment, array, store, return, variable, `tmp.data()`,
  `emit_return`, direct-intrinsic, SVE predicate/vector/register,
  byte-size-to-`svptrue_b*`, vector length/alignment, backend uninit, backend
  translation, renderer-ready IR, rendering, output, CLI/report/writer, Rust,
  compiler, generated-test, file-read, catalog-query, raw TSL parsing, or
  runtime `frozen/` behavior.

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

## Accepted Milestone 57

The Milestone 57 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 57: Size-Byte Equality Generation Predicate Lowering Slice
```

The slice is generation-time semantic lowering only. It resolves exactly the
M57 size-byte equality predicates:

```text
value<generation>(type::size_bytes(type<generation>(base::in))) == 2
value<generation>(type::size_bytes(type<generation>(base::in))) == 4
value<generation>(type::size_bytes(type<generation>(base::in))) == 8
```

M57 produces typed boolean
`GenerationPredicate(kind="type.size_bytes.equals", literal=<int>,
value=<bool>, type_tag=<tag>)` values by reusing the accepted M55
`GenerationValue(kind="type.size_bytes")` path and explicit scalar size-byte
rules. The accepted truth table is `si8`/`ui8 -> false for all selected
predicates`, `si16`/`ui16 -> true only for == 2`,
`si32`/`ui32`/`f32 -> true only for == 4`, and
`si64`/`ui64`/`f64 -> true only for == 8`.

M57 preserves M55/M56 context precedence and M52-M56 boundaries. It adds no
branch pruning, `if<generation>` parsing, `else if<generation>`, branch-chain
syntax, selected-arm/no-match provenance, general comparison parser, standalone
comparison forms outside the exact selected predicates, backend translation,
rendering, generated output, generated test sources, CLI/reporting/writer
behavior, Rust, compiler execution, broad TSIL parsing, or runtime dependency
on `frozen/`.

## Accepted Milestone 58

The Milestone 58 execution-review loop accepted with non-blocking follow-ups
after one focused documentation revision:

```text
Milestone 58: Generation-Time Lowering Stage Pipeline Boundary Slice
```

The slice is generation-time semantic lowering stage-boundary work only. It
adds an explicit typed staged contract for accepted lowering outputs:
helper/expression recognition, typed generation values, typed generation
predicates, generation control-flow pruning, and selected-body lowering.

M58 exposes this contract through typed stage records on lowered
implementations while preserving the accepted observable fields for M55
`GenerationValue(kind="type.size_bytes")`, M56
`GenerationValue(kind="type.size_bits")`, M57
`GenerationPredicate(kind="type.size_bytes.equals")`, and M42/M48/M51 branch
pruning. M59 branch-chain pruning consumes typed predicate/stage results
without backend/rendering changes or raw helper re-evaluation.

M58 adds no new generation-time helper semantics, arithmetic/comparison
semantics, size-byte branch-chain pruning, `else if<generation>` support,
no-match provenance, selected branch body handoff, direct `intrin<...>` / SVE
body lowering, vector/register metadata, backend translation expansion,
rendering, generated output, generated test sources, CLI/reporting/writer
behavior, Rust, compiler execution, broad TSIL parsing, or runtime dependency
on `frozen/`.

## Accepted Milestone 59

The Milestone 59 execution-review loop accepted with non-blocking follow-ups
after one focused documentation revision:

```text
Milestone 59: Size-Byte Equality Generation Branch-Chain Pruning Slice
```

The slice is generation-time semantic lowering control-flow pruning only. It
recognizes exactly the documented SVE size-byte no-final-else branch chain in
`tsldata/primitives/load_store/array.tsl:107-109`, with ordered `== 2`,
`== 4`, and `== 8` arms.

M59 consumes the accepted staged M57 predicate results through typed
`GenerationValue(kind="type.size_bytes")`,
`GenerationPredicate(kind="type.size_bytes.equals")`, and
`GenerationLoweringStage` records instead of adding backend/rendering helper
evaluation or a broad raw-text branch-chain evaluator. Byte sizes `2`, `4`,
and `8` record selected-arm pruning provenance; byte size `1` records explicit
no-match provenance without synthesizing a final `else`.

Branch bodies remain opaque pruning metadata. M59 emits no selected-body
lowering stage for the branch-chain path and does not add M60 selected-body
handoff, direct `intrin<...>` / SVE body lowering, broad `else if<generation>`
syntax, final `else`, reordered/missing/duplicate/nested chain support,
standalone comparison evaluation, backend translation, rendering, output,
CLI/reporting/writer behavior, Rust, compiler execution, broad TSIL parsing,
or runtime dependency on `frozen/`.

## Accepted Milestone 60

The Milestone 60 execution-review loop accepted with non-blocking follow-ups:

```text
Milestone 60: Opaque Selected Branch Body Handoff Slice
```

The slice is generation-time semantic lowering only. It consumes typed M59
`GenerationSizeByteBranchChainPruning` / `generation_control_flow_pruning`
stage output and creates distinct typed opaque selected-body handoff records.

For byte sizes `2`, `4`, and `8`, M60 preserves candidate id, selected type
tag, selected literal, opaque body text, source/provenance, and originating
branch-chain identity. For byte size `1`, M60 records an explicit no-match
handoff and does not synthesize a selected body.

M60 keeps branch bodies opaque. It does not parse or lower selected or
unselected branch-body semantics, does not invoke mini TSIL lowering for the
branch-chain path, and does not produce direct-intrinsic/SVE `TsilStatement`
values. It preserves backend raw-helper rejection and renderer
non-evaluation, and adds no backend translation, rendering, output,
CLI/reporting/writer behavior, Rust, compiler execution, broad TSIL parsing,
runtime dependency on `frozen/`, lowering-time file reads, raw TSL parsing, or
catalog queries during evaluation.

## Accepted Milestone 61

The Milestone 61 execution-review loop accepted with non-blocking follow-ups
after one focused revision:

```text
Milestone 61: Selected Branch Body Assignment Form Recognition Slice
```

The slice is generation-time lowering form-recognition work only. It consumes
typed M60 `OpaqueSelectedBranchBodyHandoff` and
`NoSelectedBranchBodyHandoff` values and exposes selected-body assignment-form
metadata through a distinct `selected_body_form_recognition` stage.

For the selected `== 2`, `== 4`, and `== 8` branch bodies, M61 recognizes only
the exact `pg = intrin<svptrue_b16/b32/b64>();` single-statement assignment
forms and preserves candidate id, selected type tag, selected literal,
originating branch-chain identity, original opaque body text, statement
provenance, assignment target text, opaque RHS text, and direct-intrinsic token
text as form metadata. For byte-size `1` no-match cases, it records an
explicit no-selected-body/no-form result.

M61 does not lower assignment semantics, validate direct intrinsics, infer SVE
predicate meaning, map byte-size literals to intrinsic suffixes, inspect
unselected branch bodies, or synthesize a body/form for `si8`/`ui8` no-match
cases. It adds no backend translation, rendering, output, generated tests,
CLI/reporting/writer behavior, Rust, compiler execution, broad TSIL parsing,
runtime dependency on `frozen/`, lowering-time file reads, raw TSL parsing, or
catalog queries during evaluation.

## Accepted Milestone 62

The Milestone 62 execution-review loop accepted with non-blocking follow-ups
after one focused documentation revision:

```text
Milestone 62: Selected Assignment Direct-Intrinsic Body IR Slice
```

M62 consumes only typed M61 `selected_body_form_recognition` outputs and
produces unresolved backend-neutral selected-body IR for the exact selected
assignment/direct-intrinsic form. It preserves M61 target/token/text,
explicit empty argument list, and provenance fields as typed IR facts. It
keeps byte-size `1` no-match cases as explicit no-body-IR results and adds the
distinct `selected_body_ir_lowering` stage.

M62 does not validate SVE/backend intrinsic meaning, infer
byte-size-to-intrinsic mappings, create backend translation requests, feed
renderers, emit generated output, or parse broad TSIL body syntax.

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
- Post-M56 planning revision follow-up: branch-chain pruning over the selected
  size-byte equality predicates remains a strong future lowering candidate now
  that M57 predicate lowering is accepted.
- Post-M56 staged-lowering planning note: the intended value -> predicate ->
  control-flow -> selected-body lowering path remains the guiding sequence.
  M58 accepted the stage-boundary contract, M59 accepted exact branch-chain
  pruning, M60 accepted opaque selected-body handoff, and post-M60 planning is
  accepted for M61 assignment-form recognition.
- M57 review follow-up: keep the private top-level generation binary scanner
  narrow. It may recognize unsupported operators only to reject them and must
  not become a general comparison parser without a selected milestone.
- M57 evidence/test follow-up: add explicit unsupported-tag predicate coverage
  for `bword` and `fdqword`, matching the cited group evidence in
  `tsldata/detail/types.tsl:20-26`.
- M58 boundary follow-up addressed by M59: exact size-byte branch-chain pruning
  consumes typed `GenerationValue` / `GenerationPredicate` stage outputs, not
  raw `GenerationExpressionRecognition.source_text` provenance.
- M58 boundary follow-up: future opaque selected-body handoff should introduce
  its own typed body record rather than stretching the current
  `selected_body_lowering` stage beyond its accepted `TsilReturnStatement`
  output.
- M58 extensibility follow-up addressed by M59: branch-chain pruning reuses the
  typed staged predicate resolver and keeps the cleanup subordinate to the
  exact chain-pruning slice.
- Post-M58 planning follow-up addressed by M59: the execution prompt and
  implementation kept staged-predicate reuse subordinate to the exact
  branch-chain pruning slice.
- M59 review follow-up: consider adding one more unsupported-shape test for a
  non-size-byte `else if<generation>` chain.
- M59 boundary follow-up: consider adding an explicit nested branch-chain
  rejection test.
- M59 extensibility follow-up addressed by M60: the accepted M60
  implementation introduced distinct typed selected body handoff records
  instead of expanding
  `GenerationSizeByteBranchChainPruning.selected_statement_text` into a body
  handoff contract.
- M59 extensibility follow-up: consider a small naming or comment cleanup
  clarifying that `_parse_generation_size_byte_branch_chain` recognizes only
  chain shape while predicate semantics remain delegated to the staged
  predicate resolver.
- M59 evidence follow-up: consider adding a fixture comment clarifying that the
  unit-test `scalar: arith` harness exercises the exact chain shape and typed
  M55/M57 behavior, not scalar corpus evidence; corpus evidence remains the
  SVE chain in `tsldata/primitives/load_store/array.tsl:107-109`.
- M59 focused docs follow-up: the fixed lowering document preserves selected
  body handoff and no-runtime-`frozen/` deferrals in substance; a future docs
  cleanup may add the exact labels `M60` and `runtime frozen behavior` to that
  focused section if desired.
- Post-M59 planning follow-up: M60 handoff diagnostics must stay
  boundary-level, such as missing selected body/provenance or unsupported
  source stage, and must not classify direct intrinsics, assignments, arrays,
  calls, casts, loops, vector metadata, backend uninit, or SVE predicates.
- Post-M59 planning follow-up: the M60 executor must introduce a distinct typed
  opaque selected-body handoff value instead of expanding M59 pruning metadata
  into the reusable body-handoff contract.
- M60 validation follow-up: consider direct unit assertions for
  `TSL-LOWER-HANDOFF-BODY-MISSING` and
  `TSL-LOWER-HANDOFF-CANDIDATE-MISSING`. Existing M60 tests cover unsupported
  source-stage and missing-provenance diagnostics.
- M60 validation follow-up: one boundary audit observed a package-boundary
  build failure while running `python -m tslgen.tooling.validation`; the
  validation auditor and orchestrator reruns passed, so this is non-blocking
  unless it recurs.
- M60 extensibility follow-up: future body-lowering slices may want a clearer
  stage split or envelope because `selected_body_lowering` now carries both
  opaque handoff values and already-lowered `TsilReturnStatement` values.
- M60 extensibility follow-up: consider renaming
  `NoSelectedBranchBodyHandoff.selected_type_tag` to a less ambiguous
  `candidate_type_tag` or `evaluated_type_tag`.
- M60 extensibility follow-up: future control-flow forms should extend through
  typed source records rather than turning the M60 handoff helper into a broad
  dispatcher or raw-text evaluator.
- M60 evidence follow-up: add a short fixture comment clarifying that the
  `vector::length` body-helper fixture is synthetic opacity coverage, not
  corpus evidence for M60 body semantics.
- M60 docs follow-up addressed by post-M60 planning: update remaining
  pre-acceptance/status wording in
  `docs/redesign/implementation-roadmap.md`,
  `docs/redesign/target-architecture.md`,
  `docs/redesign/testing-strategy.md`, and
  `docs/redesign/design-decisions.md`.
- M60 docs follow-up addressed by post-M60 planning: refresh
  `docs/redesign/behavioral-spec.md` so the parity table includes
  M58/M59/M60 and narrows remaining gaps to broader branch-chain pruning
  beyond M59 and body handling beyond the M60 opaque handoff plus M61
  form-recognition slice.
- M60 docs follow-up addressed by post-M60 planning: refresh
  `docs/redesign/generation-time-semantic-lowering.md` and
  `docs/redesign/open-questions.md` so lowering and open-question summaries
  are current through M60 and M61 form recognition.
- M60 docs follow-up addressed by post-M60 planning: refresh
  `docs/redesign/frozen-parity-baselines.md` from selected opaque handoff
  candidate wording to accepted M60 opaque handoff wording while keeping
  broader body handling deferred beyond the M61 form-recognition slice.
- Post-M60 planning follow-up addressed by M61: M61 remained a single
  selected-body assignment-form recognition boundary and did not become direct
  intrinsic lowering, SVE predicate semantic lowering, assignment lowering,
  backend translation input, renderer-ready IR, or broad TSIL parsing.
- Post-M60 planning follow-up addressed by M61: the implementation introduced
  a distinct typed form-recognition value and `selected_body_form_recognition`
  stage rather than stretching `selected_body_lowering` into a mixed semantic
  dispatcher.
- M61 extensibility follow-up: future body-lowering slices may want an explicit
  typed unsupported selected-body-form result if they need to distinguish
  unsupported selected bodies from hard diagnostics.
- M61 extensibility follow-up: if later slices need exact statement spans,
  split `selected_statement_location` from the inherited M60 handoff/source
  provenance rather than overloading the same location.
- Post-M61 planning follow-up addressed by M62: the implementation keeps
  "Direct-Intrinsic" as unresolved backend-neutral selected-body IR, not
  backend intrinsic IR, SVE semantic validation, translation input,
  renderer-ready IR, or generated output.
- Post-M61 planning follow-up addressed by M62: the implementation introduced
  the distinct `selected_body_ir_lowering` body-IR stage/value instead of
  overloading M60 handoff or M61 form-recognition records.
- Post-M61 planning follow-up addressed by M62: the implementation includes a
  synthetic mismatch test between selected byte-size literal and
  direct-intrinsic token text to prove the slice preserves M61 typed facts
  instead of inferring a size-to-intrinsic mapping.
- M62 validation follow-up: consider asserting diagnostic location and message
  text for the unsupported M62 source/boundary diagnostic. The current test
  asserts diagnostic code and severity, and validation found this
  non-blocking.
- M64 boundary follow-up: a future skeleton-producing slice should clearly own
  the proof that an in-memory typed exact array-body skeleton corresponds to
  `tsldata/primitives/load_store/array.tsl:105-111`; M64 accepts typed
  skeleton input and does not broadly parse TSIL.
- M64 extensibility follow-up addressed by M65: `lower_candidates` now
  populates `array_body_envelopes` and appends the
  `array_body_envelope_slot_assembly` stage when matching typed/provenanced
  skeleton input is supplied.
- M64 extensibility follow-up: future slot-specific lowerers should consume the
  enclosing `ExactArrayBodyEnvelopeIr`, not standalone slots, and must keep
  `opaque_source_text` as provenance rather than a raw-text dispatcher.
- M64 validation follow-up: consider tightening message assertions for more
  invalid-skeleton diagnostics. The focused revision added direct duplicate
  `selected_body_envelope` slot message coverage.
- M64 evidence follow-up: consider adding a small fixture comment tying the
  inlined opaque array-body test snippets to
  `tsldata/primitives/load_store/array.tsl:105-111`.
- Post-M64 planning follow-up addressed by M65: the implementation makes the
  skeleton-required policy concrete. No-skeleton input preserves existing
  M63-only behavior unless a candidate is explicitly marked as requiring a
  skeleton.
- Post-M64 planning follow-up addressed by M65: the implementation adds
  explicit diagnostics and tests for missing required skeleton input,
  duplicate/conflicting skeletons, skeletons supplied for candidates without
  M63 envelopes, and skeleton/envelope provenance mismatches.
- M65 validation follow-up: add an explicit determinism test for integrated
  typed skeleton input ordering, such as reversed
  `array_body_envelope_skeletons` producing identical lowering output or
  diagnostics. Review found the implementation deterministic, but this direct
  test remains useful.

## Stop Condition

No stop condition is active. The workflow proceeds with post-M65 planning.

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
