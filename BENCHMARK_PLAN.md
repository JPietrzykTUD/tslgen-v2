# Variant Benchmark And Autotune Plan

## Decision

Variant benchmarking is a useful feature, but it must be introduced as a
measurement facility before it becomes a build-time optimizer.

The intended end state is:

1. `TSL_PROFILE=auto` detects one generated profile for the native machine;
2. an explicitly enabled benchmark target compares the default implementation
   with authored variants for specializations in that profile;
3. a conservative reducer emits a build-local variant policy; and
4. final consumer translation units compile with that policy and no runtime
   dispatch.

Four constraints materially change the original implementation order:

- Benchmarking can compare only implementations that coexist as the default
  body and named `variants:`. A body removed by a recent refactor is not a
  candidate. At the 2026-07-13 review, the corpus had only 15 `variants:`
  blocks, 14 named `generic_fallback` and one named `intrinsic_gather`; it did
  not yet represent most of the recent scalar-to-composed changes. Slice 0 must
  regenerate this inventory rather than treating those counts as configuration.
- Benchmarks answer a performance question, not a semantic-correctness question.
  Every candidate must pass the authored value-test semantics before it is
  timed. Agreement with the default alone is not a correctness oracle because
  the default may be the implementation under review.
- A tiny value-test input is useful for correctness but is not a valid timing
  workload. Constant folding, cache state, mask density, index distribution,
  dependency chains, and setup cost can otherwise decide the winner.
- A one-build CMake workflow is possible, but it is not the first milestone.
  The generated library is header-only, so the benchmark must compile against a
  policy-free profile target and the public interface target must depend on the
  subsequently generated policy. A report-only and then a two-phase workflow
  should prove the model before this dependency chain is automated.

The first implementation is C++-only. Rust policy consumption and benchmarking
are deferred until the C++ policy and measurement protocol have demonstrated
stable value. Benchmarks must never execute from `build.rs`.

## Goal

Add an optional, native-machine workflow for measuring explicitly authored
implementation variants and, once the measurements are trustworthy, selecting
a compile-time winner for a concrete specialization.

Ordinary generation and dependency inclusion remain deterministic and
non-executing. Without an explicit policy, public wrappers call the authored
default implementation exactly as they do today.

The feature has three distinct modes:

| Mode | Purpose | Changes wrapper selection? |
|---|---|---|
| report | Build/run candidates and emit measurements | no |
| policy consumption | Validate and consume a previously produced policy | yes |
| autotune | Report, reduce, and consume a policy in one explicit native build | yes |

Keeping these modes separate is important: measurement remains useful when the
reducer concludes that no variant is reliably better.

## Non-Goals

- No benchmarking during `tslc generate`, an ordinary CMake build, or ordinary
  `FetchContent` inclusion.
- No use of timing as a substitute for generated value or differential tests.
- No comparison with an implementation that is no longer present in the
  generated candidate set.
- No selection between profiles, extensions, or ISAs. Profile auto-detection
  happens first; tuning chooses only among bodies for one selected
  specialization.
- No runtime dispatch or startup calibration.
- No source-data rewrite or global winner committed to `tsldata`.
- No mandatory third-party benchmark framework in the first slices.
- No memory, gather/scatter, masked, reduction, or scalable-vector policy
  decisions until their workload semantics are explicitly modeled.
- No Rust autotuning in `build.rs`.

## Compiler Boundary And Candidate Model

The implementation follows the current compiler pipeline:

```text
typed catalog
  -> selected implementation
  -> lowered default and variant bodies
  -> finalized emitted profile
  -> benchmark plan
  -> backend benchmark artifacts
  -> result records
  -> validated variant policy
  -> backend policy artifact
```

Raw JSON belongs only at manifest/result/policy I/O boundaries. Planning,
validation, reduction, and rendering use frozen typed values. The benchmark
renderer must not rediscover variants by parsing generated C++ names.

### Specialization Identity

A policy key identifies the complete specialization, not just
`primitive + extension + type`. It carries every applicable dimension:

