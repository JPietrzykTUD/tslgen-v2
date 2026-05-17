# Frozen Parity Baselines

Milestone 35 records the first functional-parity inventory and baseline
selection. It uses `frozen/` as behavioral evidence only. The selected baseline
does not port legacy modules, execute legacy workflows, or make `frozen/` a
runtime dependency of production code or tests.

Capture metadata:

- Capture date: 2026-05-01.
- Repository commit inspected: `32cf01af92743d5fdc2fd70f7fa16374d38dd957`.
- Extraction method: line-number inspection of committed `frozen/` outputs and
  current `tsldata/` source data.
- Legacy workflows executed: none.
- Fixture files copied in this milestone: none.

Accepted redesign boundaries available for future parity slices:

- `PipelineResult` retains parsed, catalog, validation, selection, dependency,
  backend manifest, artifact-plan, and rendered-artifact outputs.
- `ArtifactPlan` and `ArtifactSet` carry deterministic logical paths, metadata,
  content, and digests before any filesystem write.
- `ArtifactWriteReport` is the only accepted filesystem mutation report.
- `LoweringPlan` owns TSIL semantics before renderers consume lowered bodies.
- `BackendRenderer` receives an already-planned backend artifact request and an
  already-selected candidate set.
- `TestSourcePlan` owns production test-source planning before test rendering.
- `PipelineCoverageReport` and candidate-dependency report DTOs own reporting
  data without rerunning pipeline stages.
- The Milestone 21 validation profile remains the host-independent default
  validation surface.

## Inventory

