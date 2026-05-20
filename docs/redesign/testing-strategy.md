# Testing Strategy

Testing must prove behavior, boundaries, and determinism. The goal is not to preserve legacy internals. It is to preserve required observable behavior and make future changes safe.

## Test Principles

- Test pure logic without filesystem, hardware, shell, or template side effects.
- Use repository-grounded fixtures from `tsldata/` where useful.
- Use small synthetic fixtures for invalid cases.
- Prefer structured assertions over string matching except for golden output and diagnostics text.
- Golden files should cover stable generated artifacts, not every intermediate detail.
- Hardware detection must be mocked or injected.
- Determinism tests should run the same stage twice and compare results.

## Recommended Test Layout

```text
tslgen/
  tests/
    fixtures/
      tsl/
        valid/
        invalid/
      manifests/
      golden/
        cpp/
        rust/
        diagnostics/
    unit/
      test_diagnostics.py
      test_source_loading.py
      test_tsl_parser.py
      test_catalog_builder.py
      test_signature_rules.py
      test_reference_validation.py
      test_selection.py
      test_dependencies.py
      test_artifacts.py
      test_artifact_writer.py
      test_testgen_planning.py
      test_lowering.py
      test_reporting.py
      test_cpp_naming.py
      test_tsil_mini_lowering.py
      test_cpp_body_rendering.py
      test_testgen_rendering.py
      test_backend_manifest_completeness.py
      test_rust_declarations.py
      test_dependency_reporting.py
    integration/
      test_pipeline_catalog.py
      test_pipeline_cpp_slice.py
      test_artifact_writer_pipeline.py
      test_cli.py
      test_cli_report_write.py
      test_validation_baseline.py
      test_corpus_hygiene.py
    regression/
      test_tsldata_parse.py
      test_signature_resolution_legacy_observed.py
      test_extension_selection_legacy_observed.py
```

Existing `tslgen/tests` can be reshaped as milestones land.

## Unit Tests

Unit tests should cover:

- Diagnostics and result types.
- Frozen map/value behavior.
- Source path resolution and loading.
- TSL grammar examples.
- Catalog object construction.
- Signature parsing and normalization.
- Attribute validation.
- Template required-field validation.
- Type group and lane set expansion.
- Extension inheritance and backend support.
- Feature requirement normalization.
- Selection candidate ordering.
- Artifact writer behavior.
- Production test-source declaration normalization and planning.
- Lowering request/result construction and unsupported-payload diagnostics.
- Report rendering without filesystem side effects.
- Backend-owned naming helpers and invalid-identifier diagnostics.
- TSIL mini-lowering fixtures and unsupported-form diagnostics.
- Body rendering helpers that consume lowered values.
- Generated production test rendering helpers.
- Backend manifest/language/translation consistency checks.

Unit tests should not:

- Depend on host CPU flags.
- Invoke compilers.
- Write outside temporary directories.
- Read from `frozen/` except explicit regression fixtures if copied or referenced read-only.

## Parser Tests

Parser tests must include:

- `prim<v:=(v,v)> add(left, right):`
- Attribute lists such as `[mask=zero]`, `[aligned=*]`, and `[aligned=*, packed=*]`.
- Inline maps such as `{types [si8, ui8]}`.
- Multiline maps and lists.
- Multiline TSIL strings.
- Key lists such as `[generic, oneAPIfpga, oneAPIfpgaRTL]`.
- Parameterized keys or attributes such as `arg_count(values)=return_vector_length`.
- Comments with `#` and `//`.
- Invalid indentation and malformed string diagnostics.

Regression parser test:

- Parse every `.tsl` file under `tsldata/` and assert no errors.

## Catalog Tests

Catalog tests should assert:

- Type groups from `tsldata/detail/types.tsl`.
- Lane sets from `tsldata/detail/lane_sets.tsl`.
- Flag aliases from `tsldata/detail/flags.tsl`.
- Extension metadata from `tsldata/extensions/extension.tsl`.
- Template metadata from `tsldata/detail/templates.tsl`.
- Representative primitive declarations from `tsldata/primitives/arithmetic/fundamental.tsl`.

Tests should verify typed fields and preserved extra fields separately.

## Validation Tests

Validation fixtures should include:

- Unknown extension in implementation block.
- Unknown type group in implementation category.
- Unknown lane set in test.
- Unknown test type and `to_type`.
- Invalid `mask`.
- Invalid `aligned` and `packed`.
- Invalid `op` for masked load/store shapes.
- Missing required template field such as `aligned` for `load`.
- Extension inheritance unknown parent, self-parent, and cycle.
- Duplicate definitions where the new model forbids them.

Diagnostics tests should assert:

- Stable code.
- Severity.
- Path.
- Line and column when source exists.
- Message contains the invalid value and expected alternatives.

## Property-Style Tests

Property-style tests are useful for:

- Signature normalization idempotence.
- Flag normalization idempotence.
- Frozen value thaw/freeze round trips.
- Wildcard expansion count for `n` boolean wildcards.
- Deterministic ordering independent of input map order.
- Artifact writer digest stability.

These can be written with Hypothesis if adopted, or as small generated test loops if dependencies should remain minimal.

## Golden-File Tests

Golden tests should start small:

- One simple C++ primitive artifact, such as a binary operation for scalar or
  generic, after Milestone 22 expands beyond summary artifacts.
- One masked primitive artifact once mask semantics are implemented.
- One load/store artifact with `aligned` wildcard expansion.
- One production test source artifact after Milestone 17 establishes test-source
  planning and a rendering slice exists.
- One diagnostic report snapshot for a representative invalid fixture.

Golden update policy:

- Only update golden files when the behavior change is intentional.
- Mention the design decision or requirement update in the change.
- Keep golden inputs small enough that diffs are readable.

Golden harness helpers should:

- Compare rendered artifacts by logical path.
- Use exact content comparison unless a specific normalization policy is
  documented for that fixture.
- Assert deterministic artifact digest maps when a render path is expected to
  be stable.
- Stay in test infrastructure; production renderers must not depend on golden
  test helpers.

## Artifact Writer Tests

Milestone 16 introduces the first accepted filesystem mutation boundary. Tests
for that milestone must use temporary directories and assert:

- Absolute artifact paths, parent traversal, duplicate paths, and paths outside
  the output root are rejected before writing.
- First writes create parent directories and produce deterministic `written`
  records.
- Repeated writes with identical content produce `skipped_unchanged` records
  when skip-unchanged is enabled.
- Changed content rewrites the file and updates the digest.
- Dry-run reports match the planned mutation statuses without touching files.
- Write reports sort paths and diagnostics deterministically.

No renderer test should need to touch the real filesystem. Rendering tests
should produce `ArtifactSet` values; writer tests should consume them.

## Production Test-Source Planning Tests

Milestone 17 tests should distinguish generated production tests from tests of
the generator itself. They should assert:

- TSL `tests` declarations normalize into typed declaration objects.
- Plans filter by primitive, type, extension, backend, and selected candidate.
- Unsupported declaration shapes produce diagnostics rather than being ignored.
- Planned test artifact descriptors have stable logical paths and metadata.
- The golden harness can snapshot plans without becoming a production planning
  dependency.

Compiler invocation, runtime execution, hardware autodetection, and broad
generated test framework behavior remain out of scope until explicitly
milestoned.

## Lowering Tests

Milestone 18 tests should prove the boundary before proving full TSIL semantics.
They should assert:

