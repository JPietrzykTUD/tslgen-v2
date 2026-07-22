# Variant Benchmarking And Autotuning

Generated C++ and Rust projects can benchmark implementation variants.

C++ supports report-only benchmarking, reusable policies, and an optional
one-build autotune workflow. Rust supports explicitly admitted native report
families plus a deliberately narrow compile-time policy mapping. Its autotune
workflow is an explicit policy-free benchmark followed by a separate
policy-enabled build.

The feature is opt-in.

Normal generation does not run benchmarks.

Normal builds keep the authored default variant.

## Rust Capability Matrix

| Profile | Scenario family | Report | Consumable policy |
| --- | --- | ---: | ---: |
| `sse2` | Register | yes | Only the proven `mul/sse/si8` mapping |
| `sse2` | Vector plus immediate | yes | no |
| `avx2` | One-vector scalar reduction | yes | no |

Every other `profile × scenario-family` pair remains an explicit coverage gap.
The admission key contains only the named profile and scenario family; live
machine-profile facts remain owned by `MachineProfile` and flow into the
manifest and native feature checks.

Report-only summaries retain the reducer's observed candidate and improvement,
but the corresponding policy decision remains the authored default. A profile
with no consumable mapping does not advertise policy output and rejects
`--policy-json`; its raw JSONL and summary are the complete report artifacts.

## The Word `key` Has Three Meanings

Do not treat every benchmark key as one open dictionary.

| Name | Owned by | Shape | Purpose |
| --- | --- | --- | --- |
| Source field name | TSL author | Closed vocabulary | Adds a missing workload fact. |
| `SpecializationKey` | Compiler | Frozen typed record | Identifies one selectable specialization. |
| `stable_id` | Compiler | Derived string | Names that specialization in reports and policies. |

The source vocabulary is fixed.

The compiler record is fixed.

Neither one is an arbitrary set of strings.

## Source Benchmark Vocabulary

A primitive may contain one `benchmarks:` map.

The map accepts exactly two fields:

| Field | Value | Meaning |
| --- | --- | --- |
| `latency_chain` | Declared vector parameter name | Feed the result into this operand for latency timing. |
| `operand_domains` | Parameter-to-domain map | Restrict generated timing inputs. |

`operand_domains` accepts exactly two domain values:

| Domain | Valid parameter kind | Generated values |
| --- | --- | --- |
| `nonzero` | Vector | Bounded values that exclude zero. |
| `shift_count` | Vector or scalar | Values bounded by the element bit width. |

The compiler definitions are closed sets:

```python
_KNOWN_BENCHMARK_FIELDS = frozenset({
    "latency_chain",
    "operand_domains",
})

_KNOWN_OPERAND_DOMAINS = frozenset({
    "nonzero",
    "shift_count",
})
```

The definitions live in
`tslc/src/tslc/catalog/validation/_schema_benchmarks.py`.

Unknown fields are errors.

Unknown domains are errors.

Duplicate fields are errors.

Undeclared parameter names are errors.

## Source Examples

### Latency dependency

`mul` needs an explicit dependency operand.

```tsl
prim<v:=(v,v)> mul(factor1, factor2):
  benchmarks:
    latency_chain factor2
```

The result becomes the next `factor1` value.

```text
result_0 = mul(input_0, input_1)
result_1 = mul(input_2, result_0)
result_2 = mul(input_3, result_1)
```

`latency_chain` is valid only when:

- the primitive returns a vector;
- the named parameter is declared;
- the named parameter is a vector.

### Nonzero divisor

```tsl
prim<v:=(v,v)> mod(dividend, divisor):
  benchmarks:
    latency_chain dividend
    operand_domains:
      divisor nonzero
```

The compiler selects `bounded_nonzero` for `divisor`.

It selects `bounded_random` for `dividend`.

### Shift counts

```tsl
prim<v:=(v,s)> shift_left(data, shift):
  benchmarks:
    latency_chain data
    operand_domains:
      shift shift_count
```

The compiler selects `bounded_shift_count` for `shift`.

## What Stays Out Of TSL Source

Do not author benchmark functions in `.tsl` files.

Do not author C++ setup code there.

The compiler owns:

- seeds;
- batch sizes;
- timing rounds;
- candidate order;
- mask densities;
- memory setup;
- correctness checks;
- statistical rules;
- scenario identifiers.

Add a source fact only when the signature cannot express it safely.

## Typed Promotion

Validated source becomes frozen catalog data:

```python
@dataclass(frozen=True, slots=True)
class PrimitiveBenchmarkOperandDomain:
    parameter: str
    domain: Literal["nonzero", "shift_count"]

@dataclass(frozen=True, slots=True)
class PrimitiveBenchmarkSpec:
    latency_chain: str | None
    operand_domains: tuple[PrimitiveBenchmarkOperandDomain, ...]
```

