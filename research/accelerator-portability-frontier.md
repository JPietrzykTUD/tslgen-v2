# The database accelerator portability frontier

Assessment date: 2026-08-07

## Executive decision

The intuition behind extending TSL beyond CPU SIMD is promising, but the literal
proposal—positioning TSL as one uniform SIMD/SIMT/FPGA accelerator library—is
not a strong research contribution and is probably the wrong software
abstraction.

SIMD, SIMT, and FPGA dataflow are different execution models rather than three
interchangeable instruction-set extensions. A common interface broad enough to
hide those differences would either become a lowest-common-denominator API or
accumulate target-specific escape hatches. Moreover, portable accelerator APIs,
portable CPU/GPU database algebras, heterogeneous query engines, SQL-to-FPGA
compilers, and FPGA database overlays are established research areas.

The research-worthy question inside the proposal is instead:

> **At what abstraction level can database kernels share semantics across SIMD
> CPUs, SIMT GPUs, and spatial FPGA pipelines without target-specific semantic
> forks, and what performance tax is paid when target-specific scheduling
> freedom is removed?**

This note calls that boundary the **database accelerator portability frontier**.
The proposed contribution is not another universal IR or accelerator library.
It is a controlled experimental decomposition of portable semantics and
non-portable scheduling, normalized against strong native implementations.

This direction is a high-risk, high-cost research program. The narrower
standard-Parquet/scalable-vector question in
[`database-research-meta-study.md`](database-research-meta-study.md) remains the
better risk-adjusted first paper. If access to real GPU and FPGA hardware and
the corresponding expertise is available, however, the portability-frontier
question is the more ambitious direction.

## SIMD is widespread, but that is not itself a research gap

Explicit SIMD and compiler vectorization are important throughout analytical
database engines, including scans, predicate evaluation, compression and
decoding, hashing, partitioning, aggregation, sorting, parsing, and string
processing. Nevertheless:

- vector-at-a-time database execution is not synonymous with machine SIMD;
- important operators remain limited by latency, random memory access,
  synchronization, skew, or data movement rather than arithmetic throughput;
- GPUs expose thread and subgroup scheduling, not merely wider vector
  registers;
- an FPGA normally realizes a spatial circuit or streaming pipeline rather
  than executing a conventional sequence of vector instructions;
- end-to-end query performance may be dominated by storage decoding,
  allocation, memory placement, interconnects, or materialization.

Consequently, demonstrating that a database kernel can call TSL primitives is
engineering evidence. A scientific contribution must establish a new result
about database algorithms, execution policies, representation constraints, or
the limits of performance portability.

## Current TSL support: an evidence-based interpretation

### Compiler scope