- Lowering requests are built from selected implementation candidates and typed
  context, not raw catalog dictionaries.
- Unsupported or deferred payloads return diagnostics with stable codes and
  source context when available.
- If a minimal TSIL subset is parsed, unsupported constructs fail explicitly.
- Generation-time conditions such as `if<generation>(...)` are represented and,
  if implemented, evaluated in lowering rather than rendering.
- Lowering results are deterministic for identical candidate input.

Dependency and backend tests may consume lowered outputs only for the supported
slice. They must not rescan raw implementation payloads to bypass lowering.

## Validation Baseline Tests

Milestone 21 should make the broad check surface explicit. If a validation
script or command is added, tests should assert:

- The documented command succeeds in the dev container for the production
  package and accepted tests.
- Exploratory or quarantined modules are not imported by public API, CLI, or
  accepted pipeline tests.
- Validation does not require network access, host CPU features, compiler
  availability, or generated-output churn.
- Failures distinguish production regressions from intentionally unsupported
  sketches.

## Post-Milestone-24 Regression Tests

The next roadmap phase should add focused regression tests before broadening
generation:

- CLI combined report/write tests for `--coverage-report` with `--output-root`,
  including repeated writes and `--no-skip-unchanged`.
- C++ naming tests for function names, parameter names, invalid identifiers, and
  golden declaration output. Milestone 26 covers the scalar `binary`
  `si32`/`ui32` declaration slice and rejects invalid names rather than
  sanitizing them.
- TSIL mini-lowering tests for the direct parameter-add return form
  `emit_return(<parameter> + <parameter>);` and the M38 intrinsic-compose form
  `emit_return(intrin_compose<add>(<parameter>, <parameter>));`, plus
  malformed return forms, unsupported intrinsic names, wrong arity, invalid
  arguments, unknown operands, generation-time branches, and typed-opaque
  fallback.
- C++ body rendering tests proving bodies consume lowered data rather than raw
  TSIL text. Milestone 28 covers only the scalar `binary` `si32`/`ui32`
  parameter-add return body and diagnostics for missing or unsupported lowered
  bodies.
- Generated production test rendering golden tests over `TestSourcePlan` values.
  Milestone 29 covers only the C++ scalar `binary` `si32`/`ui32`
  metadata-style test source artifact and diagnostics for unsupported test
  artifact kinds, type tags, extra metadata, and case shapes.
- Backend manifest/language/translation-map diagnostic tests.
  Milestone 30 covers typed language-map and translation-map boundary
  promotion, active C++/Rust manifest consistency, missing-map diagnostics,
  unsupported-backend diagnostics, and C17 deferral during catalog-derived
  manifest creation.
- Rust production-shaped declaration golden tests. Milestone 31 covers the
  scalar `binary` `si32`/`ui32` body-free trait signature slice, Rust naming
  helper diagnostics, unsupported declaration inputs, and preservation of the
  original Rust summary metadata.
- Candidate-specific dependency report/API tests. Milestone 32 covers retained
  pipeline closure values, stable API helper access, deterministic JSON fields,
  deterministic escaped HTML sections, primitive-level fallback visibility, and
  candidate edge/issue/fallback rows.
- Quarantine-retirement tests only when cleanup changes code or the validation
  profile. Milestone 33 is documentation-only and requires no new tests. A
  future deletion or migration slice must run the import-boundary regression,
  update validation-profile assertions, and run the Milestone 21 profile if
  quarantine entries or accepted paths change.
- Corpus-hygiene tests only when a milestone changes validation behavior,
  corpus probes, or `tsldata` content. Milestone 34 documents policy without
  changing the validation command surface.

## Validation Baseline Profile

Milestone 21 establishes the local redesigned-code validation profile at
`tslgen.tooling.validation`. Future milestone review should run:

```sh
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
```

The profile includes:

- current-corpus probes for accepted parser behavior and selector-aware
  implementation-spec promotion, including scalar-only `blend`;
- `python -m unittest discover tslgen/tests/unit`;
- targeted `compileall` for accepted redesigned modules and unit tests;
- `ruff check` for accepted redesigned modules and unit tests;
- targeted `mypy --explicit-package-bases` with
  `MYPYPATH=tslgen/src:tslgen/tests/unit`;
- `git diff --check`.

The profile deliberately checks accepted redesigned code and tests rather than
claiming broad repository validation. Quarantined exploratory sketches remain
outside the lint/type/compile surface until a future milestone either promotes
or removes them. Milestone 33 classifies quarantined paths in
`docs/redesign/exploratory-code-retirement-plan.md`; documentation-only
classification changes require `git diff --check`, while code deletion,
migration, or validation-profile edits require the targeted import-boundary
test and the full Milestone 21 profile. `tsldata/` remains a read-only corpus
fixture target exercised by tests, not a Python lint/type target.

## Corpus Hygiene Tests

Milestone 34 defines the corpus review policy in
`docs/redesign/corpus-hygiene-policy.md` and keeps the validation command
surface unchanged. The current validation profile already includes selected
corpus probes for accepted parser behavior and selector-aware implementation
spec promotion.

`tsldata/` changes should be tested according to their review classification:

- Source-data changes require focused parser, catalog, validation, selection,
  backend metadata, lowering, or rendering tests for the behavior affected.
- Fixture-only changes belong under test fixture paths and should stay small
  enough for exact diffs to be reviewable.
- Generated artifact changes belong to artifact or golden tests, not corpus
  probes.
- Metadata-only dirty state, such as zero-line mode changes, should be
  reported and left out of implementation slices unless executable-bit intent
  is explicit.

Corpus probes must remain deterministic and host-independent. They should not
write output files, rewrite or normalize `tsldata`, require compilers, inspect
host CPU features, or depend on the network.

Future validation-profile expansion may add selected corpus checks only when
they protect accepted behavior without output churn. Any command-surface change
must update validation-profile tests and run the full Milestone 21 profile.

## Integration Tests

Integration tests should cover:

- Source loading to parsed documents.
- Parsed documents to catalog.
- Catalog validation over selected `tsldata/` files.
- Selection request to candidate set.
- Candidate set to minimal backend artifact.
- Rendered artifact set to write report using a temporary output root.
- Test-source planning from selected catalog/test declarations.
- Report printing and artifact writing in the same CLI run.
- Lowered scalar fixture through C++ body rendering.
- CLI with explicit flags and temp output.

Integration tests should use temporary directories for writes and explicit CPU flags.

## Regression Tests Against Legacy-Observed Behavior

Regression tests should map observed behavior to new requirements, not old modules.

Examples:

- Signature `v:=(v,v)` resolves to `binary`, evidenced by `frozen/generator_specs/signatures.yaml`.
- Extension `avx2_vl` inherits/falls back to `avx2`, evidenced by `tsldata/extensions/extension.tsl`.
- `avx3f` normalizes to `avx512f`, evidenced by `tsldata/detail/flags.tsl`.
- `load` requires `aligned`, evidenced by `tsldata/detail/templates.tsl`.
- `aligned=*` expands to true and false variants, evidenced by `tsldata/primitives/load_store/load.tsl`.

Avoid tests that assert legacy function names or exception types.

## Deterministic Output Tests

Determinism tests should assert:

- Same input paths in different order produce the same catalog ordering where order is semantic or sorted.
- Same selection request produces identical candidate identities.
- Same backend plan renders identical artifact content.
- Same artifact set writes identical write reports and digest maps.
- Same production test-source request produces identical test artifact
  descriptors and, once rendered, identical test artifact content.
