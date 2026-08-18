# Intermediate-representation prototype plan

## Implementation status (2026-08-06)

The source tree described below is implemented. It provides four genuinely
materialized TSL boundary representations, fused/autovectorized/scalar
references, exact-selectivity datasets, exhaustive boundary-oriented
correctness checks, deterministic staged registration, pinned dependency
identities, and Google Benchmark context/counters. It deliberately contains no
cost model or results-analysis framework.

Two focused mechanism slices are now implemented without turning the prototype
into a Cartesian experiment framework:

- `--irbench_matrix=pressure` instantiates every kernel with 1, 4, and 8
  simultaneously live aggregate states. It changes downstream SIMD register
  demand while holding input columns, boundary representation, batch size, and
  intermediate bytes fixed.
- `--irbench_matrix=threading` runs the one-aggregate candidates with explicit
  worker counts and `strong`, `weak`, or `both` scaling. Workers read disjoint
  contiguous views of one immutable exact-selectivity dataset and own private
  scratch buffers and partial results. Strong scaling holds total rows fixed;
  weak scaling holds rows per worker fixed.

These slices answer different questions. More workers create cache, bandwidth,
and execution-resource contention but do not increase a core's SIMD register
pressure. The 1/4/8-aggregate slice is the direct register-pressure probe; the
threading slice tests whether a single-thread representation result survives
parallel execution.

A Clang 22 overlay build generated from the current workspace is available on
this host. It is deliberately not based on a tagged release:

```bash
TSLC_OUTPUT_ROOT=./tslctmp/intermediate-repr/generated/mask-after \
  TSLC_BACKENDS=cpp ./dev.sh generate --profiles avx2 --backends cpp
cmake -S research/intermediate-repr-src \
  -B tslctmp/intermediate-repr/build/clang22-avx2-mask-after2 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++-22 \
  -DIRBENCH_PROFILE=avx2 -DIRBENCH_ENABLE_CLANG_OVERLAY=ON \
  -DTSL_LOCAL_SOURCE_DIR=/workspace/tslctmp/intermediate-repr/generated/mask-after
cmake --build tslctmp/intermediate-repr/build/clang22-avx2-mask-after2 --parallel
ctest --test-dir tslctmp/intermediate-repr/build/clang22-avx2-mask-after2 \
  --output-on-failure
```

The repository base commit was
`7115056373ee979c24b2d9e8a6afe43d74e9a11c`; the generated C++ tree records
the local source identity
`e7c85c78b23c996179a3bd883cdd8c5bf433cf1d12ac3130ac4c0e1945bd383f`.
That identity includes the working-tree mask-bridge change described below.
The pre-change current-workspace snapshot used for the paired diagnostic run
had generated identity
`3642e1939a027757754c756bd96982a621cfb3ff5d83dd995ef03b4ec458d79a`.
These are local generated-product identities, not release-version labels.

Clang 22.1.8 supplies `__builtin_elementwise_clzg`; the generated project also
probes and enables `ext_vector_boolean_mask_bridge`. The current-source Clang
overlay therefore configures with both capability branches. The correctness
executable validates
111 compiled candidates: all materialized and fused hardware/Clang policies at
1, 4, and 8 aggregates, plus scalar references. CTest also dry-runs a focused
pressure matrix and one-/two-worker strong/weak matrix. Clang emits `-Wpsabi`
warnings when 512-bit compiler-vector types are instantiated under the AVX2
profile; those variants are a compiler-lowering experiment, not AVX-512 ISA
claims, and require disassembly and performance-counter scrutiny before their
measurements are accepted. A hardware-only GCC 15.2.0 AVX2 build also
passes correctness and both mechanism smoke tests; it compiles 21 candidates
(the hardware and scalar 1/4/8 variants) and intentionally has no Clang-overlay
policies.

A safe registration smoke is:

```bash
tslctmp/intermediate-repr/build/clang22-avx2-mask-after2/irbench_benchmark \
  --irbench_matrix=smoke --benchmark_dry_run \
  --benchmark_filter='N=1003/B=257/sA_bp=5000/sBgA_bp=9000'
```

Focused mechanism registrations use explicit filters:

```bash
# Single-thread live-state probe; the filter should select retained scenarios.
irbench_benchmark --irbench_matrix=pressure \
  --benchmark_filter='.../aggregates=(1|4|8)/...'

# Separate parallel robustness probe; aggregate_count remains one.
irbench_benchmark --irbench_matrix=threading \
  --irbench_workers=1,2,4,8 --irbench_scaling=both \
  --benchmark_filter='.../aggregates=1/...'
```

Stage 2, pressure, threading, and confirmation refuse to run without an
explicit `--benchmark_filter`; threading additionally requires
`--irbench_workers=...`. The filter supplies retained, precommitted scenarios
selected after Stage 1. Full performance runs must still follow the protocol
below. A dry run is correctness/registration evidence, never performance
evidence.

Disassembly of the Clang AVX2 binary confirms distinct producer and consumer
symbols and calls. It also shows scratch-buffer stores and later loads for
native masks, integral masks, packed bits, and position lists. A focused native-mask check confirms materially distinct pressure specializations: the `K=4`
hot loop keeps four AVX2 aggregate vectors in registers, whereas `K=8` causes
Clang 22 to outline the TSL aggregate loop; its wrapper allocates a `0x1a0`-byte
stack-resident state object and the outlined vector loop writes eight aggregate
states back through that object on each iteration. This is a genuine codegen
cliff, but not proof of hardware register exhaustion alone: live state, inlining,
and alias analysis are confounded. Full disassembly across representations and
hardware counters remain required.

### Current-source mask-bridge diagnostic (2026-08-06)

The first current-workspace build exposed a confounder, not a research result:
Clang comparison and Boolean masks reached `to_integral` and `to_mask`
through generated per-lane tests and assignments. That implementation dominated
many compiler-vector measurements. The fix now in the current source corpus
adds a C++ compiler capability,
`ext_vector_boolean_mask_bridge`, guarded by all of the following:

- Clang Boolean extended-vector support;
- `__builtin_convertvector`;
- little-endian lane order;
- a compile probe that exercises comparison-to-Boolean packing and expansion.

The comparison-mask path converts 0/-1 lanes to a dense Boolean vector, then
bit-casts that one-bit-per-lane value to the integral mask. Expansion first
clears unused high bits, bit-casts to the Boolean vector, converts to the
comparison-mask type, and negates 0/1 lanes into canonical 0/-1 lanes. The
Boolean-mask path uses the normalized bit bridge directly. The original lane
loop remains the generated fallback when the capability is absent. Authored and
generated tests cover comparison and Boolean policies, two-lane padding, and
64-lane high bits.