- backend and selected profile;
- emitted and source primitive names;
- extension and input type;
- representation-change target;
- boolean axes and immediate value;
- generic constant values and specialized SIMD-type base bindings;
- sized-vector lane count; and
- opt-in header group, when applicable.

Target-language symbols and rendered C++ type spellings are not neutral
identity. A backend renderer derives them from the typed key.

```python
@dataclass(frozen=True, slots=True)
class BenchmarkCandidateSet:
    key: SpecializationKey
    default: VariantChoice
    alternatives: tuple[VariantChoice, ...]
    correctness_cases: tuple[BenchmarkCorrectnessCase, ...]
    scenarios: tuple[BenchmarkScenario, ...]
```

### Eligibility

A specialization is benchmarkable only when it has at least one successfully
lowered named variant, all candidates and dependencies are emitted in the
selected C++ profile, authored correctness cases cover the specialization, and
the planner supports its scenario kind.

The first supported scenario is a pure register operation with vector inputs
and a vector or scalar result. Pointer parameters, memory effects, lane lists,
masks, immediates, reductions, scalable vectors, and caller-unsafe APIs are
skipped with structured reasons.

This deliberately excludes `gather_narrow_partial` as the first policy-bearing
benchmark. It is useful later, but cache and index distributions make it a poor
test of whether the basic tuner is trustworthy.

### Making Recent Refactors Comparable

To test a composed body against its former scalar/generic fallback, both must
coexist on the same reviewed implementation leaf:

```tsl
implementation:
  tsil "...current composed body..."
variants:
  generic_fallback:
    tsil "...preserved previous fallback body..."
```

Do not mechanically restore every removed body. Inventory the changes, select
one or two pure-register specializations, and retain only semantically
equivalent candidates that pass the same tests. Variant names may describe an
implementation strategy; primitive names continue to describe semantics.

Commit-to-commit performance comparison is a separate developer benchmark and
must not be confused with generated variant autotuning.

## C++ Integration

### Default Generated Selection

Only after report-only measurements demonstrate a stable signal should the
generated C++ library gain a typed variant selector. The default selector always
chooses the authored default implementation.

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

Rendering order is a real constraint: all variant enums and selector primaries
must be visible before the policy header, and the policy specializations must be
visible before public wrapper definitions. This needs an owned render-model
boundary; it must not be solved by template string surgery.

### CMake Options

Initial options:

```cmake
option(TSL_BUILD_BENCHMARKS "Build TSL variant benchmarks" OFF)
set(TSL_VARIANT_POLICY_FILE "" CACHE FILEPATH "Precomputed TSL variant policy")
```

Behavior:

- default: use default implementation selectors;
- `TSL_BUILD_BENCHMARKS=ON`: build benchmark binaries, do not run them;
- `TSL_VARIANT_POLICY_FILE=...`: consume an existing policy and generate the
  selector override header without running benchmarks.

After report-only measurement and policy consumption are proven, add:

```cmake
option(TSL_AUTOTUNE_VARIANTS "Benchmark and select variants for this native build" OFF)
set(TSL_BENCHMARK_COMPILE_OPTIONS "" CACHE STRING "Additional code-generation options used for tuning")
```

The first autotune implementation is native-only and rejects cross-compilation.
Remote runners belong to the later two-phase workflow because their target and
runtime identity must be explicit.

### CMake Ordering Constraint

The first supported workflow is explicitly two-phase:

```text
configure with TSL_PROFILE=auto and TSL_BUILD_BENCHMARKS=ON
  -> build and run the selected-profile benchmark
  -> reduce results to a policy
  -> configure the final build with TSL_VARIANT_POLICY_FILE=<policy>
  -> compile consumers
```

This is operationally similar to profile-guided optimization and keeps the
measurement, policy, and final compilation independently inspectable.

The eventual one-build convenience workflow must avoid a policy cycle:

```text
policy-free tsl_profile_${TSL_SELECTED_PROFILE}
  -> benchmark executable
  -> raw results
  -> validated policy JSON and C++ header
  -> tsl_variant_policy target
  -> policy-enabled tsl_generated interface target
  -> consumer object compilation
```

