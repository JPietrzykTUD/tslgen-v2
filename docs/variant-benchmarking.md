# Variant Benchmarking And Autotuning

Generated C++ projects can benchmark coexisting implementation variants for
the profile selected by `TSL_PROFILE`. This is opt-in: normal generation and
normal CMake builds neither run benchmarks nor change the authored default
implementation.

The first supported scenario family is deliberately narrow. It covers fixed-
width, pure-register primitives with vector-only inputs and a vector result.
Every candidate must have authored expected-value coverage and must pass those
checks before it is timed. Masked, memory, reduction, immediate, scalable, and
caller-unsafe shapes are currently reported as unsupported by benchmark
coverage rather than assigned a guessed workload.

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
