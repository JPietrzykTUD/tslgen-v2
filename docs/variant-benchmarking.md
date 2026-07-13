# Variant Benchmarking And Autotuning

Generated C++ projects can benchmark coexisting implementation variants for
the profile selected by `TSL_PROFILE`. This is opt-in: normal generation and
normal CMake builds neither run benchmarks nor change the authored default
implementation.

The supported scenario families are deliberately narrow. Fixed-width,
pure-register primitives with vector-only inputs and a vector result receive
independent throughput scenarios; they receive a latency scenario only when the
dependency operand is unambiguous or declared by the primitive. Integral-mask
to mask conversions receive sparse, balanced, and dense throughput scenarios.
Every candidate must have authored expected-value coverage and must pass those
checks before it is timed. Memory, reduction, immediate, scalable, and
caller-unsafe shapes are reported as unsupported rather than assigned a guessed
workload.

## Workload Ownership

TSL source data does not contain benchmark functions or target-language setup.
The signature supplies parameter and result shapes, while an optional
`benchmarks:` block carries only semantic facts that cannot be inferred safely.
For example, `mul` declares which operand carries the dependency chain:

```tsl
benchmarks:
  latency_chain factor1
```

Seeds, batches, mask values, timing loops, candidate order, and statistical
rules remain compiler-owned. `tslc.benchmark.planner` resolves those facts into
typed register or mask-density scenarios. The C++ benchmark renderer then emits
direct candidate calls without making workload decisions. Shared calibration,
timing, compiler barriers, and reduction live in the generated
`tsl_benchmark_core.hpp` runtime.

Unknown benchmark fields, raw setup code, and a latency chain naming an
incompatible parameter are rejected at catalog validation. A future workload
family should add a small typed vocabulary rather than an arbitrary C++ escape
hatch.

## Report Only

Configure the generated C++ project for the native machine and explicitly
build the report target:

```bash
cmake -S generated/cpp -B build/tsl-report \
  -DTSL_PROFILE=auto \
  -DTSL_BUILD_TESTS=OFF \
  -DTSL_BUILD_BENCHMARKS=ON
cmake --build build/tsl-report --target tsl_benchmark_report
```

This writes `tsl_variant_results.jsonl` in the build directory. It does not
change wrapper selection.

## One-Build Autotune

```bash
cmake -S generated/cpp -B build/tsl-tuned \
  -DTSL_PROFILE=auto \
  -DTSL_AUTOTUNE_VARIANTS=ON
cmake --build build/tsl-tuned
```

The policy-free concrete profile target builds the benchmark tool. The tool
checks candidates, measures latency and throughput, writes raw results and a
validated policy, and renders
`build/tsl-tuned/tsl/generated/tsl_variant_policy_autotuned.hpp`. Consumer
objects linking `tsl::tsl` wait for that header and select the winner with
`if constexpr`; there is no runtime dispatch.

Autotune is native-only and currently requires a single-config CMake generator;
cross-compilation and multi-config policy builds fail clearly. An inconclusive
or conflicting measurement is not a build failure: that specialization retains
the authored default.

## Reusing A Policy

A policy created by a prior report/autotune run can be consumed without timing
again:

```bash
cmake -S generated/cpp -B build/tsl-policy \
  -DTSL_PROFILE=auto \
  -DTSL_VARIANT_POLICY_FILE=/absolute/path/to/tsl_variant_policy.json
cmake --build build/tsl-policy
```

The generated standalone tool validates the candidate manifest, selected
profile, compiler/tune context, and CPU identity before rendering the header.
A stale or foreign policy fails instead of silently applying.

Use `TSL_BENCHMARK_COMPILE_OPTIONS` for consumer-relevant code-generation
options not already carried by the selected profile. The tuner cannot infer
arbitrary private flags from downstream targets, so a policy is trustworthy
only when benchmark and consumer code-generation contexts match.

For short harness checks, `TSL_BENCHMARK_ROUNDS` and
`TSL_BENCHMARK_MINIMUM_SAMPLE_NS` are configurable. Production tuning should
keep the defaults unless measurements justify a different protocol.