The benchmark executable must not link the policy-enabled `tsl_generated`
target. It compiles against the selected concrete profile target and includes
the concrete profile header. Only the public interface target depends on the
generated policy target.

CMake follows dependencies added to interface libraries transitively to their
consumers, but this ordering must still be tested with Ninja and Makefiles, both
standalone and when the generated project is a subproject. CMake only
orchestrates commands and dependencies; compiler-owned code validates results,
chooses a winner, and renders the policy header.

The standalone generated C++ project currently has no runtime dependency on the
Python compiler. One-build autotune must not duplicate the reducer in CMake or a
second ad-hoc implementation merely to preserve that property. Before Slice 4,
choose one owned distribution model: ship a generated standalone reducer, ship
an explicitly required `tslc` benchmark tool, or keep autotune two-phase. This
is a go/no-go decision for the one-build convenience path.

An explicitly requested autotune fails on setup, compilation, execution,
correctness, or policy-validation failure. A statistically inconclusive result
is not an infrastructure failure: it produces a documented `default` decision.

## Rust Integration

The neutral manifest/result/policy schema should avoid C++-only identities, but
no Rust selector or benchmark runner belongs in the initial feature.

If C++ validates the model, Rust may later consume a precomputed policy through
a generated policy module. Benchmark execution remains a separate explicit
command or target. It must not run from `build.rs`: build scripts may execute in
host/target configurations that do not represent the final runtime machine and
must not unexpectedly perform noisy host-sensitive work.

Rust selection also needs its own code-generation proof. A constant `match` is
not accepted merely on the assumption that unused branches optimize exactly
like C++ `if constexpr`. Add policy consumption first; consider Rust benchmark
generation only after zero-overhead selection is demonstrated on stable Rust.

## Benchmark Harness

The benchmark harness should be generated from typed facts:

- primitive name;
- signature/result kind;
- parameter kinds;
- type tag;
- extension;
- boolean axes and generic params;
- available variant IDs;
- authored correctness cases; and
- typed benchmark scenarios.

It must not classify primitive names like `gather` or `add` in production
benchmark generation. If benchmark setup needs primitive-family-specific data,
that should be represented by typed benchmark scenarios later.

### Correctness Inputs And Timing Scenarios Are Separate

The benchmark subsystem should reuse value-test materialization and assertion
facts for correctness. It must not embed an entire `ValueTestCasePlan` as its
timing workload.

```text
value-test facts -> BenchmarkCorrectnessCase
signature/scenario facts -> BenchmarkScenario
```

The first pure-register timing scenario generates a deterministic batch from an
explicit seed, covers ordinary and edge values, cycles through many input
instances, keeps setup outside the timed region, and consumes every result. This
prevents one tiny authored example from becoming a constant-folded hot loop.

Latency and throughput are different performance questions. When both are
valid for a signature, emit both a dependency-chain scenario and an independent
calls scenario. A candidate is policy-selectable only if it dominates the
default across the canonical scenarios; conflicting winners are
`inconclusive`.

### Correctness Before Timing

For every candidate, including the default:

1. materialize an authored input outside the timed region;
2. run the detail implementation directly;
3. compare its result and observable side effects with the authored expected
   result using the same comparison semantics as generated value tests; and
4. reject the candidate set if any candidate fails.

For memory primitives, correctness must include memory output buffers. For
masked/scatter/store-like primitives, the benchmark harness may initially limit
itself to shapes already supported by value-test planning.

Default-versus-variant agreement is an additional diagnostic, not the primary
oracle. Correctness happens outside the timed loop and a failure never produces
a timing result.

### Detail-Symbol Calls

Benchmarks should call generated detail implementations directly:

```text
detail::primitives::<primitive>_impl<...>::apply(...)
detail::primitives::<primitive>_impl_<variant><...>::apply(...)
```

They should not call the public wrapper, because the public wrapper may already
be policy-selected. The public wrapper is what the policy changes; the
benchmark must measure each candidate independently.

### Generated C++ Harness Shape