- Same generated test-source rendering request produces identical content.
- Same lowering input produces identical lowered results or diagnostics.
- Same report/write CLI invocation produces identical stdout/stderr contract and
  write-report effects.
- Parallel-enabled stages produce identical outputs with one worker and multiple workers.

## Test Fixtures

Use three fixture classes:

- Repository fixtures: read-only references to `tsldata/` for broad compatibility.
- Minimal valid fixtures: small files under `tests/fixtures/tsl/valid`.
- Minimal invalid fixtures: targeted files under `tests/fixtures/tsl/invalid`.

Fixture guidelines:

- Keep invalid fixtures focused on one error family unless testing accumulation.
- Include comments showing which requirement the fixture covers.
- Avoid copying large legacy outputs unless a golden test needs them.

## Toolchain Tests

Generated C++/Rust compile tests are valuable but should be optional or separately marked because they depend on compilers, target hardware, qemu, rustup targets, and flags.

Recommended markers:

- `unit`
- `integration`
- `golden`
- `toolchain`
- `slow`

Default CI should run unit, integration, and golden tests that are host-independent.

## Coverage Goals

Early milestones:

- High coverage for diagnostics, parsing, catalog construction, and validation.

Middle milestones:

- Branch coverage for selection, feature requirements, wildcard expansion, and extension fallback.

Backend milestones:

- Representative template coverage, not exhaustive template count.
- Golden coverage for stable generated artifacts.

Post-Milestone-15 milestones:

- Writer path-safety and skip-unchanged coverage before any CLI writes files.
- Generated test-source planning coverage before generated tests are rendered or
  executed.
- Lowering boundary diagnostics before broad TSIL parsing.
- Validation baseline coverage before claiming repository-wide checks.

Post-Milestone-24 milestones:

- CLI report/write interaction coverage before adding legacy compatibility
  aliases.
- C++ declaration naming and body golden coverage before expanding template
  families.
- TSIL mini-lowering coverage before any renderer consumes implementation
  semantics.
- Production test rendering coverage before compiler or runtime test execution.
- Backend metadata consistency coverage before language/translation maps drive
  broad rendering.

## Post-Milestone-34 Stabilization Validation

The post-Milestone-34 phase is a stabilization/release-readiness review rather
than a new implementation milestone. Validation should prove the accepted
surface remains coherent and should not expand behavior opportunistically. The
full release-readiness gate is recorded in
`docs/redesign/stabilization-release-checklist.md`.

Required stabilization checks:

- Run the Milestone 21 validation profile:
  `PYTHONPATH=tslgen/src python -m tslgen.tooling.validation`.
- Run the unit, integration, and golden tests that cover accepted API/CLI,
  artifact writer, reporting, dependency reporting, lowering, C++ rendering,
  Rust rendering, backend metadata, test generation, validation quarantine, and
  corpus hygiene behavior.
- Run deterministic output checks for repeated artifact rendering, report
  serialization, artifact writing with skip-unchanged enabled, and CLI
  report/write stream behavior.
- Run `git diff --check` for documentation and fixture whitespace safety.
- Inspect dirty `tsldata/**` state with the corpus hygiene commands before
  making any source-data or release-readiness claim.

Checks that remain out of the default stabilization surface:

- Host compiler or runtime execution of generated C++/Rust tests.
- Network-dependent packaging or publishing.
- Host CPU feature detection.
- Broad Python lint/type checks over quarantined exploratory code.
- Corpus-wide normalization or permission-bit cleanup.

## Functional Parity Testing

The post-Milestone-34 functional parity phase uses `frozen/` as behavioral
evidence only. Tests must validate observable behavior through accepted
redesign boundaries and must not import or execute legacy generator modules.

Parity fixture rules:

- Golden fixtures copied or excerpted from `frozen/out/**` must record source
  path, line or excerpt range when practical, capture date if regenerated, and
  selected parity level.
- Whole-file golden parity is allowed only when the selected artifact is small
  enough to review. Large files such as `frozen/out/tsl/tsl_native.hpp` and
  `frozen/out/reports/primitive_coverage.json` should normally be represented
  by selected excerpts or derived semantic fixtures.
- If legacy output is unstable, overly broad, or includes incidental formatting,
  create a redesign-owned golden baseline and document why byte-for-byte legacy
  parity is not required.
- Golden fixtures must live under the redesign test fixture tree, not be read
  from `frozen/` at test runtime.

Milestone 35 baseline-selection rule:

- `docs/redesign/frozen-parity-baselines.md` records the first C++
  `binary/add` parity target and the exact legacy evidence ranges.
- Milestone 35 does not copy fixture files. Future milestones that consume the
  baseline must create small fixtures under the redesign test fixture tree and
  add provenance tests in the same slice.
- The first C++ parity fixtures should prefer selected excerpts or
  redesign-owned generated goldens over whole-file legacy copies.
- Tests must never read `frozen/out/**` at runtime as the expected-output source.

For each parity milestone, tests should cover:

- Exact golden output when the selected parity level is byte-for-byte.
- Semantic equivalence when exact formatting is intentionally not required,
  such as function names, wrapper delegation, parameter order, return type,
  intrinsic call, test inputs/expected values, or report fields.
- Deterministic output across repeated runs.
- Structured diagnostics for unsupported legacy behavior.
- No runtime dependency on `frozen`.
- No parser-private or syntax-tree leakage into domain, lowering, rendering, or
  test-generation logic.
- No hidden filesystem side effects outside `io.artifact_writer`.

Default parity validation must remain host-independent. Generated C++ or Rust
compile/run checks belong behind optional `toolchain` or `slow` markers until a
dedicated execution milestone accepts compiler, qemu, rustup, and dependency
requirements.

Recommended first parity checks:

- Milestone 35: fixture provenance and baseline-selection tests if fixtures are
  added.
- Milestone 36: C++ `tsl/tsl_native.hpp` output path, selected support
  preamble, artifact order, digest, unsupported layout diagnostics, and fixture
  provenance tests. CMake sidecar and writer behavior tests remain deferred
  unless the milestone explicitly touches those boundaries.
- Milestone 37: C++ `binary/add` primary/specialization/wrapper golden tests,
  lowered-model rendering tests, unsupported scalar-slice diagnostics, digest
  determinism, and fixture provenance tests.
- Milestone 38: TSIL intrinsic-compose lowering unit tests for the accepted
  `intrin_compose<add>` return, lowered helper model shape, typed-opaque
  fallback, deterministic output, and unsupported-form diagnostics for modifier
  metadata, nested calls, generation-time suffixes, loops, variables, wrong
  arity, unsupported names, and unknown parameters.
- Milestone 39: transitional native C++ `binary/add` intrinsic specialization
  golden tests for the selected `avx2/f32` output, diagnostics for unsupported
  native intrinsic/type/extension combinations, digest determinism, fixture
  provenance tests, and an explicit test/doc note that renderer-local intrinsic
  mapping is not an expansion path.
- Milestone 40: backend translation-boundary correction tests, including typed
  intrinsic-composition input/output, C++ type-map access from
  `types_cpp.tsl`, selected `add + avx2 + f32 -> _mm256_add_ps` composition
  through metadata, renderer consumption of already-resolved backend-call IR,
  raw-TSIL non-rescan tests, rejection or diagnostics for unresolved
  `if<generation>`, `type<generation>`, and `value<generation>` reaching
  translation, missing-map and missing-translated-call diagnostics,
  determinism, no runtime dependency on `frozen/`, and regression coverage
  preventing renderer-owned intrinsic lookup growth for the selected slice.
