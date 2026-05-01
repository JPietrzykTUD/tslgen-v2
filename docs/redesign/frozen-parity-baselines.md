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
| `frozen/out/tsl/tsl_native.hpp` | C++ | generated header | primary, specialization, wrapper | `fundamental/add` first; broad native families later | `scalar`, `avx2` first; broad native extensions later | `si32`, `ui32`, `f32` first | none for golden inspection; C++ compiler only for optional future execution | first C++ output target | semantic equivalence plus redesign-owned exact golden text; selected snippets only | M36, M37, M39 |
| `frozen/out/tsl/tsl_generic.hpp` | C++ | generated header | generic specializations and wrappers | broad primitive families | `generic` | sized generic type matrix | none for inspection; C++ compiler for optional execution | deferred generic parity evidence | semantic equivalence; no whole-file byte parity | later generic C++ milestone |
| `frozen/out/tsl/CMakeLists.txt` | C++ | sidecar build metadata | output layout | all generated headers | selected generated header set | n/a | CMake only if execution is selected later | selected as output-layout sidecar evidence | byte-for-byte whole-file candidate when a future sidecar slice selects it | deferred after M36 |
| `frozen/out/tsl/tsl_flags.cmake` | C++ | sidecar compile flags | output layout | all generated headers | required native extensions | n/a | CMake/C++ compiler only if execution is selected later | selected as required-flags sidecar evidence | semantic for required flag sets; byte-for-byte only for a selected generated input | deferred after native C++ parity |
| `frozen/out/reports/primitive_coverage.json` | report | coverage JSON | row-oriented coverage | broad primitive catalog | broad extension matrix | broad type matrix | none | report parity evidence, not first output target | selected-row semantic/field parity; no whole-file byte parity | M42 |
| `frozen/out/reports/primitive_coverage.html` | report | coverage HTML | row table | broad primitive catalog | broad extension matrix | broad type matrix | none | documentation/report evidence only for now | redesign-owned HTML unless a later milestone selects exact rows | later docs/report milestone |
| `frozen/jinja/cpp/test_file.j2` | C++ | generated test source evidence | test file wrapper | broad test families | selected test extension | selected test type | none for inspection; `gtest`/C++ only for optional execution | selected generated-test structure evidence | semantic equivalence for one generated test source | M40 |
| `frozen/jinja/cpp/test_case.j2` | C++ | generated test case evidence | `binary` first; broad tests later | `fundamental/add` first | selected extension | `si32` first | none for inspection; `gtest`/C++ only for optional execution | selected generated-test behavior evidence | semantic equivalence for test name, inputs, expected values, wrapper call, and assertion shape | M40 |
| `frozen/generator_specs/tests.yaml` | C++/Rust | test planning metadata | test support policy | broad primitive families | runtime and fixed-width extension policy | broad type matrix | none | test planning and runtime-lane evidence | semantic policy evidence; no direct golden output | M40 and later toolchain phase |
| `frozen/generator_specs/backend_cpp.yaml` | C++ | backend manifest evidence | primary, specialization, wrappers, combined templates | broad template families | all C++ supported extensions | broad type matrix | none | C++ backend metadata evidence | semantic manifest policy; no template-file architecture | M36, M37, M39 |
| `frozen/generator_specs/backend_rust.yaml` | Rust | backend manifest evidence | primary, specialization, wrappers, trait | broad Rust families | Rust-supported extensions | broad type matrix | Cargo only for future execution | deferred Rust parity evidence | semantic manifest policy; no current output baseline | future Rust parity phase |
| `frozen/generator_specs/wrapper_shapes.yaml` | C++/Rust | wrapper signature evidence | `binary` first; broad wrappers later | `fundamental/add` first | selected extension | selected type | none | selected wrapper relationship evidence | semantic equivalence for public wrapper signature and delegation | M37 |
| `frozen/tsl-gen/tsl_gen/tsil.lark` | neutral lowering | TSIL grammar evidence | expressions, calls, loops, intrinsics | broad primitive TSIL | all | all | none | TSIL syntax evidence | semantic lowering fixtures only; no legacy parser dependency | M38 and later TSIL milestones |
| `tsldata/primitives/arithmetic/fundamental.tsl` | source corpus | TSL primitive source | `binary` first | `fundamental/add` | `scalar`, `avx2` first | `si32`, `ui32`, `f32` first | none | active source evidence for selected baseline | accepted source-data behavior, not generated output | M37, M38, M39, M40 |
| `frozen/run_all.sh` | workflow | generation/build/test/docs workflow | all | selected by CLI filters | host-derived or explicit extensions | broad | CMake, compilers, optional qemu, Cargo, MkDocs | workflow parity evidence | one generation-only workflow first; build/test/docs deferred | M41 |
| `frozen/run_tests.py` | workflow | generated test execution workflow | test execution | selected primitives or files | explicit extension matrix | broad | CMake, compilers, optional qemu, Cargo, possible googletest fetch | executable-test evidence | not in default validation; future optional toolchain policy | future toolchain phase |
| `frozen/tsl-gen/tsl_gen/app/cli.py` | workflow | legacy CLI evidence | codegen and tests | selected primitives/templates | explicit extensions and CPU flags | broad | none for inspection | CLI compatibility evidence | one mapped generation workflow first; no drop-in claim | M41 |