First-slice C++ benchmark code can use a small built-in harness instead of
Google Benchmark. It calibrates to a minimum sample duration and executes a
seeded, interleaved schedule of candidates over an input batch. The exact loop
shape belongs to the benchmark renderer; a single closure repeatedly returning
the same value is specifically insufficient.

Conceptual shape:

```cpp
for (auto const& round : seeded_interleaved_schedule) {
  for (auto candidate : round.candidates) {
    auto iterations = calibrate(candidate, input_batch, minimum_sample_time);
    raw_samples.push_back(
        measure(candidate, input_batch, iterations, compiler_barrier));
  }
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

This example only illustrates direct detail calls; it does not make gather an
eligible first-slice timing scenario. The generated benchmark source lives under
the generated C++ project,
for example:

```text
cpp/bench/tsl_variant_bench_<profile>.cpp
```

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

For store/scatter/memory-output primitives, the harness must also consume or
validate the output buffer so writes cannot be optimized away.

### Timing Rules

The first version uses `std::chrono::steady_clock`, warmup, calibrated repeated
iterations, deterministic input batches, and a local compiler barrier.

Candidates run in paired, interleaved, seed-derived order so drift affects them
as evenly as practical. Results retain raw samples rather than only aggregates.
The reducer requires correctness, repeated agreement on direction, and a
practical improvement larger than observed noise. Ties, excessive dispersion,
or latency/throughput disagreement select the default with an `inconclusive`
reason.

The exact statistical rule should be chosen from pilot measurements. A fixed
"seven samples and five percent" rule is not an acceptance criterion.

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
  "scenario": "throughput_independent",
  "variant": "intrinsic_gather",
  "correct": true,
  "warmup_iterations": 10000,
  "seed": 41731,
  "iterations": 1000000,
  "raw_ns_per_call": [1.18, 1.31, 1.22, 1.27]
}
```

Policy reduction is a separate step:

```text
benchmark result records -> neutral policy JSON -> C++ policy header
```

The reducer selects a variant only when all required correctness and scenario
records exist, their manifest/tune-context identities match, and paired results
show stable dominance. Otherwise it selects `default` with a structured reason.

### Later Benchmark Scenarios

Value-test inputs remain correctness inputs. Later timing scenarios model the
performance-relevant distributions for each supported family.

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

Do not add this DSL in the first slice. Start with typed pure-register scenarios
and let real gaps justify benchmark-specific source data.

## Cache And Reproducibility

Autotune decisions are valid only for the candidate and tune context that
produced them. The fingerprint includes at least:

- generated candidate/manifest content hash;
- compiler executable, ID, version, and target triple;
- complete benchmark compile and link options, including optimization,
  floating-point, sanitizer, and LTO state;
- selected profile and its feature flags;
- CMake configuration/build type;
- CPU identity and detected feature set;
- benchmark protocol/schema version, seeds, and runner; and
- best-effort runtime metadata such as OS and CPU affinity.

A timestamp is provenance, not a cache-validity input. Policy consumption
rejects a mismatched manifest or tune context; it does not silently rerun a
benchmark during an ordinary build.

Consumer-private compiler options cannot always be inferred by the benchmark
target. A policy is valid only when benchmark and consumer code-generation
options match. `TSL_BENCHMARK_COMPILE_OPTIONS` makes extra tuning options
explicit, but it cannot prove equivalence with arbitrary downstream targets.

## Implementation Slices

### Slice 0: Candidate And Question Audit

- Inventory existing variant-bearing slots for a representative native
  auto-detected profile.
- Map recent fallback-to-composition changes to bodies that still coexist and
  bodies that were replaced.
- Choose one or two pure-register candidates and state whether the pilot
  measures latency, throughput, or both.
- Preserve a previous semantically equivalent fallback as a named variant only
  for the reviewed pilot where necessary.
- Confirm all pilot candidates pass authored and differential correctness tests.

Exit criterion: at least one meaningful current-machine candidate set exists.

### Slice 1: Report-Only C++ Pilot