- Milestone 41: documentation/inventory validation for the generation-time
  semantic lowering contract, including explicit generation context fields,
  helper inventory, backend drift risk reassessment, milestone adaptation
  decisions, and `git diff --check`. Milestone 41 selects the next future slice:
  boolean primitive-attribute branch pruning for
  `if<generation>(value<generation>(primitive::attribute(aligned)))`. That
  future slice must test deterministic branch selection, unknown attribute
  diagnostics, non-boolean attribute diagnostics, missing generation context
  diagnostics, malformed branch diagnostics, unresolved nested helper
  diagnostics, backend-translation rejection of unresolved generation helpers,
  and renderer non-evaluation regression coverage.
- Milestone 42: primitive-attribute generation branch pruning tests for
  `if<generation>(value<generation>(primitive::attribute(aligned)))`, including
  true/false pruning, selected-branch-only diagnostics, missing/non-boolean/
  unknown attribute diagnostics, missing context diagnostics, malformed and
  unsupported condition diagnostics, backend-translation rejection of unresolved
  helper IR, existing direct-add and intrinsic-compose lowering regressions,
  C++ backend regressions, and validation profile coverage.
- Milestone 43: base scalar type generation query tests for
  `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`, and
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`. Tests
  should cover `si32` and `ui32`, selected-candidate type-tag defaults,
  explicit generation-context type overrides, missing and unknown type-tag
  diagnostics, unsupported float/pointer/generic companion conversions,
  unsupported helper-shape diagnostics, deterministic lowered semantic type
  values, backend-translation rejection of unresolved raw generation type text,
  resolved `GenerationTypeRef` values remaining unsupported except for the
  selected M45 suffix and M46 C++ type-spelling requests, renderer
  non-evaluation, and unchanged Milestone 42 branch-pruning regressions. Prose
  shorthand such as
  `base::signed_of(base::in)` is tested as unsupported unless written in the
  exact nested accepted form.
- Milestone 44: docs-only validation with `git diff --check`; no runtime tests.
  The roadmap must define the M45 suffix translation tests, exact typed
  inputs, expected `epi32` output for selected `si32` and `ui32` native integer
  add candidates, diagnostics, and renderer non-evaluation regressions before
  implementation resumes.
- Milestone 45: backend intrinsic suffix modifier translation tests over typed
  M43 `GenerationTypeRef` inputs cover selected `si32` and `ui32` native
  integer add suffix success, `epi32` output, missing `GenerationTypeRef`,
  unsupported modifier family, unsupported type tag, unsupported backend,
  unsupported extension, unsupported intrinsic base, unsupported source ref
  kind, missing translation metadata, missing modifier metadata, malformed
  modifier request, raw generation-helper rejection, determinism, and renderer
  non-evaluation.
- Milestone 46: backend C++ scalar type spelling tests over typed M43
  `GenerationTypeRef` inputs, including `base.in`, `base.signed_of`, and
  `base.unsigned_of` refs for `si32 -> int32_t` and `ui32 -> uint32_t`,
  language-map key normalization or equivalent typed metadata, missing-map
  diagnostics, raw-helper rejection, determinism, and no renderer-local type
  lookup.
- Milestone 47: native integer C++ `binary/add` golden fixture and provenance
  tests for selected `avx2` `si32` and `ui32` output, plus diagnostics for
  missing, unsupported, and ambiguous translated suffix/type values, missing
  translated native integer plan, determinism, M39/M40 `avx2/f32` regressions,
  and no compiler execution. The selected fixture is
  `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_i32_u32_excerpt.hpp`.
- Milestone 48: signedness type-predicate branch-pruning tests cover the exact
  `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
  plus `else<generation>` form, including `si32` true-branch pruning,
  `ui32` false-branch pruning, selected-branch-only unresolved-helper
  diagnostics, malformed branch diagnostics, unsupported predicate and nested
  type-query diagnostics, missing type context, unknown or unsupported type
  tags, non-integer signedness predicates, determinism, backend-translation
  rejection of raw unresolved generation helpers, and renderer non-evaluation.
- Milestone 49: generated C++ `add_i32_basic` test-source parity tests should
  cover the selected redesign-owned golden fixture and provenance, repeated
  rendering determinism, typed `TestSourcePlan` consumption, explicit typed
  C++ type-spelling consumption, unsupported backend/artifact
  kind/extension/type/case-shape/metadata/vector/type-spelling diagnostics, and
  regression coverage that the existing metadata-style C++ production-test
  artifact remains stable. No compiler execution, `gtest` fetch, CLI workflow,
  Rust test rendering, or broad generated-test parity is part of this check.
- Milestone 50: legacy coverage JSON adapter row tests should cover the
  selected `add` / `avx2` / `cpp` / `f32` golden row fixture and provenance,
  selected field mapping, stable field ordering, deterministic serialization,
  legacy string-valued booleans only at the adapter boundary, unsupported
  request diagnostics, missing/ambiguous selected row diagnostics, missing
  primitive class/template metadata diagnostics, no runtime `frozen/` reads, no
  parser/selection/lowering/rendering reruns during serialization, and
  regression coverage that existing redesign coverage JSON and HTML reports
  remain stable.
- Milestone 51: plain-`else` signedness generation branch tests should cover
  the exact M48 signedness predicate with plain `else`, `si32` true-branch
  pruning, `ui32` false-branch pruning, M48 `else<generation>` regression
  coverage, selected-branch-only unresolved-helper diagnostics, no diagnostics
  for unresolved helpers in the unselected branch, malformed plain-`else`
  branch diagnostics, unsupported predicate and nested type-query diagnostics,
  missing type context, unknown or unsupported type tags, non-integer
  signedness predicates, deterministic pruning and diagnostic ordering,
  backend-translation rejection of raw unresolved generation helpers, and
  renderer non-evaluation. No conversion body lowering, backend translation,
  rendering, generated output, Rust, CLI/reporting, or compiler execution is
  part of this check.
- Milestone 52: concrete integer generation type/signedness tests should cover
  `type<generation>(base::in)`,
  `type<generation>(base::signed_of(type<generation>(base::in)))`,
  `type<generation>(base::unsigned_of(type<generation>(base::in)))`, and the
  exact M48/M51 signedness branch forms across `si8`, `ui8`, `si16`, `ui16`,
  `si32`, `ui32`, `si64`, and `ui64`. Tests should prove signed tags choose
  true branches, unsigned tags choose false branches, selected-branch-only
  diagnostics remain intact, wildcard/group tags stay unsupported as selected
  concrete tags, unsupported floats/pointers/masks/unknown tags keep explicit
  diagnostics, repeated lowering is deterministic, backend translation still
  rejects raw generation helpers, and renderers remain non-evaluating. No
  backend suffix/type-spelling expansion, vector/register metadata, branch-body
  lowering, generated output, Rust, CLI/reporting, or compiler execution is
  part of this check.
- Milestone 53: concrete integer generation rule-source tests should prove the
  accepted M52 rule set is provided as deterministic typed domain/catalog rule
  values rather than a lowering-private table. Tests should cover rule ordering,
  missing singleton tags, missing companion pairs, inconsistent rule data,
  wildcard/group selectors, unsupported floats/pointers/masks, unknown tags,
  and concrete-looking unselected tags such as `si128`. Existing M52 lowering
  behavior and diagnostics should remain unchanged. No backend translation
  expansion, rendering, generated output, Rust, CLI/reporting, or compiler
  execution is part of this check.