The paired diagnostic used the same command for the pre- and post-change local
products:

```bash
irbench_benchmark --irbench_matrix=stage2 \
  --benchmark_filter='scaling=strong/N=65536/B=16384/sA_bp=(100|9000)/sBgA_bp=9000/distribution=random/seed=2672458773$' \
  --benchmark_min_time=0.25s --benchmark_min_warmup_time=0.20 \
  --benchmark_repetitions=9 --benchmark_enable_random_interleaving=true
```

Both runs contain 74 paired median cells. Representative compiler-vector changes
are:

| Cell, Filter-A selectivity 1% | Before median | After median | Before/after |
|---|---:|---:|---:|
| Boolean, 256-bit, integral | 381,448 ns | 10,671 ns | 35.7x |
| Boolean, 512-bit, integral | 516,008 ns | 10,997 ns | 46.9x |
| Comparison, 256-bit, fused | 64,422 ns | 7,313 ns | 8.8x |
| Comparison, 128-bit, packed bits | 148,471 ns | 153,902 ns | 0.96x |

The last row is an important counterexample: the bridge does not cure all
compiler-vector code generation. Post-change symbols still show outlined
algorithm helpers for the slow 128-bit Boolean and 512-bit packed-bit cases,
whereas the fast 256-bit cases inline completely. Blanket `always_inline` or
`flatten` attributes were deliberately not added; the remaining cliffs are
mechanism evidence to investigate, not a reason to obscure code generation.

The following are the within-run materialized-representation oracle results:

| Filter-A selectivity | Fastest materialized choice | Median | Nearest dense alternative | Position-list median |
|---:|---|---:|---:|---:|
| 1% | positions, Clang 512 comparison | 9,653 ns | integral, Clang 256 Boolean: 10,671 ns | 9,653 ns |
| 90% | integral, Clang 256 Boolean | 10,800 ns | native, Clang 512 Boolean: 11,005 ns | 30,749 ns |

At 1%, positions beat the best integral choice by 10.5%. At 90%, positions are
184.7% slower than the best integral choice, although integral beats native by
only 1.9%. The best fused Clang reference is still faster (7,313 ns at 1% and
7,310 ns at 90%), so the result concerns an unavoidable boundary, not a reason
to materialize when fusion is legal.

This is a positive direction check, not a passed go/no-go gate:

- H1 is promising: the observed sparse/dense crossover is large, and choosing
  integral everywhere incurs 10.5% regret in the tested sparse cell.
- H1 is not established: only one process, seed, distribution, data size, batch
  size, and aggregate count were measured; confidence intervals and independent
  confirmation runs are absent.
- H2 is also not established. Compiler vectors are now competitive, and the
  apparent winner changes from 512-bit comparison/positions to 256-bit
  Boolean/integral, but the best same-representation width/policy margins are
  generally below the predeclared 5% threshold.
- Unaffected scalar, autovectorized, and hardware-reference medians shifted by
  roughly 5-17% between the two processes. The very large bridge improvements
  are credible as a defect removal, but smaller cross-process differences must
  not be treated as scientific effects.

Therefore the mask fix makes the prototype worth pursuing through Stage 1 and
confirmation. It does not yet justify implementing a predictive cost model.

## Decision at a glance

This prototype asks one question before building a cost model:

> At an unavoidable batch boundary in a columnar `Filter A -> Filter B ->
> Aggregate` pipeline, does the best representation of the rows passing
> `Filter A` change materially and repeatably with workload and SIMD
> realization?

The prototype is deliberately smaller than `research/pipcost-src/`:

- the measured code is C++ using the generated TSL API;
- Google Benchmark owns calibration, repetition, interleaving, and JSON output;
- there is one batch-at-a-time execution model;
- there is no cost model, Python package, experiment database, orchestration
  framework, database engine, or autotuner in the first prototype;
- fused execution is a measured reference, not a representation candidate;
- a cost model is justified only if the benchmark first demonstrates stable,
  consequential crossover points.

The implementation starts from scratch below this directory. It must not copy
the architecture or source files from `research/pipcost-src/`. Earlier results
may later be used as independent context, but they are not an input or baseline
for this experiment.

## Elevator pitch

- Columnar engines must sometimes cross a non-fused boundary between operators.
- At that boundary, active rows can be stored as native SIMD masks, integral
  mask words, packed bits, or positions.
- These formats trade conversion work, bytes materialized, sequential scanning,
  and sparse gathers differently.
- TSL can instantiate the same logical kernels for hardware-intrinsic SIMD and
  Clang vector types, at 128-, 256-, and 512-bit widths and with two Clang mask
  contracts.
- The prototype measures whether those choices create a real, predictable
  database planning problem—or whether one simple fixed choice is sufficient.

## Ownership and repository boundary

This is an independently owned downstream research prototype. It consumes a
generated TSL C++ library but is not a `tslc` compiler stage, backend,
projection, benchmark generator, or source-data feature.

The dependency direction is:

```text
generated TSL C++ product -> intermediate-repr prototype
```

The prototype must not require changes to `tslc/` or `tsldata/`. It must not
parse generated C++, inspect TSIL bodies, infer intrinsic names, or reinterpret
compiler metadata. It may use only public generated headers, CMake targets, and
functions. If a required operation is unavailable for a policy, that
combination is a recorded capability gap rather than a reason to add a
prototype-specific compiler special case.

The relevant existing public contracts are evidenced by:

- [`tslc/DESCRIPTION.md`](../../tslc/DESCRIPTION.md), which documents the Clang
  vector overlay, mask policies, and generated target naming;
- [`tsl_algorithm.hpp`](../../tslc/src/tslc/backend/assets/tsl_algorithm.hpp),
  whose mask-layout algorithms accept a SIMD parallelism policy;
- [`tsl_algorithm_detail_core.hpp`](../../tslc/src/tslc/backend/assets/tsl_algorithm_detail_core.hpp),
  which defines policy-to-vector and selected-row loading behavior;
- [`mask_specific.tsl`](../../tsldata/primitives/conversion/mask_specific.tsl),
  which defines the `to_integral` and `to_mask` representation bridge;
- [`rnd_access.tsl`](../../tsldata/primitives/load_store/rnd_access.tsl), which
  defines `gather_narrow` for selected-row access;
