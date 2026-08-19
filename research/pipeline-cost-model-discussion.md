# Pipeline cost-model discussion

## Purpose

This note records and reconciles two parts of the discussion around
[`pipeline-cost-model-idea.md`](pipeline-cost-model-idea.md):

1. the proposed mental model for exploring SIMD-aware columnar query
   pipelines; and
2. the critical requirements that would later turn that mental model into a
   defensible experiment or research contribution.

The proposal was initially interpreted too narrowly as a nearly final
experimental design. That was not its intended role. As a conceptual map, the
proposed decomposition into intermediate format, processing model, and
execution context is useful and points in the right direction.

## Elevator pitch

> Use TSL to generate controlled, semantically equivalent realizations of
> database pipelines with different active-row representations and execution
> granularities. Study how workload, hardware, compiler, and resource
> conditions change the best realization, and determine whether those changes
> can be explained and predicted.

TSL does not currently provide the database pipeline optimizer or its cost
model. Its value is as a target-aware implementation and generation substrate
that makes the physical alternatives easier to construct, verify, and compare
without maintaining a separate hand-written implementation for every ISA,
vector width, compiler approach, and language.

## The mental model

The proposed design space can be understood as four layers:

```text
Logical query
Filter -> Filter -> Aggregate
        |
        v
Database execution choices
A: How is the active row set represented?
B: How far does each invocation move through the pipeline?
        |
        v
SIMD realization supplied by TSL
ISA, SIMD width, native implementation, compiler-vector implementation
        |
        v
Execution context
data size, selectivity, worker count, system pressure
```

This leads to a natural research process:

1. Express one logical pipeline.
2. Construct semantically equivalent physical variants for combinations of
   the A and B choices.
3. Use TSL implementations for the architecture-specific operations within
   each physical variant.
4. Execute those variants under selected D conditions.
5. identify and explain crossover points.
6. Construct a cost model or adaptive policy only after establishing that
   meaningful, repeatable crossovers exist.

The decomposition is therefore a good starting point. It separates the
database decision from its SIMD realization and from the context that affects
its cost.

## A. Active-row representation

The original three alternatives capture an important database execution
choice:

- **A1: native masks**: keep activity in the target's native mask type, which
  may be a compact predicate or an all-bits-zero/all-bits-one vector.
- **A2: integral masks**: call `to_integral` and represent the active lanes in
  an ordinary integral mask.
- **A3: position lists**: materialize the row identifiers of qualifying
  elements.

Two clarifications make this model more precise.

### A0: no materialized intermediate

The most important additional case for a simple filter-and-aggregate pipeline
is:

- **A0: transient register mask**: produce the native predicate and consume it
  immediately in a fused subsequent filter, masked load, or aggregation
  without storing it.

This separates a native mask used as an ephemeral register value from a native
mask materialized as an array. Their costs and meanings are very different.

### Integral mask chunks versus a packed bitmap

It is useful to distinguish:

- one integral mask value per SIMD chunk; and
- a densely packed bitmap over a batch or relation.

They can coincide, but that is not automatic. The physical contract must state
the scope of each mask, lane order, unused bits, storage type, and whether
adjacent chunks form a dense bitstream.

This suggests the following slightly expanded representation vocabulary:

- **A0**: transient native mask, no materialization;
- **A1**: materialized native-mask chunks;
- **A2a**: materialized integral-mask chunks;
- **A2b**: packed batch or relation bitmap;
- **A3**: position list;
- **A4, later**: compacted value stream.

Compacted values are a plausible later alternative when substantial
downstream processing can operate densely. They are not necessary for the
first experiment.

### Why native masks are especially interesting

“Native mask” is not one uniform storage format. For 16 32-bit lanes, a compact
AVX-512 predicate can occupy roughly two bytes, whereas an all-bits-per-lane
512-bit vector mask can occupy 64 bytes. Thus, materializing a supposedly
equivalent native mask can have a radically different memory footprint across
SIMD representations.

This is one of the strongest reasons TSL is relevant: it knows the concrete
target representation while allowing the database experiment to refer to the
same logical predicate.

### A useful analytical intuition

For an ideal packed bitmap and 32-bit positions:

```text
packed bitmap:  1 bit per input row
position list: 32 bits per selected row

equal output size at selectivity = 1 / 32 = 3.125%
```