- Add typed `SpecializationKey`, candidate-set, correctness-case, scenario, and
  project-plan values.
- Plan from finalized lowered/emitted facts without parsing rendered names.
- Generate one policy-free C++ benchmark executable for the selected profile.
- Add deterministic batched inputs, direct detail calls, correctness gating,
  calibrated/interleaved timing, and JSONL output.
- Add `TSL_BUILD_BENCHMARKS`; do not change public wrappers.

Exit criterion: repeated pilot runs expose either a stable difference or an
honest inconclusive result, and the raw evidence is inspectable.

### Slice 2: Conservative Reducer

- Parse result JSON into typed records.
- Validate candidate, manifest, scenario, and tune-context identity.
- Reduce paired samples to `selected`, `default`, or `inconclusive`.
- Emit neutral policy JSON and a human-readable summary.
- Test noisy, conflicting, stale, failed-correctness, and missing-result cases.

Exit criterion: the reducer never selects from incomplete, invalid, or unstable
evidence.

### Slice 3: Manual C++ Policy Consumption

- Add selector primaries and the render-order hook.
- Convert a validated neutral policy to a build-local C++ header in
  compiler/backend-owned code.
- Add `TSL_VARIANT_POLICY_FILE` consumption.
- Verify compile-time selection and optimized elimination of the unselected
  branch.

Exit criterion: a precomputed policy changes only the intended wrapper
specialization; default builds remain deterministic.

### Slice 4: Explicit One-Build CMake Autotune

- Add the policy-free benchmark target and generated policy target chain.
- Reuse `TSL_SELECTED_PROFILE` from existing auto detection.
- Make the public interface depend on policy generation only when explicitly
  enabled.
- Reject cross-compilation and context mismatches.
- Test ordering in a standalone generated project and as a consuming CMake
  subproject.

Exit criterion: consumer objects cannot start before a valid policy header
exists, and the benchmark target has no dependency cycle through the public
target.

### Slice 5: Broader Scenario Coverage

- Add more pure-register signature shapes.
- Add typed mask, reduction, memory, and gather/scatter scenarios one family at
  a time.
- Add source-authored benchmark metadata only where typed signature-derived
  scenarios are insufficient.
- Track benchmark eligibility/skip coverage separately from primitive compile
  and value-test coverage.

### Slice 6: Rust Policy Evaluation

- Decide whether stable Rust can express zero-overhead per-specialization
  selection cleanly.
- Add policy consumption before considering Rust benchmark generation.
- Keep all Rust benchmark execution outside normal `cargo build` and
  `build.rs`.

## Validation

Every implementation slice runs the normal compiler checks:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)
git diff --check
```

Slices touching generated C++ layout or executable benchmarks additionally run
the generated build/value gates and focused native benchmark-project tests.
Timing assertions must not enter ordinary CI; CI checks planning, compilation,
correctness, schema handling, and reducer behavior with synthetic samples.

## Acceptance Criteria

The feature is healthy when:

- ordinary generation and builds remain deterministic and non-executing;
- only explicit, coexisting, semantically equivalent candidates are compared;
- candidate correctness is established before timing;
- timing scenarios are typed, repeatable, and separate from tiny correctness
  examples;
- auto detection selects the profile once and autotune only selects a body
  within that profile;
- report-only mode is useful without wrapper changes;
- the reducer defaults on noisy or conflicting evidence;
- policies are bound to exact candidate and tune contexts;
- C++ selection is compile-time and adds no runtime dispatch;
- the one-build dependency graph is tested and cycle-free; and
- unsupported scenarios produce structured skips rather than invented results.

## Open Decisions To Resolve With The Pilot

- Which recent pure-register refactor gives the first meaningful coexisting
  default/variant pair on an auto-detected native profile?
- Which canonical latency/throughput scenarios are valid for that signature?
- What paired-noise metric and practical improvement threshold match observed
  run-to-run behavior?
- Which compile options constitute the supported tune context for downstream
  consumers?
- Is one-build autotune sufficiently valuable after the two-phase workflow is
  available, or does its additional CMake ordering surface outweigh the
  convenience?