The active compiler documentation defines `tslc` as a compiler that generates a
SIMD wrapper library; see [`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md) and
[`tslc/CHARTER.md`](../tslc/CHARTER.md). Its central model is a primitive
specialized for an extension, scalar type, and target-language backend. TSIL is
raw target text plus typed semantic islands, not a general target-language or
kernel AST.

Adding GPU kernel launch, thread/block topology, address spaces, barriers,
occupancy, stream graphs, FIFOs, pipeline scheduling, or FPGA resource
allocation directly to this compiler would therefore be a substantial product
and architecture change, not another target extension.

### CUDA declaration

[`tsldata/extensions/extension.tsl`](../tsldata/extensions/extension.tsl)
contains a `cuda` extension declaration, but the active target-family
capabilities do not admit it for generation. The support-policy test explicitly
asserts that the CUDA family is unsupported in
[`tslc/tests/test_support_policy.py`](../tslc/tests/test_support_policy.py).

The declaration should not be presented as a working SIMT backend. A credible
SIMT result would require at least:

- a defined mapping between TSL values and per-thread/subgroup values;
- subgroup collectives, masks, shuffles, synchronization, and address spaces;
- kernel launch and memory-management integration;
- executable value tests on actual GPU hardware;
- performance comparison with native CUDA, HIP, or SYCL implementations.

### oneAPI FPGA slice

The `oneapi_fpga` extension is more substantial. It:

- inherits the portable `generic` implementation family;
- uses a compile-time sized vector model;
- represents masks as `ac_int<LANES, false>` in C++;
- has FPGA-specific primitive implementations and an RTL marker;
- participates in oneAPI-specific compile profiles and tool/device detection.

The generated-profile tests in
[`tslc/tests/test_profile_rendering.py`](../tslc/tests/test_profile_rendering.py)
verify the sized type, mask spelling, and emitted primitive specializations.
The CMake helper in
[`tslc/src/tslc/backend/assets/cpp_profile_auto_helpers.cmake`](../tslc/src/tslc/backend/assets/cpp_profile_auto_helpers.cmake)
detects Intel compilers and possible FPGA devices.

Static inspection did not find an owned flow for SYCL kernel submission, FPGA
emulation as an execution target, synthesis, place-and-route, report parsing,
bitstream production, or board execution. The defensible current description
is therefore:

> TSL can generate an FPGA-oriented, sized vector primitive family and gate it
> on oneAPI-related tooling; the repository does not yet provide evidence of a
> complete, synthesized, performance-validated FPGA database-kernel backend.

Compile success, generated `ac_int` types, or device detection must not be
treated as FPGA performance evidence.

### oneAPI lifecycle risk

Intel deprecated its FPGA support package after compiler version 2025.0 and
removed integrated Altera FPGA support in the 2025.1 compiler. The 2026 compiler
also removed deprecated FPGA-related SYCL extensions. See:

- [Intel FPGA Support Package deprecation notice](https://www.intel.com/content/www/us/en/developer/tools/oneapi/fpga-download.html)
- [Intel oneAPI DPC++/C++ Compiler 2025 release notes](https://www.intel.com/content/www/us/en/developer/articles/release-notes/oneapi-dpcpp/2025.html)
- [SYCL breaking changes in the 2026 compiler](https://www.intel.com/content/www/us/en/developer/articles/technical/sycl-breaking-changes-oneapi-dpcpp-compiler-2026.html)

A new research project should not make the discontinued integrated oneAPI FPGA
path its sole foundation. Viable options are:

1. pin compiler 2025.0 only to reproduce the existing prototype;
2. migrate to Altera's current dedicated FPGA tools;
3. use an AMD/Xilinx Vitis HLS flow;
4. define a tool-independent HLS boundary and treat each vendor flow as a
   target-specific implementation.

Only actual synthesis and hardware execution count toward a three-model claim.

## Why the broad general-accelerator claim collides

No literature search proves that a question has never been answered. It can
identify the closest claims, define a narrower non-overlapping question, and
state the residual uncertainty. The following assessment reflects the
literature screen completed on 2026-08-07.

| Tempting claim | Closest prior work | Assessment |
|---|---|---|
| One portable database algebra for CPU and GPU | [Voodoo](https://people.eecs.berkeley.edu/~matei/papers/2016/vldb_voodoo.pdf) introduces a vector algebra and control vectors for CPU/GPU database execution | Collided |
| One common IR for heterogeneous analytics | [Weld](https://people.eecs.berkeley.edu/~matei/papers/2017/cidr_weld.pdf) captures SQL, ML, and graph workloads in a common IR | Collided |
| A portable operator set across CPU, GPU, and FPGA | [In-Depth Analysis of OLAP Query Performance on Heterogeneous Hardware](https://link.springer.com/content/pdf/10.1007/s13222-021-00384-w.pdf) evaluates portable database primitives on all three and concludes that architecture-specific implementations and engines remain necessary | Collided |
| Treat an FPGA as a custom SIMD target | [Program your (custom) SIMD instruction set on FPGA in C++](https://www.vldb.org/cidrdb/papers/2024/p53-pietrzyk.pdf) makes this claim in the direct TSL research lineage | Collided with project lineage |
| Compile queries automatically to FPGA operators | [SQL2FPGA](https://zhenman.github.io/files/J18-TRETS2024-SQL2FPGA.pdf) uses an engine-neutral query-plan representation, FPGA-aware optimizations, and CPU/FPGA placement | Collided |
| A performance-portable GPU database library | The 2026 [SYCLDB preprint](https://arxiv.org/abs/2607.07632) studies a portable GPU engine and reports closing much of the gap to synthesized CUDA/HIP code | Crowded |
| Quantify the abstraction boundary by separately constraining semantics and scheduling on SIMD, SIMT, and FPGA database kernels | No exact answer found in this screen; the heterogeneous OLAP study is the closest warning | Conditional research gap |

The surviving distinction is narrow but important. Prior work demonstrates
portable systems, compares devices, or introduces target-specific compilers.
The proposed study would make **the permitted amount of target specialization**
the controlled independent variable and measure the resulting performance
regret and semantic divergence.

## Recommended research direction

### Primary research question

> At which abstraction boundary can database kernels retain a single typed
> semantic description while allowing sufficiently different SIMD, SIMT, and
> FPGA schedules to achieve near-native performance?

### Secondary questions

1. Which kernel properties force an algorithmic fork rather than merely a new
   schedule?
2. Is a primitive-level semantic contract sufficient, or is a shared
   operator/suboperator graph also viable?
3. Does a uniform schedule fail for predictable reasons such as divergence,
   random access, cross-tuple state, variable output cardinality, or
   synchronization?
4. Can implementation-capability facts predict where an abstraction will lose
   performance before running a complete autotuning search?
5. Does retaining exact database semantics—nulls, overflow, ordering, and
   malformed-input behavior—change the apparent portability frontier?

### Abstraction ladder

Every retained kernel should have three treatment variants:

| Variant | Shared across targets | Target-specific freedom | Purpose |
|---|---|---|---|
| **U: universal implementation** | semantics, kernel graph, and schedule | primitive spelling and unavoidable launch glue | Tests the literal general-library proposition |
| **S: shared semantics** | typed operation semantics and logical dataflow | schedule, memory placement, parallel decomposition, and buffering | Tests the proposed semantics/schedule split |
| **N: native oracle** | nothing required beyond input/output semantics | complete algorithm and implementation | Establishes the achievable target-local baseline |

The central metric is target-normalized regret, not raw cross-device speed:

```text
regret(variant, target, kernel, scenario)
    = time(variant, target, kernel, scenario)
      / time(native_oracle, target, kernel, scenario)
      - 1
```

For throughput-oriented FPGA pipelines, use the equivalent inverse-throughput
form and report latency separately. The primary comparison must use the same
input bytes, logical semantics, result, residency assumptions, and measurement
boundary.

## Hypotheses and falsifiers

Thresholds should be finalized after a pilot but before the full experiment.
The following values make the initial proposal concrete.

### H1: regular kernels admit semantic portability

For regular and state-local database kernels, variant S remains within 15% of
the native target oracle on SIMD, SIMT, and FPGA targets without target checks
or target-specific algorithm branches in the semantic layer.

**Falsifier:** any retained target needs semantic target branches or an
algorithmic fork, or the shared-semantics version has more than 15% regret after
reasonable target-specific scheduling.

### H2: schedules are not generally portable

The universal variant U incurs at least 25% regret on at least one execution
model for two of the three retained kernels, while variant S recovers at least
half of that loss.

**Falsifier:** one schedule remains close to native on every target, or allowing
target-specific scheduling does not recover the loss. The former would support
the stronger universal-library proposition; the latter would indicate that the
shared semantics or implementation quality is the actual limitation.

### H3: the portability frontier follows kernel properties

Predeclared properties—cross-tuple state, variable work per input, variable
output cardinality, random access, and synchronization scope—separate kernels
that need only schedule specialization from kernels that require a different
algorithm.

**Falsifier:** the observed failures do not follow the predeclared properties,
or compiler maturity, memory bandwidth, or accidental implementation quality
explains the results more directly.

### H4: TSL provides controlled experimental leverage

TSL-generated CPU variants and cross-target semantic tests reduce unintended
implementation differences: the compared variants share operation contracts,
edge cases, and input/result definitions while retaining explicit native,
composed, and fallback provenance.

**Falsifier:** substantial semantics must be reimplemented independently for
every target, generated tests share the same defect as the implementation, or
TSL limitations dominate the measured performance differences.

H4 is supporting evidence, not the primary database contribution.

## Kernel selection

Start with three kernels chosen to expose different execution pressures rather
than attempting a complete SQL engine.

### K1: regular fused scan

```text
load -> nullable predicates -> projection -> scalar/grouped aggregate
```

This is the control case. It exercises predicates, masks, reductions, null
semantics, and fusion with mostly regular memory access.

Vary predicate selectivity, correlation, null density, payload width, and
whether output is materialized. Integrate the retained implementation into at
least one TPC-H Q6-like query.

### K2: standard Parquet lightweight decode and consume

```text
standard RLE/bit-packed dictionary IDs
    -> decode
    -> predicate
    -> aggregate or Arrow-compatible output
```

This adds state transitions and an externally fixed byte contract. Vary bit
width, run-length distribution, transition frequency, page size, selectivity,
and materialized versus fused consumption. Inputs must remain valid standard
Parquet pages and must not be redesigned for a target.

### K3: irregular hash probe

```text
keys -> hash/probe -> match mask -> payload gather -> aggregate/output
```

This stresses data-dependent work, random access, divergence, compaction or
refill, and FPGA memory-system limitations. Vary load factor, hit rate, probe
length, key skew, table residency, payload width, and output multiplicity.

Use one SSB- or TPC-H-derived join fragment after the isolated mechanism is
understood.

## Target implementations

### SIMD CPU

- Use TSL for explicit primitive families and controlled alternatives.
- Include at least two meaningfully different CPU vector models where
  practical: for example AVX2/AVX-512 plus SVE or RVV.
- Compare with a compiler-autovectorized implementation and a tuned native
  intrinsic implementation.
- Record vector frequency effects, lane utilization, cache behavior, branch
  behavior, and generated code.

### SIMT GPU

- Use actual subgroup/warp implementations, not a host vector emulation.
- Allow target-specific thread/block mapping, ballot/shuffle operations,
  shared memory, atomics, and occupancy tuning in variant S.
- Use native CUDA or HIP as the oracle. A SYCL implementation may be a
  portability candidate, but must not also be the only oracle.
- A claim spanning GPU vendors requires hardware from at least two GPU
  families; otherwise scope the claim to the tested SIMT target.

### FPGA

- Use an actively supported HLS/vendor flow or explicitly pin a legacy flow for
  reproducibility.
- Variant S may choose unrolling, lane count, stream width, FIFOs, memory
  banking, replication, and pipeline placement while preserving common
  semantics.
- The oracle may use a handwritten HLS or RTL-assisted design, but its
  semantics and measurement boundary must match.
- Record initiation interval, achieved frequency, LUT/ALM, register, BRAM, DSP,
  memory-channel utilization, compile time, and board power.
- Emulator results validate correctness only. The primary result requires
  synthesis and execution on a physical board.

## Correctness contract

Performance comparisons are invalid unless all targets implement the same
database semantics.

- Use an independent scalar reference, not a reference generated from the same
  TSL body.
- Differentially compare every output across all targets.
- Include empty inputs, tails, nulls, overflow boundaries, duplicate keys,
  missing keys, high skew, malformed Parquet input, and adversarial run
  transitions.
- Define floating-point ordering and reproducibility explicitly if floating
  aggregates are admitted.
- Distinguish implementation failure, unsupported semantics, compiler failure,
  synthesis failure, timeout, and incorrect result.
- Preserve exact source, compiler, driver, generated-artifact, bitstream, and
  hardware identities.

## Metrics and confounders

### Primary metrics

- target-normalized performance regret;
- end-to-end latency and steady-state throughput;
- energy per input and output tuple;
- bytes moved between storage, host, device, and materialized buffers;
- correctness and supported-scenario coverage;
- count and identity of target-specific semantic forks.

### Target-explanatory metrics

- CPU cycles, instructions, branches, cache misses, vector utilization, and
  frequency;
- GPU occupancy, warp execution efficiency, memory transactions, atomics, and
  achieved bandwidth;
- FPGA initiation interval, frequency, resources, memory bandwidth, stalls,
  and FIFO pressure.

### Secondary engineering metrics

- authored semantic definitions and target schedules;
- target-specific implementation count;
- code generation, native compilation, and FPGA synthesis time;
- change amplification when adding a primitive, kernel, target, or semantic
  edge case.

Lines of code alone are not a scientific measure because boundaries can be
gamed. Report concrete semantic decisions, schedule parameters, implementation
identities, and test obligations alongside any size measure.

### Required measurement boundaries

Report at least two views:

1. resident kernel execution, isolating computation and local memory behavior;
2. end-to-end execution, including required transfer, allocation,
   materialization, launch, and FPGA configuration costs.

Do not choose whichever boundary favors an accelerator. A result dominated by
PCIe or configuration may be an important systems result, but it is not
evidence about the kernel abstraction itself.

## Software ownership

The first prototype should be an independently packaged downstream research
consumer rather than a direct expansion of `tslc`:

```text
typed database-kernel semantics
             |
   execution-model schedules
      /          |          \
 TSL SIMD     GPU SIMT     FPGA dataflow
```

The downstream tool may consume public typed compiler facts, generated TSL
libraries, implementation provenance, and generated test inputs. It should own:

- database-kernel graphs;
- GPU kernel and scheduling semantics;
- FPGA stream and resource semantics;
- accelerator memory placement and transfer;
- native baselines, measurement, and research reports.

Dependencies must point from the research tool to `tslc`, never in reverse.
Only a separately justified, projection-neutral compiler slice should change
`tslc` or `tsldata`. If the experiment later identifies a stable shared
primitive concept, it can be added through the normal typed compiler boundary.

In particular, do not model a GPU warp or FPGA pipeline merely by adding more
conditions to the current SIMD `Extension` type. If new compiler vocabulary is
eventually warranted, SIMT groups and spatial streams should be represented as
real, distinct domain concepts with explicit invariants.

## Novelty boundary

A paper must explicitly avoid the following claims:

- “the first portable accelerator library”;
- “the first database engine for CPU, GPU, and FPGA”;
- “the first portable database operator algebra”;
- “the first SQL-to-FPGA compiler”;
- “the first custom SIMD instruction set on FPGA”;
- “one source automatically performs well everywhere”;
- “generated code is inherently faster than handwritten code.”

The candidate contribution is instead:

1. a controlled abstraction ladder that independently varies semantic and
   scheduling portability;
2. native-normalized performance regret across three genuinely different
   execution models;
3. a falsifiable classification of database-kernel properties that determine
   the portability frontier;
4. a semantics/schedule architecture that recovers performance where a
   universal implementation fails;
5. a reproducible artifact in which TSL provides controlled primitive families,
   provenance, and correctness evidence.

If the study only produces three implementations and compares their raw speed,
it collapses into the already published heterogeneous-hardware comparison. The
controlled abstraction variable and explanatory mechanism are essential.

## Relationship to Arrow and Parquet

Arrow and Parquet should not become a generic “formats on accelerators” claim.
That space is increasingly crowded:

- the 2026 preprint [Do GPUs Really Need New Tabular File Formats?](https://arxiv.org/abs/2602.17335)
  studies standard-compliant, GPU-aware Parquet configuration;
- the 2026 preprint [Oasis](https://arxiv.org/abs/2608.02268) offloads Parquet
  decoding into an FPGA-based SmartNIC datapath;
- FPGA Parquet-to-Arrow conversion and FPGA Parquet readers already exist;
- production CPU and GPU readers already contain vectorized decoders and
  predicate pushdown.

Parquet remains valuable in two narrower roles:

1. as one fixed-byte, fixed-semantics kernel in the accelerator-portability
   study;
2. as the independent, lower-risk question about standard Parquet's
   vector-length-dependent decoding tax across SVE and RVV, described in
   [`database-research-meta-study.md`](database-research-meta-study.md).

Arrow is primarily the interoperable materialized-output contract. Comparing
Arrow versus Parquet or merely generating an Arrow/Parquet decoder is not a
sufficient research contribution.

## Pilot and go/no-go gates

Do not begin by implementing three complete query engines. Use one kernel on
one real target of each execution model.

### Pilot kernel

Use either the regular fused scan or the standard Parquet dictionary-ID decode
followed by a predicate and sum. Implement U, S, and N variants with identical
inputs and results.

### Proceed only if

1. all implementations pass an independent differential oracle;
2. the common semantic layer contains no target-name checks or hidden target
   algorithms;
3. each S variant is within 20% of its native oracle in at least one meaningful
   scenario;
4. U loses materially on at least one execution model and S recovers a
   substantial part of the loss;
5. the result survives code inspection and is not caused by missing compiler
   flags, accidental allocation, debug code, frequency changes, or an obviously
   weak oracle;
6. the FPGA result is synthesized and executed on hardware;
7. transfer-inclusive and resident measurements tell a coherent story;
8. TSL limitations do not dominate the CPU result.

### Stop or narrow the project if

- the FPGA toolchain or hardware cannot support reproducible experiments;
- the semantic layer immediately requires target-specific algorithms;
- native-oracle implementations cannot be made credible;
- universal and separated variants perform nearly identically everywhere;
- all differences vanish in end-to-end queries;
- the only contribution becomes source-code reduction or backend generation.

A failed pilot is useful project guidance. It should prevent a multi-year
engineering effort whose research surface is already flat.

## Alternative directions

| Direction | Novelty status after this screen | Effort | Recommendation |
|---|---|---:|---|
| Database accelerator portability frontier | Conditional; closest prior work is damaging but does not appear to run the exact abstraction-ladder experiment | Very high | Best ambitious program if real hardware and expertise are available |
| Standard Parquet's scalable-vector decode tax | Survives the separate screen; GPU/FPGA generalizations are crowded | Medium | Best risk-adjusted first paper |
| SIMD-batched MVCC version resolution | Possible narrow gap, but lane refill and MVCC scan acceleration have substantial prior art | High | Independent backup requiring deeper search |
| Bounded exact SQL DECIMAL across SIMD ISAs | Possible narrow CPU-SIMD gap; GPU arbitrary-precision work exists | Medium-high | Independent backup |
| Automatically select a custom FPGA SIMD primitive set under a resource budget | General custom-instruction selection, database FPGA overlays, UPP, and the CIDR 2024 TSL lineage create high collision risk | Very high | Pursue only after a focused novelty audit identifies a new optimization problem |
| Add CUDA, SYCL, or HLS backends and benchmark them | Engineering only | Very high | Do not use as the main research question |

## Publication positioning

This project is likely to sit between database systems, programming languages,
and computer architecture. It needs database-specific kernels, semantics, and
end-to-end query evidence to be credible at a database venue. Without that
integration, PPoPP, CGO, ASPLOS, or an accelerator workshop may be a more
natural audience than SIGMOD or VLDB.

A publication-shaped claim would be:

> Across regular, stateful, and irregular database kernels, we quantify the
> performance tax of constraining target specialization on SIMD CPUs, SIMT
> GPUs, and spatial FPGA pipelines. We show which semantic structures can be
> shared, which schedules must remain target-specific, and which kernel
> properties force an algorithmic fork. A typed semantics/schedule separation
> recovers near-native performance in the portable region; TSL supplies the
> controlled primitive implementations, provenance, and differential tests.

This wording is justified only if the native-normalized results, classification
and end-to-end evidence all survive.

## Recommended decision

1. Do **not** reposition the current project as a finished general accelerator
   library.
2. If pursuing the ambitious direction, describe TSL as a **generator of
   explicit data-parallel semantic building blocks with execution-model-specific
   realizations**.
3. Build the first three-model experiment as an isolated downstream research
   prototype.
4. Require actual GPU and FPGA execution before expanding compiler scope or
   making a heterogeneous-acceleration claim.
5. In parallel, retain the standard-Parquet/scalable-vector pilot as the
   lower-cost publication path.
6. Repeat the novelty search through DBLP, ACM DL, IEEE Xplore, recent
   SIGMOD/PVLDB/ICDE/CIDR proceedings, PPoPP/CGO/ASPLOS, FPGA/FPL proceedings,
   and the citation graphs of the closest papers before committing to the full
   implementation.

The most defensible long-term vision is not “one API hides every accelerator.”
It is “one explicit semantic catalog tells us what can be shared, while the
research identifies and preserves what must remain hardware-specific.”