| Evidence path | Backend | Artifact kind | Template family | Primitive family | Extension | Type | Required toolchain | Parity relevance | Recommended parity level | Proposed milestone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `frozen/out/tsl/tsl_native.hpp` | C++ | generated header | primary, specialization, wrapper | `fundamental/add` first; broad native families later | `scalar`, `avx2` first; broad native extensions later | `si32`, `ui32`, `f32` first | none for golden inspection; C++ compiler only for optional future execution | first C++ output target | semantic equivalence plus redesign-owned exact golden text; selected snippets only | M36, M37, M39 transitional, M40 correction |
| `frozen/out/tsl/tsl_generic.hpp` | C++ | generated header | generic specializations and wrappers | broad primitive families | `generic` | sized generic type matrix | none for inspection; C++ compiler for optional execution | deferred generic parity evidence | semantic equivalence; no whole-file byte parity | later generic C++ milestone |
| `frozen/out/tsl/CMakeLists.txt` | C++ | sidecar build metadata | output layout | all generated headers | selected generated header set | n/a | CMake only if execution is selected later | selected as output-layout sidecar evidence | byte-for-byte whole-file candidate when a future sidecar slice selects it | deferred after M36 |
| `frozen/out/tsl/tsl_flags.cmake` | C++ | sidecar compile flags | output layout | all generated headers | required native extensions | n/a | CMake/C++ compiler only if execution is selected later | selected as required-flags sidecar evidence | semantic for required flag sets; byte-for-byte only for a selected generated input | deferred after native C++ parity |
| `frozen/out/reports/primitive_coverage.json` | report | coverage JSON | row-oriented coverage | broad primitive catalog | broad extension matrix | broad type matrix | none | report parity evidence, not first output target | selected-row semantic/field parity; no whole-file byte parity | M50 for selected `add`/`avx2`/`cpp`/`f32` row; broader coverage parity later |
| `frozen/out/reports/primitive_coverage.html` | report | coverage HTML | row table | broad primitive catalog | broad extension matrix | broad type matrix | none | documentation/report evidence only for now | redesign-owned HTML unless a later milestone selects exact rows | later docs/report milestone |
| `frozen/jinja/cpp/test_file.j2` | C++ | generated test source evidence | test file wrapper | broad test families | selected test extension | selected test type | none for inspection; `gtest`/C++ only for optional execution | selected generated-test structure evidence | semantic equivalence for one generated test source | M49 for selected `add_i32_basic`; broader generated-test source rendering later |
| `frozen/jinja/cpp/test_case.j2` | C++ | generated test case evidence | `binary` first; broad tests later | `fundamental/add` first | selected extension | `si32` first | none for inspection; `gtest`/C++ only for optional execution | selected generated-test behavior evidence | semantic equivalence for test name, inputs, expected values, wrapper call, and assertion shape | M49 for selected `add_i32_basic`; broader generated-test source rendering later |
| `frozen/generator_specs/tests.yaml` | C++/Rust | test planning metadata | test support policy | broad primitive families | runtime and fixed-width extension policy | broad type matrix | none | test planning and runtime-lane evidence | semantic policy evidence; no direct golden output | M49 for selected C++ source fixture; broader generated-test and toolchain phases later |
| `frozen/generator_specs/backend_cpp.yaml` | C++ | backend manifest evidence | primary, specialization, wrappers, combined templates | broad template families | all C++ supported extensions | broad type matrix | none | C++ backend metadata evidence | semantic manifest policy; no template-file architecture | M36, M37, M40 |
| `frozen/generator_specs/backend_rust.yaml` | Rust | backend manifest evidence | primary, specialization, wrappers, trait | broad Rust families | Rust-supported extensions | broad type matrix | Cargo only for future execution | deferred Rust parity evidence | semantic manifest policy; no current output baseline | future Rust parity phase |
| `frozen/generator_specs/wrapper_shapes.yaml` | C++/Rust | wrapper signature evidence | `binary` first; broad wrappers later | `fundamental/add` first | selected extension | selected type | none | selected wrapper relationship evidence | semantic equivalence for public wrapper signature and delegation | M37 |
| `frozen/tsl-gen/tsl_gen/tsil.lark` | neutral lowering | TSIL grammar evidence | expressions, calls, loops, intrinsics | broad primitive TSIL | all | all | none | TSIL syntax evidence | semantic lowering fixtures only; no legacy parser dependency | M38 and later TSIL milestones |
| `tsldata/primitives/arithmetic/fundamental.tsl` | source corpus | TSL primitive source | `binary` first | `fundamental/add` | `scalar`, `avx2` first | `si32`, `ui32`, `f32` first | none | active source evidence for selected baseline | accepted source-data behavior, not generated output | M37, M38, M39 transitional, M40 correction |
| `frozen/run_all.sh` | workflow | generation/build/test/docs workflow | all | selected by CLI filters | host-derived or explicit extensions | broad | CMake, compilers, optional qemu, Cargo, MkDocs | workflow parity evidence | one generation-only workflow first; build/test/docs deferred | deferred CLI milestone |
| `frozen/run_tests.py` | workflow | generated test execution workflow | test execution | selected primitives or files | explicit extension matrix | broad | CMake, compilers, optional qemu, Cargo, possible googletest fetch | executable-test evidence | not in default validation; future optional toolchain policy | future toolchain phase |
| `frozen/tsl-gen/tsl_gen/app/cli.py` | workflow | legacy CLI evidence | codegen and tests | selected primitives/templates | explicit extensions and CPU flags | broad | none for inspection | CLI compatibility evidence | one mapped generation workflow first; no drop-in claim | deferred CLI milestone |

## Selected First Parity Target

The first parity target is C++ `binary/add` output for `tsl/tsl_native.hpp`.
It is split across future implementation slices so each slice remains
reviewable:

1. M36 owns the selected output path and minimum support preamble.
2. M37 owns scalar primary, specialization, and wrapper parity for `si32` and
   `ui32`.
3. M38 owns the selected bare `intrin_compose<add>` lowering slice.
4. M39 owns the transitional native `avx2/f32` output slice and must not be
   expanded as the long-term architecture.
5. M40 owns backend translation and intrinsic-composition correction while
   preserving the selected M39 output from already-resolved backend-call IR.