Downstream benchmark code consumes these objects.

It does not consume raw source maps.

## Scenario Inference

`tslc.benchmark.scenarios` combines the signature with the typed benchmark facts.

| Specialization shape | Scenarios |
| --- | --- |
| Fixed vector result with vector inputs | Independent throughput. Latency when the dependency is known. |
| Vector plus scalar result | Independent throughput. Latency only when the vector operand is declared. |
| Vector plus immediate result | Independent throughput and dependency latency for each authored immediate. |
| `(cptr, vidx, sImm) -> v` | Hot-L1 throughput for each scale and index type. |
| Integral mask to mask | Sparse, balanced, and dense throughput. |
| Vector comparison to mask | Independent throughput only. |
| Single-vector reduction to scalar | Independent throughput only. |

Examples:

```text
v := (v, v) + latency_chain right
  -> throughput_independent
  -> latency_dependency_chain

s := (v)
  -> throughput_independent
  -> no fabricated vector latency chain

m := (v, v)
  -> throughput_independent
  -> no fabricated mask-to-vector chain
```

Other memory shapes are unsupported.

Masked reductions are unsupported.

Scalable specializations are unsupported.

Caller-unsafe specializations are unsupported.

The coverage report records the reason.

## Specialization Identity

The generated manifest contains a field named `key`.

That value is a serialized `SpecializationKey`.

It is not the source `benchmarks:` map.

It is not a `set` or `frozenset`.

It is a frozen dataclass with ordered fields:

```python
SpecializationKey(
    backend_id="cpp",
    profile_name="avx2",
    primitive_name="mul",
    source_primitive_name="mul",
    extension_name="avx2",
    type_tag="si32",
    result_kind="v",
    param_kinds=("v", "v"),
    lanes=8,
)
```

The full record can also carry:

- target type and target extension;
- boolean axes;
- an immediate value;
- generic values;
- SIMD type bindings;
- overload positions;
- header group.

`canonical_fields()` returns these values in a fixed order.

That ordered tuple is the policy identity.

## IDs And Hashes

The compiler derives a readable `stable_id`:

```text
avx2_mul_avx2_si32_<12 hex characters>
```

The suffix hashes `SpecializationKey.canonical_fields()`.

Candidates have separate IDs:

```text
default
generic_fallback
another_authored_variant
```

`default` always comes first.

Other candidate IDs come from authored variant names.

Scenario IDs are compiler-owned:

```text
throughput_independent
latency_dependency_chain
throughput_hot_l1
mask_sparse
mask_balanced
mask_dense
```

The manifest hash covers:

- protocol version;
- profile facts;
- specialization keys and stable IDs;
- candidate IDs and body hashes;
- scenarios;
- correctness cases;
- required features.

A changed identity produces a changed manifest hash.

## Planning Flow

```text
primitive signature + benchmarks block + authored tests + lowered variants
  -> typed correctness cases
  -> typed timing scenarios
  -> candidate set
  -> manifest
  -> generated backend benchmark tool
  -> JSONL results
  -> observed report decision
  -> validated policy when the specialization has a compile-time mapping
  -> optional compile-time variant selection
```

Every candidate must pass authored expected-value cases before timing.

Value-test tags do not decide benchmark eligibility.

Focused primitive generation stays focused.

Omit `--primitives` to benchmark the full catalog.

## Coverage Gate

Benchmark coverage is ratcheted independently for C++ and Rust. The no-option
command remains the C++ compatibility gate:

```bash
./dev.sh benchmark-ratchet
```

Run the separate Rust report-and-policy gate with:

```bash
./dev.sh benchmark-ratchet --backend rust
```

The audit checks:

- selected variant slots reach planning;
- dependency closure keeps those slots;
- correctness data exists;
- a typed scenario exists;
- emitted candidates match coverage identity.

The C++ gate retains `coverage/benchmark-baseline.json` and
`coverage/benchmark-shape-inventory.md`. Its existing issue identities and
inventory remain unchanged.

Rust uses `coverage/benchmark-rust-baseline.json` and
`coverage/benchmark-rust-shape-inventory.md`. Its baseline records every raw
gap membership rather than collapsing equal-looking lowered slots. It also
records every profile manifest hash, emitted specialization identity, ordered
candidate ID/body hash, independent policy status, and compiler-rendered
mapping hash. A report can therefore remain honestly `report_only`; only a
policy-supported report must have a complete mapping. Explanatory reason text
is excluded from stable identity for both backends.

Refresh only the intended backend's two evidence files after reviewing a
deliberate coverage change:

```bash
./dev.sh benchmark-ratchet --update
./dev.sh benchmark-ratchet --backend rust --update
```

The Rust command never reads or updates the C++ evidence files, and conversely
the default C++ command does not accept Rust evidence.

