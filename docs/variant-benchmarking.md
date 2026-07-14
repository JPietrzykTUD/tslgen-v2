# Variant Benchmarking And Autotuning

Generated C++ projects can benchmark coexisting implementation variants for
the profile selected by `TSL_PROFILE`. This is opt-in: normal generation and
normal CMake builds neither run benchmarks nor change the authored default
implementation.

The supported scenario families are explicit and typed. Fixed-width,
pure-register primitives with vector inputs and a vector result receive
independent throughput scenarios; they receive a latency scenario only when the
dependency operand is unambiguous or declared by the primitive. This includes
vector-plus-scalar operations and immediate operations, with immediate
candidates separated by each authored concrete value. Integral-mask to mask
conversions receive sparse, balanced, and dense throughput scenarios.
Vector comparisons that return a mask receive independent throughput
measurement. They do not receive a fabricated latency chain because feeding a
mask back into a vector operand would also measure an unrelated conversion.
Single-vector reductions with a scalar result receive independent throughput
measurement; they do not receive a fabricated latency chain because their
scalar result cannot feed the next vector input without measuring an unrelated
broadcast. The indexed-load shape `(cptr, vidx, sImm) -> v` receives a bounded
hot-L1 throughput scenario for each authored scale and SIMD index-type binding.
It does not claim to represent cold, streaming, strided, or adversarial access.
Every candidate must have authored expected-value coverage and must pass those
checks before it is timed. Other memory, masked-reduction, scalable, and
caller-unsafe shapes are reported as unsupported rather than assigned a guessed
workload.

Benchmark planning covers every variant-bearing specialization in the emitted
profile, including selected primitive dependencies. It does not silently turn a
focused `--primitives` generation into a full-catalog build; omit that filter
when the generated library and its benchmark inventory should cover the entire
catalog. Value-test tags do not control benchmark eligibility. Authored tests
are reused only as typed correctness oracles, while timing workloads come from
the separately planned scenarios below.

The repository gate audits that boundary over every loaded C++ machine profile
and arithmetic type:

```bash
./dev.sh benchmark-ratchet
```

It fails if an authored variant shape is never selected, a selected variant slot
is lost during lowering or dependency closure, correctness/scenario planning is
unsupported, or an emitted candidate and its coverage identity disagree. The
generated `coverage/benchmark-shape-inventory.md` also lists every current
signature and planner-sensitive special case. Shapes without authored variants
are recorded as `not applicable`, rather than assigned speculative timing
semantics. After an intentional complete corpus change, refresh it with
`./dev.sh benchmark-ratchet --update`.

The Generated Build CI workflow also runs the opt-in generated-build tests in
`test_benchmark_variants.py`. On x86, that gate compiles the generated benchmark
sources, executes the autotuner, and verifies that a consumer built afterward
observes the selection recorded in the generated policy. The gate also
cross-compiles a NEON benchmark and executes a short functional smoke
under QEMU. The emulated run verifies ARM candidate correctness, timing-loop
execution, and report serialization only; its timings never produce a consumed
policy. Run the complete gate locally with:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  -m generated_build tslc/tests/test_benchmark_variants.py
```

## Workload Ownership

TSL source data does not contain benchmark functions or target-language setup.
The signature supplies parameter and result shapes, while an optional
`benchmarks:` block carries only semantic facts that cannot be inferred safely.
For example, `mul` declares which operand carries the dependency chain:

```tsl
benchmarks:
  latency_chain factor1
```

Input safety constraints use the same semantic boundary. Integer `mod`, for
example, keeps zero divisors out of timing batches without embedding a setup
function:

```tsl
benchmarks:
  latency_chain dividend
  operand_domains:
    divisor nonzero
```

Dynamic vector or scalar shift operands use `shift_count`, which generates
values bounded by the element width:

```tsl
benchmarks:
  latency_chain data
  operand_domains:
    count shift_count
```

Seeds, batches, mask values, timing loops, candidate order, and statistical
rules remain compiler-owned. `tslc.benchmark.scenarios` resolves those facts
into typed register, vector-scalar, immediate, indexed-load, mask-result,
reduction, or mask-density scenarios, while `tslc.benchmark.planner` owns
candidate admission and correctness availability. The C++ benchmark renderer
then emits direct candidate calls without making workload decisions.
Shared calibration, timing, compiler barriers, and reduction live in the
generated `tsl_benchmark_core.hpp` runtime.

Unknown benchmark fields and domains, raw setup code, incompatible latency
chains, and domains attached to incompatible parameter kinds are rejected at
catalog validation. A future workload family should add a small typed vocabulary
rather than an arbitrary C++ escape hatch.

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
