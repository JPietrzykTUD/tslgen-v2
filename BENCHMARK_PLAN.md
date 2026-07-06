# Variant Benchmark And Autotune Plan

## Goal

Add an optional benchmarking and autotuning workflow for implementation
variants.

Generated libraries already contain the default implementation and every
authored variant. Benchmarking should use those emitted symbols to decide which
variant is fastest for a concrete specialization on a concrete build/runtime
environment, then feed that decision back as a build-local policy.

This feature must not make ordinary generation or ordinary dependency inclusion
host-sensitive. Default behavior remains deterministic: public API wrappers call
the default `implementation` unless an explicit variant policy selects a
variant.

## Design Principles

- `tslc` remains a compiler, not a benchmarking framework.
- Variants remain typed source/catalog/lowered/rendered data.
- Benchmarking is opt-in, explicit, and build-local.
- Benchmark winners are not source truth and do not belong in `tsldata`.
- Public wrappers must always have a safe default fallback.
- Cross-compilation must not accidentally try to execute target binaries.
- C++ and Rust should share a neutral policy format, while each ecosystem uses
  its native build integration.

## Non-Goals

- No benchmarking during normal `tslc generate`.
- No benchmarking during normal `FetchContent` inclusion.
- No automatic source-data rewrites based on benchmark results.
- No global "fastest variant" baked into `tsldata`.
- No mandatory Google Benchmark, Criterion, or external benchmark framework in
  the first slice.
- No profile-specific magic hidden in render templates.
- No Rust selection through CMake as the primary interface.

## Key Concepts

### Variant

An authored alternative implementation body attached to one implementation leaf.
Variants inherit the same requirements and public caller-safety contract as the
default implementation.

### Benchmark Manifest

A generated machine-readable inventory of emitted benchmarkable variant choices.
It should contain enough typed identity to generate benchmark calls without
parsing symbol names:

```json
{
  "backend": "cpp",
  "profile": "skylake",
  "primitive": "gather_narrow_partial",
  "extension": "avx512",
  "type": "ui32",
  "signature": "v:=(cptr,vidx,sImm)",
  "axes": {
    "scale": "4"
  },
  "generic_params": {
    "IndicesType": "simd<ui64,avx512>",
    "N": "8"
  },
  "default_symbol": "gather_narrow_partial_impl",
  "variants": [
    {
      "id": "intrinsic_gather",
      "symbol": "gather_narrow_partial_impl_intrinsic_gather"
    }
  ]
}
```

The exact format can evolve, but it must be generated from typed lowered data,
not by regexing generated source.

### Variant Policy

A build-local decision artifact saying which variant to use for a concrete
specialization.

Neutral policy example:

```json
{
  "version": 1,
  "producer": "tsl-variant-bench",
  "compiler": {
    "id": "clang",
    "version": "18.1.8",
    "flags_hash": "..."
  },
  "host": {
    "cpu": "Intel(R) Xeon...",
    "features": ["avx512f", "avx512dq"]
  },
  "decisions": [
    {
      "backend": "cpp",
      "profile": "skylake",
      "primitive": "gather_narrow_partial",
      "extension": "avx512",
      "type": "ui32",
      "axes": {
        "scale": "4"
      },
      "generic_params": {
        "IndicesType": "simd<ui64,avx512>",
        "N": "8"
      },
      "selected": "intrinsic_gather",
      "reason": "median_ns_per_call improved by 18.4%",
      "correctness": "passed"
    }
  ]
}
```

The policy should also be able to say "default" explicitly.

## C++ Integration

### Default Generated Selection

The generated C++ library should provide a typed variant selector for each
primitive that has variants. The default selector always chooses the default
implementation.

Example shape:

```cpp
namespace tsl::detail::variants {

enum class gather_narrow_partial_variant {
  default_,
  intrinsic_gather,
};

template <class Vec, class IndicesType, auto scale, std::size_t N>
struct gather_narrow_partial_selector {
  static constexpr auto best = gather_narrow_partial_variant::default_;
};

} // namespace tsl::detail::variants
```

The public wrapper dispatches through the selector:

```cpp
template <class Vec, class IndicesType, auto scale, std::size_t N>
inline typename Vec::register_type gather_narrow_partial(...) {
  using selector =
      tsl::detail::variants::gather_narrow_partial_selector<
          Vec, IndicesType, scale, N>;

  if constexpr (
      selector::best ==
      tsl::detail::variants::gather_narrow_partial_variant::intrinsic_gather) {
    return tsl::detail::primitives::
        gather_narrow_partial_impl_intrinsic_gather<
            Vec, IndicesType, scale, N>::apply(...);
  } else {
    return tsl::detail::primitives::
        gather_narrow_partial_impl<
            Vec, IndicesType, scale, N>::apply(...);
  }
}
```

This avoids global preprocessor switches selecting unavailable variants for
unrelated instantiations.

### Policy Header

CMake may generate an override header into the build directory:

```text
<build>/tsl/generated/tsl_variant_policy_autotuned.hpp
```

The shipped/generated include tree should keep stable defaults and optionally
include the build-local override:

```cpp
#pragma once

#if defined(TSL_HAS_AUTOTUNED_VARIANT_POLICY)
#  include <tsl/generated/tsl_variant_policy_autotuned.hpp>
#endif
```

The override header contains explicit selector specializations:

```cpp
namespace tsl::detail::variants {

template <>
struct gather_narrow_partial_selector<
    tsl::simd<std::uint32_t, tsl::avx512>,
    tsl::simd<std::uint64_t, tsl::avx512>,
    4,
    8> {
  static constexpr auto best =
      gather_narrow_partial_variant::intrinsic_gather;
};

} // namespace tsl::detail::variants
```

The override header must be generated in the build tree, never written into the
source or installed include tree unless explicitly packaged as a named policy.

### CMake Options

Recommended options:

```cmake
option(TSL_BUILD_BENCHMARKS "Build TSL variant benchmarks" OFF)
option(TSL_AUTOTUNE_VARIANTS "Run TSL variant benchmarks and select variants" OFF)
set(TSL_VARIANT_POLICY_FILE "" CACHE FILEPATH "Precomputed TSL variant policy")
set(TSL_BENCHMARK_RUNNER "" CACHE STRING "Optional runner for target benchmark binaries")
```

Behavior:

- default: use default implementation selectors;
- `TSL_BUILD_BENCHMARKS=ON`: build benchmark binaries, do not run them;
- `TSL_AUTOTUNE_VARIANTS=ON`: build and run benchmarks, then write a build-local
  selector override header;
- `TSL_VARIANT_POLICY_FILE=...`: consume an existing policy and generate the
  selector override header without running benchmarks.

`TSL_AUTOTUNE_VARIANTS=ON` must be explicit. It should fail clearly when CMake
is cross-compiling and no benchmark runner is configured.

### CMake Ordering Constraint

Autotune must complete before user translation units compile.

For a header-only/interface style library this is tricky because consumers may
start compiling as soon as they link the interface target. The CMake package
should therefore expose a concrete generated policy target and make the public
TSL target depend on it when autotune is enabled.

Conceptual shape:

```cmake
add_custom_command(
  OUTPUT ${CMAKE_BINARY_DIR}/tsl/generated/tsl_variant_policy_autotuned.hpp
  COMMAND tsl_variant_bench_runner ...
  DEPENDS tsl_variant_benchmarks
)

add_custom_target(tsl_variant_policy
  DEPENDS ${CMAKE_BINARY_DIR}/tsl/generated/tsl_variant_policy_autotuned.hpp
)

add_dependencies(tsl tsl_variant_policy)
target_compile_definitions(tsl INTERFACE TSL_HAS_AUTOTUNED_VARIANT_POLICY=1)
target_include_directories(tsl INTERFACE ${CMAKE_BINARY_DIR})
```

The exact target shape depends on the current generated CMake layout, but the
dependency direction must be:

```text
benchmarks -> policy header -> user compilation
```

## Rust Integration

Rust should not be controlled primarily through CMake. The Rust integration
should use Cargo-native build behavior.

### Rust Policy Module

Rust does not have C++-style partial specialization. The Rust way is to generate
a policy module from a neutral policy file.

Default generated policy:

```rust
pub enum GatherNarrowPartialVariant {
    Default,
    IntrinsicGather,
}

pub mod variant_policy {
    pub const GATHER_NARROW_PARTIAL_UI32_AVX512_UI64_SCALE4_N8:
        super::GatherNarrowPartialVariant =
        super::GatherNarrowPartialVariant::Default;
}
```

Autotuned policy module:

```rust
pub mod variant_policy {
    pub const GATHER_NARROW_PARTIAL_UI32_AVX512_UI64_SCALE4_N8:
        super::GatherNarrowPartialVariant =
        super::GatherNarrowPartialVariant::IntrinsicGather;
}
```