6. M43 owns exact base scalar generation-time type queries needed before native
   integer suffix/type work.
7. M44-M46 own the backend modifier and type-spelling boundaries before native
   integer output expands.
8. M47 is the accepted native integer add parity slice for `avx2` `si32` and
   `ui32`.
9. M48 is the accepted signedness predicate branch-pruning slice over typed M43
   `base.in` values. It supports later shift/conversion parity and is not an
   output parity slice.
10. M49 is accepted as the generated C++ `add_i32_basic` test-source parity
   slice.
11. M50 is accepted as the legacy coverage JSON adapter row slice.
12. M51 is accepted as the exact plain-`else` signedness branch-pruning syntax
   slice. It remains generation-time lowering only and is not an output parity
   slice.
13. M52 is accepted as the concrete integer generation type/signedness
   expansion slice. It remains generation-time lowering only and is not an
   output parity slice.
14. M53 is accepted as the catalog-validated concrete integer generation
    rule-source slice. It remains a semantic rule-source boundary only and is
    not an output parity slice.
15. M54 is accepted as the catalog-derived concrete integer rule pipeline
    wiring slice. It wires the M53 rule source through the normal
    lowering-input path and is not an output parity slice.
16. M55 is a generation-time semantic lowering
    slice for the exact scalar size-byte value query. It produces typed
    generation values and is not an output parity slice.
17. M56 is accepted as a generation-time semantic lowering slice for the exact
    scalar size-bytes-times-eight arithmetic value expression. It is not an
    output parity slice.
18. M57 is accepted as a generation-time semantic lowering slice for exact
    size-byte equality predicates over `== 2`, `== 4`, and `== 8`. It is not
    an output parity slice.
19. CLI workflow compatibility, coverage JSON adapter breadth beyond the
    selected M50 row, executable generated tests, and broad generated-test parity
    remain deferred until explicitly selected as separate milestones.

This selected output target is small enough because it uses one primitive
family, one template family, two scalar integer type tags, one native
floating-point extension/type pair, and selected AVX2 integer output after
typed suffix/type-spelling translation. It exercises the important parity
boundaries without requiring full headers, full TSIL, all wrappers,
generated-test execution, Rust parity, or broad report/documentation parity.
M50 reintroduces only one selected report row while full report/documentation
parity remains deferred. M48, M51, and M52 are post-output lowering
prerequisites for later shift/conversion parity, not additional generated-output
targets. M49 reintroduces only one generated C++ test-source parity baseline
and still does not add compiler execution.

## Baseline Decisions

### CPP-ADD-LAYOUT

- Exact behavior target: emit the selected C++ generated header under logical
  path `tsl/tsl_native.hpp`.
- Legacy evidence path: `frozen/out/tsl/tsl_native.hpp`,
  `frozen/out/tsl/CMakeLists.txt`, and `frozen/out/tsl/tsl_flags.cmake`.
- Source line ranges:
  - `frozen/out/tsl/tsl_native.hpp:1-30` for includes and basic support macros.
  - `frozen/out/tsl/tsl_native.hpp:147-167` for scalar/AVX2 extension tags and
    the `simd` primary declaration evidence.
  - `frozen/out/tsl/tsl_native.hpp:720-725` for `detail::reg_param` evidence.
  - `frozen/out/tsl/CMakeLists.txt:1-9` remains sidecar evidence for a later
    output-workflow slice.
  - `frozen/out/tsl/tsl_flags.cmake:1-2` remains required-flags sidecar
    evidence for a later native-extension slice.
- Fixture path selected by M36:
  `tslgen/tests/fixtures/golden/parity/cpp/native_layout_excerpt.hpp`.
- Fixture provenance:
  `tslgen/tests/fixtures/golden/parity/cpp/native_layout_excerpt.provenance.md`.
- Parity level: exact logical path parity; selected-preamble semantic parity
  with redesign-owned exact golden output. Whole-header byte parity is
  explicitly not selected.