- [`masked_aggregation_operator.cpp`](../../examples/cpp/masked_aggregation_operator.cpp),
  [`selection_vector_operator.cpp`](../../examples/cpp/selection_vector_operator.cpp),
  and [`selected_aggregate_consume_operator.cpp`](../../examples/cpp/selected_aggregate_consume_operator.cpp),
  which demonstrate the constituent public operations.

Runtime output belongs under `tslctmp/intermediate-repr/`, never in this source
directory.

## Research hypotheses

### Primary hypothesis H1: representation crossovers exist

> For a batch-at-a-time, two-filter columnar pipeline with a real materialized
> boundary after the first filter, no one of native-mask chunks, integral-mask
> chunks, packed bits, and position lists is consistently near-optimal across
> first-filter selectivity, conditional second-filter selectivity, batch size,
> working-set size, and match distribution.

This is falsified for the studied scope if one fixed representation remains
within 5% of the per-scenario oracle in every repeatable scenario, or if
apparent winner changes are within measurement uncertainty.

### Secondary hypothesis H2: Clang realization is a planning dimension

> On one x86 machine profile and under the same Clang compiler, the preferred
> representation or its cost changes materially among hardware-intrinsic TSL,
> Clang compiler vectors of different lengths, and Clang's comparison-vector
> versus Boolean-vector mask policies.

This is separate from H1. It must not be used to enlarge the first sweep before
H1 shows that the representation choice matters.

H2 is falsified if the compiler-vector variants are uniformly dominated, or if
one length and mask policy remains within 5% of the best Clang realization in
all retained scenarios.

### Mechanism hypothesis H3: downstream state can move crossovers

> For the same input and materialized boundary, increasing the number of
> simultaneously live SIMD aggregate states from 1 to 4 or 8 can change the
> relative cost or winner among native masks, integral masks, packed bits, and
> positions because representations leave different register, instruction, and
> memory budgets for the consumer.

This is a targeted mechanism hypothesis, not a new full-matrix axis. The
pressure query computes deterministic `SUM(c XOR salt_i)` states over exactly
the same qualifying rows and combines their scalar results into one checksum.
It is falsified if representation rankings and regret remain stable, or if
disassembly/counters show that timing changes are explained by extra arithmetic
without changed register allocation, spills, or relevant execution pressure.

### Robustness hypothesis H4: parallel execution can move crossovers

> A representation winner measured on one core may cease to be near-optimal
> when independent workers scan disjoint partitions concurrently because dense
> intermediates, packed masks, and sparse gathers stress shared caches and
> memory bandwidth differently.

H4 is tested only after useful single-thread cases are retained. Strong scaling
holds total relation size fixed; weak scaling holds rows per worker fixed. It is
falsified if winner and regret remain stable across precommitted worker counts,
or if changes cannot be reproduced under pinned placement. H4 is not evidence
about SIMD register pressure: every worker executes the same one-aggregate
kernel on its own core.

### What the hypotheses do not claim

- They do not claim that fully fused pipelines should materialize masks.
- They do not claim that a Boolean Clang mask maps to a hardware predicate
  register. TSL explicitly does not make that guarantee.
- They do not claim that vector width and machine ISA are the same decision.
- They do not claim that a learned or analytical cost model is already needed.
- They do not claim that worker count is a proxy for per-core SIMD register
  pressure.
- They do not claim that eight synthetic aggregates represent every real SQL
  aggregate workload.
- They do not generalize beyond the tested query, data type, hosts, compilers,
  and steady-state scan protocol without later evidence.

## Fixed logical query

The only initial query is:

```sql
SELECT SUM(c)
FROM t
WHERE a < p1 AND b < p2;
```

The pressure matrix keeps that query as the `K=1` baseline and adds synthetic
`K=4` and `K=8` forms:

```sql
SELECT SUM(c XOR salt_0), ..., SUM(c XOR salt_(K-1))
FROM t
WHERE a < p1 AND b < p2;
```

The fixed salts make every state semantically distinct while reusing column
`c`; therefore input bytes, selectivity, and boundary bytes do not grow with
`K`. `K` is a compile-time template parameter so the generated kernel can keep
independent vector accumulators live. This is a controlled pressure probe, not
a claim that XOR aggregates are themselves a database contribution.

Its physical boundary is intentionally fixed:

```text
for each batch:
    Filter A over column a
    -> materialize active rows in representation R
    -> call a separately compiled consumer
       Filter B over column b, restricted by R
       -> aggregate matching values from column c
```

The producer and consumer are separate translation units, LTO is disabled, and
the boundary functions are non-inline. This is essential: otherwise the
compiler could fuse the two stages and erase the intermediate whose cost is
being studied.

Initial semantics are narrow and explicit:

- `a`, `b`, and `c` are separate contiguous `std::int32_t` columns;
- `p1` and `p2` are runtime values;
- the result is an exact `std::int64_t` sum;
- generated `c` values are bounded so both vector partial sums and the final
  scalar sum cannot overflow;
- there are no nulls, encodings, compression, dictionaries, strings, or
  variable-width values;
- predicate order is fixed;
- input order is preserved;
- positions are batch-relative `std::uint32_t` row identifiers;
- the final partial batch is semantically identical to the scalar reference;
- every candidate returns the same result and observed selected-row counts.

Using separate predicate and aggregate columns prevents the benchmark from
collapsing into a mask-population-count experiment.

## Candidate intermediate representations

Only the following four variants participate in the representation oracle.

### R1: native-mask chunks

Store one `Vec::mask_type` per SIMD chunk after Filter A. The concrete storage
therefore follows the selected TSL vector and mask policy. It may be an
all-bits-per-lane vector, a compact AVX-512 mask, or a dense Clang Boolean
vector.

The consumer loads the stored mask, evaluates Filter B, combines the masks via
TSL mask primitives, and performs a masked aggregate. No bit-cast assumptions
are allowed.

### R2: integral-mask chunks

Call `tsl::to_integral<Vec>` after Filter A and store one `Vec::imask_type` per
SIMD chunk. The consumer reconstructs or consumes the active mask through
TSL's representation-safe bridge before applying Filter B.

This is not the same as a dense relation bitmap: a fixed-width integral value
is stored for every SIMD chunk even when only a few low bits are meaningful.

### R3: packed bits

Store one dense bit per input row, with a documented least-significant-bit
lane order and zeroed unused tail bits. The consumer scans the bitmap and
applies Filter B only under the active lanes.

The initial implementation should use TSL's public `mask_layout::bits`
algorithm path rather than inventing a second packing convention.

### R4: position list