Wrapper dispatch:

```rust
match variant_policy::GATHER_NARROW_PARTIAL_UI32_AVX512_UI64_SCALE4_N8 {
    GatherNarrowPartialVariant::IntrinsicGather => {
        <S as detail::primitives::GatherNarrowPartialIntrinsicGatherImpl<
            IndicesType, scale, N,
        >>::apply(base_ptr, index)
    }
    GatherNarrowPartialVariant::Default => {
        <S as detail::primitives::GatherNarrowPartialImpl<
            IndicesType, scale, N,
        >>::apply(base_ptr, index)
    }
}
```

Because the selected constant is known at compile time, the unused branch should
be eliminated by the optimizer.

### Cargo Build Script

Recommended shape:

```text
build.rs
  reads TSL_VARIANT_POLICY or defaults to generated default policy
  writes OUT_DIR/variant_policy.rs

lib.rs
  include!(concat!(env!("OUT_DIR"), "/variant_policy.rs"));
```

Environment knobs:

```bash
TSL_VARIANT_POLICY=/path/to/policy.json cargo build
TSL_AUTOTUNE_VARIANTS=1 cargo build
TSL_BUILD_BENCHMARKS=1 cargo build
```

First Rust slice can consume a policy file only. Running benchmarks from
`build.rs` should be treated carefully because Cargo build scripts that execute
host-sensitive benchmarks can surprise users. If supported, it must be opt-in.

## Benchmark Harness

The benchmark harness should be generated from typed facts:

- primitive name;
- signature/result kind;
- parameter kinds;
- type tag;
- extension;
- boolean axes and generic params;
- available variant IDs;
- existing value-test cases where usable.

It must not classify primitive names like `gather` or `add` in production
benchmark generation. If benchmark setup needs primitive-family-specific data,
that should be represented by typed benchmark scenarios later.

### Benchmark Inputs

The first benchmark slice should reuse authored value-test inputs.

Reasons:

- value tests already provide valid inputs for the primitive shape;
- value tests already encode expected behavior;
- the value-test planner already knows how to materialize vectors, masks,
  scalars, pointers, lane lists, buffers, and memory effects;
- no new benchmark data DSL is needed for the first slice.

The benchmark planner should therefore derive benchmark cases from value-test
plans:

```text
ValueTestCasePlan
  -> BenchmarkCasePlan
```

The benchmark layer should add timing and call-target information only. It
should not rediscover how to build arguments.

Conceptual typed shape:

```python
@dataclass(frozen=True, slots=True)
class BenchmarkCasePlan:
    value_case: ValueTestCasePlan
    default_target: DetailCallTarget
    variant_targets: tuple[DetailCallTarget, ...]
    scenario_name: str
    samples: int
    iterations: int
    warmup_iterations: int
```

The scenario name can initially come from the value-test case name or tags, for
example:

```text
basic
edge
misaligned
basic_partial
```

Benchmark-specific authored scenarios are a later feature. Add them only when
value-test-derived inputs prove too synthetic for a primitive family.

### Correctness Before Timing

For every benchmarked variant:

1. materialize the value-test inputs;
2. run the default implementation;
3. run the variant implementation;
4. compare default output against the authored expected output when available;
5. compare variant output against the authored expected output when available;
6. always compare variant output against the default output;
7. compare side effects such as output buffers for store/scatter-like cases;
8. benchmark only if correctness passes.

For memory primitives, correctness must include memory output buffers. For
masked/scatter/store-like primitives, the benchmark harness may initially limit
itself to shapes already supported by value-test planning.

Correctness must happen outside the timed loop, and should fail the benchmark
case clearly rather than produce a timing result.

### Detail-Symbol Calls

Benchmarks should call generated detail implementations directly:

```text
detail::primitives::<primitive>_impl<...>::apply(...)
detail::primitives::<primitive>_impl_<variant><...>::apply(...)
```

They should not call the public wrapper, because the public wrapper may already
be policy-selected. The public wrapper is what the policy changes; the
benchmark must measure each candidate independently.

Rust should likewise call the generated detail traits/functions directly rather
than the public wrapper.

### Generated C++ Harness Shape

First-slice C++ benchmark code can use a small built-in harness instead of
Google Benchmark.

Conceptual shape:

```cpp
template <class Fn>
bench_result run_bench(Fn&& fn) {
  for (std::size_t i = 0; i < warmup_iterations; ++i) {
    do_not_optimize(fn());
  }

  std::array<double, samples> sample_ns{};
  for (std::size_t sample = 0; sample < samples; ++sample) {
    auto start = clock::now();
    for (std::size_t i = 0; i < iterations; ++i) {
      do_not_optimize(fn());
    }
    auto end = clock::now();
    sample_ns[sample] = elapsed_ns(end - start) / iterations;
  }

  return summarize(sample_ns);
}
```

Per benchmark case:

```cpp
auto default_fn = [&] {
  return tsl::detail::primitives::
      gather_narrow_partial_impl<Vec, IndicesType, scale, N>::apply(
          base_ptr, index);
};

auto intrinsic_fn = [&] {
  return tsl::detail::primitives::
      gather_narrow_partial_impl_intrinsic_gather<
          Vec, IndicesType, scale, N>::apply(base_ptr, index);
};
```

The generated benchmark source should be placed under the generated C++ project,
for example:

```text
cpp/bench/tsl_variant_bench_<profile>.cpp
```

### Generated Rust Harness Shape

First-slice Rust benchmark code can use `std::time::Instant` and
`std::hint::black_box` instead of Criterion.

Conceptual shape:

```rust
fn run_bench<F, R>(mut f: F) -> BenchResult
where
    F: FnMut() -> R,
{
    for _ in 0..WARMUP_ITERATIONS {
        std::hint::black_box(f());
    }

    let mut samples = [0.0; SAMPLES];
    for sample in 0..SAMPLES {
        let start = std::time::Instant::now();
        for _ in 0..ITERATIONS {
            std::hint::black_box(f());
        }
        samples[sample] = start.elapsed().as_nanos() as f64 / ITERATIONS as f64;
    }

    summarize(samples)
}
```

Generated Rust benchmark binaries can live under:

```text
rust/src/bin/variant_bench_<profile>.rs
```

Rust benchmark execution must remain opt-in. A normal `cargo build` must not run
benchmark binaries.

### Anti-Optimization Rules

The benchmark must prevent the compiler from deleting or folding the measured
work.

C++ can use a local helper:

```cpp
template <class T>
inline void do_not_optimize(T const& value) {
#if defined(__GNUC__) || defined(__clang__)
  asm volatile("" : : "g"(&value) : "memory");
#else
  volatile auto const* sink = &value;
  (void)sink;
#endif
}
```

Rust should use:

```rust
std::hint::black_box(value)
```

For store/scatter/memory-output primitives, the harness must also consume or
validate the output buffer so writes cannot be optimized away.

### Timing Rules

The first version should use minimal built-in timing:

- C++: `std::chrono`, warmup loop, repeated iterations, anti-optimization helper;
- Rust: `std::time::Instant`, warmup loop, repeated iterations,
  `std::hint::black_box`.

Decision should be conservative:

- require correctness;
- require a clear threshold, e.g. 5-10 percent median improvement;
- use multiple runs;
- record min/median/p95 or at least min/median;
- keep default when results are too close or too noisy.

### Result Records

Benchmark output should be machine-readable, preferably JSON Lines, so results
can stream and partial failures remain inspectable.

Example record:

```json
{
  "backend": "cpp",
  "profile": "skylake",
  "primitive": "gather_narrow_partial",
  "extension": "avx512",
  "type": "ui32",
  "scenario": "basic_partial",
  "variant": "intrinsic_gather",
  "correct": true,
  "warmup_iterations": 10000,
  "iterations": 1000000,
  "samples": 7,
  "min_ns_per_call": 1.18,
  "median_ns_per_call": 1.25,
  "p95_ns_per_call": 1.34
}
```

Policy reduction is a separate step:

```text
benchmark result records -> neutral policy JSON -> C++ policy header / Rust policy module
```

The reducer should select a variant only when correctness passed and the median
improvement beats the configured threshold. Otherwise it should select
`default`.

### Later Benchmark Scenarios

Value-test inputs are correct and useful first inputs, but they may not be
performance-representative for every primitive family.

Examples:

- gather/scatter may need random, strided, clustered, and cache-local index
  distributions;
- load/store may need aligned, unaligned, hot, and larger-buffer cases;
- mask-heavy primitives may need sparse, dense, and alternating masks;
- branchy fallbacks may need distributions that exercise both paths.

If needed, add a later typed source-data feature such as:

```tsl
benchmarks:
  - tags [hot, random_indices]
    case { ... }
```