- Sidecar decision: M36 does not render `tsl/CMakeLists.txt` or
  `tsl/tsl_flags.cmake`. `tsl_flags.cmake` depends on native-extension required
  flags that are not rendered until later parity slices, so sidecars remain
  evidence only for now.
- Validation method: artifact descriptor/logical-path golden tests,
  deterministic digest checks, unsupported layout diagnostics, and fixture
  provenance tests that do not read from `frozen/` at runtime.
- Known limitations: broad helper functions, all includes, all macros, and all
  sidecar flag combinations remain deferred. The preamble fixture contains only
  the support declarations needed before M37 adds scalar primary,
  specialization, and wrapper parity.

### CPP-ADD-SCALAR

- Exact behavior target: primary `detail::add_binary` declaration, scalar
  `simd<int32_t, scalar>` and `simd<uint32_t, scalar>` specializations, and
  public `tsl::add<Vec>` wrapper delegation.
- Legacy evidence path: `frozen/out/tsl/tsl_native.hpp` and
  `frozen/generator_specs/wrapper_shapes.yaml`.
- Source line ranges:
  - `frozen/out/tsl/tsl_native.hpp:805-810` for the primary detail declaration.
  - `frozen/out/tsl/tsl_native.hpp:19433-19452` for
    `simd<int32_t, scalar>`.
  - `frozen/out/tsl/tsl_native.hpp:19513-19532` for
    `simd<uint32_t, scalar>`.
  - `frozen/out/tsl/tsl_native.hpp:39071-39075` for public wrapper delegation.
  - `frozen/generator_specs/wrapper_shapes.yaml:47-56` for the C++ `binary`
    wrapper signature evidence.
- Active source evidence path: `tsldata/primitives/arithmetic/fundamental.tsl`.
- Active source line ranges:
  - `tsldata/primitives/arithmetic/fundamental.tsl:2` for
    `prim<v:=(v,v)> add(left, right)`.
  - `tsldata/primitives/arithmetic/fundamental.tsl:27-31` for scalar
    `emit_return(left + right);`.
- Fixture path selected by M37:
  `tslgen/tests/fixtures/golden/parity/cpp/add_scalar_excerpt.hpp`.
- Fixture provenance:
  `tslgen/tests/fixtures/golden/parity/cpp/add_scalar_excerpt.provenance.md`.
- Parity level: semantic equivalence against legacy evidence plus an exact
  redesign-owned golden file for generated output. Byte-for-byte legacy
  whitespace parity is not selected for scalar specializations or wrappers.
- Validation method: M37 tests assert primary name `add_binary`, scalar C++
  type mapping, `has_return_value`, `native_supported`, parameter order,
  lowered `return left + right;`, public wrapper name `add`, delegation to
  `::tsl::detail::add_binary<Vec>::apply(left, right)`, unsupported
  template/type/extension/wrapper diagnostics, digest determinism, and fixture
  provenance without reading from `frozen/` at runtime.
- Known limitations: ABI naming, overload policy, masked variants, generic
  loop-backed variants, and combined binary specializations remain deferred.

### CPP-ADD-AVX2-F32

- Exact behavior target: native C++ specialization for `add_binary` over
  `simd<float, avx2>` using `_mm256_add_ps(left, right)`.
- Legacy evidence path: `frozen/out/tsl/tsl_native.hpp`.
- Source line range:
  - `frozen/out/tsl/tsl_native.hpp:24337-24355`.
- Active source evidence path: `tsldata/primitives/arithmetic/fundamental.tsl`.
- Active source line range:
  - `tsldata/primitives/arithmetic/fundamental.tsl:77-80` for the `avx2/f?`
    `intrin_compose<add>` form.
- Report evidence path:
  - `frozen/out/reports/primitive_coverage.json:57762-57777` records
    `add`, `avx2`, `cpp`, `f32`, `has_tsil=true`, and
    `effective_present=true`.
