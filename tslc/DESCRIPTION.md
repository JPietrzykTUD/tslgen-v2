# tslc — what it is and how it works

A deep-orientation companion to [README.md](README.md) (quick start) and
[CHARTER.md](CHARTER.md) (the design rules). This file explains the *shape* of
the system: what it compiles, the pipeline, the two nested input languages, and
the design decisions that matter.

## What it is

`tslc` is a **compiler that generates a SIMD wrapper library**. It reads a
declarative data language (`.tsl` files under `tsldata/`) describing abstract
SIMD *primitives* (`add`, `sub`, `load`, `gather`, `blend`, …) and emits
deterministic, compilable **C++ and Rust** source implementing each primitive
across a matrix of:

- **hardware extensions** — `scalar`, `sse`, `avx2`, `avx512`, `neon`, `sve`, a
  portable `generic`, … (with inheritance/fallback chains);
- **scalar types** — `si8…si64`, `ui8…ui64`, `f32`, `f64`;
- **machine profiles** — skylake, icelake, etc. (a named CPU-feature set).

The architecture keeps a rich **vocabulary** of domain/IR types while
**budgeting plumbing tightly**: one body model (`Segment`), one lowered form
(`LoweredSpecialization`), and result objects that carry only `(value,
diagnostics)`. Progress is tracked by a coverage table
(*primitive × extension × backend → compiles?*) and by generated artifacts that
build, not by the number of internal abstractions.

## The pipeline

The compiler is a pure function once source data and static compiler assets are
loaded, orchestrated in [pipeline.py](src/tslc/pipeline.py):

```
sources + compiler assets → parse → catalog → select → scan body → lower → finalize names → validate/plan → render → write → verify
```

| Stage | Module | Role |
|---|---|---|
| **compiler assets** | [compiler_assets.py](src/tslc/compiler_assets.py) | Load the bundled grammar and render assets |
| **sources** | [sources.py](src/tslc/sources.py) | Read `.tsl` source files |
| **syntax** | [syntax/](src/tslc/syntax/) | Lark grammar → parse tree (outer declarations + TSIL body envelopes) |
| **catalog** | [catalog/](src/tslc/catalog/) | Promote parse tree → typed, immutable domain model (`Primitive`, `Extension`, `Catalog`) |
| **select** | [select/](src/tslc/select/) | For each `(backend, extension, type)` slot, pick the best implementation body |
| **ir / scan** | [ir/](src/tslc/ir/) | Turn a TSIL body into a recursive `tuple[Segment, ...]` — *not* an AST |
| **lower** | [lower/](src/tslc/lower/) | Walk segments, resolve queries/intrinsics → `LoweredSpecialization` |
| **backend** | [backend/](src/tslc/backend/) | Own target type projection, helper manifests, emitted profiles, validation, and C++/Rust function text |
| **value tests** | [value_tests/](src/tslc/value_tests/) | Plan executable cases from finalized emitted names |
| **benchmark** | [benchmark/](src/tslc/benchmark/) | Plan explicit implementation-variant measurements and render the optional C++ benchmark/policy tool |
| **render** | [render/](src/tslc/render/) | Format validated profiles and prebuilt test plans into headers/modules, dispatch, CMake/Cargo, and docs |
| **output** | [output/](src/tslc/output/) | Write the file tree; build-verify with real toolchains (incl. SDE/QEMU emulation) |

Entry points: [cli.py](src/tslc/cli.py) (installed as `tslc`, also
`python -m tslc`) and [api.py](src/tslc/api.py). The CLI discovers repository
defaults through [project_config.py](src/tslc/project_config.py). Catalog-only
author validation is a separate boundary in
[authoring.py](src/tslc/authoring.py): `tslc check` stops after parse, catalog
promotion, invariants, and TSIL shell validation unless explicit slot filters
request selection and lowering. Catalog `list`/`show` and `doctor` consume the
same typed catalog, backend registry, machine-profile projection, and verifier
drivers rather than maintaining parallel compiler knowledge.

## The input language (two nested languages)

### 1. The outer TSL data language

