# Pipeline cost-model prototype implementation plan

## Implementation correction (2026-07-30)

The implemented prototype now pins generation to the exact TSL `v0.2.7` tag,
supports TSL's native mask layout, times explicit compiler-autovectorized and
vectorization-disabled scalar references, and separates optimizer candidates
from measured references. Representation pilots compare only batch-materialized
native, integral, packed-bit, and position-list candidates. A separate batch
pilot compares fused, batch-local native, and relation-wide native execution.
Width-specific configs cover SSE2 (128 bit), AVX2 (256 bit), and Skylake
AVX-512 (512 bit). These corrections supersede any older wording below that
implies fused execution is a representation candidate or that native mask
materialization is unavailable.

## Status and decision

This document plans a prototype derived from:

- [`pipeline-cost-model-idea.md`](pipeline-cost-model-idea.md); and
- [`pipeline-cost-model-discussion.md`](pipeline-cost-model-discussion.md).

The prototype code will live entirely under:

```text
research/pipcost-src/
```

Generated TSL projects, build directories, raw measurements, fitted models,
reports, disassembly, and all other runtime output will live under:

```text
tslctmp/pipcost/
```

`research/pipcost-src/` does not exist at the time this plan is written. This
plan creates no prototype code; its first implementation slice will create the
directory and its local contract.

The prototype is an independently owned downstream research consumer of
`tslc`. It is not:

- a `tslc` compiler stage;
- a compiler-owned projection;
- a `tslc` backend or command;
- TSL source data;
- an extension of the existing primitive-variant benchmark planner.

Dependencies point from the prototype to the public compiler product. Neither
`tslc` nor `tsldata` may import, register, configure, or change behavior for
the prototype.

## Goal

Implement the smallest system that can answer the following falsifiable
question:

> For a fixed columnar `filter -> filter -> aggregate` query, do active-row
> representation and execution granularity have stable, explainable
> performance crossover points that a small cost model can predict better than
> fixed or local policies?

The prototype should:

1. generate or consume a selected C++ TSL library;
2. implement several semantically equivalent complete query pipelines;
3. verify every pipeline against one scalar reference;
4. collect deterministic, provenance-rich raw measurements;
5. identify the measured oracle plan for every scenario;
6. fit a deliberately simple cost model;
7. evaluate chosen-plan regret against the oracle and fixed baselines;
8. stop honestly if the plan space does not justify an optimizer.

## Research hypothesis

The initial hypothesis is:

> The best representation of a filter result depends jointly on active-row
> density, materialization scope, batch size, working set, SIMD realization,
> and the remaining consumer; therefore, a fixed representation policy is
> measurably suboptimal in some repeatable regions.

The prototype does not assume that this hypothesis is true. Its first purpose
is to determine whether a meaningful planning problem exists.

## Architectural ownership

### Compiler-owned facts consumed by the prototype

The prototype should reuse rather than reconstruct:

- `.tsl` source discovery and validation;
- machine-profile definitions;
- target and backend availability;
- primitive selection and dependency closure;
- concrete C++ type and callable spellings;
- native mask and integral-mask types;
- generated C++ algorithm helpers;
- target feature and build flags;
- compiler diagnostics and coverage outcomes;
- deterministic generated artifacts.

The initial implementation should use only:

- `tslc.api.generate_project`;
- `tslc.api.write_artifacts`;
- the public `tslc doctor --format json` command;
- the generated C++ CMake product and public generated headers.

The public generation result exposes generated artifacts, diagnostics,
coverage, skipped slots, and emitted profiles. The prototype should calculate
an evidence digest from the public artifact digest manifest rather than
importing a private compiler input-digest implementation.

If an essential compiler-owned fact is not publicly accessible, stop and
classify it:

1. If it is projection-neutral and useful to other downstream consumers,
   propose a separate focused `tslc` API slice.
2. If it is pipeline-, workload-, or experiment-specific, keep it in
   `pipcost`.

No private compiler import should be added merely to avoid designing the
proper downstream contract. If a private import later becomes unavoidable, it
must be isolated in one compatibility module and documented as a lockstep
dependency.

### Prototype-owned facts

`pipcost` owns:

- the fixed logical query;
- active-row representations;
- complete physical plan identities;
- materialization and batching policy;
- synthetic data generation;
- scalar reference semantics;
- benchmark scenarios and matrix expansion;
- measurement procedure;
- host and build evidence;
- raw record schema;
- summaries and oracle decisions;
- cost-model fitting;
- plan selection and regret evaluation;
- all runtime skips and prototype diagnostics.

These facts must not be presented as compiler guarantees.

### No target-text parsing

The prototype should call the generated C++ API. It must not parse generated
C++, inspect TSIL bodies, infer intrinsic names, or rewrite target text.
Disassembly is permitted as measurement evidence, but it is not an input to
compiler semantics or correctness.

## Current repository evidence supporting the plan

Static inspection found the following existing support:

- [`tslc/src/tslc/api.py`](../tslc/src/tslc/api.py) exposes in-memory
  generation, artifact writing, and generated-project verification.