Append each qualifying batch-relative row number to a contiguous
`std::uint32_t` array. The consumer gathers Filter B and aggregate values for
those positions, applies the second predicate, and aggregates passing values.

The producer may use the public policy-parametric TSL selection helper. The
existing selected-row convenience helpers choose a generic vector from a lane
count, so the consumer must instead use a small tool-local loop parameterized
by the exact `Vec` and call public TSL operations such as `gather_narrow`, mask
combination, masked `hadd`, and scalar tail handling. This preserves the
hardware-versus-Clang realization being measured without modifying TSL.

### Representation invariants

For every representation and policy, record and test:

- exact intermediate element type and `sizeof`;
- logical lanes represented per element;
- bytes allocated and bytes logically written per batch;
- position count or active-row count after Filter A;
- active-row count after Filter B;
- lane order and tail behavior;
- batch-relative position semantics;
- result equality with the scalar oracle.

## Measured references, not candidates

Three references clarify the result but are excluded from the representation
oracle:

### Fused TSL reference

Evaluate both predicates and aggregate in one TSL loop without a memory-resident
active-row intermediate. This answers how much the forced boundary costs. It is
not evidence for choosing among boundary representations.

### Compiler-autovectorized scalar-source reference

Compile a straightforward branchy C++ loop with normal `-O3` optimization.
This shows what the compiler achieves without explicit TSL calls. It must be
described as an autovectorization reference, not as scalar execution.

### Vectorization-disabled scalar reference

Compile the same source shape in a separate target with vectorization disabled:

- Clang: `-fno-vectorize -fno-slp-vectorize`;
- GCC: `-fno-tree-vectorize`.

This is the actual scalar performance reference and the correctness oracle.
The build records the exact compiler and effective flags for both reference
targets.

## SIMD realization taxonomy

The plan treats machine profile, vector length, implementation realization,
and mask policy as distinct facts.

For `std::int32_t`, the C++ policy types are:

```cpp
// Hardware implementation selected by the generated machine profile.
tsl::dataparallel::fixed<4>   // 128 bits
tsl::dataparallel::fixed<8>   // 256 bits
tsl::dataparallel::fixed<16>  // 512 bits

// Clang compiler-vector implementation, comparison-result mask.
tsl::dataparallel::clang_fixed<4>
tsl::dataparallel::clang_fixed<8>
tsl::dataparallel::clang_fixed<16>

// Same Clang data vectors, dense Boolean-vector mask.
tsl::dataparallel::clang_fixed<
    4, tsl::dataparallel::clang_mask::boolean_vector>
```

The Boolean form is registered only when
`__has_feature(ext_vector_type_boolean)` is true. Missing support is reported as
a capability skip, never silently replaced by the comparison-vector policy.

Direct realization comparisons use the same Clang executable and flags:

| Machine profile | Natural hardware policy | Matching Clang policies |
|---|---:|---:|
| SSE2 | `fixed<4>` | `clang_fixed<4>` comparison and Boolean |
| AVX2 | `fixed<8>` | `clang_fixed<8>` comparison and Boolean |
| AVX-512 | `fixed<16>` | `clang_fixed<16>` comparison and Boolean |

The AVX2 Clang width experiment additionally measures `clang_fixed<4>`,
`clang_fixed<8>`, and `clang_fixed<16>` under the same AVX2 machine flags. That
experiment asks how Clang lowers requested compiler-vector lengths on one
machine profile; it does not rename 512-bit compiler vectors as AVX-512.

GCC measures hardware-intrinsic TSL and the two scalar-source references only.
It cannot instantiate the Clang overlay. GCC-versus-Clang hardware results test
compiler robustness; they are not a direct hardware-versus-compiler-vector
comparison.

## Experimental dimensions

### Core dimensions

| Dimension | Meaning | Initial values |
|---|---|---|
| Representation | Boundary format | native, integral chunks, packed bits, positions |
| Batch size | Rows sharing one intermediate buffer | 1 Ki, 16 Ki, 256 Ki rows |
| Relation size | Steady-state scan working set | 64 Ki and 16 Mi rows |
| Filter-A selectivity | Density written to the boundary | 1%, 10%, 50%, 90% |
| Conditional Filter-B selectivity | Fraction of A survivors also passing B | 10%, 90% initially; 50% in confirmation |
| Match distribution | Spatial shape at fixed density | random initially; clustered in confirmation |
| Machine profile | Available x86 feature set | AVX2 first; SSE2 and AVX-512 confirmation |
| SIMD realization | How vector operations are expressed | hardware TSL, Clang compiler vector |
| Clang vector length | Requested compiler-vector width | 128, 256, 512 bits |
| Clang mask policy | Concrete mask contract | comparison vector, Boolean vector |
| Compiler | Code-generation implementation | Clang first; GCC confirmation for hardware TSL |

Only combinations with `batch_rows <= relation_rows` are registered.

Filter-B selectivity is conditional on passing Filter A. Two scenarios with
the same final selectivity but different `(sA, sB|A)` are not interchangeable:
they materialize different amounts of data and perform different amounts of
second-stage work.

### Targeted mechanism dimensions

These are separate precommitted matrices, not additions to the core Cartesian
product:

| Dimension | Meaning | Initial values |
|---|---|---|
| Live aggregate states | Per-worker SIMD accumulator demand | 1, 4, 8 |
| Worker count | Concurrent disjoint partitions | explicitly supplied, beginning with 1 and 2 |
| Scaling contract | Rows held constant | strong: total rows; weak: rows per worker |

The pressure matrix keeps workers at one. The threading matrix keeps aggregate
count at one. Crossing these axes is forbidden until each isolated experiment
shows a repeatable effect and a concrete follow-up hypothesis is precommitted.

### Deferred dimensions

The following are scientifically interesting but excluded until the core
choice passes the go/no-go gate:

- morsel scheduling, NUMA placement policy, and shared-output reduction;
- artificial compute or memory stress;
- cold-cache flushing;
- nulls and SQL three-valued logic;
- compressed or dictionary-encoded columns;
- wider types and mixed-width columns;
- compacted value streams;
- more than one downstream consumer;
- relation-global operator-at-a-time materialization;
- Rust and non-x86 architectures.

System stress is especially easy to make irreproducible. If later added, it
needs a calibrated, recorded load generator and is a separate experiment—not
another unchecked Cartesian axis.

## Staged experiment matrix

The full Cartesian product is deliberately forbidden. Each stage is unlocked
by the preceding evidence.

### Stage 0: capability and correctness smoke