- Report field construction evidence:
  - `frozen/tools/report_primitive_coverage.py:242-266` records the selected
    row field construction and string-valued boolean conversion.
- Fixture path selected by M39:
  `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_f32_excerpt.hpp`.
- Fixture provenance:
  `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_f32_excerpt.provenance.md`.
- Parity level: semantic equivalence against legacy evidence plus an exact
  redesign-owned golden file for generated output. Byte-for-byte legacy
  whitespace parity is not selected.
- Validation method: M38 lowers the selected bare `intrin_compose<add>` helper
  form, M39 renders a deterministic transitional C++ specialization with
  `simd<float, avx2>`, parameter order `left, right`, `native_supported=true`,
  and `_mm256_add_ps(left, right)`, and M40 preserves that output while proving
  the selected backend intrinsic call is derived from typed `tsldata` metadata
  and consumed as already-resolved backend-call IR instead of renderer-local
  intrinsic lookup.
- Known limitations: integer intrinsic suffix inference, AVX512/SSE/NEON/SVE
  variants, masks, generic calls, and translation-map-wide evaluation remain
  deferred.

### CPP-ADD-AVX2-I32-U32

- Exact behavior target: native C++ specializations for `add_binary` over
  `simd<int32_t, avx2>` and `simd<uint32_t, avx2>` using
  `_mm256_add_epi32(left, right)`.
- Legacy evidence path: `frozen/out/tsl/tsl_native.hpp`.
- Source line ranges:
  - `frozen/out/tsl/tsl_native.hpp:24460-24477` for
    `simd<int32_t, avx2>`.
  - `frozen/out/tsl/tsl_native.hpp:24712-24729` for
    `simd<uint32_t, avx2>`.
- Active source evidence path: `tsldata/primitives/arithmetic/fundamental.tsl`.
- Active source line range:
  - `tsldata/primitives/arithmetic/fundamental.tsl:65-75` for the `avx2/?i?`
    `intrin_compose<add, suffix=value<backend>(intrin::suffix(...))>` form.
- Prerequisite phase:
  - M44 selects intrinsic suffix as the first backend modifier family.
  - M45 translates the selected suffix from typed M43 `GenerationTypeRef`
    values and produces `epi32` for selected `si32`/`ui32` AVX2 integer add
    suffix requests.
  - M46 translates selected C++ type spellings from typed M43
    `GenerationTypeRef` values.
- M47 output:
  - M47 renders the selected integer output only after those translated values
    exist and uses `_mm256_add_epi32(left, right)` for both selected signed and
    unsigned 32-bit AVX2 add specializations.
- Fixture path:
  `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_i32_u32_excerpt.hpp`.
- Parity level: semantic equivalence against legacy evidence plus an exact
  redesign-owned golden file for the selected excerpt. Whole-header
  byte-for-byte parity is not selected.
- Known limitations: SSE, AVX512, masks, generic calls, generated tests,
  compiler execution, and translation-map-wide evaluation remain deferred.

### CPP-ADD-I32-TEST

- Exact behavior target: one generated C++ test source for `add_i32_basic`.
- Legacy evidence paths: `frozen/jinja/cpp/test_file.j2`,
  `frozen/jinja/cpp/partials/test_common.j2`,
  `frozen/jinja/cpp/test_case.j2`,
  `frozen/jinja/cpp/partials/test_vectors.j2`, and
  `frozen/generator_specs/tests.yaml`.
- Source line ranges:
  - `tsldata/primitives/arithmetic/fundamental.tsl:6` for `add_i32_basic`
    inputs and expected values.
  - `frozen/jinja/cpp/test_file.j2:1-56` for include and `TEST(...)`
    registration structure.
  - `frozen/jinja/cpp/partials/test_common.j2:1-13` for the boolean test
    function and `Vec` alias shape.
  - `frozen/jinja/cpp/test_case.j2:51-63` for the `binary` test-case shape.
  - `frozen/jinja/cpp/partials/test_vectors.j2:38-50` for store-vector
    expansion through `tsl::store_aligned_false<Vec>(...)`.
  - `frozen/generator_specs/tests.yaml:45-59` for C++ test-generation policy
    evidence.