- [`tslc/src/tslc/backend/helper_requirements.py`](../tslc/src/tslc/backend/helper_requirements.py)
  defines compiler-owned C++ algorithm-helper roots, including `load`,
  `to_integral`, `to_mask`, `gather_narrow`, `compress_store`,
  `mask_population_count`, and `mask_binary_and`.
- [`tslc/src/tslc/backend/assets/tsl_algorithm.hpp`](../tslc/src/tslc/backend/assets/tsl_algorithm.hpp)
  contains public C++ helpers for predicate materialization, selection-vector
  production and refinement, masked aggregation, and selected aggregation.
- [`examples/cpp/masked_aggregation_operator.cpp`](../examples/cpp/masked_aggregation_operator.cpp)
  demonstrates materialized native, integral, byte, and packed-bit masks
  followed by masked aggregation.
- [`examples/cpp/selection_vector_operator.cpp`](../examples/cpp/selection_vector_operator.cpp)
  demonstrates dense and masked position-list production.
- [`examples/cpp/selected_refinement_operator.cpp`](../examples/cpp/selected_refinement_operator.cpp)
  demonstrates position-list refinement over a subsequent predicate.
- [`examples/cpp/selected_aggregate_consume_operator.cpp`](../examples/cpp/selected_aggregate_consume_operator.cpp)
  demonstrates aggregation over selected rows.
- [`examples/cpp/CMakeLists.txt`](../examples/cpp/CMakeLists.txt) demonstrates
  consuming a generated TSL C++ project through CMake.
- [`supplementary/buildsystem/machine_profiles.json`](../supplementary/buildsystem/machine_profiles.json)
  already defines `avx2`, `skylake`, later AVX-512 profiles, and AMD x86
  profiles.