Purpose: prove that each promised C++ policy and representation can compile and
produce identical results before timing anything.

- TSL: exact current-workspace base commit, working-tree identity, and
  generated-artifact digest; a tagged release may be measured separately but
  must not substitute for the current project state;
- Google Benchmark: pinned `v1.9.5` source release;
- compilers: one supported Clang and one supported GCC;
- profiles: SSE2, AVX2, and AVX-512 only when the host natively supports them;
- policies: natural hardware width plus all available Clang widths and mask
  policies;
- sizes: deliberately awkward row counts such as 0, 1, `lanes - 1`, `lanes`,
  `lanes + 1`, 1003, and `batch_rows + 3`;
- selectivities: none, one lane, alternating, all, and deterministic random;
- checks: result, Filter-A count, final count, ordering, sentinels after the
  produced positions, and zeroed packed-bit tails.

AVX-512 timing is skipped on a non-AVX-512 host; emulation is valid for
correctness but never for performance evidence.

### Stage 1: does the representation choice pay off?

Purpose: test H1 with the smallest credible matrix.

- compiler: Clang;
- machine profile: AVX2;
- SIMD policy: hardware `fixed<8>` only;
- representations: all four;
- batch sizes: 1 Ki, 16 Ki, 256 Ki rows;
- relation sizes: 64 Ki and 16 Mi rows;
- Filter-A selectivities: 1%, 10%, 50%, 90%;
- conditional Filter-B selectivities: 10%, 90%;
- distribution: deterministic random;
- workers: one;
- references: fused TSL, compiler-autovectorized scalar source, and
  vectorization-disabled scalar source.

This is at most 192 materialized benchmark cases before invalid
`batch_rows > relation_rows` combinations are removed. It is small enough to
repeat rigorously and broad enough to expose the sparse/dense and cache/batch
trade-offs.

Proceed only if the H1 gate below passes.

### Stage 1P: does live downstream state change the answer?

Purpose: test H3 on a small set of Stage-1 scenarios and separate a potential
register-allocation mechanism from representation volume.

- compiler/profile/policy: Clang, AVX2, hardware `fixed<8>` first;
- aggregate states: 1, 4, 8 compile-time-specialized accumulators;
- representations: all four plus fused and scalar references for context;
- scenarios: at most 6--12 precommitted sparse/dense and cache-/memory-resident
  Stage-1 cases, prioritizing observed crossovers or high regret;
- workers: one;
- controls: identical input, selectivity, batch size, column bytes, and
  intermediate bytes for all `K`;
- required mechanism evidence: disassembly for every `K`, compiler optimization
  remarks where useful, and hardware counters for cycles, instructions, cache
  misses, and spills or load/store effects available on the host.

Do not interpret slower `K=8` execution alone as register-pressure evidence:
more aggregates necessarily execute more XOR/add work. The relevant result is a
repeatable *interaction* between `K` and representation, supported by codegen or
counter evidence.

### Stage 1T: does the single-thread result survive parallel workers?

Purpose: test H4 only on retained Stage-1 cases.

- aggregate states: one;
- workers: precommitted physical-core counts, beginning with 1 and 2 and later
  powers of two up to one NUMA node;
- strong scaling: one exact `N`-row dataset partitioned across workers;
- weak scaling: one exact `(N * workers)`-row dataset, giving `N` rows per
  worker;
- ownership: immutable shared inputs, contiguous disjoint views, private
  intermediate scratch, private partial result, no timed global reduction;
- metric: wall-clock time/throughput; Google Benchmark CPU time is diagnostic;
- required controls: external CPU affinity, physical-core placement, NUMA
  placement, frequency/thermal state, and memory-bandwidth counters.

The implementation intentionally does not pin threads or mutate host policy. A
performance run is unacceptable unless the external command and topology are
recorded.

### Stage 2: does Clang realization change the answer?

Purpose: test H2 without multiplying the entire discovery matrix.

Retain 12–24 Stage-1 scenarios:

- every repeatable representation crossover;
- sparse and dense endpoint controls;
- at least one cache-resident and one memory-resident case;
- at least two batch sizes;
- cases where the best fixed representation has the largest regret.

Under Clang and the AVX2 machine profile, compare:

- hardware `fixed<8>`;
- comparison-mask `clang_fixed<4|8|16>`;
- Boolean-mask `clang_fixed<4|8|16>` where supported;
- all four boundary representations.

This isolates three questions:

1. Is a Clang compiler-vector realization competitive with native-intrinsic
   TSL under the same compiler?
2. Is requested vector length itself workload-dependent?
3. Does mask representation change native-mask materialization enough to
   affect the database-level choice?

### Stage 3: confirmation, not exploration

Purpose: test whether the discovered effects survive reasonable changes in
hardware profile, compiler, seed, and distribution.

- profiles: SSE2, AVX2, and AVX-512 on native hardware;
- natural-width Clang comparison: hardware, comparison mask, Boolean mask;
- GCC: hardware TSL only;
- data: a second random seed and a clustered-run distribution;
- conditional Filter-B selectivity: add 50%;
- scenarios: only endpoints, crossover neighborhoods, and high-regret cases
  selected before seeing these confirmation results.

Do not tune the retained scenario list after inspecting Stage-3 outcomes.

### Stage 4: optional mechanism study

Only after a crossover is replicated, add focused component benchmarks for:

- Filter-A production alone;
- intermediate scan/conversion alone;
- Filter-B plus aggregate consumption;
- intermediate bytes written and read;
- selected gather cost as a function of position density and clustering.

These explain a demonstrated effect. They must not replace the end-to-end
pipeline result.

## Dataset construction

One deterministic C++ fixture generates all columns before timing. It uses a
small, explicitly implemented PRNG such as SplitMix64; no implementation-defined
standard-library distribution is used.

Generation constructs membership explicitly rather than hoping a random
threshold realizes the requested selectivity:

1. choose exactly `round(N * sA)` rows for Filter A;
2. among those rows, choose exactly `round(activeA * sB_given_A)` for Filter B;
3. assign `a` and `b` values on the appropriate side of runtime thresholds;
4. fill `c` with deterministic bounded non-zero values;
5. optionally permute memberships for random distribution or place them in
   fixed-length runs for clustered distribution;
6. compute the scalar expected sum and both observed counts once.

Every result record reports requested and realized selectivity. Dataset
construction, expected-result computation, allocation, and page prefaulting
remain outside the timed region.