For 64-bit positions, the corresponding point is 1.5625%. These are only
storage break-even points. The performance crossover can be very different
because a position list can avoid downstream work but introduces index
creation, indirect loads, gathers, and potentially poor locality.

The position-list contract must eventually state:

- 16-, 32-, or 64-bit row identifiers;
- batch-relative or relation-global positions;
- ordering guarantees;
- whether output is shared or worker-local;
- how later consumers load the selected rows.

## B. Processing model

The original processing alternatives are useful endpoints:

- **B1: operator at a time**: execute an operator over the complete input and
  materialize its complete result before the next operator begins.
- **B2: batch at a time**: process a bounded partition through the relevant
  operators before moving to the next partition.
- **B3: tuple at a time**: move individual elements through the pipeline.

For the initial mental model, this is sufficient. For a later optimizer, B
should be separated into several related but orthogonal decisions.

### Materialization and fusion boundaries

The optimizer must decide after which operators an intermediate is written.
A fully fused pipeline can keep its predicate in registers. A staged pipeline
can materialize after the first filter but fuse the second filter with the
aggregate. Full operator-at-a-time execution places a boundary after every
operator.

### Batch size

Batch-at-a-time is a continuum:

```text
complete relation <- large batches <- small batches <- fully fused execution
```

The batch size controls:

- whether intermediates remain cache-resident;
- interpretation or call overhead;
- how much work can be amortized;
- position-list and bitmap scope;
- register pressure and fusion opportunities.

### Tuple-at-a-time is not synonymous with scalar

A compiled, data-centric pipeline can be fully fused while still using SIMD
vectors internally. The important property is that results move directly
through the remaining operators without a memory-resident intermediate.
Scalar execution should be retained as a baseline, but it is a separate choice
from pipeline fusion.

### Morsel size is separate

A morsel is a unit of work scheduled to a worker. A worker may run a fully
fused or batch-oriented pipeline over that morsel. Consequently:

- batch size controls intermediate execution granularity;
- morsel size controls parallel scheduling granularity;
- SIMD width controls register-level parallelism.

Conflating these would make it difficult to attribute a performance effect to
the correct mechanism.

### A and B interact

The representation and processing-model choices are not independent.

A small batch-local position list may remain in cache and use relative
positions. A relation-sized position list may require large global indexes and
additional memory traffic. A native mask can be nearly free inside a fused
stage but expensive when stored across the complete relation.

Therefore, a later planner should choose a representation on each pipeline
edge together with the placement of materialization boundaries.

Example plans include:

```text
Filter 1
  -> transient native mask
Filter 2
  -> transient native mask
Aggregate
```

```text
Filter 1
  -> batch-local integral masks
Filter 2
  -> retained integral masks
Aggregate
```

```text
Filter 1
  -> position list
Filter 2
  -> refined position list
Aggregate selected rows
```

## D. Context and experimental dimensions

The proposed dimensions answer the correct conceptual question:

> Which conditions could change the best A/B choice?

They become easier to reason about when grouped by role.

| Role | Dimensions |
|---|---|
| Physical decisions | representation per edge, materialization boundaries, batch size, SIMD recipe and width |
| Workload properties | working-set size, per-filter selectivity, correlation, selected-position locality, predicate cost, downstream reuse |
| Build and platform context | CPU profile, ISA, compiler, intrinsic versus compiler-vector implementation |
| Runtime resource state | available workers, memory-bandwidth pressure, compute pressure, cache contention, NUMA placement |

### D1: data size

Data size is essential, but the useful quantity is the complete working set
relative to the cache hierarchy:

- bytes read from every predicate and aggregate column;
- bytes written and reread for intermediates;
- whether working state fits in L2, LLC, or only DRAM;
- whether the experiment assumes warm or cold data.

Row count alone is insufficient because the same number of rows can touch
different numbers and widths of columns.

### D2: selectivity

Selectivity is central, but a multi-filter pipeline needs more than one final
percentage:

- selectivity of the first predicate;
- conditional selectivity of the second predicate given the first;
- correlation between predicates;
- random, clustered, or run-like positions of qualifying rows.

Two batches can have the same selectivity but very different position-list
costs if one produces long contiguous runs and the other produces random
positions.