## Selected First Parity Target

The first parity target is C++ `binary/add` output for `tsl/tsl_native.hpp`.
It is split across future implementation slices so each slice remains
reviewable:

1. M36 owns the selected output path and minimum support preamble.
2. M37 owns scalar primary, specialization, and wrapper parity for `si32` and
   `ui32`.
3. M38 owns the next TSIL lowering form:
   `emit_return(intrin_compose<add>(left, right));`, represented as a
   backend-neutral intrinsic-compose return.
4. M39 owns native `avx2/f32` intrinsic rendering.
5. M40 owns one generated C++ test source for `add_i32_basic`.
6. M41 may map one generation-only CLI workflow to the accepted pipeline after
   the selected C++ artifact exists.
7. M42 may add selected legacy coverage JSON row parity.

This target is small enough because it uses one primitive family, one template
family, two scalar integer type tags, and one native floating-point
extension/type pair. It exercises the important parity boundaries without
requiring full headers, full TSIL, all wrappers, generated-test execution, Rust
parity, or report/documentation parity.

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
- Fixture path in this milestone: none.
- Proposed future fixture path:
  `tslgen/tests/fixtures/golden/parity/cpp/add_avx2_f32_excerpt.hpp`.
- Parity level: semantic equivalence against legacy evidence plus an exact
  redesign-owned golden file for future generated output. Byte-for-byte legacy
  whitespace parity is not selected.
- Validation method: M38 lowers the selected `intrin_compose<add>` form to a
  typed intrinsic-compose return named `add` with ordered parameter-reference
  arguments; future M39 must render a deterministic C++ specialization with
  `simd<float, avx2>`, parameter order `left, right`,
  `native_supported=true`, and `_mm256_add_ps(left, right)`.
- Known limitations: integer intrinsic suffix inference, AVX512/SSE/NEON/SVE
  variants, masks, generic calls, and translation-map-wide evaluation remain
  deferred.

### CPP-ADD-I32-TEST

- Exact behavior target: one generated C++ test source for `add_i32_basic`.
- Legacy evidence paths: `frozen/jinja/cpp/test_file.j2`,
  `frozen/jinja/cpp/test_case.j2`, and `frozen/generator_specs/tests.yaml`.
- Source line ranges:
  - `tsldata/primitives/arithmetic/fundamental.tsl:6` for `add_i32_basic`
    inputs and expected values.
  - `frozen/jinja/cpp/test_file.j2:1-56` for include and `TEST(...)`
    registration structure.
  - `frozen/jinja/cpp/test_case.j2:51-63` for the `binary` test-case shape.
- Fixture path in this milestone: none.
- Proposed future fixture path:
  `tslgen/tests/fixtures/golden/parity/cpp/add_i32_basic_test.cpp`.
- Parity level: semantic equivalence for test name, selected primitive,
  input vectors, expected vector, wrapper call, and assertion intent.
  Byte-for-byte legacy template output is not selected.
- Validation method: future M40 must render deterministic test source from
  `TestSourcePlan` data and must not execute compilers or `gtest` by default.
- Known limitations: executable assertion framework breadth, mask resizing,
  runtime-lane tests, support headers, and compile/run orchestration remain
  deferred.

### COVERAGE-ADD-AVX2-F32-ROW

- Exact behavior target: selected legacy-style coverage JSON row fields for
  `add`, `avx2`, `cpp`, `f32`.
- Legacy evidence path: `frozen/out/reports/primitive_coverage.json`.
- Source line range:
  - `frozen/out/reports/primitive_coverage.json:57762-57777`.
- Fixture path in this milestone: none.
- Proposed future fixture path:
  `tslgen/tests/fixtures/golden/parity/reports/add_avx2_f32_coverage_row.json`.
- Parity level: selected-field semantic parity and stable field ordering for
  the adapter output. Whole-report row count parity is not selected.
- Validation method: future M42 must render rows from accepted report DTOs and
  must not rerun parsing, selection, lowering, or rendering during report
  serialization.
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
- Full TSIL grammar, semantic calls, loops, variables, type/value queries,
  generation-time conditions, and backend translation-map evaluation.
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