- Milestone 54: catalog-derived concrete integer generation rule wiring tests
  prove normal pipeline-facing lowering receives an explicitly
  catalog-derived `ConcreteIntegerGenerationRuleSet`, preserves all accepted
  M52/M53 type-query and signedness branch behavior, reports
  `TSL-DOMAIN-GEN-RULE-*` diagnostics for missing or inconsistent explicit
  rule data without hidden default fallback, and remains deterministic. No
  backend translation expansion, rendering, generated output, Rust,
  CLI/reporting, or compiler execution is part of this check.
- Milestone 55: scalar size-byte generation value tests should prove exactly
  `value<generation>(type::size_bytes(type<generation>(base::in)))` lowers to
  deterministic typed integer values for selected scalar tags:
  `si8`/`ui8 -> 1`, `si16`/`ui16 -> 2`, `si32`/`ui32`/`f32 -> 4`, and
  `si64`/`ui64`/`f64 -> 8`. Tests should prove `f32`/`f64` are accepted only
  for this exact query, unsupported wildcard/group tags and unknown tags
  diagnose cleanly, malformed or incomplete explicit scalar size rule data does
  not fall back to defaults, existing M52-M54 integer behavior is unchanged,
  backend translation rejects raw unresolved generation helpers, and renderers
  remain non-evaluating. No arithmetic/comparison lowering, branch pruning from
  size values, backend translation expansion, rendering, generated output,
  Rust, CLI/reporting, or compiler execution is part of this check.
- Milestone 56 tests cover only the exact
  `value<generation>(type::size_bytes(type<generation>(base::in))) * 8`
  arithmetic expression. They prove it lowers to deterministic typed integer
  bit-width values for selected scalar tags:
  `si8`/`ui8 -> 8`, `si16`/`ui16 -> 16`, `si32`/`ui32`/`f32 -> 32`, and
  `si64`/`ui64`/`f64 -> 64`. Tests reject reversed operands, unsupported
  literals/operators, nested arithmetic, comparisons, branch pruning, and
  surrounding body lowering while preserving M52-M55 behavior, raw-helper
  rejection, and renderer non-evaluation.
- Milestone 57 tests cover only exact size-byte equality predicates from
  `tsldata/primitives/load_store/array.tsl:107-109`. Tests prove each
  selected scalar tag produces the expected boolean result for `== 2`, `== 4`,
  and `== 8`: `si16`/`ui16` true only for `== 2`,
  `si32`/`ui32`/`f32` true only for `== 4`, `si64`/`ui64`/`f64` true only for
  `== 8`, and `si8`/`ui8` false for all selected predicates. Tests
  reject unsupported operators, literals, reversed comparisons, nested or mixed
  operands, wildcard or group selected tags, and branch-chain/body lowering
  while preserving M42/M48/M51 and M52-M56 behavior, raw-helper rejection, and
  renderer non-evaluation.
- Milestone 58 tests cover the generation-time lowering stage boundary. They
  prove M55/M56 value results, M57 predicate results, and M42/M48/M51 branch
  pruning are unchanged while accepted values and predicates are visible
  through the staged contract. Tests continue proving raw helper rejection,
  renderer non-evaluation, deterministic stage output, and no M57 size-byte
  branch-chain pruning.
- Milestone 59 tests only the exact size-byte equality branch-chain pruning
  slice: `si16`/`ui16` select `== 2`, `si32`/`ui32`/`f32` select `== 4`,
  `si64`/`ui64`/`f64` select `== 8`, and `si8`/`ui8` record explicit no-match
  provenance without synthesizing a final `else`. Tests should also prove
  unsupported branch-chain shapes are rejected,
  branch bodies remain opaque, unselected/no-match bodies are not diagnosed,
  M55/M57/M58 outputs remain unchanged, raw-helper rejection and renderer
  non-evaluation are preserved, and no generated output changes.
- Milestone 60 tests only opaque selected branch body handoff: deterministic
  selected-body provenance for the `== 2`, `== 4`, and `== 8` arms, explicit
  no-selected-body behavior for `si8`/`ui8`, unselected bodies ignored even
  when they contain deferred helpers or unsupported body syntax,
  boundary-level invalid handoff-state diagnostics, M57/M58/M59 regressions,
  raw-helper rejection, renderer non-evaluation, and no generated output or
  golden-file changes.
- Milestone 61 tests only selected-body assignment-form recognition from M60
  handoff values: deterministic
  recognition for the `pg = intrin<svptrue_b16/b32/b64>();` selected bodies,
  explicit no-selected-body/no-form behavior for `si8`/`ui8`,
  unsupported-form and malformed-body diagnostics, unselected bodies remaining
  uninspected,
  M57-M60 regressions, raw-helper rejection, renderer non-evaluation, and no
  generated output or golden-file changes.
- Milestone 62 tests only unresolved selected assignment/direct-intrinsic body
  IR from M61 form-recognition values: deterministic IR records for
  `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`, explicit no-selected-body/
  no-body-IR results for `si8`/`ui8`, preservation of target/token/text/
  provenance fields, a mismatch test proving selected byte-size literals are
  not mapped to intrinsic tokens, unsupported M62 source/form diagnostics,
  M57-M61 regressions, raw-helper rejection, renderer non-evaluation, and no
  generated output or golden-file changes.
- Milestone 63 tests only the backend-neutral selected-body envelope over M62
  body IR values: deterministic selected envelopes with exactly one typed
  sequence entry for `svptrue_b16`, `svptrue_b32`, and `svptrue_b64`,
  explicit no-body envelopes for `si8`/`ui8`, preservation of M62
  target/token/text/provenance and selected facts without reparsing original
  body text, mismatch preservation proving no byte-size-to-token inference,
  unsupported source/type or inconsistent-envelope diagnostics, M57-M62
  regressions, raw-helper rejection, renderer non-evaluation, and no generated
  output or golden-file changes.
- Milestone 64 tests only exact array-body envelope slot assembly over M63
  envelopes: deterministic five-slot structural envelopes for the exact
  `array.tsl:105-111` shape, a selected-body slot referencing M63
  `svptrue_b16`, `svptrue_b32`, and `svptrue_b64` envelopes, explicit no-body
  branch slots for `si8`/`ui8`, preservation of opaque slot text/provenance
  and slot order, candidate/type/branch provenance mismatch diagnostics,
  missing/reordered/duplicate/extra slot diagnostics, proof that non-branch
  slots remain opaque and non-semantic, M57-M63 regressions, raw-helper
  rejection, renderer non-evaluation, and no generated output or golden-file
  changes.
- Milestone 65 tests only exact array-body envelope pipeline integration:
  `lower_candidates` populates `array_body_envelopes` from typed/provenanced
  M64 skeleton input, appends the `array_body_envelope_slot_assembly` stage
  after `selected_body_envelope_lowering`, preserves selected and no-body M63
  cases, reports missing required skeleton, duplicate skeleton, conflicting
  skeleton, orphan skeleton, and skeleton provenance-mismatch diagnostics,
  preserves existing M57-M64 outputs and ordering, proves deterministic
  repeated normal lowering runs, keeps raw-helper rejection and renderer
  non-evaluation, and changes no generated output or golden files.