For threading, the fixture generates requested selectivity once at the *global*
relation size and shares that immutable allocation among the Google Benchmark
worker group. Contiguous quotient/remainder partitioning gives every row to
exactly one worker. This matters: generating one rounded-selectivity relation
per worker can change global survivor counts across worker counts and invalidate
strong-scaling comparisons. Each worker validates its own view before timing;
the framework sums raw counters across workers.

The initial benchmark is a warm, steady-state scan. A 16-Mi-row relation uses
approximately 192 MiB for the three input columns, before scratch space, and is
intended to exceed ordinary last-level caches. The JSON context records the
host cache inventory; if that assumption is false on a test host, choose and
record a larger relation before the experiment is frozen.

## Fair kernel contract

Every materialized candidate must:

- execute the same two predicates in the same order;
- include production, materialization writes, later reads, Filter B, and the
  aggregate in the timed interval;
- allocate maximum scratch capacity before timing;
- reuse the same input fixture and thresholds;
- process the same batch sequence and scalar tail;
- write a real intermediate that the separately compiled consumer reads;
- avoid allocation, logging, data generation, and correctness checking inside
  the timed loop;
- expose one scalar checksum to `benchmark::DoNotOptimize`;
- call `benchmark::ClobberMemory` after a complete pipeline invocation;
- report input rows through `state.SetItemsProcessed`;
- report logical input bytes separately from intermediate bytes;
- never count the fused reference as an intermediate-format winner.

For threaded runs, additionally require one immutable shared input relation,
disjoint complete row ownership, private scratch per worker, private aggregate
results, no timed synchronization or final reduction beyond Google Benchmark's
iteration barriers, and `UseRealTime()` as the primary clock. Strong-scaling
counters must sum to the one-worker global row and survivor counts; weak-scaling
counters must grow with worker count.

The producer and consumer boundary uses explicit instantiations in separate
translation units. CMake disables interprocedural/LTO optimization for all
benchmark targets. A disassembly spot check must confirm a materialized store,
call boundary, and later load for each representation before performance data
is accepted.

## Implemented source layout

The prototype is intentionally limited to the following small tree:

```text
research/intermediate-repr-src/
├── PLAN.md
├── CMakeLists.txt
├── cmake/
│   └── Dependencies.cmake
├── include/intermediate_repr/
│   ├── scenario.hpp
│   ├── kernel_api.hpp
│   └── kernel_templates.hpp
└── src/
    ├── benchmark_main.cpp
    ├── correctness_main.cpp
    ├── datasets.cpp
    ├── produce.cpp
    ├── consume.cpp
    └── references.cpp
```

No Python package, generic configuration system, result database, generated
source, or model-fitting code belongs in the first implementation.

### `scenario.hpp`

Owns literal research facts only:

- relation rows;
- batch rows;
- requested selectivities;
- distribution and seed;
- thresholds;
- stable scenario identities and explicit matrix selection names.

It must not discover TSL profiles or reconstruct compiler capabilities.

### `kernel_api.hpp`

Defines the small ABI between benchmark code and separately compiled kernels:

```cpp
struct columns_view;
struct scratch_view;
struct pipeline_result;

using pipeline_fn = pipeline_result (*)(
    columns_view, scratch_view, std::size_t batch_rows,
    std::int32_t p1, std::int32_t p2);
```

Each registered candidate has a stable literal identity containing:

```text
profile / realization / vector_bits / mask_policy / representation /
aggregate_count / scaling / workers / relation_rows / batch_rows /
selectivity_a / selectivity_b_given_a / distribution / seed
```

### `kernel_templates.hpp`

Contains the common TSL-based algorithms parameterized by:

- exact vector policy;
- mask layout or position-list tag;
- compile-time aggregate count (`1`, `4`, or `8`);
- alignment policy, fixed to unaligned initially.

It may wrap public TSL calls but must not contain x86 intrinsics. Small local
repetition is preferable to a framework that obscures the four physical plans.

### `produce.cpp` and `consume.cpp`

Own explicit template instantiations and enforce the materialization boundary.
They are compiled without LTO. Public TSL algorithm helpers should be used for
native, integral, and packed-bit layouts. The position consumer owns the
minimal exact-policy gather loop described above.

### `references.cpp`

Owns the fused TSL and scalar-source references. The same scalar-source
function is compiled into normal and vectorization-disabled targets so their
source semantics cannot drift.

### `correctness_main.cpp`

Runs exhaustive boundary-shaped cases without Google Benchmark timing. It
prints a concise failure identity and exits non-zero on the first mismatch.

### `benchmark_main.cpp`

Registers only combinations supported by the selected build. It adds compiler,
TSL, Google Benchmark, profile, feature, policy, and build-mode context to the
JSON report. Registration order is deterministic. It also parses the
prototype-owned `pressure` and `threading` matrices, creates one shared dataset
fixture per registered worker group, partitions exact global data, and reports
aggregate, worker, scaling, scratch, and intermediate-volume counters.

## CMake and dependency plan

Use CMake 3.20 or newer and C++17, matching the generated C++ project examples.

### TSL

- reproducibility source: the exact local current-workspace base commit plus
  the working-tree diff/status identity used for generation;
- preferred artifact input: generate the C++ product once from that exact
  workspace snapshot into `tslctmp/intermediate-repr/generated/` and record
  both its compiler-reported source identity and artifact-manifest digest;
  generation is setup, never part of a timed run;
- optional release comparison: a verified generated release archive is a
  separate historical baseline, never the source for current-state conclusions;
- development override: `TSL_LOCAL_SOURCE_DIR`, pointing to an already
  generated C++ root, with its artifact digest and dirty-source identity
  recorded and results kept separate from every other source snapshot;
- selected machine profile: one explicit `TSL_PROFILE` cache value per build
  directory;
- normal compiler: link `tsl::<profile>`;
- Clang overlay build: link `tsl::<profile>_clang` and fail clearly when the
  target is unavailable;
- never fall back silently from a requested overlay to the base target.

Each compiler/profile combination receives a separate build directory below
`tslctmp/intermediate-repr/build/`. The benchmark must not use `-march=native`
on top of profile flags because that would blur the named TSL machine profile.

### Google Benchmark