An indentation-sensitive, YAML-ish DSL. A primitive declares a signature, docs,
authored test cases, and a tree of implementations keyed by
`extension → type-group`. Abbreviated from
[`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl):

```
prim<v:=(v,v)> add(left, right):
  tests:
    - {tags [basic], type "si32", case {inputs [[1,2,...],[8,7,...]], expected [9,9,...]}}
  impls:
    avx2:
      ?i?:                         # type-group wildcard: any integer width
        requires [avx, avx2]
        implementation:
          tsil "complete(intrin<add, build[suffix=base::signed_of(base::in)]>(left, right));"
```

- **Signatures** (`v:=(v,v)`): `v` vector, `m` mask, `s` scalar, `ptr`/`usize`
  (presence makes it a free function), `lanes<s>` a lane list.
- **Type-group keys**: `?i?` (any int), `f?` (any float), `arith` (all), plus
  concrete tags. Ranked by **specificity** — `si32` beats `?i?` beats `arith`.
- **Extension fallback**: extensions form `inherits` chains (e.g. `avx2_vl →
  avx2`); an active variant can explicitly `supersedes` another extension while
  still borrowing fallback bodies from its inheritance chain.
- **Target-family capabilities**: `target_families:` owns behavioral roles for
  source-named extension families—fallback classification, free-function
  ownership, declared-register requirements, and index-vector support—and for
  profile families, including whether a profile runs natively without an
  emulator. Selection, lowering, translation, and verification consume those
  typed roles instead of recognizing family-name strings.
- **Fixed-width SVE**: `sve128`/`sve256`/`sve512` inherit scalable `sve` bodies
  but supersede `sve` in their fixed profiles, so one profile emits one SVE
  model. The fixed width is a compile mode (`sve_vector_bits_N`) plus C++ flags
  such as `-msve-vector-bits=N`, not a separate hardware target feature.
  Scalable `sve` remains available through the separate `sve` profile; fixed
  profiles make `dataparallel::native` resolve to the selected fixed SVE model.
- **Clang vector overlays**: C++ profiles may expose the opt-in
  `clang_v128`/`clang_v256`/`clang_v512` extensions through a dedicated
  `tsl_<profile>_clang.hpp` header and `tsl::<profile>_clang` CMake target.
  These compiler-vector types do not participate in `native` or `fixed<N>`
  inference. Consumers explicitly request one with
  `dataparallel::simd_for_t<clang_fixed<N>, T>`, where `N` is the lane count;
  the guarded overlay maps the resulting bit width to the corresponding
  `clang_v128`/`clang_v256`/`clang_v512` extension. The default uses Clang's
  comparison-result vector as its mask. Consumers may instead request the
  dense boolean-vector representation with
  `clang_fixed<N, clang_mask::boolean_vector>` when Clang reports
  `__has_feature(ext_vector_type_boolean)`. The generated data vector is the
  same; only the mask contract changes. A body that needs a hardware
  implementation uses the typed `vector::fixed` query, which dependency closure
  resolves concretely while C++ renders
  `dataparallel::simd_for_t<fixed<N>, T>`. Their `comparison_lane_vector` mask
  policy derives `mask_type` from Clang's exact vector-comparison result. Direct
  mask operations retain all-one/all-zero lane semantics, while
  `to_integral`/`to_mask` form the representation-safe bridge to hardware masks;
  mask objects are never assumed bit-cast-compatible. The dense boolean mask is
  not assumed to map to a hardware predicate register, and its explicit policy
  keeps that performance choice benchmarkable without changing the default.
  Rust does not emit these
  compiler-builtin extensions: stable Rust's SIMD surface is the
  architecture-specific `core::arch`, while its analogous portable
  `core::simd::Simd<T, N>` and lower-level compiler SIMD facilities remain
  nightly-only. A future nightly Rust path belongs in a separate opt-in
  `portable_simd` overlay rather than behind the Clang-specific policy.
- **Mask policies**: `[mask=zero]` (zeroing) and `[mask=pass_through]` (merge).
- `requires`, `safety` (internal/caller unsafe), and boolean attribute wildcards
  (e.g. `[aligned=*]`, expanded at catalog-build time).

### 2. The inner TSIL body language — the key design decision

A function body is **semi-valid target-language code sprinkled with TSIL keyword
islands**. Per the charter: *we do not parse C++/Rust expressions; we translate
only keyword islands.* [ir/scan.py](src/tslc/ir/scan.py) scans a body into a
recursive `tuple[Segment, ...]`:

- **`RawText`** — target source, passed through verbatim; line and block comments
  are opaque to the keyword scanner (including nested Rust block comments);
- **`Region`** — a recognized keyword island whose `<...>` shell is parsed by
  syntax-only helpers in [ir/region_syntax.py](src/tslc/ir/region_syntax.py) and
  whose `(...)` payload is recursively scanned.

`let<type>(Name, ...)` creates a typed lowering binding rather than a target-language
declaration. TSIL-owned type positions resolve it directly, for example
`cast<static>(Name, value)` or `var<typed>(Name, local, init)`. Use `type(Name)` only
to insert its spelling into otherwise raw target text. A bare `Name` inside `RawText`
is ordinary target text and is never searched or rewritten, including in comments,
literals, and Rust lifetimes.

The descriptor registry
([ir/region_registry.py](src/tslc/ir/region_registry.py)) is the lexical source
of truth consumed by scanning and shell validation. The typed lower-owned
registration
([lower/region_handlers/registry.py](src/tslc/lower/region_handlers/registry.py))
joins each keyword's handler factory with its implementation-state effect, so
lowering and state classification cannot drift into parallel keyword lists.
Together they cover `complete`, `intrin`, `helper`, `op`, `call`, `value`,
`type`, `cast`, `var`, `let`, `mask`, `mem`, `lanes`, `io`, `if`,
`select_expr`, `loop`, `switch`, and `assume_aligned`. **A call-shaped keyword
grows by adding a lexical descriptor, its owned validator when needed, and one
lowering registration row. A genuinely new structural body shape also adds one
paired scanner/malformed-scanner parser registration in `ir/scan.py`.**

So `intrin<add, build[suffix=base::signed_of(base::in)]>(left, right)` becomes
`_mm256_add_epi32(...)` for AVX2/si32, and
`call<primitive=mov, attrs[mask=zero]>(...)` resolves to another generated
primitive. Generation-time queries (`base::in`, `vector::length`,
`is_same(...)`) and control (`if<generation>`, `loop<generation>`,
`switch<compile>`) are evaluated *at compile time* against the concrete
type/extension being specialized.

## Lowering & assembly

The [Lowerer](src/tslc/lower/lowerer.py) walks the segments for one
`(primitive, extension, type, backend)` slot → a `LoweredSpecialization`
(concrete type spellings, register type, body text, mask policy, safety,
required target features). Region handlers
([lower/region_handlers/](src/tslc/lower/region_handlers/)) translate each
keyword; a query evaluator ([lower/queries.py](src/tslc/lower/queries.py))
resolves the `<...>` selectors.

Successful `call<...>` lowering records typed dependency origins using the same
query evaluator and live generation-time control flow that produced the body.
The pipeline then runs a **profile-scoped dependency closure**: from the
requested primitives it resolves those lowered call facts
([lower/dependencies.py](src/tslc/lower/dependencies.py)), lowers callees, and
**prunes to a fixpoint** any specialization whose callees aren't themselves
emitted for the same `simd<type,ext>` (else the generated call wouldn't link).
It also **propagates bottom-up** unsafe-ness, required target features, and
implementation-state joins through the live call graph
([_pipeline_closure.py](src/tslc/_pipeline_closure.py),
`_propagate_transitive_call_facts`).

After closure, constructing an
[backend/emitted_profile.py](src/tslc/backend/emitted_profile.py) profile uses
[backend/emitted_names.py](src/tslc/backend/emitted_names.py) to finalize masked
and immediate wrapper names, then freezes deterministic per-backend groups.
Backend validators reject contradictory declared
capabilities before artifacts are constructed, while an extension that declares
a backend unsupported is not admitted as a coverage attempt for that backend.
Helper dependency roots and helper
admission both come from typed manifests in
[backend/helper_requirements.py](src/tslc/backend/helper_requirements.py).

Backends differ idiomatically (a `BackendDialect`,
[backend/translation.py](src/tslc/backend/translation.py), abstracts type
spellings, intrinsic composition, call syntax, and unsafe framing). The
[backend registry](src/tslc/backend/registry.py) owns each backend's dialect
factory, artifact media type and renderers, documentation formatter, validation,
helper manifest, value-test support, optional benchmark planner and renderer,
verification adapter, and
post-generation formatting/documentation specs. Signature type
projection machinery and the concrete C++/Rust projection tables are co-located
in [backend/signature_types.py](src/tslc/backend/signature_types.py), then shared
by function emitters and documentation formatting. They are backend-owned facts,
not registry capabilities. Backend-neutral variant/body facts live in
[backend/primitive_rendering.py](src/tslc/backend/primitive_rendering.py);
language documentation assembly and Rust type-parameter/state-query spelling
live in focused sibling modules rather than the function emitters.

Sized-vector lane arithmetic crosses that boundary as a typed `LaneCount`.
C++ renders scaled symbolic counts as constant expressions; stable Rust rejects
them before target text is produced unless selection has monomorphized the
count. Neutral lowering never constructs a C++ or Rust lane-count expression.

- **C++** — `*_impl<Vec>` struct partial-specializations + wrapper function
  templates ([backend/cpp.py](src/tslc/backend/cpp.py)).
- **Rust** — traits + impls + turbofish wrappers, explicit `unsafe {}` framing,
  `core::arch` intrinsic qualification ([backend/rust.py](src/tslc/backend/rust.py)).
  Generated rustdoc uses a `cfg(doc)` profile-neutral facade containing one
  public signature per emitted Rust primitive; concrete profile availability
  stays in the specialization explorer, while normal builds retain their
  Cargo-feature-selected `profile` alias.

A static substrate ships as assets
([backend/assets/tsl_core.hpp](src/tslc/backend/assets/tsl_core.hpp),
[tsl_core.rs](src/tslc/backend/assets/tsl_core.rs)) defining `simd<T,Ext>` /
`SimdVector` and helpers. Whole-file scaffolding and stable profile metadata
also live there as named templates; Python renderers supply only finalized,
typed holes and dynamic declarations. Backend target-text values use
[target_text.py](src/tslc/target_text.py); [render/](src/tslc/render/) only formats
finalized, validated profiles, prebuilt value-test plans, and prebuilt
benchmark plans into a per-profile project with a top-level dispatch
header/module.

The optional [benchmark/](src/tslc/benchmark/) stage consumes finalized C++
specializations and authored value-test facts. It plans every explicitly
coexisting named variant in the emitted primitive/dependency closure, emits
structured skip coverage for unsupported signature shapes, and renders a
standalone native benchmark/policy tool. Value-test tags do not control
benchmark admission. Workload semantics are resolved in
[benchmark/scenarios.py](src/tslc/benchmark/scenarios.py) before rendering:
pure-register scenarios carry
their operand generators and dependency parameter, vector-plus-scalar scenarios
keep the scalar input independent, immediate scenarios carry an authored
concrete value, indexed-load scenarios carry a SIMD index binding and bounded
hot-L1 memory contract, vector-to-scalar reduction scenarios carry an
independent input generator, vector-input mask-result scenarios carry their
operand generators, and integral-mask conversion scenarios carry exact
active-lane counts. A primitive uses the
validated `benchmarks.latency_chain` catalog fact only when its latency operand
is ambiguous; `benchmarks.operand_domains` can constrain a compatible vector or
scalar operand to a validated domain such as `nonzero` or `shift_count`. Source
data never embeds benchmark C++. The generated CMake project runs the tool only
through explicit report, policy, or autotune options;
ordinary generation and builds retain the authored default.

## Differential value tests

Authored `tests:` blocks (input lanes → expected lanes) drive the
[value_tests/](src/tslc/value_tests/) subsystem, which generates **executable**
C++/Rust tests: build a SIMD register from a lane array, run the generated
primitive, read the result back, compare to `expected`. Each case plan groups
inputs, expectations, invocation facts, memory layouts, representation changes,
scalable harness facts, and differential harness facts into frozen typed
components
([value_tests/case_components.py](src/tslc/value_tests/case_components.py));
[case-kind capabilities](src/tslc/value_tests/case_capabilities.py) validate
those facts through the focused
[case plan](src/tslc/value_tests/case_plan.py) before rendering. The
`status_pointer` case kind validates nondeterministic status-plus-output
contracts by checking the status domain and failure-path output preservation,
without inventing vector lanes or a deterministic success value. The
array↔register round-trip uses auto-discovered "harness primitives"
(`from_array`, `to_array`,
`to_integral`, found by signature shape in
[value_tests/harness.py](src/tslc/value_tests/harness.py)). A **differential**
mode cross-checks each hardware implementation against the portable `generic`
one. [output/verify.py](src/tslc/output/verify.py) then actually compiles and
runs them — optionally under **Intel SDE** or **qemu-aarch64** so
AVX-512/NEON/SVE code runs on hardware that lacks it.

## State / outcome

- **Coverage-not-completeness**: in `partial` mode a primitive whose body can't
  be lowered yet is *recorded as a skip*, not a failure; `strict` mode promotes
  skips to errors. [coverage.py](src/tslc/coverage.py) and
  [maintenance/](src/tslc/maintenance/) (e.g. `coverage_inventory`)
  operationalize the charter's coverage-not-completeness rule. `tslc coverage
  inventory` is read-only by default and folds finalized lowering outcomes into
  one typed report with text, Markdown, and JSON renderers. Its profile/backend
  percentages share a logical-candidate denominator, while explicit `--update`
  and `--check` modes own the canonical tracked Markdown evidence.
- **Honest edges**: [support_policy.py](src/tslc/support_policy.py) centralizes
  what the compiler can emit today; some keyword forms are *recognized so a
  body skips cleanly* rather than leaking through as raw text.
- **Tests**: the default pytest run exercises the pure-logic suite and skips
  generated C++/Rust build/value gates. Run `pytest --run-generated-builds
  tests/test_build_verify.py tests/test_value_tests.py` when a slice needs real
  toolchain coverage. Run the suite from the **repo root**, not from `tslc/` —
  `tests/test_value_test_planning.py` reads source via repo-root-relative paths
  and otherwise reports false failures.

## Where to look first

- Big picture / rules: [README.md](README.md), [CHARTER.md](CHARTER.md).
- The body model: [ir/segments.py](src/tslc/ir/segments.py),
  [ir/scan.py](src/tslc/ir/scan.py).
- Orchestration: [pipeline.py](src/tslc/pipeline.py).
- A real primitive with all the moving parts:
  [`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl).