- Milestone 66 tests cover only exact array-initialization slot form IR:
  consume accepted M65 `array_body_envelopes`, refine exactly the
  `opaque_pre_branch_array_initialization` slot, preserve slots `1` through
  `4` as opaque, preserve envelope/slot provenance and the variable token
  `tmp`, record unresolved helper leaves without evaluating vector length,
  vector alignment, base type, or backend uninit values, report malformed
  exact-form diagnostics, prove deterministic lowering, keep raw-helper
  rejection and renderer non-evaluation, and change no generated output or
  golden files.
- Milestone 67 tests cover only typed deferred helper-request IR over
  accepted M66 leaves: classify exactly the base-type, vector-length,
  vector-alignment, and backend-uninit leaves into deterministic request
  records; preserve leaf text, source locations, and M65/M66 provenance; prove
  no helper values are resolved and no backend translation requests are
  created; cover direct M66 form, stage-output, and typed
  `LoweredImplementation` container sources; cover unsupported source, missing
  or multiple forms, missing/mismatched leaves, unsupported leaf text, and
  provenance diagnostics; keep M57-M66 behavior, raw-helper rejection,
  renderer non-evaluation, generated outputs, and golden files unchanged.
- Milestone 68 tests cover only typed base-type request resolution over
  accepted M67 request IR: consuming direct request IR, stage output, and typed
  `LoweredImplementation` container sources; resolving exactly the
  `type<generation>(base::in)` request to a typed base-type result equivalent
  to `GenerationTypeRef(kind="base.in")`; preserving M67 provenance; proving
  vector length, vector alignment, and backend uninit requests remain
  unresolved; covering missing/multiple request IR, missing/duplicate/mismatched
  base-type request records, unsupported selected types, unsupported request
  text, and provenance diagnostics; proving no raw helper text is parsed, no raw
  query-string helper evaluator is called on M67 leaf text, no file/catalog
  reads happen during evaluation, and generated outputs/golden files remain
  unchanged.
- Milestone 69 tests prove behavior-preserving extraction of the accepted
  M64-M68 array-initialization stage assembly tail: direct helper/private
  pipeline tests return the same existing tuples and stage records; normal
  `lower_candidates` emits identical `LoweredImplementation` fields, stage
  names/order, diagnostic codes, source locations, and deterministic output;
  representative M64/M66/M68 failure paths preserve early-return diagnostics;
  skeleton and no-skeleton paths remain unchanged; raw helper evaluators are
  not called; and generated outputs/golden files remain unchanged. A
  pipeline-level M67 diagnostic propagation test remains a non-blocking
  follow-up for the next slice that touches the extracted pipeline.
- Milestone 70 tests prove exact array-initialization vector-length
  request resolution through explicit typed metadata: direct resolver tests,
  normal `lower_candidates` stage-order tests after
  `array_initialization_base_type_request_resolution`, missing/duplicate/
  conflicting/unsupported metadata diagnostics, malformed or mismatched M67
  request diagnostics, deterministic ordering for repeated and reversed
  metadata inputs, unchanged base-type behavior, unresolved vector alignment
  and backend uninit requests, no raw helper parsing or raw query evaluator
  calls on M67 leaf text, no catalog/`tsldata`/host CPU reads during lowering
  evaluation, and no backend translation/rendering or generated-output churn.
- Milestone 71 tests prove exact array-initialization vector-alignment request
  resolution through explicit typed metadata: direct resolver tests, normal
  `lower_candidates` stage-order tests after
  `array_initialization_vector_length_request_resolution`, missing/duplicate/
  conflicting/unsupported metadata diagnostics, malformed or mismatched M67
  request diagnostics, deterministic ordering for repeated and reversed
  metadata inputs, unchanged base-type and vector-length behavior, unresolved
  backend uninit request, no raw helper parsing or raw query evaluator calls
  on M67 leaf text, no catalog/`tsldata`/host CPU reads during lowering
  evaluation, and no backend translation/rendering or generated-output churn.
- Milestone 72 tests prove exact array-initialization helper-set
  completion without backend translation: direct aggregate tests from accepted
  M71 resolution, normal `lower_candidates` stage-order tests after
  `array_initialization_vector_alignment_request_resolution`, typed
  backend-uninit request identity checks, missing/duplicate/mismatched request
  diagnostics, deterministic ordering, unchanged M68/M70/M71 behavior,
  pipeline-level M67 diagnostic propagation where touched, no raw helper
  parsing or raw query evaluator calls, no catalog/`tsldata`/host CPU/backend
  map reads during lowering evaluation, and no declaration/array lowering,
  backend translation/rendering, golden-file, or generated-output churn.
- Milestone 73 tests should prove exact first-slot declaration-shell
  structural IR without generic declaration/array semantics: direct resolver
  tests from accepted M72 helper-set completion, normal `lower_candidates`
  stage-order tests after `array_initialization_helper_set_completion`,
  preservation of M68/M70/M71 helper facts and M72 deferred backend-uninit
  policy, malformed exact-shell and provenance diagnostics, deterministic
  ordering, unchanged M66-M72 behavior, no raw helper parsing or raw query
  evaluator calls, no catalog/`tsldata`/host CPU/backend map reads during
  lowering evaluation, and no backend translation/rendering, generic
  `var`/`array_type` parsing, allocation/lifetime, store/return, golden-file,
  or generated-output churn.
- Milestone 74 tests prove exact array-body structural sequence and
  structural/provenance slot-role classification without body semantics:
  direct sequence tests from accepted M64/M65 envelope state plus accepted M73
  declaration-shell IR, normal `lower_candidates` stage-order tests after
  `array_initialization_declaration_shell_lowering`, exact five-entry role
  order for `array.tsl:105-111`, M73 shell linkage only to slot 0, M63
  selected/no-body envelope linkage only to the selected-body slot, opaque
  preservation for the predicate-init, post-branch store-call, and
  return-emission slots, unsupported/missing/duplicate source diagnostics,
  provenance and role-order diagnostics, deterministic ordering, unchanged
  M63-M73 behavior, no raw helper parsing or raw query evaluator calls, no
  catalog/`tsldata`/host CPU/backend map reads during lowering evaluation,
  and no backend translation/rendering, generic body/declaration/array
  parsing, variable/allocation/store/return semantics, golden-file, or
  generated-output churn.
- Milestone 75 tests prove exact predicate path structural/request IR
  without SVE, store, variable-scope, backend, renderer, or output semantics:
  direct tests from accepted M74 sequence state, normal `lower_candidates`
  stage-order tests after `array_body_structural_sequence_classification`,
  exact slot-1/slot-2/slot-3 `pg` path linkage, selected `svptrue_b16/b32/b64`
  update request preservation when accepted selected-body evidence exists,
  explicit no-update preservation for accepted no-body cases, unsupported/
  missing/duplicate source diagnostics, context/provenance/token mismatch
  diagnostics, malformed exact predicate-init and store-call predicate-token
  shape diagnostics, deterministic ordering, unchanged M57-M74 behavior, no
  raw helper parsing or raw query evaluator calls, no catalog/`tsldata`/host
  CPU/backend map reads during lowering evaluation, and no backend
  translation/rendering, generic predicate/store/body lowering, golden-file,
  or generated-output churn.
