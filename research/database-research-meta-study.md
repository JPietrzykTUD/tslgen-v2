# Database-systems research directions enabled by TSL

Assessment date: 2026-08-07

## Executive decision

The most promising role for `tslc` and `tsldata` is not to be the research
question. They should be the experimental instrument that makes a database
question answerable under controlled changes of ISA, vector width, mask model,
implementation strategy, compiler, and language.

The current bitmask-versus-position-list study should not be the main paper.
Its latest results suggest that a very simple policy is already close to the
scenario oracle, and prior database work has directly studied bitmap and
selection-vector choices. The prototype remains useful as a benchmark and as
evidence that TSL can generate controlled alternatives, but the evidence does
not currently justify a cost-model contribution.

Apache Parquet and Arrow do offer a stronger direction. The best concrete
question found in this review is:

> **Do standard, interoperable Parquet encodings impose a
> vector-length-dependent decode tax on scalable-vector processors, and can a
> reader remain near-optimal across SVE and RVV without changing the file
> format?**

This is not the already crowded question “can SIMD accelerate Parquet
decoding?” It holds the Parquet bytes and logical decode semantics fixed and
varies the hardware vector model and the decoder's staging strategy. Arrow is
the natural materialized output contract. TSL is useful because it can express
the same decoder semantics across fixed-width x86/Arm and scalable SVE/RVV,
generate the implementation family, expose native/composed/fallback
provenance, and drive differential correctness tests.

The ranked recommendation is:

1. Run a small go/no-go pilot for **standard Parquet decoding across runtime
   vector lengths**.
2. If the pilot exposes stable and consequential crossovers, expand it into a
   database scan study and optionally a fleet-robust Parquet writer policy.
3. Treat **selective nested Parquet-to-Arrow reconstruction** only as a
   possible follow-on; recent work creates substantial novelty risk.
4. Keep **SIMD-batched MVCC version resolution** and **portable bounded
   high-precision SQL DECIMAL** as independent backup directions.
5. Use TSL capability provenance and cross-language generation as evaluation
   dimensions, not as substitutes for a database contribution.

## What “not solved already” can and cannot mean

No literature search can prove that nobody has solved a question. It can only
identify the nearest published claims, define a non-overlapping claim, and make
the remaining uncertainty explicit. This review uses the following labels:

- **survives this screen**: no work found that answers the same question under
  the same independent variables and outcome measures;
- **conditional**: a narrower question may survive, but adjacent recent work
  must be read and cited carefully before implementation;
- **collided**: existing work already contains the proposed central comparison
  or result;
- **engineering only**: useful implementation work without a distinct
  database-systems hypothesis.

The literature cutoff for this note is 2026-08-07. Before claiming novelty in a
submission, repeat the search in DBLP, ACM Digital Library, IEEE Xplore, arXiv,
the proceedings of SIGMOD, VLDB/PVLDB, ICDE, CIDR, DaMoN, ADMS, and the citation
graphs of every closest paper. Search author repositories as well as titles:
recent papers are not always indexed consistently.

The proposed Parquet question **survives this screen**, but that is a decision
to run a pilot, not a novelty certificate.

## Why TSL must be apparatus rather than subject

A strong paper needs a claim that remains meaningful if `tslc` is replaced by
“our controlled implementation generator.” Examples are:

- an interoperability cost imposed by a standard columnar encoding;
- a database execution policy that changes with vector length or semantic ISA
  capability;
- a new algorithm for irregular database work such as version-chain traversal;
- a performance/correctness trade-off for exact SQL arithmetic.

TSL then makes the experiment unusually credible:

- one authored semantic strategy can be projected to several target families;
- target-specific native, composed, and fallback paths remain explicit;
- fixed-width and scalable-vector profiles can be compared without silently
  changing the database operation;
- alternative implementations can be generated and correctness-gated;
- C++ and Rust can be compared when that comparison is scientifically useful;
- source and generated-product identities can be recorded for reproducibility.