- Fixture path in this milestone:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.cpp`.
- Provenance path in this milestone:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.provenance.md`.
- Parity level: semantic equivalence for test name, selected primitive,
  input vectors, expected vector, wrapper call, typed C++ `int32_t` spelling in
  the `Vec` alias, boolean test function shape, and assertion/registration
  intent.
  Byte-for-byte legacy template output is not selected.
- Validation method: M49 must render deterministic test source from
  `TestSourcePlan` data and explicit typed C++ type-spelling input. It must not
  execute compilers or `gtest` by default.
- Known limitations: executable assertion framework breadth, mask resizing,
  runtime-lane tests, support headers, and compile/run orchestration remain
  deferred.

### COVERAGE-ADD-AVX2-F32-ROW

- Exact behavior target: selected legacy-style coverage JSON row fields for
  `add`, `avx2`, `cpp`, `f32`.
- Legacy evidence path: `frozen/out/reports/primitive_coverage.json`.
- Source line range:
  - `frozen/out/reports/primitive_coverage.json:57762-57777`.
- Field-construction evidence:
  - `frozen/tools/report_primitive_coverage.py:242-266`.
- Fixture path selected by M50:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.json`.
- Provenance path selected by M50:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.provenance.md`.
- Parity level: selected-field semantic parity and stable field ordering for
  the adapter output. Whole-report row count parity is not selected.
- Validation method: M50 must render the selected row from accepted typed report
  DTOs and must not rerun parsing, selection, lowering, or rendering during
  report serialization.
- Known limitations: full coverage matrix parity and HTML/site parity remain
  deferred.

## Deferred Families

- Whole-file byte-for-byte parity for `tsl_native.hpp` and `tsl_generic.hpp`.
- Broad C++ wrappers, combined specializations, masks, loads/stores, casts,
  reductions, sequences, allocation, and stream output.
- Generic and oneAPI FPGA sized-extension code generation.
- Rust generated output, Rust bodies, Rust generated tests, and Cargo
  integration.
- C17 activation.
- Full TSIL grammar, semantic calls, loops, variables, broad type/value
  queries, generation-time conditions beyond the selected M42/M48/M51 pruning
  forms, concrete integer rule-source behavior beyond accepted M53 ownership
  and M54 catalog-to-lowering wiring, scalar value queries beyond the selected
  M55 size-byte helper, arithmetic over generation values beyond accepted M56,
  comparisons over generation values beyond the accepted M57 exact size-byte
  equality predicate slice, branch-chain pruning beyond the accepted narrow M59
  slice over those predicates, selected branch body handling beyond the
  accepted opaque M60 handoff, M61 assignment-form recognition slice, and
  accepted M62 unresolved body-IR shape plus accepted M63 singleton envelope
  shape, accepted M64 exact structural slot envelope, and accepted M65
  pipeline integration for that envelope, selected M66 exact
  array-initialization slot form IR, and backend translation-map evaluation
  beyond the selected M40/M45/M46 requests.
- Executable generated tests, compiler invocation, qemu, rustup targets, and
  googletest download or vendoring.
- Full legacy CLI drop-in compatibility and `run_all.sh` replacement.
- Full primitive coverage JSON/HTML/site parity.

## Future Fixture Provenance Requirements

When a future milestone creates fixture files from the selected baselines, each
fixture must record:

- source evidence path;
- source line range or extraction method;
- capture date or source commit;
- whether the fixture is copied verbatim, excerpted, normalized, or
  redesign-owned;
- intended parity level;
- known limitations.

Fixture tests must assert that provenance metadata exists and that the fixture
does not read from `frozen/` at test runtime.