Predicate ordering may later become another optimizer decision, but it should
initially be held fixed.

### D3: worker count

Worker count is relevant, especially because representations have different
parallelization costs:

- masks and bitmaps can usually be written into predetermined disjoint ranges;
- a global position list needs per-worker buffers, prefix sums, or a merge;
- aggregates need worker-local state followed by reduction;
- memory bandwidth may saturate before all cores are used;
- NUMA placement can dominate at higher worker counts.

This is a valuable later dimension, but it should not obscure the first
single-thread representation study.

The research objective must also be explicit: minimizing the latency of one
query, maximizing system throughput, or minimizing resource consumption can
lead to different worker-count decisions.

### D4 and D6: ISA and SIMD width

These are related rather than fully independent. AVX2 versus AVX-512 changes
more than register width:

- mask representation;
- available compress, expand, gather, and masked operations;
- instruction throughput and port pressure;
- generated remainder handling;
- potentially frequency and thermal behavior.

The initial x86 focus is reasonable. Testing 256- and 512-bit realizations on a
machine supporting both provides a useful controlled first comparison, but a
credible portability claim eventually needs multiple x86 microarchitectures.

### D5 and D7: implementation family and compiler

Native intrinsics versus Clang vector builtins is an interesting
performance-portability question, but it is secondary to the database
representation decision.

The comparison matrix is necessarily unbalanced:

- native-intrinsic code can be compiled with GCC and Clang;
- Clang vector extensions can only be tested with Clang.

The sound comparisons are therefore:

1. GCC versus Clang for the same native-intrinsic realization; and
2. native intrinsics versus Clang vectors under Clang.

These variables should initially be used to test whether the discovered model
is robust, rather than multiplying every cell of the primary experiment.

### D8: system pressure

Compute and memory pressure are promising later dimensions, particularly for
runtime adaptation. The four informal quadrants are a useful mental model, but
an experiment would need reproducible and measurable definitions:

- a controlled co-running workload;
- cores assigned to the query and stressor;
- achieved memory bandwidth;
- LLC occupancy and misses;
- CPU frequency;
- NUMA placement;
- repeated measurements of variability.

Combining worker count and system pressure expands the project into
resource-aware query execution or scheduling. That could support a later
research contribution, but it should not be part of the first experiment.

## What TSL contributes

TSL is not valuable because masks, bitmaps, position lists, SIMD widths, or
batch execution are themselves new. Its potential value is experimental and
methodological:

- one abstract primitive vocabulary across target profiles;
- target-specific native mask knowledge;
- explicit native and integral mask conversions;
- selection-vector production and consumption;
- masked and selected aggregation;
- fixed and native SIMD widths;
- native-intrinsic and Clang-vector realizations;
- C++ and Rust backends;
- generated correctness tests;
- deterministic implementation and dependency identities.

Static repository inspection shows that several required execution paths
already exist:

- C++ selection-vector production, selected refinement, selected aggregation,
  and masked aggregation in
  [`tsl_algorithm.hpp`](../tslc/src/tslc/backend/assets/tsl_algorithm.hpp);
- corresponding Rust paths in
  [`tsl_algorithm.rs`](../tslc/src/tslc/backend/assets/tsl_algorithm.rs);
- native, integral, packed-bit, and byte mask-layout support in the algorithm
  assets;