The compiler already models scalable SVE and RVV extensions in
[`tsldata/extensions/extension.tsl`](../tsldata/extensions/extension.tsl),
including runtime lane counts and distinct predicate policies. Fixed SVE
profiles and an RVV verification profile are present in
[`supplementary/buildsystem/machine_profiles.json`](../supplementary/buildsystem/machine_profiles.json).
The selection and dependency pipeline records concrete implementation and
dependency facts, as described in
[`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md).

Those capabilities are a strong reason to use TSL. They are not by themselves
a database research result.

## Assessment of the current bitmask/position-list direction

### Original question

The current idea asks whether a database pipeline should retain active rows as
native masks, integral mask chunks, packed bits, or positions at a materialized
operator boundary, and whether a target-aware cost model can predict the best
choice. The design is documented in
[`pipeline-cost-model-idea.md`](pipeline-cost-model-idea.md), while the focused
prototype and its predeclared gates live in
[`intermediate-repr-src/PLAN.md`](intermediate-repr-src/PLAN.md).

This is a legitimate database decision. It is also a heavily studied one. In
particular, [*Filter Representation in Vectorized Query Execution* (DaMoN
2021)](https://db.cs.cmu.edu/papers/2021/ngom-damon2021.pdf) directly compares
bitmaps and selection vectors, examines selectivity-dependent thresholds, and
evaluates the choice in NoisePage. That work does not cover every TSL target or
mask model, but it occupies the central novelty claim.

### What the local results currently say

The prototype has already found real implementation effects, including a large
compiler-vector mask-conversion defect and sparse/dense representation
crossovers. Those are useful engineering and mechanism findings.

They are not yet a compelling optimizer result. A retrospective point-estimate
check over the 24 scenario medians pooled from:

- `../tslctmp/intermediate-repr/results/stage1-go-no-go-run1.json`;
- `../tslctmp/intermediate-repr/results/stage1-go-no-go-run2.json`; and
- `../tslctmp/intermediate-repr/results/stage1-confirmation-second-seed.json`

found that the trivial policy “positions when Filter A selectivity is 1%,
packed bits otherwise” has approximately 1.22% mean regret and 4.89% worst-case
regret against the materialized-representation oracle. This was a post-hoc
calculation over medians, not the predeclared bootstrap analysis, so it must not
be reported as a confirmed statistical result. It is nevertheless strong
negative guidance: the prototype's own H1 gate requires at least 10% worst-case
regret for the best fixed/simple policy before building a cost model.

The fused reference is also faster in important cells. The representation
question matters only at an unavoidable materialization boundary; it is not an
argument to introduce such a boundary.

### Decision

Do not spend the next research cycle building a learned or analytical cost
model for this experiment. Preserve the prototype for:

- regression and differential testing of generated mask operations;
- a supporting example in a broader vector-length study;
- validation of experimental methodology;
- a negative result if the predeclared confirmation is completed rigorously.

It should not be the primary publication thesis unless new, predeclared
workloads overturn the simple-policy result by a material margin and create a
novelty distinction from the 2021 study.

## Systematic screening method

Each candidate was reduced to the following form:

```text
database decision or mechanism
    + controlled independent variables
    + measurable system outcome
    + explicit falsifier
    + closest-work boundary
    + a reason TSL changes what can be tested
```

A candidate survives only if it passes all five tests below.

### 1. Database significance

The outcome must concern a database mechanism or system property: scan cost,
materialization, access path, concurrency-control work, exact SQL execution,
query latency, throughput, resource use, or performance portability. Primitive
throughput alone is insufficient.

### 2. Non-trivial decision surface

At least two outcomes must be plausible before measurement. “SIMD is faster
than scalar” is not enough. A useful question contains a crossover, a limit, a
robustness claim, or a mechanism that can fail.

### 3. Genuine TSL leverage

TSL should control an otherwise expensive product dimension: ISA family,
fixed/scalable vector model, implementation provenance, compiler/language, or a
large family of semantically equivalent variants. If one handwritten AVX2 loop
answers the question, TSL is incidental.

### 4. Falsifiability and stop conditions

The hypothesis needs predeclared effect sizes, uncertainty handling, and a
negative result that stops expansion. A benchmark matrix without a decision
rule is not a research design.

### 5. Novelty after collision search

The central comparison must not already be the contribution of the closest
paper. Merely adding more ISAs, using TSL, or reimplementing an established
algorithm does not restore novelty.

## Prior-work map and eliminated question families

| Question family | Closest work or established result | Consequence for a new TSL study |
|---|---|---|
| Portable SIMD abstraction for databases | [Template Vector Library](https://www.vldb.org/cidrdb/papers/2020/p28-ungethuem-cidr20.pdf) | “A hardware-independent SIMD API for databases” is already occupied. |
| Per-operator micro-adaptation | [Micro Adaptivity in Vectorwise](https://ir.cwi.nl/pub/21351/21351B.pdf) | Runtime selection among implementation variants is established; a new study needs a new transfer, robustness, or semantic-capability result. |
| Adaptive generation/fusion | [Excalibur](https://www.vldb.org/pvldb/vol16/p829-boncz.pdf) and [Relaxed Operator Fusion](https://www.vldb.org/pvldb/vol11/p1-menon.pdf) | Generic “generate many query variants and choose” is crowded. |
| Bitmap versus positions/selection vectors | [Filter Representation in Vectorized Query Execution](https://db.cs.cmu.edu/papers/2021/ngom-damon2021.pdf) | The current central comparison has a direct collision. |
| Small-chunk materialization/compaction | [Data Chunk Compaction in Vectorized Execution](https://people.iiis.tsinghua.edu.cn/~huanchen/publications/data-chunk-compaction-sigmod25.pdf) | Generic compaction timing and learned thresholds are now directly studied. |
| Portable SIMD compression/decompression | [FastLanes compression layout](https://www.vldb.org/pvldb/vol16/p2132-afroozeh.pdf) and [FastLanes file format](https://www.vldb.org/pvldb/vol18/p4629-afroozeh.pdf) | A new layout or generic portable decoder is not a clean gap. Preserve standard Parquet and ask a different question. |
| General comparison of Arrow, Parquet, and ORC | [Empirical Evaluation of Columnar Storage Formats](https://www.vldb.org/pvldb/vol17/p148-zeng.pdf) and [Data Formats in Analytical DBMSs](https://arxiv.org/abs/2411.14331) | Another format benchmark is not enough. |
| Direct selection on encoded Parquet | [Selection Pushdown in Column Stores using Bit Manipulation Instructions](https://www.microsoft.com/en-us/research/publication/selection-pushdown-in-column-stores-using-bit-manipulation-instructions/) | Generic encoded predicate pushdown, including a Parquet evaluation, is occupied. |
| Parquet compact nulls versus Arrow placeholders | [NULLS! Revisiting Null Representation in Modern Columnar Formats](https://db.cs.cmu.edu/papers/2024/zeng-damon24.pdf) | Arrow validity/null conversion is not an open main question by itself. |
| Relational processing of nested Parquet | [Nested Parquet Is Flat, Why Not Use It?](https://www-db.cs.tum.edu/~rey/papers/nestedparquet_rey.pdf) | Flattening nested Parquet and generating keys/joins has a direct recent result. |
| Structural encoding and random access | [Lance: Efficient Random Access in Columnar Storage through Adaptive Structural Encodings](https://arxiv.org/abs/2504.15247) | A generic Parquet/Arrow structural-layout or random-access study has high collision risk. |
| Broad RVV database acceleration | [RISC-V Meets RDBMS](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/ADMS/ADMS25-06.pdf) | “RVV accelerates scans” is occupied; vector-length-dependent mechanisms remain more specific. |
| MVCC design and scan overhead | [Empirical MVCC evaluation](https://www.vldb.org/pvldb/vol10/p781-Wu.pdf), [Fast Serializable MVCC](https://db.in.tum.de/people/sites/muehlbau/papers/mvcc.pdf), and [memory-optimized MVCC](https://www.vldb.org/pvldb/vol15/p2797-freitag.pdf) | A SIMD study must introduce and isolate a new traversal algorithm, not merely vectorize visibility tests. |
| Arbitrary-precision SQL arithmetic on accelerators | [UltraPrecise](https://xiaodongzhang1911.github.io/Zhang-papers/TR-24-1.pdf) | Generic arbitrary-precision database arithmetic is occupied on GPUs; a bounded-precision, portable CPU question is narrower. |
| Learned cost estimation | [Zero-shot cost estimation](https://www.vldb.org/pvldb/vol15/p2361-hilprecht.pdf) and extensive learned-cost literature | Using ML to predict a kernel winner is not novel without a new transferable structure or guarantee. |

## Ranked directions

Scores are 1 (weak) to 5 (strong). “Novelty confidence” means confidence after
this screen, not certainty.

| Rank | Direction | DB importance | TSL leverage | Falsifiability | Novelty confidence | Cost | Verdict |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | Standard Parquet's vector-length-dependent decode tax | 5 | 5 | 5 | 4 | 3 | Primary pilot |
| 2 | Vector-length-aware boundaries in DB execution generally | 5 | 5 | 4 | 4 | 5 | Larger program; narrow through Parquet first |
| 3 | Selective nested Parquet-to-Arrow reconstruction | 5 | 5 | 4 | 2 | 4 | Conditional follow-on only |
| 4 | SIMD-batched MVCC version resolution | 5 | 4 | 4 | 3 | 5 | Independent backup |
| 5 | Portable SIMD for bounded high-precision SQL DECIMAL | 4 | 5 | 5 | 3 | 4 | Independent backup |
| 6 | Capability-aware policy transfer/pruning | 3 | 5 | 5 | 2 | 3 | Secondary evaluation, not main DB claim |

## Direction 1: the decode tax of standard Parquet on scalable vectors

### Research gap

Parquet fixes interoperable byte layouts and encoding state machines. Its
[encoding specification](https://parquet.apache.org/docs/file-format/data-pages/encodings/)
includes plain values, dictionary IDs encoded with an RLE/bit-packing hybrid,
delta binary packing, delta byte arrays, and byte-stream split. Nested columns
add [definition and repetition levels](https://parquet.apache.org/docs/file-format/nestedencoding/).

Existing work establishes all of the following:

- Parquet decoding is an important CPU cost.
- Individual encodings can be SIMD-optimized.
- new SIMD-friendly layouts can be dramatically faster;
- direct extraction from encoded data can accelerate selective queries;
- Parquet, ORC, and Arrow have measurable end-to-end trade-offs.

The screen did **not** find a study that holds standard Parquet bytes fixed and
asks whether one vector-length-agnostic decoder remains near the per-machine
oracle across SVE/RVV vector lengths, or whether a reader needs a
vector-length-conditioned staging strategy. That distinction matters. A new
format can align its blocks to its vector algorithm; an interoperable reader
must accept the layout already on disk.

### Primary research question

> For standard Parquet pages, which encoding families admit one
> vector-length-agnostic decoder with bounded performance regret across SVE and
> RVV, and which require vector-length- or capability-conditioned staging even
> though the file format is unchanged?

This is a database/storage-format question about the portability cost of a
de-facto lake format. “TSL can generate a decoder” is the method, not the claim.

### Secondary questions

1. Is nominal vector length sufficient to predict the best decoder, or do
   semantic capabilities such as byte permutes, compress, predicate handling,
   widening shifts, and gather matter more?
2. Does the winning strategy change when output is materialized as an
   [Arrow array](https://arrow.apache.org/docs/format/Columnar.html) versus
   consumed immediately by a filter or aggregate?
3. If reader-side conflicts exist, can a standard-compliant Parquet writer
   choose encoding and page parameters that minimize worst-case decoding
   regret across a heterogeneous fleet rather than optimize one machine?

The third question is contingent. Workload-aware encoding selection already
exists. It becomes interesting only if the first study demonstrates conflicting
machine optima caused by vector model or semantic capability.

### Hypotheses and falsifiers

Define the regret of decoder strategy `s` in scenario `x` as:

```text
regret(s, x) = time(s, x) / min(time(candidate, x)) - 1
```

Candidates and scenarios must be predeclared. Report confidence intervals for
both time and relative differences.

#### H1: irregular standard encodings expose VLEN-dependent regret

For at least two predeclared regions involving arbitrary-width bit packing,
RLE transitions, or delta state, one source-level VLA decoder has at least 15%
regret relative to the best valid strategy, and the effect repeats on real
scalable-vector hardware with a second vector length or implementation.

**Falsifier:** one VLA strategy remains within 10% of the scenario oracle for
all retained regions, or apparent gaps disappear under independent runs and
code inspection. That is a useful negative result: standard Parquet decoding
does not require VLEN-aware dispatch in the tested scope.

#### H2: conditioned staging recovers portability without a new format

A strategy chosen from runtime vector length and a small semantic-capability
signature reduces worst-case regret below 10%, without machine-specific source
bodies for every encoding/bit width and without changing the Parquet bytes.

**Falsifier:** recovery requires hand-specialized recipes proportional to the
full target matrix, loses to production readers, or merely moves cost into
temporary buffers and cache traffic.

#### H3: the decoder decision is consequential to database scans

For at least two predeclared scan queries, decoder choice changes scan-stage
time by at least 10% and end-to-end query time by at least 5% once I/O,
decompression, Arrow materialization, filtering, and aggregation are accounted
for.

**Falsifier:** decoder differences disappear below page decompression, I/O,
allocation, or later operators. In that case the result may be a codec artifact,
not a database-systems contribution.

#### H4: format regularity predicts portability

Plain and byte-stream-split controls have lower strategy regret than arbitrary
bit widths and stateful RLE/delta encodings after normalizing for bytes decoded.

**Falsifier:** encoding structure does not explain the differences, or a simpler
factor such as compiler quality or memory bandwidth explains all observations.

### Experimental design

#### Format contract

- Inputs must be valid standard Parquet pages produced by at least two
  independent writers where practical.
- The primary study must not alter on-disk value order, introduce a FastLanes
  layout, or attach a private sidecar required by the decoder.
- Start without Snappy/Zstd to isolate lightweight encoding. Add block
  compression only after establishing that lightweight decode is a material
  fraction of scan time.
- Decode into standards-conforming Arrow buffers for the materialization path.
  Arrow variable-size values use offsets plus a data buffer, and nullable/nested
  arrays use validity buffers, so output construction cost must be included.

#### Initial encodings

1. `PLAIN` integers as a control;
2. `RLE_DICTIONARY` IDs using the RLE/bit-packing hybrid;
3. `DELTA_BINARY_PACKED` integers;
4. `BYTE_STREAM_SPLIT` floating-point values;
5. definition/repetition levels only after primitive values are understood.

Use adversarial and natural regions: bit widths around byte/lane boundaries,
short and long RLE runs, transition-heavy streams, monotone and noisy deltas,
dictionary cardinality, page size, null density, and truncated tails. Include
real column distributions after the mechanism matrix is fixed.

#### Decoder candidates

- production Arrow C++ and/or `parquet-rs` decoder;
- scalar reference with vectorization disabled;
- compiler-autovectorized scalar source where applicable;
- one TSL-authored VLA loop;
- TSL-authored capped or staged virtual widths;
- per-target optimized candidate as an oracle, not automatically as a fair
  deployable baseline;
- a redesigned-layout result such as FastLanes only as an upper-bound/context
  oracle, never as a standard-Parquet candidate.

#### Hardware requirements

- fixed-width controls: at least AVX2 and either AVX-512 or NEON;
- scalable-vector evidence: real SVE and/or RVV machines;
- the main claim requires at least two real scalable-vector lengths or
  implementations, ideally spanning SVE and RVV;
- QEMU and fixed compile modes are suitable for correctness and code-generation
  checks, not performance evidence;
- record frequency behavior, AVX-512 downclocking where relevant, compiler,
  flags, microcode, NUMA placement, and runtime vector length.

If access to suitable scalable hardware is unavailable, do not relabel an
x86-width comparison as a VLA result. Choose a backup direction or first build
only a non-publishable feasibility artifact.

#### Database integration

The minimum end-to-end path is:

```text
Parquet page bytes
    -> lightweight decode
    -> Arrow-compatible values/validity
    -> predicate
    -> aggregate or projected output
```

Integrate the retained decoder strategies behind one reader interface in an
existing engine or reader library. At least one query must materialize Arrow;
at least one may fuse decode with a simple consumer to test whether
materialization changes the decision. Use a small scan workload first, then
TPC-H/DS-derived scan fragments only after mechanism hypotheses survive.

#### Correctness

- differential comparison with a production Parquet reader;
- round trips from multiple writers;
- exact edge cases for every bit width and run transition;
- nulls, empty pages, page tails, malformed-input rejection, and overflow;
- cross-target comparison of decoded Arrow buffers;
- sanitizers and fuzzing for the decoder boundary.

Generated tests may share TSL facts with implementations, so at least one
oracle must be independent of the generated code.

#### Metrics

- cycles and nanoseconds per decoded value and per input byte;
- end-to-end scan/query latency and throughput;
- instructions, branches, branch misses, cache misses, and front-end stalls;
- temporary bytes, output bytes, and allocation time;
- code size and compile time;
- per-scenario regret and policy worst-case regret;
- authored and target-specific implementation count as a secondary
  maintainability measure.

### Why TSL genuinely helps

The experiment needs a family of semantically equivalent decoders whose
differences are controlled rather than accidentally inherited from unrelated
libraries. TSL can provide:

- a shared primitive vocabulary for bit operations, shifts, widening,
  permutations, masks, loads/stores, and reductions;
- runtime lane counts for SVE/RVV and fixed-width controls from the same source
  corpus;
- explicit native/composed/fallback provenance for mechanism analysis;
- generated variants for different staging widths and capability policies;
- differential tests across generated C++ targets;
- a way to measure whether the source effort grows with new semantic
  obligations or with the complete target matrix.

Before implementing a decoder, perform a coverage inventory. Prefix/segmented
scan, byte-table permutation, arbitrary bit unpacking, compress, and safe
unaligned/tail loads are likely pressure points. A missing primitive is not
evidence for the hypothesis; it is a pilot cost and may expose that TSL is not
yet suitable.

### Novelty boundary

The study must say explicitly what it is not:

- not another SIMD wrapper or Parquet library;
- not a new compression layout—FastLanes already provides a strong result;
- not another broad Arrow/Parquet/ORC comparison;
- not generic encoded predicate pushdown;
- not “RVV makes a scan faster”;
- not a claim that generated code is inherently faster than handwritten code.

Its candidate contribution is a measured law and remedy for the interaction
between **an unchanged interoperable format** and **runtime vector length / ISA
semantic capability**.

### Small go/no-go pilot

Do not begin with a complete Parquet reader. Implement one standard
RLE/bit-packed dictionary-ID page decoder with:

- bit widths `{1, 3, 7, 13, 17, 31}`;
- long-RLE, short-RLE, bit-packed, and transition-heavy streams;
- scalar, production-library, one-loop VLA, and two staged-width candidates;
- Arrow-compatible `uint32` output;
- AVX2 plus at least one real scalable-vector target;
- independent differential correctness and disassembly inspection.

Proceed only if all of the following hold:

1. all candidates decode identical standard pages;
2. a TSL candidate is competitive enough that generator quality is not the
   dominant confounder;
3. at least two strategies win in different predeclared vector-length or
   encoding regions with a repeated margin of at least 15%;
4. the best simple strategy has at least 10% worst-case regret;
5. the effect is not explained entirely by a compiler bug, accidental
   inlining, frequency changes, or emulation.

If the gate fails, stop. A polished multi-encoding framework will not turn a
flat decision surface into a research result.

## Direction 2: vector-length-aware database execution boundaries

### Question

> Can a vectorized database engine use one hardware-length-agnostic execution
> policy across SVE/RVV implementations, or must logical batch size, state
> layout, and materialization/fusion boundaries depend on runtime vector length
> and semantic capability?

This is broader than Parquet. Candidate operators include filter/aggregate,
hash probing, partitioning, sorting networks, and lane-refilled irregular
traversal. The [SVE architecture](https://arxiv.org/abs/1803.06185) promises
binary portability across vector lengths; it does not promise that a complete
database execution policy is optimal across them. The recent RVV database
study demonstrates acceleration but does not establish a cross-VLEN policy.

### Falsifiable hypothesis

A fixed logical batch/boundary policy incurs at least 15% worst-case regret
across a predeclared operator and hardware matrix, while a policy using runtime
VL, per-lane state size, selectivity, and a small capability signature reduces
that regret below 10%.

**Falsifier:** the same batch and boundary policy stays within 10% of the oracle,
or performance differences are explained by ordinary cache-size tuning rather
than scalable-vector semantics.

### Why it is ranked second

This may be the strongest long-term program and it uses TSL exceptionally well,
but it is too broad for a first experiment. It risks reproducing decades of
vector-size, morsel-size, fusion, and micro-adaptivity work with newer hardware.
Parquet supplies a narrower fixed semantic and byte-level contract. If the
format pilot reveals a general VLEN mechanism, this broader question becomes a
natural second paper or unifying evaluation.

## Direction 3: selective nested Parquet-to-Arrow reconstruction

### The tempting question

Parquet represents nested structure through definition and repetition levels,
while Arrow arrays use validity bitmaps and, for lists/variable-size values,
offset buffers. Reconstructing Arrow can therefore require level decoding,
prefix/segmented-prefix operations, allocation, and value placement.

A narrowly surviving question may be:

> When predicates retain only selected parents or children, can a
> scalable-vector algorithm construct only the required Arrow validity and
> offset hierarchy directly from Parquet level streams, and when is that
> preferable to full reconstruction or retaining a flat relational view?

### Hypothesis

For sufficiently selective nested scans, selection-aware level decoding and
segmented offset construction reduce decode-plus-materialization time by at
least 20% and peak temporary memory by at least 25%, while staying within 10%
of full reconstruction for dense scans.

**Falsifier:** level processing is not a material bottleneck, allocation/value
copy dominates, a production reader already performs the equivalent work, or
the method loses once complete query semantics are included.

### Collision risk

This direction is **conditional**, not currently recommended as an independent
first paper:

- [Nested Parquet Is Flat, Why Not Use It?](https://www-db.cs.tum.edu/~rey/papers/nestedparquet_rey.pdf)
  already scans nested leaf columns independently and reconstructs relations
  with generated keys and joins.
- [Lance](https://arxiv.org/abs/2504.15247) directly studies structural
  encodings, nested data, scan/random access, and Parquet/Arrow trade-offs.
- [NULLS!](https://db.cs.cmu.edu/papers/2024/zeng-damon24.pdf) studies compact
  Parquet nulls versus Arrow-style placeholder values and SIMD-assisted
  conversion.
- production systems already implement selective Parquet reading and late
  materialization; for example, DataFusion documents
  [row-level filter pushdown](https://datafusion.apache.org/blog/2025/03/21/parquet-pushdown/).

Do not claim novelty for “SIMD level decoding,” “faster Parquet-to-Arrow,” or
“process nested Parquet as flat columns.” The only plausible wedge is the
combination of selection-aware structural reconstruction, scalable vectors,
and a demonstrated database-level crossover not answered by those systems.

### TSL pressure points

This direction would genuinely exercise prefix/segmented scans, mask-to-bitmap
packing, compress, gathers/scatters, and runtime lane counts. It may therefore
be a good TSL stress test even if the novelty audit rules it out as a paper.

## Direction 4: SIMD-batched MVCC version resolution

### Question

> For analytical scans over MVCC data, can lane-refilled SIMD traversal resolve
> visible versions faster than scalar chain walking or lockstep SIMD across
> realistic chain-length skew, without changing transaction semantics or the
> storage layout?

The possible algorithm keeps several tuple version chains in flight, advances
active lanes by gather, removes completed lanes, and refills freed lanes. This
is related to established lane-refill techniques for divergent query pipelines,
including [work on countering control-flow divergence](https://link.springer.com/article/10.1007/s00778-019-00547-y),
but applies them to version visibility and reconstruction.

### Hypothesis

For a predeclared range of dirty-tuple ratios, chain-length distributions, and
snapshot ages, lane refill improves visibility/reconstruction throughput by at
least 20% over both scalar and lockstep SIMD, with no more than 5% overhead in
the mostly-unversioned common case.

**Falsifier:** pointer latency and gather cost dominate, realistic garbage
collection keeps chains too short, VersionedPositions-like synopses remove the
work, or a scalar implementation remains within 10%.

### Novelty risk

MVCC scan acceleration is mature. HyPer's
[Fast Serializable MVCC](https://db.in.tum.de/people/sites/muehlbau/papers/mvcc.pdf)
uses synopses of versioned positions to preserve fast scans, and many systems
avoid chain traversal through storage/layout choices. At least one contemporary
implementation documents
[vectorized visibility processing](https://docs.rs/sochdb-storage/latest/sochdb_storage/vectorized_scan/index.html).
The screen found no refereed paper centered on lane-refilled SIMD version-chain
resolution, but a deeper code and patent search is required.

### Why TSL helps

The algorithm depends on gather, comparison masks, compress/refill, pointer or
index representation, and runtime vector length—operations whose relative
capability differs sharply across AVX2, AVX-512, SVE, and RVV. TSL can generate
controlled lockstep and refill variants. A credible study still needs a real
MVCC engine integration and concurrent update/scan evaluation; a static chain
microbenchmark is only a pilot.

## Direction 5: portable bounded high-precision SQL DECIMAL

### Question

> Can a portable multi-limb SIMD representation make exact DECIMAL128/256 SQL
> expressions and aggregates fast across CPU ISAs, and which operations are
> limited by carry propagation, scale alignment, overflow, or missing vector
> capabilities?

This is deliberately narrower than arbitrary precision. It targets bounded
precisions common in storage and financial analytics, exact SQL semantics, and
CPU execution across at least two ISA families.

### Hypothesis

A structure-of-arrays limb representation plus vectorized add/subtract,
multiply, comparison, and staged carry handling improves retained
DECIMAL128/256 expression throughput by at least 2x over the engine's scalar
multiword path on two ISA families, while preserving exact overflow, scale, and
rounding semantics. The low-precision path must remain within 10% of the
engine's native fixed-width implementation.

**Falsifier:** carry/scale dependencies serialize the relevant expressions,
conversion dominates query time, gains occur only in artificial arithmetic
loops, or per-ISA recipes share too little semantic structure for TSL to help.

### Novelty boundary

[UltraPrecise](https://xiaodongzhang1911.github.io/Zhang-papers/TR-24-1.pdf)
already provides arbitrary-precision fixed-point arithmetic in a GPU database.
Database engines and general-purpose libraries already implement 128/256-bit
integers. The possible new result is a portable CPU SIMD algorithm family with
full SQL semantics and end-to-end expression/aggregate evidence—not the
existence of Decimal256 or generic multi-precision SIMD.

### Why TSL helps

Multi-limb arithmetic needs capabilities such as widening multiply, high-half
multiply, comparison, carry masks, shifts, and lane rearrangement. TSL can make
native, composed, and fallback paths explicit and test the same SQL operation
across languages/ISAs. The generated tests would need independent big-integer
or decimal oracles and adversarial overflow/rounding cases.

## Direction 6: capability-aware transfer as a supporting result

TSL's typed dependency closure can label a database kernel's primitive paths as
native, composed, fallback, or unsupported. This could support the hypothesis:

> Semantic capability and implementation provenance predict when a database
> kernel policy transfers across machines better than ISA name or vector width,
> and can safely eliminate dominated calibration candidates.

This is falsifiable using held-out machines and oracle regret. However, it is
closer to autotuning/compiler research than to a primary database contribution,
and generic performance prediction is already crowded. It is best used as the
policy layer for Direction 1 or 2 after meaningful crossovers exist.

A legitimate result would require all of the following:

- a predeclared candidate-pruning rule based only on compiler-owned typed facts;
- held-out hardware, compiler, or language evaluation;
- calibration reduction and worst-case regret;
- an audit showing whether any oracle winner was pruned;
- comparison with width/ISA labels and simple measured heuristics.

If static provenance does not improve transfer, report that negative result and
keep it as explanatory metadata.

## Arrow/Parquet ideas that should not be main projects

| Idea | Assessment | Reason |
|---|---|---|
| “A SIMD Parquet decoder generated by TSL” | Engineering only | Production libraries and papers already vectorize decoding. |
| “A new SIMD-friendly columnar format” | Collided/high risk | FastLanes has both a layout and a full file-format result. |
| “Filter encoded Parquet without decoding” | Collided | Selection pushdown using x86 bit-manipulation instructions reports Parquet and end-to-end Spark gains. |
| “Bitmap versus selection vector while scanning Parquet” | Collided | It combines the current weak result with an existing representation paper. |
| “Convert Parquet nulls to Arrow validity faster” | Collided | `NULLS!` directly analyzes the representation mismatch and AVX-512 optimization. |
| “Flatten nested Parquet for relational processing” | Collided | SIGMOD 2025 already presents this approach with on-the-fly keys and joins. |
| “Compare Parquet, Arrow, and ORC” | Collided | Multiple recent empirical studies do so systematically. |
| “Choose the best Parquet encoding per column” | Crowded | Encoding selection is established; only a new fleet-robust/VLEN-conflict result might survive. |
| Cross-ISA differential testing of Parquet readers | Valuable artifact | Useful for correctness and TSL evaluation, but not by itself a database hypothesis. |

## Recommended research program

### Phase A: zero-code novelty and feasibility audit

1. Snowball citations from FastLanes, Selection Pushdown, the two format
   evaluations, `NULLS!`, Nested Parquet, Lance, and the RVV database paper.
2. Search production Arrow C++, `parquet-rs`, Velox, DuckDB, DataFusion, and
   ClickHouse for SVE/RVV decoders and runtime-width dispatch.
3. Inventory TSL coverage for the RLE/bit-pack pilot without adding primitives.
4. Confirm access to real scalable-vector hardware. Emulation is not enough.
5. Write a one-page preregistration containing candidate algorithms, bit widths,
   datasets, effect thresholds, reducers, and stop conditions.

### Phase B: one-encoding pilot

Implement only the RLE/bit-packed dictionary-ID slice described above. Keep it
as a downstream research consumer; do not make `tslc` or `tsldata` own Parquet
semantics. Add a TSL primitive only when it is independently meaningful and
projection-neutral.

The output of this phase is a decision, not a framework:

- **go** if there are stable VLEN/capability-conditioned winners and meaningful
  regret;
- **stop** if one implementation is robustly near-optimal;
- **repair and repeat once** if a generated-code defect, rather than the
  hypothesis, dominates.

### Phase C: database relevance

If Phase B passes, integrate the candidates behind a production reader
interface and evaluate materialized Arrow scans plus one fused consumer. Only
then add more encodings, real datasets, and end-to-end queries.

### Phase D: optional generalization

Choose one extension based on the observed mechanism:

- fleet-robust standard-Parquet writer configuration if machines prefer
  conflicting encodings/page parameters;
- the broader vector-length-aware boundary policy if the effect generalizes
  beyond decoding;
- selective nested reconstruction if level/offset construction is a measured
  bottleneck and the novelty audit survives.

Do not pursue all three in one paper.

## Publication-shaped claims

A credible format paper could eventually claim:

> Across standard Parquet encodings and real fixed/scalable-vector CPUs, we
> identify which encoding structures are performance-portable under one VLA
> decoder and which exhibit a measurable vector-length-dependent decode tax.
> A capability- and VL-conditioned staging method reduces worst-case reader
> regret without changing on-disk bytes, and improves integrated scans.

That statement is publishable only if every clause has evidence. In
particular:

- “standard Parquet” requires interoperable inputs and unchanged bytes;
- “scalable-vector” requires real hardware;
- “identify” requires mechanism evidence, not only timings;
- “reduces regret” requires predeclared candidates and held-out evaluation;
- “improves scans” requires a reader/engine integration;
- the TSL artifact must be competitive and independently correctness-tested.

A negative but still informative result would be:

> A single VLA decoder remains within a small bound of the per-target oracle
> across the tested standard encodings; query engines do not need VLEN-aware
> decoder dispatch in this scope. The remaining performance gap to redesigned
> formats comes from the on-disk layout rather than reader specialization.

This negative result is scientifically cleaner than manufacturing a cost model
after the decision surface proves flat.

## Final recommendation

Use Parquet as the fixed, externally meaningful contract and Arrow as the
in-memory boundary. Start with the smallest irregular standard encoding and ask
whether runtime vector length changes the optimal decoding strategy. This
question is falsifiable, database-relevant, not answered by the closest work
found in this screen, and genuinely benefits from TSL's ability to generate and
verify the same semantics across fixed and scalable SIMD models.

Do not start by implementing a complete format reader or by adding a large set
of codec-specific primitives to TSL. First establish three things: real
scalable hardware is available, the one-encoding pilot has consequential
crossovers, and the collision audit still finds no direct answer. If any of
those fails, switch to the MVCC or bounded-DECIMAL pilot rather than expanding
an engineering artifact without a research claim.