- Milestone 76 tests now prove exact post-branch intrinsic call-site
  structural/request IR without ARM/SVE, store, memory, pointer,
  variable-scope, backend, renderer, or output semantics: direct tests from
  accepted M75 predicate-path state, normal `lower_candidates` stage-order
  tests after `predicate_path_structural_request_lowering`, exact argument
  token/provenance recording for `pg`, `tmp.data()`, and `a`, explicit linkage
  from argument `0` `pg` to the accepted M75 slot-3 predicate-token use,
  diagnostics for malformed call-site shapes and token/argument mismatches,
  deterministic ordering, unchanged M57-M75 behavior including
  selected-branch-only diagnostics, no raw helper parsing or raw query
  evaluator calls, no catalog/`tsldata`/host CPU/backend map reads during
  lowering evaluation, and no backend translation/rendering, generic
  call/store/body lowering, golden-file, or generated-output churn.
- Milestone 77 tests prove behavior-preserving lowering architecture
  extraction, not new semantics: the full lowering-boundary unit suite remains
  green, focused M77 tests cover the private `_pipeline.py` stage-fact/
  dependency snapshot and the private `_exact_shapes.py` recognizer-token
  boundary, public `tslgen.lowering` imports remain stable, representative
  M57-M76 diagnostics keep their codes/severity/source locations where already
  asserted, repeated runs remain deterministic, and no backend translation,
  rendering, generated output, broad body/call/store/return parsing, raw
  helper dispatch, catalog/`tsldata`/host CPU/backend map reads, or runtime
  `frozen/` use is introduced.
- Milestone 78 tests must prove behavior-preserving package decomposition and
  real facade shrinkage: the full lowering-boundary unit suite remains green,
  focused M78 tests prove public import stability and exact array-body /
  array-initialization pipeline equivalence after code moves, `boundary.py`
  line-count validation proves at least 1,000 physical lines were removed from
  the 12,371-line pre-M78 baseline, representative M57-M77 diagnostics and
  deterministic ordering remain unchanged, and no backend translation,
  rendering, generated output, broad body/call/store/return/declaration/array
  semantics, raw helper dispatch, catalog/`tsldata`/host CPU/backend map
  reads, import cycles, duplicate moved code, or runtime `frozen/` use is
  introduced.
- M78 execution adds focused module-decomposition tests asserting that the
  accepted exact lowering types/functions still resolve through the
  `tslgen.lowering`/`boundary.py` facade while exact array-body shape rules and
  diagnostics resolve through the new private modules. The measured
  `boundary.py` line count is 11,109, which is 1,262 physical lines below the
  pre-M78 baseline.
- Milestone 79 tests must prove behavior-preserving typed model ownership
  extraction: the full lowering-boundary unit suite remains green; accepted
  public exact model/function imports remain stable through `tslgen.lowering`
  and `tslgen.lowering.boundary`; new private model modules import without
  circular dependency on `boundary.py`; `_array_body_shapes.py` consumes the
  shared exact helper aliases/specs instead of duplicating them; targeted
  `_array_body_diagnostics.py` helpers use moved models or small private
  protocols instead of unconstrained `Any`; representative moved model keys,
  constructor invariants, diagnostic codes/severity/source locations/messages,
  stage names/order, selected-branch-only diagnostics, and deterministic
  ordering remain unchanged; `boundary.py` line count is measured against the
  11,109-line post-M78 baseline; and no backend translation, rendering,
  generated output, golden-file churn, broad TSIL/body/call/store/return/
  declaration/array parsing, raw helper dispatch, catalog/`tsldata`/host CPU/
  backend map reads, import cycles, duplicate moved code, or runtime `frozen/`
  use is introduced.
- M79 execution adds focused unit coverage for the `boundary.py` facade
  re-exporting model-owned exact classes, `_array_body_shapes.py` sharing exact
  helper aliases/rules from `_array_body_models.py`, and
  `_array_body_diagnostics.py` consuming typed protocols instead of importing
  `Any`. The full lowering-boundary suite remains the primary behavior
  preservation check, and the measured `boundary.py` line count is 8,915,
  which is 2,194 physical lines below the 11,109-line post-M78 baseline.
- Milestone 80 tests must prove behavior-preserving validation boundary
  extraction: the full lowering-boundary unit suite remains green; public
  exact lowering imports remain stable through `tslgen.lowering` and
  `tslgen.lowering.boundary`; the new private validation module and accepted
  private lowering modules do not import `boundary.py`; representative moved
  validators/request-record helpers preserve diagnostic codes, severities,
  messages, paths, lines, columns, source locations, keys, and deterministic
  ordering; stage names/order/output identities and pipeline snapshots remain
  unchanged; `boundary.py` line count is measured against the 8,915-line
  post-M79 baseline; and no backend translation, rendering, generated output,
  broad TSIL/body/call/store/return/declaration/array parsing, raw helper
  dispatch, catalog/`tsldata`/host CPU/backend map reads, import cycles,
  duplicate moved code, or runtime `frozen/` use is introduced.
- M80 execution adds focused ownership/import-boundary tests for
  `tslgen.lowering._array_body_validation`, including AST checks against
  absolute and relative imports of `boundary.py`. The full lowering-boundary
  suite remains green, and `boundary.py` measures 7,208 physical lines against
  the 8,915-line post-M79 baseline.
- M81 execution adds and preserves focused generation-core ownership and
  import-boundary tests for the private generation modules. The tests prove
  public import stability, private-module import direction, and accepted
  generation-time behavior through the full lowering-boundary suite while
  rejecting private-module imports of `boundary.py` in absolute or relative
  form.
- M82 execution adds focused selected-body ownership/import-boundary coverage
  while preserving the full lowering-boundary suite. The tests prove public
  selected-body model imports through `tslgen.lowering` and
  `tslgen.lowering.boundary` remain stable, the new private selected-body
  model module and accepted private lowering modules do not import
  `boundary.py` or the package facade, concrete selected/no-selected envelope
  checks replace the broad structural seam, and M64-M76 consumers continue to
  observe the same nested envelope identity, stage order, and no-reparse
  behavior.
- M83 execution adds focused stage-contract ownership/import-boundary coverage
  while preserving the full lowering-boundary suite. The tests prove
  `GenerationLoweringStage`, stage aliases, and accepted mini-TSIL value-model
  dependencies resolve through `tslgen.lowering.boundary`, the new private
  stage-contract module owns the accepted stage/output contract, every accepted
  stage/output pairing validates, unknown-stage and wrong-output rejection keep
  the same exception class and message shape, private lowering modules do not
  import `boundary.py` or the package facade, and stage ordering, keys, output
  identity, and pipeline snapshots remain stable. `boundary.py` now measures
  4,807 physical lines, below the accepted M82 4,965-line baseline. Validation
  returned focused M83 `7 passed, 265 deselected`, full lowering-boundary
  `272 passed`, focused lowering mypy success across 15 source files, and full
  tooling validation success with corpus probes `3 passed`, unit discovery
  `606` tests OK, compileall OK, ruff OK, mypy OK across 119 source files, and
  diff-check OK.
- M84 testing proves exact array-body pipeline/source-adapter ownership moved
  without behavior change. Coverage includes private import-boundary tests for
  the new exact array-body pipeline/source/lowering modules, public facade
  import/call stability, representative direct typed value, stage-output, and
  `LoweredImplementation`-like source-adapter inputs, diagnostic preservation
  for unsupported/missing/duplicate/conflict/orphan/provenance-mismatch source
  cases, pipeline snapshot stability, stage order, keys, output identity,
  deterministic source locations, full lowering-boundary preservation, focused
  lowering mypy, tooling validation, and a line-count check against the
  accepted M83 4,807-line `boundary.py` baseline. Validation returned focused
  M84 `88 passed, 188 deselected`, full lowering-boundary `276 passed`,
  focused lowering mypy success across 18 source files, and full tooling
  validation success with corpus probes `3 passed`, unit discovery `610` tests
  OK, compileall OK, ruff OK, mypy OK across 122 source files, and diff-check
  OK. `boundary.py` now measures 1,898 physical lines.