Run generated benchmark tests with:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  -m generated_build tslc/tests/test_benchmark_variants.py
```

The ARM emulation check is functional only.

Its timings never create a consumed policy.

## Rust Explicit Two-Phase Autotune

Run these POSIX-shell commands from the generated Rust crate. The benchmark
help prints the profile-specific commands and the compiler-owned flag set:

```bash
cd generated/rust
env -u TSL_RUST_VARIANT_POLICY_FILE \
  cargo bench --profile bench \
    --bench tsl_variant_bench_sse2 \
    --no-default-features \
    --features variant_benchmarks \
    -- --help
```

First, create raw samples, a summary, and a native build-local policy without
allowing an existing policy input into the benchmark build:

```bash
artifact_dir="${CARGO_TARGET_DIR:-$PWD/target}/tsl-benchmark/sse2"
mkdir -p "$artifact_dir"

export TSL_RUST_BENCHMARK_CONTEXT='local-native-sse2-v1'
export CARGO_INCREMENTAL=0
export RUSTFLAGS='-Copt-level=3 -Cdebuginfo=0 -Cdebug-assertions=no -Coverflow-checks=no -Clto=off -Clinker-plugin-lto=no -Cembed-bitcode=no -Ccodegen-units=1 -Cpanic=unwind -Crpath=no -Cstrip=none -Ctarget-feature=+sse,+sse2'

env -u CARGO_ENCODED_RUSTFLAGS -u TSL_RUST_VARIANT_POLICY_FILE \
  cargo bench --profile bench \
    --bench tsl_variant_bench_sse2 \
    --no-default-features \
    --features variant_benchmarks \
    -- \
    --results "$artifact_dir/results.jsonl" \
    --summary "$artifact_dir/summary.txt" \
    --policy-json "$artifact_dir/policy.json"
```

`TSL_RUST_VARIANT_POLICY_FILE` must be absent, not present with an empty value.
The benchmark target also rejects policy-enabled builds independently. If the
runner or another build-local input changes, use a new
`TSL_RUST_BENCHMARK_CONTEXT` identity.

Second, build the consumer separately with the precomputed policy and the same
profile, feature set, context, and compiler flags:

```bash
env -u CARGO_ENCODED_RUSTFLAGS \
  TSL_RUST_VARIANT_POLICY_FILE="$artifact_dir/policy.json" \
  cargo build --profile bench \
    --no-default-features \
    --features variant_benchmarks
```

The consumer keeps `variant_benchmarks` enabled only so its generated-code
context exactly matches the producer; the build script validates the policy and
does not execute timing code. An ordinary build with no policy input still uses
the authored default. Results and policies belong below the Cargo target tree,
never below generated `src/`. The artifact expression follows a custom
`CARGO_TARGET_DIR`; pass an absolute policy path when a downstream build runs
from a different working directory.

Rust policies are native x86-64, CPU-, compiler-, Cargo-, generated-source-, and
context-bound artifacts. They are not portable across machines, emulators, or
unrecorded build inputs. Keep the generated defaults for production tuning;
the short `--rounds 3 --minimum-sample-ns 1000` settings are only for harness
checks.

## C++ Report Only

```bash
cmake -S generated/cpp -B build/tsl-report \
  -DTSL_PROFILE=auto \
  -DTSL_BUILD_TESTS=OFF \
  -DTSL_BUILD_BENCHMARKS=ON
cmake --build build/tsl-report --target tsl_benchmark_report
```

This writes `tsl_variant_results.jsonl`.

It does not change wrapper selection.

## C++ One-Build Autotune

```bash
cmake -S generated/cpp -B build/tsl-tuned \
  -DTSL_PROFILE=auto \
  -DTSL_AUTOTUNE_VARIANTS=ON
cmake --build build/tsl-tuned
```

The build creates:

```text
build/tsl-tuned/tsl/generated/tsl_variant_policy_autotuned.hpp
```

Consumer code selects the winner with `if constexpr`.

There is no runtime dispatch.

Autotune is native-only.

It requires a single-config CMake generator.

An inconclusive result keeps the authored default.

## C++ Policy Reuse

```bash
cmake -S generated/cpp -B build/tsl-policy \
  -DTSL_PROFILE=auto \
  -DTSL_VARIANT_POLICY_FILE=/absolute/path/to/tsl_variant_policy.json
cmake --build build/tsl-policy
```

The tool validates:

- the candidate manifest;
- the profile;
- compiler and tune context;
- CPU identity.

A stale policy fails.

A foreign policy fails.

Use `TSL_BENCHMARK_COMPILE_OPTIONS` for relevant private code-generation flags.

Benchmark and consumer flags must match.

`TSL_BENCHMARK_ROUNDS` and `TSL_BENCHMARK_MINIMUM_SAMPLE_NS` support short harness checks.

Keep the defaults for production tuning unless measurements justify a change.