- [`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md) documents the opt-in Clang
  fixed-width vector overlays and their distinct mask policies.

This evidence shows that the prototype is plausible. It does not prove that
all intended kernels compile for every profile or that any performance
crossover exists. The capability-inventory slice must establish those facts.

## Scope

### Prototype query

The first logical query is:

```sql
SELECT SUM(c)
FROM t
WHERE a < p1 AND b > p2;
```

Initial semantics are deliberately narrow:

- `a`, `b`, and `c` are separate contiguous `int32` columns;
- thresholds `p1` and `p2` are runtime scalar values;
- the aggregate is an exact signed `int64` sum;
- generated `c` values are bounded so the scalar reference cannot overflow;
- there are no nulls, encodings, compression, dictionaries, or variable-width
  values;
- predicate order is fixed;
- input alignment uses the explicit unaligned path initially;
- row order is preserved where a representation has an order;
- a position list uses unsigned 32-bit relation-global row identifiers;
- every physical plan must return exactly the scalar reference result.

Using a separate aggregate column prevents the experiment from degenerating
into mask population count. A later reuse extension may add:

```sql
SELECT SUM(c), SUM(d)
FROM t
WHERE a < p1 AND b > p2;
```

### Deliberate initial simplification

The first physical-plan family evaluates both predicates as one filter stage:

```text
combined predicate = (a < p1) AND (b > p2)
```

All first-family plans therefore scan both predicate columns. They differ only
in:

- whether the combined active set is materialized;
- which representation is materialized;
- whether it is consumed per batch or after the complete relation.

This isolates the representation boundary between filtering and aggregation.
It does not yet test early avoidance of the second predicate.

Only after the first-family comparison works and produces meaningful evidence
should the prototype add a true cascade:

```text
Filter(a)
  -> choose representation
Filter(b)
  -> refine representation
Aggregate(c)
```

The cascade is where remaining-pipeline-aware planning and dynamic programming
become justified.

### Initially fixed

- backend: generated C++;
- scalar type: signed 32-bit integers;
- aggregate type: signed 64-bit integer;
- one native x86 host;
- one compiler for the first pilot;
- one hardware-supported profile for the first pilot;
- one worker;
- warm repeated execution;
- no external system stress;
- no database-engine integration.

### Deferred

- Rust;
- multiple workers and NUMA;
- resource interference;
- compressed or encoded columns;
- null semantics;
- compacted value streams;
- joins and grouped aggregation;
- automatic predicate reordering;
- arbitrary SQL or relational algebra;
- a generic query compiler;
- runtime switching between plans;
- a production autotuner;
- a full machine-learning model;
- end-to-end database-engine integration.

## Physical plan space

### Stable plan vocabulary

The benchmark binary owns a deterministic plan registry. Every plan entry
contains:

- stable `plan_id`;
- active-row representation;
- processing mode;
- mask layout, if applicable;
- position width, if applicable;
- compile-time lane count or native-width policy;
- whether an intermediate is materialized;
- whether the intermediate is batch-local or relation-wide;
- whether the plan is supported in the current generated build.

The binary exposes the registry through:

```text
pipcost-bench --list-plans --format json
```

The Python orchestration layer consumes that registry. It must not maintain a
second handwritten list of supported C++ plans.

### First complete plans

| Plan family | Active-set representation | Processing mode | Intended implementation |
|---|---|---|---|
| `fused_mask` | transient native mask | fully fused | direct TSL load, compare, mask AND, select-zero, and reduction in one loop |
| `batch_native_mask` | materialized native-mask chunks | batch at a time | `predicate_binary` with native layout, then `aggregate_masked_unary`; reuse batch scratch |
| `batch_integral_mask` | materialized integral-mask chunks | batch at a time | same helper sequence with integral layout |
| `batch_bitmask` | packed bits | batch at a time | same helper sequence with packed-bit layout |
| `batch_positions_u32` | 32-bit positions | batch at a time | `select_indices_binary`, then `aggregate_selected_unary` |
| `full_native_mask` | relation-wide native-mask chunks | operator at a time | native mask plan with batch size equal to row count |
| `full_integral_mask` | relation-wide integral-mask chunks | operator at a time | integral mask plan with batch size equal to row count |
| `full_bitmask` | relation-wide packed bitmap | operator at a time | packed-bit plan with batch size equal to row count |
| `full_positions_u32` | relation-wide positions | operator at a time | position plan with batch size equal to row count |

The initial smoke gate needs only:

- `fused_mask`;
- `batch_integral_mask`;
- `batch_bitmask`;
- `batch_positions_u32`;
- their complete-relation counterparts where the same implementation can use
  `batch_rows == rows`.

Native-mask materialization is admitted after the capability inventory proves
that its generated public storage and consumer path builds for the selected
profile.

### Batch semantics

For every non-fused plan:

1. allocate maximum scratch capacity before timing;
2. divide `[0, rows)` into deterministic consecutive batches;
3. produce the active-set representation for one batch;
4. consume it immediately for the aggregate;
5. reuse the same scratch allocation for the next batch;
6. handle the final partial batch correctly.

`batch_rows == rows` is the operator-at-a-time endpoint. Smaller batch sizes
are batch-at-a-time execution. `fused_mask` has no intermediate batch and
ignores `batch_rows`.

### SIMD width

For `int32`, controlled fixed widths correspond conceptually to:

- 4 lanes: 128 bits;
- 8 lanes: 256 bits;
- 16 lanes: 512 bits.

The capability inventory must determine which combinations compile and map to
the intended generated target for each profile. Unsupported combinations
produce explicit plan skips rather than fallback claims.

The first smoke run should use one supported lane count. Width comparison is
added only after representation correctness and measurement stability.

## Synthetic data model

### Required properties

The generator must independently control:

- row count;
- first-predicate selectivity;
- conditional second-predicate selectivity among first-predicate matches;
- combined selectivity;
- qualifying-position pattern;
- seed;
- bounded aggregate values.

Supported patterns begin with:

- `random`: qualifying positions are deterministically shuffled;
- `clustered`: qualifying positions occur in deterministic contiguous runs.

The generator first decides qualification truth values and then encodes column
values around fixed thresholds. This avoids relying on accidental probability
from a numeric distribution and permits exact observed selectivities.

### Reproducibility

Use a small explicitly implemented and versioned pseudo-random generator, such
as SplitMix64, rather than a standard-library shuffle whose complete behavior
may vary across implementations.

Every scenario identity includes:

- generator schema version;
- generator algorithm version;
- all requested selectivities;
- pattern parameters;
- row count;
- seed;
- aggregate-value bounds.

Data generation is never part of the timed interval.

### Correctness reference

One scalar function implements the query directly. Before timing a physical
plan for a scenario:

1. calculate the scalar result once;
2. execute the physical plan outside timing;
3. compare exact `int64` results;
4. reject the plan/scenario pair if they differ.

Correctness cases must cover:

- zero rows;
- one row;
- row counts below the SIMD width;
- exact multiples of the width;
- partial vector tails;
- partial batches;
- 0% and 100% selectivity;
- no rows surviving the first predicate;
- no rows surviving the second predicate;
- all rows surviving both predicates;
- random and clustered positions;
- batch sizes smaller and larger than the row count.

## Proposed source layout

```text
research/pipcost-src/
├── AGENTS.md
├── CHARTER.md
├── README.md
├── pyproject.toml
├── configs/
│   ├── smoke.json
│   ├── pilot-representation.json
│   ├── pilot-batch.json
│   └── held-out.json
├── src/
│   └── pipcost/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── domain.py
│       ├── tsl_project.py
│       ├── build.py
│       ├── host.py
│       ├── matrix.py
│       ├── runner.py
│       ├── records.py
│       ├── reduce.py
│       ├── oracle.py
│       ├── cost_model.py
│       └── evaluate.py
├── cpp/
│   ├── CMakeLists.txt
│   ├── include/
│   │   └── pipcost/
│   │       ├── data.hpp
│   │       ├── measurement.hpp
│   │       ├── plan.hpp
│   │       └── query.hpp
│   ├── src/
│   │   ├── main.cpp
│   │   ├── data.cpp
│   │   ├── measurement.cpp
│   │   ├── plan_registry.cpp
│   │   ├── reference.cpp
│   │   └── plans/
│   │       ├── fused_mask.cpp
│   │       ├── materialized_mask.cpp
│   │       └── positions.cpp
│   └── tests/
│       └── kernel_tests.cpp
└── tests/
    ├── test_config.py
    ├── test_matrix.py
    ├── test_records.py
    ├── test_reduce.py
    ├── test_oracle.py
    ├── test_cost_model.py
    └── test_cli.py
```

This is a target layout, not a requirement to create every module in the first
slice. Modules should be added only when their owned behavior exists. In
particular, `cost_model.py` and `evaluate.py` should not be created before the
measurement/oracle gate passes.

### Local contract

`CHARTER.md` will state:

- one-way dependency on the generated TSL product and public `tslc` API;
- ownership of database and measurement semantics;
- no compiler registry or default mutation;
- no target-text parsing or source rewriting;
- all generated and runtime output under `tslctmp/pipcost`;
- deterministic plan, scenario, build, and record identities;
- correctness before timing;
- explicit skips for unsupported hardware or generated capabilities.

`AGENTS.md` will own prototype-specific validation commands and reiterate that
prototype work does not authorize `tslc` or `tsldata` changes.

## Python orchestration

### Dependency policy

The initial Python package should use the standard library plus the local
`tslc` package. It should not require NumPy, pandas, SciPy, scikit-learn, or a
plotting library for the MVP.

Raw JSONL, summary JSON, CSV, and Markdown are sufficient. Optional notebooks
or plotting can be added later without becoming the measurement authority.

### Target command surface

The proposed commands are:

```text
pipcost doctor
pipcost generate
pipcost build
pipcost check
pipcost run
pipcost summarize
pipcost fit
pipcost evaluate
```

These names describe target behavior; they do not exist yet.

#### `pipcost doctor`

- invoke `tslc doctor --backend cpp --format json`;
- record compiler and profile readiness;
- check that all requested runtime profiles are native to the current host;
- check required tools without installing them;
- report CPU affinity, frequency-governor visibility, and performance-counter
  availability without changing system settings;
- reject an unsupported target before executing a target-specific benchmark.

Emulation may verify correctness but must never supply performance evidence.

#### `pipcost generate`

- call `tslc.api.generate_project` for the selected C++ profiles and `si32`;
- request the query primitives needed by direct fused kernels;
- let the compiler-owned helper manifest close algorithm-helper roots;
- fail if required primitive/profile/type slots are skipped;
- write artifacts only to a configured `tslctmp/pipcost/generated/...` root;
- record the generated artifact digest manifest, compiler version, request,
  diagnostics, and relevant coverage entries.

The initial likely direct primitive roots are:

- `load`;
- `set1`;
- `less_than`;
- `mask_binary_and`;
- `select`;
- `hadd`.

This list must be confirmed by the capability inventory; it is not permission
to duplicate compiler dependency closure.

#### `pipcost build`

- configure CMake using the generated project as a local source directory;
- never fetch dependencies or generated archives from the network;
- select one generated TSL profile explicitly;
- select the C++ compiler explicitly;
- build under a unique `tslctmp/pipcost/build/<build-id>/` directory;
- export `compile_commands.json`;
- hash the final executable;
- record the compiler executable, version, target profile, build type, and
  effective command lines.

The CMake integration should adapt the local generated-project consumption
pattern in [`examples/cpp/CMakeLists.txt`](../examples/cpp/CMakeLists.txt) but
omit the URL/`FetchContent` network path.

#### `pipcost check`

- list the plans compiled into the binary;
- run C++ correctness tests;
- compare every supported plan with the scalar reference over the smoke cases;
- verify that unsupported plan/profile/width combinations are explicit;
- optionally capture disassembly for structural review;
- write no measurement policy.

#### `pipcost run`

- load one immutable experiment configuration;
- create a unique run directory;
- enumerate scenarios deterministically;
- query the binary's plan registry;
- preflight every plan/scenario pair;
- run warmups and paired raw trials;
- retain every raw sample;
- write run metadata and completion state last;
- never overwrite an existing completed run.

#### `pipcost summarize`

- validate the complete expected sample inventory;
- group samples by scenario and plan;
- calculate median, minimum, maximum, median absolute deviation, and selected
  percentile statistics;
- identify missing, failed, or noisy cells explicitly;
- produce a deterministic oracle table;
- never silently discard an outlier or failed sample.

#### `pipcost fit`

- consume only declared training scenarios;
- fit a versioned simple cost model;
- record training data identities and model parameters;
- refuse to train on held-out scenarios;
- write the model as deterministic JSON.

#### `pipcost evaluate`

- apply a fitted model to held-out scenarios;
- select one complete plan per scenario;
- compare the selected plan with the measured oracle and baselines;
- report top-1 accuracy, median regret, p95 regret, and worst-case regret;
- retain unsupported or missing decisions as failures or explicit gaps.

## C++ benchmark binary

### Plan isolation

Each plan has a separately named entry function. The plan boundary may be
`noinline` so the compiler cannot merge complete plans, while the loop inside
the plan remains fully optimizable.

Calling overhead is amortized over a sufficiently large timed workload and is
included consistently in every plan.

Plan implementations must not use virtual dispatch in the hot loop. The CLI
chooses the plan once before timing.

### Anti-optimization rules

- Input buffers and thresholds are runtime values.
- Every timed execution produces an aggregate result.
- The result participates in a process-visible checksum written to the raw
  record.
- Scratch buffers escape sufficiently to preserve intended materialization.
- Allocation, data generation, plan lookup, and record formatting occur
  outside the timed interval.
- The benchmark verifies that nominally materialized plans still contain the
  expected separate loops and memory traffic through disassembly and counters.

Disassembly evidence is a validation aid. The plan must not assert an exact
instruction sequence unless that sequence is itself a measured experimental
fact tied to a compiler/build identity.

### Timing

The initial timer is `std::chrono::steady_clock`. The runner calibrates an
inner iteration count so a sample lasts long enough to dominate timer and call
overhead.

For every scenario:

1. generate data;
2. calculate the scalar reference;
3. perform correctness executions;
4. warm every admitted plan;
5. execute plans in deterministic shuffled order within paired blocks;
6. record every elapsed sample and checksum.

An optional later x86 cycle counter may be added behind a separately tested
timer interface. It must handle serialization and migration correctly and
must not replace wall-clock evidence without validation.

### Scratch allocation

Before timing, allocate worst-case capacity for:

- native-mask chunks;
- integral-mask chunks;
- packed bits;
- `rows` 32-bit positions.

Batch plans reuse scratch. Complete-relation plans use the same allocation
contract with `batch_rows == rows`. No plan may gain an advantage by omitting
capacity management from its correctness or setup path while another includes
allocation in its timed path.

## Experiment configuration

### Configuration principles

- JSON is the initial human- and machine-readable input format.
- Every config has a schema version.
- Paths resolve relative to the config file or repository root explicitly.
- Unknown keys and invalid combinations fail.
- Scenario expansion is deterministic and produces a persisted scenario
  manifest before execution.
- A config may define several named, bounded studies; the default must not
  expand the complete A/B/D Cartesian product.

### Smoke configuration

The first smoke matrix should cover:

- rows: `0`, `1`, `7`, `8`, `15`, `16`, `1003`, and one larger value;
- combined selectivity: `0%`, approximately `50%`, and `100%`;
- pattern: random;
- batches: one partial batch, one ordinary batch, and full relation;
- one seed;
- one supported SIMD width;
- `fused_mask`, integral mask, packed bits, and 32-bit positions.

This is a correctness and workflow matrix, not performance evidence.

### Pilot studies

Do not begin with one giant cross product. Use staged studies:

1. **Representation sweep**
   - one working-set size;
   - one batch size;
   - one SIMD width;
   - dense selectivity sweep with extra points near the bitmap/position
     storage crossover.
2. **Batch sweep**
   - selectivities on both sides of observed crossovers;
   - several powers-of-two batch sizes plus complete relation.
3. **Working-set sweep**
   - fixed representative selectivities;
   - row counts spanning likely private-cache, LLC, and DRAM regimes.
4. **Locality sweep**
   - random and clustered qualifying positions at equal selectivity.
5. **Width sweep**
   - only after the selected profile proves legal fixed-width variants.

Cache-regime labels should be derived after recording the actual host cache
sizes and bytes touched. Row count remains the reproducible configuration
input.

### Training and held-out scenarios

Training and evaluation grids are declared before model evaluation.

For example:

- training selectivities: `1, 5, 10, 25, 50, 75, 95%`;
- held-out selectivities: `2, 7, 15, 35, 65, 85%`;
- at least one held-out row count;
- at least one held-out batch size;
- separate seeds for final validation.

The precise grid may change after the smoke phase, but it must be frozen before
the final pilot data are classified as training or held out.

## Evidence and record schema

### Identity layers

Every raw sample must be attributable to:

#### Prototype identity

- `pipcost` schema and version;
- deterministic manifest digest of files under `research/pipcost-src`;
- plan registry digest;
- experiment-config digest.

#### TSL identity

- `tslc` version;
- generation request;
- selected backend and machine profile;
- generated artifact digest manifest;
- required coverage and skip records.

#### Build identity

- compiler executable and version;
- target profile;
- build type;
- effective compile and link command lines;
- generated TSL root digest;
- benchmark executable SHA-256.

#### Host identity

- operating system and kernel;
- CPU vendor, family, model, stepping, and model name;
- visible CPU feature flags;
- online CPU count;
- cache sizes;
- selected CPU affinity;
- NUMA node where observable;
- frequency governor and current frequency where observable;
- whether virtualization is detected;
- performance-counter availability.

The tool observes and records these facts. It does not change the governor,
disable turbo, change kernel settings, reserve huge pages, or mutate global
system configuration.

#### Scenario identity

- logical query version;
- generator version;
- row count;
- requested and observed selectivities;
- pattern and pattern parameters;
- seed;
- batch size;
- SIMD width policy.

#### Sample identity

- stable run ID;
- scenario ID;
- plan ID;
- paired block and repetition;
- plan order within the block;
- inner iteration count;
- elapsed nanoseconds;
- rows processed;
- checksum;
- status and structured skip/failure reason.

### File publication order

Each run directory contains:

```text
run.json
host.json
build.json
scenarios.json
plans.json
samples.jsonl
summary.json
oracle.json
COMPLETE
```

`COMPLETE` is written last. Summarization rejects an incomplete run unless the
caller explicitly requests diagnostic recovery.

Raw samples are append-only within a new run directory. Derived summaries,
models, and evaluations must name the exact raw-run digests they consume.

## Cost-model prototype

### Model 0: measured oracle

Before fitting anything, calculate the best measured median plan for every
complete scenario. Ties use a declared tolerance and deterministic plan-ID
ordering.

The oracle is not a deployable policy. It is the upper bound against which
policies are evaluated.

### Model 1: fixed policies

Evaluate:

- always fused;
- always integral masks;
- always packed bits;
- always positions;
- one manually declared selectivity threshold.

These baselines determine whether a cost model is necessary.

### Model 2: lookup and interpolation

The first learned model is deliberately transparent:

- categorical partition by profile, SIMD width, representation family, and
  position pattern;
- ordered coordinates for row count, batch size, and observed selectivity;
- exact lookup where a training point exists;
- bounded interpolation between neighboring selectivity points within the
  same categorical context;
- explicit unsupported result rather than unbounded extrapolation.

The model predicts one cost for every legal complete plan, then selects the
minimum.

It must serialize as deterministic JSON and expose the training points and
interpolation decision used for every prediction.

### No dynamic programming in the first family

The first query family enumerates a small set of complete plans. Selecting the
minimum predicted complete-plan cost is sufficient. Adding a generic pipeline
IR and dynamic-programming optimizer at this point would be speculative
plumbing.

Dynamic programming becomes justified only after the filter-cascade extension
introduces independent per-edge representation choices and transitions.

### Later compositional model

If complete-plan interpolation succeeds, investigate an interpretable
component model:

```text
cost =
    dense predicate scan
  + representation production
  + bytes materialized
  + representation reload or enumeration
  + selected consumer work
  + per-batch overhead
```

The component model should be accepted only if it predicts held-out complete
pipelines. Good fits to isolated component measurements are insufficient.

## Filter-cascade extension

This extension begins only after the initial scientific gate passes.

### New physical alternatives

- keep an integral or packed mask after `Filter(a)`, refine it with
  `Filter(b)`, then masked-aggregate `c`;
- emit positions after `Filter(a)`, refine them over `b`, then aggregate
  selected `c`;
- keep everything fused;
- convert mask to positions between the two filters;
- optionally retain a native predicate within a batch.

### Typed downstream pipeline model

Introduce only the vocabulary needed for the fixed linear pipeline:

- `Filter`;
- `Sum`;
- `Representation`;
- `Recipe`;
- `PipelineEdge`;
- `Plan`.

A recipe declares:

- required input representation;
- output representation;
- whether it materializes;
- supported plan/profile/width identities;
- its measured cost key.

For a linear pipeline, dynamic programming retains the cheapest path to every
legal output representation after each operator.

Correctness remains owned by end-to-end scalar comparison. The planner does
not synthesize arbitrary target code or infer primitive semantics.

### Density-adaptive extension

Only after the static cascade planner works:

1. process one batch's first predicate;
2. observe its exact active count;
3. ask the model whether to retain a mask or emit positions for the remaining
   operators;
4. include conversion and switching costs;
5. compare with the per-batch measured oracle and static plans.

This extension is a separate research slice, not part of the MVP acceptance
criteria.

## Implementation slices

Each slice delivers one observable behavior and keeps generated output in
`tslctmp/pipcost`.

### Slice 0: downstream scaffold and contract

Create:

- `research/pipcost-src/CHARTER.md`;
- `research/pipcost-src/AGENTS.md`;
- `research/pipcost-src/README.md`;
- minimal `pyproject.toml`;
- `src/pipcost/__init__.py`, `__main__.py`, and `cli.py`;
- a focused Python test directory.

Deliver:

- `pipcost --help`;
- configured scratch-root validation;
- no import-time compiler registration or filesystem writes.

Validation:

- import `tslc`, snapshot registered backends/defaults, import `pipcost`, and
  prove the snapshot is unchanged;
- prove all tool writes resolve below the configured
  `tslctmp/pipcost` root;
- run Python compile and focused tests.

### Slice 1: capability inventory and generated TSL project

Implement `pipcost doctor` and `pipcost generate`.

Deliver:

- machine-readable toolchain/profile report;
- one generated C++ TSL project under scratch;
- exact artifact digest manifest;
- required primitive/profile/type coverage report;
- explicit failure on required skips.

Validation:

- generate the smallest useful `si32`/C++/profile set;
- verify the public algorithm header is admitted;
- build-verify the generated TSL project using compiler-owned verification;
- prove no file below `tslc/` or `tsldata/` changes.

Stop if fewer than the fused, integral-mask, packed-bit, and position
constituent operations are available and correct on one native profile.

### Slice 2: C++ data generator and scalar reference

Create the benchmark CMake target, deterministic input generator, fixed query,
and scalar reference.

Deliver:

- `pipcost-bench --self-test`;
- exact selectivity and pattern generation;
- JSON description of observed input properties;
- tail and boundary correctness tests.

Validation:

- CTest over the complete correctness edge matrix;
- cross-check generated observed selectivities in Python;
- repeat generation with the same seed and compare hashes.

### Slice 3: fused-mask plan

Implement one direct TSL fused pipeline.

Deliver:

- stable plan registry;
- `fused_mask` for one selected SIMD realization;
- exact scalar-reference agreement;
- plan listing in JSON.

Validation:

- zero, full, and intermediate selectivity;
- all tail cases;
- disassembly review proving one fused hot loop and no materialized
  active-set buffer;
- checksum remains observable.

### Slice 4: materialized mask plans

Implement integral and packed-bit batch-local plans, then complete-relation
endpoints. Add native-mask storage only when supported.

Deliver:

- batch scratch allocation outside timing;
- `batch_integral_mask`;
- `batch_bitmask`;
- full endpoints through `batch_rows == rows`;
- optional native-mask plan with an explicit capability result.

Validation:

- compare every layout and batch size with the scalar result;
- canary scratch bounds;
- verify the materialized loops remain distinct in optimized code;
- verify scratch is reused and never allocated in the timed plan body.

### Slice 5: position-list plans

Implement 32-bit position production and selected aggregation.

Deliver:

- `batch_positions_u32`;
- `full_positions_u32`;
- produced-count and ordering checks;
- explicit capacity contract.

Validation:

- exact produced positions for small cases;
- scalar aggregate agreement;
- random and clustered positions;
- 0% and 100% output;
- partial batches and relation sizes above one batch.

### Slice 6: raw measurement harness and provenance

Implement calibrated timing, paired plan ordering, and raw JSONL output.

Deliver:

- immutable run directories;
- host, build, generated-artifact, scenario, and plan manifests;
- complete expected sample inventory;
- completion marker written last.

Validation:

- inject a fake timer for deterministic unit tests;
- detect missing, duplicate, and foreign samples;
- prove plan order is deterministic for a given run seed;
- prove data generation and allocation are outside timed intervals;
- run a small explicit native smoke measurement.

### Scientific Gate A: does a plan space exist?

Run the bounded representation pilot before implementing a cost model.

Proceed only if:

- at least two different plans win in repeatable regions, or a fixed policy
  has a predeclared materially nonzero regret;
- plan rankings are stable across repeated runs and seeds;
- differences exceed observed timing noise;
- the observed effects can be related to representation bytes, selected work,
  batching, or memory behavior.

The pilot should preregister a materiality threshold before final collection.
A reasonable starting proposal is a 5% slowdown relative to the oracle, but it
must be finalized before inspecting held-out results.

If Gate A fails, publish the phase diagram and negative conclusion as the
prototype result. Do not add an optimizer to manufacture complexity.

### Slice 7: reduction, summaries, and measured oracle

Implement deterministic inventory validation and summary derivation.

Deliver:

- summary JSON/CSV;
- oracle table;
- fixed-policy regret report;
- noise and missing-cell report.

Validation:

- golden small raw datasets;
- permutation-invariant reduction;
- deterministic tie handling;
- incomplete-run rejection;
- all summaries name raw-run digests.

### Slice 8: lookup cost model and complete-plan selector

Implement training/held-out separation, bounded interpolation, and evaluation.

Deliver:

- deterministic model JSON;
- prediction explanation;
- chosen plan for each held-out scenario;
- accuracy and regret report;
- comparison with all fixed baselines and a manual threshold.

Validation:

- no held-out record enters fitting;
- exact training-point predictions;
- bounded interpolation tests;
- extrapolation produces an explicit unsupported decision;
- deterministic model serialization;
- oracle and regret calculations checked by hand-sized fixtures.

### Scientific Gate B: is a model justified?

Proceed to the cascade planner only if:

- the model materially improves over the best fixed policy;
- held-out median, p95, and worst-case regret meet preregistered bounds;
- calibration uses substantially fewer points than exhaustive enumeration;
- prediction explanations correspond to observed crossover behavior.

If a single threshold matches the model, prefer and report the threshold.

### Slice 9: true filter cascade and transition plans

Add first-filter representation choices, position refinement, mask refinement,
and per-edge transition identities.

Deliver:

- explicit filter-cascade plans;
- conditional-selectivity scenarios;
- end-to-end correctness;
- transition-cost measurements.

Do not add dynamic programming in the same slice.

### Slice 10: typed linear planner

Add the minimal typed pipeline/recipe model and dynamic-programming search.

Deliver:

- plan enumeration from legal recipes;
- deterministic cheapest path per edge representation;
- comparison with exhaustive complete-plan enumeration.

Validation:

- small hand-computed plan lattices;
- illegal transition rejection;
- deterministic tie breaking;
- exhaustive-equivalence tests.

### Slice 11: portability study

After the planner works:

- add supported 128-, 256-, and 512-bit variants;
- add another x86 profile/microarchitecture;
- compare GCC and Clang for native-intrinsic plans;
- compare native intrinsics and Clang vector overlays under Clang.

Treat unsupported combinations as structured gaps. Do not infer a compiler
main effect from the intentionally unbalanced Clang-vector matrix.

### Explicitly later

The following require separate plans:

- density-adaptive runtime switching;
- multiple workers and NUMA;
- controlled compute/memory interference;
- Rust parity;
- database-engine integration;
- TPC-H or SSB end-to-end evaluation.

## Planned validation commands

Commands below describe the intended implementation workflow. They are not run
as part of writing this plan.

### Python

```bash
python -m compileall -q research/pipcost-src/src/pipcost
PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pytest -q \
  --basetemp=tslctmp/pipcost/pytest \
  research/pipcost-src/tests
```

Add mypy once the package has substantive typed modules:

```bash
MYPYPATH=tslc/src:research/pipcost-src/src \
  python -m mypy research/pipcost-src/src/pipcost
```

### Generated TSL and C++

Exact commands will be owned by `pipcost` and its local `AGENTS.md`, but the
underlying checks are:

```bash
PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost doctor --profile avx2

PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost generate --profile avx2

PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost build --profile avx2 --compiler clang++

PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost check --profile avx2
```

The generated project and build paths must be printed and remain below
`tslctmp/pipcost`.

### Measurement smoke

```bash
PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost run \
  --config research/pipcost-src/configs/smoke.json

PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost summarize --run <run-id>
```

### Repository hygiene

```bash
git diff --check
```

No default validation command should run a long performance study.
Hardware-dependent runs must be explicit and report unavailable profiles or
counters rather than silently substituting emulation.

## Main risks and design responses

### Risk: the compiler collapses nominally different plans

**Response:** isolate plan entry points, preserve materialization through
observable scratch, review optimized disassembly, and record machine-code
identity. Do not count two source plans as separate evidence if they compile to
the same relevant loop.

### Risk: the helper abstraction dominates the comparison

**Response:** use the generated public helper API consistently for materialized
plans and direct TSL primitives only for the necessarily fused plan. Add a
controlled direct-loop comparison later if helper overhead appears in profiles.

### Risk: position-list and mask plans perform unequal logical work

**Response:** the first family evaluates the same combined predicate densely
for every plan and differs only at the aggregate boundary. Early predicate
avoidance belongs to the separately evaluated cascade extension.

### Risk: cache labels are guessed

**Response:** configure explicit row counts and record actual cache sizes and
bytes touched. Assign cache-regime interpretations during analysis.

### Risk: an unsupported profile is executed

**Response:** `doctor` and a native host-feature preflight must pass before
execution. SDE/QEMU results are correctness-only and never performance data.

### Risk: measurement noise creates false crossovers

**Response:** pin the process where permitted, record rather than mutate host
state, use paired randomized blocks, retain raw samples, repeat across seeds
and runs, and require effects to exceed a preregistered noise/materiality
threshold.

### Risk: the prototype becomes a general query compiler

**Response:** keep one fixed query and explicit complete plans through Gate B.
Add only the small `Filter`/`Sum`/representation vocabulary required for the
cascade after evidence justifies global search.

### Risk: the project becomes a benchmark matrix without insight

**Response:** use staged studies, explain crossover mechanisms, evaluate
decision regret, and stop when a simple fixed policy or threshold suffices.

### Risk: full recalibration is required for every build

**Response:** measure calibration cost and hold out compilers, widths, row
counts, and eventually machines. If the model cannot transfer with modest
calibration, characterize it honestly as build-local autotuning.

### Risk: current TSL coverage is incomplete

**Response:** make Slice 1 a hard inventory gate. Unsupported operations remain
structured gaps. A missing prototype capability does not automatically justify
a compiler or `tsldata` change.

## MVP completion criteria

The implementation prototype is complete when:

1. all source code, tests, configs, and local documentation live under
   `research/pipcost-src`;
2. all generated/build/runtime output lives under `tslctmp/pipcost`;
3. one native x86 profile builds and runs;
4. the scalar reference and at least four complete plan families agree over
   the correctness matrix;
5. fused, integral-mask, packed-bit, and 32-bit-position plans are represented;
6. batch-local and complete-relation endpoints execute;
7. raw samples carry complete scenario, plan, TSL, build, binary, and host
   identity;
8. summaries and the measured oracle are reproducible from raw records;
9. fixed policies are evaluated;
10. Gate A is decided explicitly;
11. if Gate A passes, the lookup/interpolation model is evaluated on frozen
    held-out scenarios;
12. Gate B is decided explicitly;
13. no `tslc`, `tsldata`, compiler registry, generated default, or ordinary
    generated artifact behavior changes for the prototype.

The MVP does not require dynamic programming, runtime adaptation, multiple
workers, stress workloads, Rust, or database-engine integration.

## Publication transition

The prototype alone is seed evidence, not automatically a paper.

If Gates A and B pass, the strongest next research unit is:

> A representation-aware filter-cascade planner that jointly chooses active-set
> representation and materialization boundaries, uses exact batch-local density
> where available, and achieves low regret across held-out workloads and x86
> SIMD realizations.

A credible database publication would still need:

- a true multi-edge cascade or broader pipeline space;
- comparison with fixed, threshold, local, and oracle policies;
- multiple x86 microarchitectures;
- cardinality-error and data-skew analysis;
- an actual database or research-engine integration;
- end-to-end workload evidence;
- a complete related-work and novelty analysis.

If the prototype shows that one representation or one threshold is sufficient,
the correct outcome is a negative result and a decision not to build the
larger optimizer.