- Planned M85 testing should prove selected-body lowering ownership moves
  without behavior change. Required coverage includes private import-boundary
  tests for the new selected-body lowering module, public facade import/call
  stability, replacement of the M84 selected-body-lowerer ownership guard,
  selected-body diagnostic preservation for unsupported source, missing
  provenance/body, malformed assignment, unsupported target/RHS,
  extra-statement, direct-intrinsic unsupported, and envelope inconsistency
  cases, pipeline snapshot stability, stage order, keys, output identity,
  selected-branch-only behavior, deterministic source locations, full
  lowering-boundary preservation, focused lowering mypy, tooling validation,
  and a line-count check against the accepted M84 1,898-line `boundary.py`
  baseline.
- M85 execution added focused public facade identity/call stability, private
  forbidden-import checks for `_selected_body_lowering.py`, selected-body
  diagnostic preservation including the focused `PrunedGenerationBranch`
  source-location regression, and selected-body stage/output identity and
  deterministic source-location coverage. Validation returned focused M85
  `12 passed, 268 deselected`, full lowering-boundary `280 passed`, focused
  lowering mypy success across 19 source files, and full tooling validation
  success with corpus probes `3 passed`, unit discovery `614` tests OK,
  compileall OK, ruff OK, mypy OK across 123 source files, and diff-check OK.
  `boundary.py` now measures 1,417 physical lines and
  `_selected_body_lowering.py` measures 538 physical lines.
- M86 execution added focused public facade identity/call stability, private
  import-direction checks for `_lowering_inputs.py` and
  `_mini_tsil_lowering.py`, payload classification and typed-opaque diagnostic
  preservation, direct parameter-add return lowering, `intrin_compose<add>`
  return lowering, mini-TSIL diagnostic/source-location preservation,
  stage/output identity, deterministic pipeline, and selected-branch-only
  coverage. Validation returned focused M86 `9 passed, 277 deselected`, full
  lowering-boundary `286 passed`, focused lowering mypy success across
  21 source files, and full tooling validation success with corpus probes
  `3 passed`, unit discovery `620` tests OK, compileall OK, ruff OK, mypy OK
  across 125 source files, and diff-check OK. `boundary.py` now measures
  1,145 physical lines, `_lowering_inputs.py` measures 128 physical lines, and
  `_mini_tsil_lowering.py` measures 188 physical lines.
- M87 execution added focused exact return-emission structural/request IR
  coverage without source-body repair. Coverage includes the exact
  `emit_return(tmp);` shape with accepted whitespace, returned-token linkage to
  the M73 declaration-shell variable token, M76 source forms, a narrow
  M76-only source protocol regression, deterministic stage insertion after the
  M76 post-branch call-site stage, source-location and key preservation,
  selected-branch-only behavior, snapshot identity, import boundaries, and
  negative diagnostics for malformed `emit_return`, wrong returned token,
  missing semicolon, expression/extra argument/member-access forms, missing or
  wrong return slot, context mismatch, and provenance mismatch. Validation
  returned focused M87 `6 passed, 286 deselected`, full lowering-boundary
  `292 passed`, focused lowering mypy success across 22 source files, and full
  tooling validation success with corpus probes `3 passed`, unit discovery
  `626` tests OK, compileall OK, ruff OK, mypy OK across 126 source files, and
  diff-check OK.
- M88 execution added exact array-body structural package assembly coverage
  from accepted M64-M87 facts without semantic body lowering. Coverage includes
  positive package assembly, source-ordered member identity and provenance
  preservation, missing/duplicate/malformed/mismatched/out-of-order/
  provenance-inconsistent diagnostics, deterministic package keys, stage order
  after `return_emission_structural_request_lowering`, selected-branch-only
  behavior, pipeline snapshot stability, import-boundary checks for the focused
  package module, and negative coverage proving no source-body repair, broad
  TSIL parsing, store/return/backend/SVE semantics, rendering, or generated
  output is introduced. Validation returned focused M88
  `8 passed, 291 deselected`, full lowering-boundary `299 passed`, focused
  lowering mypy success across 23 source files, and full tooling validation
  success with corpus probes `3 passed`, unit discovery `633` tests OK,
  compileall OK, ruff OK, mypy OK across 127 source files, and diff-check OK.
- M89 execution added exact array backend-deferred request inventory coverage
  from the accepted M88 package without backend resolution. Coverage includes
  positive inventory assembly from direct package, M88 stage output, and
  one-package source inputs; identity/provenance preservation for the M88
  package, M72 deferred backend-uninit value, and M67 backend-value request
  record; diagnostics for unsupported, missing, duplicate, malformed,
  context-mismatched, wrong-policy, wrong-request, wrong-source-text,
  source-location, slot/variable, and provenance-inconsistent inputs;
  deterministic stage order after `array_body_structural_package_assembly`;
  selected-branch-only behavior; pipeline snapshot stability; import-boundary
  checks for the focused inventory module; and negative coverage proving no
  backend map reads, backend-uninit translation, renderer-ready IR, rendering,
  generated output, or generic backend-value evaluation is introduced.
  Validation returned focused M89 `15 passed, 291 deselected`, full
  lowering-boundary `306 passed`, focused lowering mypy success across 24
  source files, and full tooling validation success with corpus probes
  `3 passed`, unit discovery `640` tests OK, compileall OK, ruff OK, mypy OK
  across 128 source files, and diff-check OK.
- M90 planning selects exact array lowering completion package coverage. The
  execution tests should prove positive completion-package assembly from direct
  M89 inventory input, M89 stage-output input, and narrowly validated
  package-plus-inventory source input; identity/provenance preservation for
  accepted M88/M89/M73/M72/M67 objects; explicit unresolved dependency records
  for the accepted M89 `value_backend_uninit_array` member; diagnostics for
  unsupported, missing, duplicate, malformed, package/inventory mismatched,
  context-mismatched, source-location mismatched, wrong-member-set,
  wrong-policy, and provenance-inconsistent inputs; deterministic stage order
  after `array_backend_deferred_request_inventory`; selected-branch-only
  behavior; pipeline snapshot stability; import-boundary checks for the
  focused completion module; and negative coverage proving no backend map
  reads, backend-uninit translation, Stage 9 planning, renderer-ready IR,
  rendering, generated output, source-body repair, broad TSIL parsing, or
  generic backend-value evaluation is introduced.

Deferred parity checks:

- Generated C++ test-source parity beyond the selected M49 `add_i32_basic`
  source fixture remains deferred until explicitly reintroduced as its own
  milestone.
- CLI compatibility workflow tests from the old Milestone 41 resume only after
  a selected CLI workflow is explicitly reintroduced as its own milestone.
- Legacy-style coverage JSON adapter tests beyond the selected M50 row remain
  deferred until broader report parity is reintroduced as its own milestone.

## Review Expectations

Reviewers should check:

- Tests exercise new architecture, not legacy compatibility shims.
- Invalid inputs produce diagnostics rather than crashes.
- Deterministic tests exist for any new ordering-sensitive collection.
- Golden files are readable and intentionally scoped.