Pin [Google Benchmark `v1.9.5`](https://github.com/google/benchmark/releases/tag/v1.9.5)
and its archive digest. `FetchContent` may populate only the scratch build tree;
it must not vendor files into this source directory. Disable upstream tests and
installation. Link `benchmark::benchmark`, not `benchmark_main`, because the
prototype adds context and registers policies explicitly.

Google Benchmark's [official user guide](https://github.com/google/benchmark/blob/main/docs/user_guide.md)
documents repetitions, warmup, random interleaving, JSON output, custom
context, and optimization barriers. The prototype relies only on those public
features.

### Build modes

Provide literal CMake options rather than a configuration framework:

```text
IRBENCH_PROFILE=sse2|avx2|skylake
IRBENCH_ENABLE_CLANG_OVERLAY=ON|OFF
TSL_LOCAL_SOURCE_DIR=<optional generated tree>
```

The configure step fails if the selected compiler/profile cannot build the
requested policy. No runtime CPUID dispatch is needed; each binary represents
one explicit build context.

## Google Benchmark protocol

The first accepted runs use:

```text
--benchmark_min_time=0.25s
--benchmark_min_warmup_time=0.20
--benchmark_repetitions=9
--benchmark_enable_random_interleaving=true
--benchmark_out=<run>.json
--benchmark_out_format=json
```

Do not use `--benchmark_report_aggregates_only`; retain individual repetition
records. The default CPU time is the primary single-thread metric, with real
time retained as a scheduling-noise diagnostic. Threaded registrations use
Google Benchmark `Threads(...)` and `UseRealTime()`; wall time and aggregate
rows/second are primary for that separate experiment, while summed CPU time is
diagnostic.

Operational protocol:

1. run `correctness_main`;
2. run `--benchmark_dry_run` to validate registration and capability skips;
3. pin single-thread runs to one physical core outside the program; for
   threaded runs, pin exactly the precommitted physical-core set and record
   logical-CPU, socket, core, SMT, and NUMA placement;
4. record CPU model, microcode, kernel, governor/turbo state, cache sizes,
   compiler path/version, effective compile command, TSL tag/digest, Google
   Benchmark tag/digest, Git commit, and dirty-worktree status;
5. run the complete randomized-interleaving benchmark;
6. repeat the run in a fresh process;
7. reject a run with thermal throttling, frequency instability, background
   load, correctness failure, or changed build/context identity.

The program observes and reports host state; it does not modify governors,
turbo settings, affinity, or other system configuration itself.

## Metrics and decision rules

### Primary metric

For single-thread matrices: median CPU nanoseconds per input row for the
complete two-filter aggregate pipeline, including intermediate production and
consumption.

For the threading matrix: median wall-clock nanoseconds per global input row
and aggregate rows per second. Strong-scaling speedup is relative to the same
`N`-row one-worker case; weak-scaling efficiency compares constant rows per
worker.

### Secondary metrics

- real nanoseconds per row;
- rows per second;
- intermediate bytes per input row;
- intermediate bytes per Filter-A survivor;
- Filter-A and final survivor counts;
- producer and consumer time from optional Stage-4 component runs;
- code size and compile time only if H2 reveals a useful compiler-vector
  policy.

Do not use “GB/s” as the only result: position lists intentionally avoid some
column reads, so a single byte denominator can hide the mechanism.

### Scenario oracle

For each complete scenario, build context, aggregate count, worker count, and
scaling contract:

```text
oracle_time = minimum median time among R1..R4
regret(candidate) = (candidate_time - oracle_time) / oracle_time
```

References are not eligible for this oracle.

For each candidate, retain all individual Google Benchmark repetitions. Report
the median and a 95% bootstrap confidence interval for its time and for the
relative difference to the apparent winner. Use a fixed resampling seed and a
predeclared reducer. A winner is “material” only when the lower confidence
bound on its advantage exceeds zero and the point advantage is at least 5% in
both independent processes. This reduction is a transparent evidence step,
not a predictive cost model; the raw JSON remains authoritative.

### H1 go/no-go gate

Proceed toward a cost model only if all of the following hold:

1. at least two representations win in different predeclared scenario regions;
2. each claimed crossover repeats in two processes and a second seed or
   distribution;
3. the winner margin is at least 5% and larger than run-to-run uncertainty;
4. the best single fixed representation has at least 10% worst-case regret in
   the retained confirmation scenarios;
5. the effect survives correctness, disassembly, and provenance checks.

If these conditions fail, stop. The honest conclusion is that this query and
scope do not justify a representation-aware cost model.

### H2 go/no-go gate

Treat Clang realization as a planning dimension only if:

1. a compiler-vector policy is competitive rather than uniformly dominated;
2. at least two realization/length/mask choices win in replicated regions, or
   realization changes the preferred database representation;
3. the material margin is at least 5%; and
4. code-size and compile-time costs do not make the apparent runtime win
   obviously impractical.

Otherwise choose the robust fixed realization and remove this dimension from
any later optimizer.

### H3 go/no-go gate

Treat aggregate state/register demand as a representation-selection feature
only if:

1. the representation ranking or regret changes materially between `K=1` and
   `K=4|8` in replicated precommitted scenarios;
2. intermediate bytes and input rows are identical across `K`;
3. disassembly confirms distinct live accumulator/codegen shapes and, where a
   spill claim is made, actual stack traffic; and
4. counters or controlled component evidence distinguish register/execution
   pressure from the unavoidable extra arithmetic.

If only absolute runtime grows with `K`, H3 fails and aggregate count should not
enter a representation cost model.

### H4 go/no-go gate

Treat worker count or resource saturation as a representation-selection feature
only if pinned, replicated strong/weak runs show a material interaction between
worker count and representation, not merely ordinary parallel speedup. Global
row/survivor counts must obey the scaling contract, and the effect must survive
a second process and placement check. If rankings remain stable, report the
scaling result but exclude worker count from the selector.

## Implementation slices

Each slice ends in an executable fact and should be reviewed before the next
one begins.

### Slice 1: build and TSL policy smoke

Add CMake, pinned dependencies, and one tiny executable that instantiates:

- AVX2 hardware `fixed<8>`;
- Clang comparison-mask `clang_fixed<4|8|16>`;
- Clang Boolean-mask `clang_fixed<4|8|16>` when available;
- `load`, `less_than`, mask combination, `to_integral`, `to_mask`,
  `gather_narrow`, and masked aggregation operations.

Exit criterion: every supported policy compiles, runs, and reports its concrete
lane count and mask/intermediate sizes. Unsupported policies fail configuration
or appear as explicit skips.

### Slice 2: scalar semantics and datasets

Implement deterministic exact-selectivity data generation, scalar oracle, and
awkward-size correctness cases.

Exit criterion: requested versus realized selectivity and expected sums are
stable across repeated processes and both compilers.

### Slice 3: one real boundary, two representations

Implement native-mask and position-list producer/consumer pairs in separate
translation units for AVX2 hardware TSL.

Exit criterion: disassembly shows materialization; correctness passes; Google
Benchmark emits stable named JSON records with no timed setup.

This slice is the earliest low-effort feasibility result. If the two extreme
representations show no meaningful difference even at 1% versus 90%
selectivity, reassess before implementing the remaining matrix.

### Slice 4: complete representation set

Add integral-mask chunks and packed bits using the same kernel contract.

Exit criterion: all four candidates pass representation invariants and the
Stage-1 sweep completes twice.

### Slice 5: Clang realization slice

Register compiler-vector widths and both mask policies for only the retained
Stage-1 cases.

Exit criterion: same-compiler hardware-versus-Clang comparisons exist for
identical data and physical plans, with exact capability reporting.

### Slice 6: focused pressure and threading probes

Instantiate one, four, and eight aggregate states for all candidates, but expose
them only through the pressure matrix. Add explicit Google Benchmark worker
registrations for the one-aggregate threading matrix, using a shared exact
dataset, disjoint views, private scratch, strong/weak scaling, and real time.

Exit criterion: all specializations pass correctness; dry-run CTests cover all
three aggregate counts and one-/two-worker strong/weak registration; strong
scaling preserves exact global counts; disassembly establishes whether the
pressure kernels actually create the intended codegen distinction.

### Slice 7: confirmation

Add the precommitted SSE2/AVX-512, GCC, clustered, and second-seed cases.

Exit criterion: H1--H4 receive explicit pass/fail verdicts for the slices that
were unlocked. No cost model is implemented in this slice.

### Separate future project: selection policy

Only after an H1 pass, design a small explainable selector. Its initial
features should be limited to facts the experiment has shown useful, such as:

- Filter-A density;
- conditional remaining selectivity;
- batch rows;
- working-set class;
- concrete intermediate bytes per row;
- machine profile and exact SIMD realization;
- aggregate count only after an H3 pass;
- worker/resource state only after an H4 pass.

Evaluate it on held-out scenarios and hosts using chosen-plan regret. Do not
retrofit a model into this prototype merely because a cost-model storyline is
attractive.

## Risks and required controls

### Compiler erases the boundary

Control: separate translation units, no LTO, non-inline functions, scratch
passed through the public ABI, and disassembly evidence.

### Extra aggregate work is mislabeled as register pressure

Control: compare the interaction between representation and `K`, not raw
`K=1` versus `K=8` time. Keep input and intermediate bytes fixed, inspect each
specialized consumer, and require codegen/counter evidence before mentioning
spills or register pressure.

### Threading silently changes data or placement

Control: generate one exact global dataset, partition every row once, validate
each view, and require global strong-scaling counters to match one worker. Pin
physical cores and record NUMA placement externally; unpinned dry runs establish
functionality only.

### Wide Clang vectors change ABI or lower unexpectedly

Control: retain the `-Wpsabi` warning in the experimental record, keep the
producer/consumer ABI free of vector types, inspect 128/256/512-bit symbols,
and do not infer ISA width from requested compiler-vector length.

### “Native mask” changes meaning across policies

Control: treat concrete size and mask policy as recorded experimental facts.
Never equate native mask with compact hardware predicate.

### Position-list code measures a different SIMD policy

Control: the selected-row consumer is templated on the exact `Vec` and calls
public TSL `gather_narrow`; do not use the lane-count-only convenience helper in
the H2 comparison.

### Final selectivity hides first-stage work

Control: vary and report `sA` and `sB|A` independently.

### Combinatorial explosion

Control: staged gates, sparse retained scenarios, and a ban on the full cross
product.

### Cache labels are wrong on a host

Control: record cache inventory and actual relation bytes; interpret “hot” and
“memory-resident” only after checking those facts.

### TSL helper overhead or implementation quality dominates

Control: keep physical plans semantically exact, inspect generated assembly,
and use Stage-4 component measurements. A poor helper is an empirical result,
not evidence for the abstract representation unless a reasonable equivalent
implementation is also considered.

### Benchmark order or system drift creates false crossovers

Control: Google Benchmark random repetition interleaving, two processes,
affinity, warmup, individual repetitions, and predeclared confirmation cases.

### A useful fused implementation makes all candidates look pointless

Interpretation: this is expected when fusion is legal. The research question
applies only to real boundaries caused by blocking operators, code-size or
compilation constraints, reusable selections, exchange/scheduling boundaries,
or downstream reuse. A large fusion gap does not invalidate the comparison,
but a paper must motivate where such a boundary occurs in an actual engine.

## Prototype success and failure outcomes

### Strong positive result

Multiple representations win by material margins in stable regions, the best
fixed choice has consequential regret, and TSL exposes or controls a mechanism
that would otherwise require multiple hand-maintained ISA implementations.

This justifies a later selector and database-engine integration.

### Useful negative result

One representation is consistently near-optimal, or crossovers vanish under
replication. Do not build a cost model. Report the dominance region and use the
prototype as evidence for a simpler engine policy.

### Inconclusive result

Margins are near noise, capability gaps prevent comparable variants, or
results depend on unverified generated code. Improve the measurement boundary
or stop; do not convert ambiguity into a research claim.

## Publication relevance if the gates pass

The benchmark alone is not a top-tier database paper. A credible later paper
would still need:

- a database-system integration with genuine pipeline boundaries;
- representative analytical workloads or operator fragments;
- multiple contemporary x86 hosts and preferably another architecture;
- comparison with the engine's existing mask/selection policy;
- held-out evaluation of a selector, including regret and overhead;
- analysis of why the chosen representation changes;
- compile-time, code-size, and maintainability costs;
- a clear account of what TSL enables beyond hand-written per-ISA kernels.

The prototype's job is narrower and more valuable at this point: determine
whether that larger research investment has an empirical foundation.

## Final stop conditions

Stop implementation and record the reason if:

- the public generated TSL API cannot instantiate comparable policies without
  compiler or source-data changes;
- the materialization boundary cannot be proven in generated machine code;
- candidate semantics or tail handling differ;
- Stage 1 shows no stable, material representation payoff;
- Stage 2 shows no stable Clang realization payoff;
- native hardware for a claimed performance profile is unavailable;
- a pressure claim cannot be tied to distinct generated code or mechanism
  evidence;
- threaded measurements cannot be run with controlled affinity and topology;
- expanding the matrix becomes the goal instead of answering H1--H4.

The desired output is an honest decision, not a large benchmark framework.