- Clang fixed-width vector overlays documented in
  [`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md).

No pipeline-level performance claim follows from the existence of these
helpers. They only lower the cost of constructing the first controlled
experiment. Their generated behavior and machine code still require
verification in the eventual benchmark.

TSL also does not currently generate an arbitrary database pipeline or select
its physical plan. A downstream research tool or database integration must own:

- the logical pipeline;
- physical representations;
- operator recipes;
- generated pipeline variants;
- measurements;
- cost estimation;
- plan search and runtime adaptation.

That tool should consume `tslc` facts in one direction. Database planning
semantics and measured policies should not become ordinary compiler or
`tsldata` semantics.

## The right initial pipeline

A simple pipeline is appropriate:

```sql
SELECT SUM(c)
FROM t
WHERE a < p1 AND b > p2;
```

Using separate columns for `a`, `b`, and `c` forces the physical plans to make
real decisions about accessing downstream data.

Starting only with `COUNT(*)` would be less informative. A fused implementation
can count mask bits without ever materializing or consuming the proposed
intermediate representations.

A useful second case is:

```sql
SELECT SUM(c), SUM(d)
FROM t
WHERE a < p1 AND b > p2;
```

This introduces reuse. Materializing positions or a bitmap may become
worthwhile when several downstream consumers reuse the same active set. It
directly tests the global hypothesis:

> The best representation depends on the remaining pipeline, not only on the
> filter that produced it.

## From mental model to research programme

### Stage 1: establish that a meaningful choice exists

Construct a few complete physical implementations:

- fully fused transient masks;
- batch-local integral masks or bitmaps;
- batch-local position lists;
- full-materialization variants.

Measure them over selected data sizes, selectivities, and batch sizes. The
first result should be an oracle phase diagram showing which complete plan wins
under which conditions.

This is a falsification stage. If one strategy dominates or one simple
threshold is always close to the oracle, a larger optimizer is not justified.

### Stage 2: explain the crossover points

Relate the observed winners to:

- intermediate bytes written and reread;
- downstream rows avoided;
- contiguous loads versus indirect loads and gathers;
- native-to-integral conversion costs;
- cache and TLB behavior;
- memory-bandwidth saturation;
- batch-local reuse;
- SIMD width and mask representation.

This stage is what turns a benchmark table into scientific insight.

### Stage 3: construct the cost model

A simple initial model is preferable:

```text
cost(plan) =
    sum(stage-kernel costs)
  + sum(conversion + materialization + reload costs)
  + parallel scheduling and reduction costs
```

For a linear pipeline, a dynamic program can track the cheapest known plan for
each active-set representation at every operator boundary.

The model should be evaluated primarily by decision quality:

- regret relative to the exhaustively measured oracle;
- worst-case slowdown;
- frequency of selecting the correct or near-correct plan;
- number of calibration measurements required;
- robustness to selectivity-estimation error.

Prediction RMSE alone is not sufficient if small numerical errors select an
expensive plan.

### Stage 4: test portability

After a model works on the initial configuration, investigate:

- AVX2 versus AVX-512;
- 128-, 256-, and 512-bit realizations where meaningful;
- GCC and Clang;
- native intrinsics and Clang vectors;
- additional x86 microarchitectures.

The thresholds are expected to change. A stronger result is that the same
model structure transfers with a small amount of per-machine calibration.

If every machine or compiler requires exhaustive measurement of every plan,
the result is mainly an autotuning artifact rather than a general cost model.

### Stage 5: runtime adaptation

A promising stronger direction is **density-adaptive active-set execution**:

1. A filter naturally produces a native mask.
2. The executor observes the exact number of active lanes in the current
   batch.
3. Based on the remaining pipeline and target-calibrated costs, it decides to:
   - retain predication;
   - convert to an integral bitmap;
   - emit positions;
   - later, compact values.
4. Different batches may choose different representations when data is skewed.

This avoids depending exclusively on a global selectivity estimate. It also
turns the cost model into an observable execution decision rather than a static
benchmark lookup.

Worker availability and resource pressure can later become additional runtime
inputs, with switching costs and hysteresis included explicitly.

## A deliberately small first experiment

The first experiment should avoid the full Cartesian product.

### Fixed initially

- one 32-bit integer type;
- one generated backend;
- one compiler;
- one x86 machine;
- single-threaded execution;
- no external stress;
- fixed predicate order.

### Physical plans

1. Fully fused native masks with no materialized intermediate.
2. Batch-local integral masks or packed bitmaps.
3. Batch-local position lists.
4. Optionally, complete-relation materialization for comparison.

### Primary dimensions

- working sets representing L2, LLC, and DRAM regimes;
- first-filter selectivity;
- conditional second-filter selectivity;
- independent versus correlated predicates;
- random versus clustered qualifying positions;
- several batch sizes;
- 256- versus 512-bit execution where supported.

### Metrics

- end-to-end cycles per input row;
- bytes read, written, and materialized;
- cache and TLB misses;
- achieved memory bandwidth;
- instructions and branches;
- generated code size;
- compile time as a secondary metric;
- repeated raw samples and confidence intervals.

The generated machine code must also be inspected. An optimizing compiler may
eliminate a supposedly materialized intermediate or fuse two nominally
different strategies. TSL specialization identity proves which source recipe
was selected; it does not prove that two recipes remain different machine-code
plans.

### Baselines

- always fused/native masks;
- always integral masks or bitmaps;
- always position lists;
- one manually chosen selectivity threshold;
- greedy local decisions;
- pipeline-aware cost model;
- exhaustive measured oracle.

### Stop conditions

The broader optimizer should be reconsidered if:

- one physical strategy dominates the meaningful space;
- a single threshold stays close to the oracle;
- apparent crossovers are not repeatable;
- compiler noise dominates the database variables;
- complete-pipeline measurements cannot be predicted better than trivial
  policies;
- the required calibration is essentially exhaustive.

Negative results at this stage are valuable because they prevent a large
engineering project without a defensible research claim.

## Novelty and related-work risk

The individual ingredients are established:

- [MonetDB/X100](https://www.cidrdb.org/cidr2005/papers/P19.pdf) established
  cache-conscious vectorized or batch-at-a-time query processing.
- [Everything You Always Wanted to Know About Compiled and Vectorized Queries
  But Were Afraid to Ask](https://www.vldb.org/pvldb/vol11/p2209-kersten.pdf)
  compared compiled and vectorized execution, including vector-size and SIMD
  effects.
- [Rethinking SIMD Vectorization for In-Memory
  Databases](https://www.cs.columbia.edu/~orestis/sigmod15.pdf) studied SIMD
  database operators, including selections and indexed memory access.
- [Relaxed Operator
  Fusion](https://www.vldb.org/pvldb/vol11/p1-menon.pdf) is a particularly
  important comparison for staging and materialization boundaries.
- [Micro Adaptivity in
  VectorWise](https://doi.org/10.1145/2463676.2465292) is a strong novelty
  threat to a generic claim about automatically selecting implementation
  variants based on hardware, compiler, data, and changing conditions.
- [Morsel-Driven
  Parallelism](https://db.in.tum.de/~leis/papers/morsels.pdf) establishes the
  distinction between worker scheduling units and internal pipeline execution.

Therefore, the contribution cannot be:

- masks, bitmaps, or position lists are new;
- batch-at-a-time execution is new;
- SIMD-aware database execution is new;
- generating multiple implementation variants is new;
- online selection among low-level variants is new.

The potentially defensible contribution is their joint treatment:

> ISA-dependent active-set representations, representation conversions, and
> fusion/materialization boundaries should be planned together because their
> transition costs and downstream effects make fixed or local policies
> systematically suboptimal.

A stronger runtime version is:

> Exact batch-local density and remaining-pipeline costs can guide adaptive
> active-set representation changes with low regret relative to an oracle,
> despite data skew and architecture-specific mask semantics.

These are plausible research claims, not established novelty claims. A complete
literature review is still required before publication.

## What would constitute a publication

A phase diagram from one machine is useful seed evidence but is unlikely to be
a top-tier database paper by itself.

A stronger paper would require:

- a clearly specified physical plan space;
- an interpretable cost model or adaptive policy;
- exhaustive-oracle comparisons in the bounded space;
- evidence that local and fixed policies fail in meaningful regions;
- evaluation across multiple x86 microarchitectures;
- sensitivity to selectivity errors and data skew;
- a real database-engine or research-engine integration;
- end-to-end workload results;
- reproducible code generation and measurement evidence.

TSL would be the enabling artifact and experimental substrate. The scientific
contribution would be the representation-aware database execution model,
planner, and resulting empirical insight.

## Final assessment

As a mental model, the proposed A/B/D decomposition is neither boring nor
misguided. It identifies the correct components:

- **A** describes how the active row set crosses operator boundaries.
- **B** describes how aggressively the pipeline is fused or staged.
- **D** describes the workload, hardware, build, and runtime conditions that
  may change the best A/B choice.
- **TSL** supplies controlled target-specific realizations of the constituent
  operations.

The immediate goal should not be to implement a large optimizer. It should be
to construct three or four semantically equivalent complete pipelines and
determine whether stable, explainable crossover regions actually exist.

If they exist and simple policies fail, the next compelling direction is a
pipeline-aware or density-adaptive active-set optimizer. If they do not, the
negative result shows that a more elaborate optimizer is not justified.