Do not add this DSL in the first slice. Start with value-test-derived
benchmarking and let real gaps justify benchmark-specific source data.

## Cache And Reproducibility

Autotune decisions are valid only for the environment that produced them. The
policy output should record enough data to detect stale choices:

- generated library/version hash;
- variant manifest hash;
- compiler ID and version;
- compile flags hash;
- profile name;
- target triple;
- CPU identity and feature set;
- benchmark runner, if any;
- timestamp;
- benchmark command.

CMake/Cargo should rerun or reject stale policy output when relevant inputs
change.

## Suggested Slices

### Slice 1: Selection Hook Metadata

- Generate C++ default selector enums/templates for primitives with variants.
- Keep all selectors defaulting to `default_`.
- Public wrappers dispatch through selectors.
- No benchmark execution yet.

Validation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py
./dev.sh build --primitives gather_narrow_partial --profiles skylake --backends cpp
```

### Slice 2: C++ Policy Header Consumption

- Add generated include hook for a build-local policy header.
- Add CMake option for `TSL_VARIANT_POLICY_FILE`.
- Convert a neutral JSON policy or explicit CMake input into selector
  specializations.
- Add tests proving unknown variants/specializations diagnose clearly.

Validation:

```bash
./dev.sh build --primitives gather_narrow_partial --profiles skylake --backends cpp
```

Plus one generated-project test that forces `intrinsic_gather` and checks the
public wrapper compiles.

### Slice 3: Benchmark Case Planning From Value Tests

- Add a typed benchmark planner that consumes value-test plans.
- Produce `BenchmarkCasePlan` values with default and variant detail-call
  targets.
- Support only value-test case kinds that can be repeated safely.
- Emit diagnostics or skip records for cases that cannot become benchmarks yet.
- Do not add benchmark-specific source syntax.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py
```

Add focused benchmark-planner tests with fake value-test plans and one real
`gather_narrow_partial` corpus case.

### Slice 4: C++ Benchmark Build

- Generate benchmark manifest.
- Generate/build a C++ benchmark executable from `BenchmarkCasePlan` values for
  one representative primitive: `gather_narrow_partial`.
- Call default and variant detail symbols directly.
- Run correctness checks before timing.
- Write JSONL result records.
- Add `TSL_BUILD_BENCHMARKS`.
- Do not run benchmarks automatically yet.

Validation:

```bash
cmake --build ... --target tsl_variant_benchmarks
```

### Slice 5: C++ Autotune

- Add `TSL_AUTOTUNE_VARIANTS`.
- Run benchmark executable only when explicitly enabled.
- Emit build-local policy header.
- Keep default fallback when benchmark fails, unless strict autotune is enabled.

Suggested additional option:

```cmake
option(TSL_AUTOTUNE_STRICT "Fail build when variant autotune fails" OFF)
```

### Slice 6: Rust Policy File Consumption

- Generate Rust variant enums/constants or policy module hooks.
- Add Cargo `build.rs` support to read neutral JSON policy.
- Write `OUT_DIR/variant_policy.rs`.
- Dispatch wrappers through compile-time constants.

Validation:

```bash
./dev.sh build --primitives gather_narrow_partial --profiles skylake --backends rust
cargo test
```

### Slice 7: Rust Benchmark Build And Optional Autotune

- Generate Rust benchmark binary or bench target from `BenchmarkCasePlan`
  values.
- Call default and variant detail traits/functions directly.
- Run correctness checks before timing.
- Write JSONL result records.
- Add opt-in Cargo/environment controls.
- Emit neutral JSON policy.
- Keep benchmark execution out of default `cargo build`.

## Open Questions

- How much benchmark scenario metadata can be reused from existing value tests?
- Do memory-heavy primitives need authored benchmark scenarios before results
  are meaningful?
- Should policies select one variant per specialization, or allow scenario-
  dependent selection later?
- Should release artifacts ship precomputed policies for named profiles?
- Should autotune produce both JSON and backend-native headers/modules?

## Acceptance Criteria

The feature is healthy when:

- normal generated library inclusion remains deterministic and non-executing;
- autotune is opt-in and build-local;
- C++ uses typed selector templates rather than global variant macros;
- Rust uses Cargo-native generated policy modules;
- policies are generated from benchmark results, not committed source edits;
- stale policies are detected or conservatively ignored;
- every selected variant still has a default fallback;
- benchmark failures produce clear diagnostics rather than broken generated code.
