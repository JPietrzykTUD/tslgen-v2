# Evaluation plan: semantic-key compilation

## Purpose

This plan defines the evidence needed to accept, narrow, or reject the proposal
in [`README.md`](README.md). It evaluates an exact database technique, not a
Unicode approximation and not merely the overhead of a SIMD abstraction.

The primary rule is:

> Every performance comparison must perform equivalent semantic work, include
> all required fallback and materialization costs, and first pass exact
> differential validation against the pinned ICU/engine baseline.

Binary collation is useful as an upper bound on recoverable performance. It is
not a correctness-equivalent competitor for locale-aware queries.

## Research questions

- **RQ1 — semantic fast domain:** Which Unicode and collation features admit a
  conservative SIMD implementation with useful coverage on real multilingual
  data?
- **RQ2 — execution structure:** Does processing one independent string per
  lane, with dynamic compaction/refill, outperform scalar ICU and the same
  transducer without refill under realistic length and complexity skew?
- **RQ3 — physical product and placement:** When should an engine construct a
  bounded ordering prefix, an equality fingerprint, or a complete key, and
  should it do so per Arrow batch, per dictionary, or not at all?
- **RQ4 — database effect:** Do the kernel gains survive allocation, fallback,
  hashing/comparison, payload movement, and other operator costs in filtering,
  grouping, joining, and sorting?
- **RQ5 — semantic portability:** Can one semantic algorithm and table format
  remain correct and useful across fixed- and scalable-vector ISAs without
  target-specific algorithm forks?
- **RQ6 — limiting factors:** Are performance and coverage controlled by table
  locality, gather cost, lane occupancy, prefix ambiguity, exception rate,
  output bytes, dictionary reuse, or another measurable factor?

## Confirmatory hypotheses

These hypotheses and their primary scenarios must be preregistered before
confirmatory runs. Exploratory results may motivate later work but cannot be
substituted after a failed primary test.

### H1: kernel value

On at least three preregistered real corpora from materially different
language/script families, the complete candidate path—TSL SIMD fast path,
reason-specific ICU fallback, and required output writes—has throughput at
least **1.8x** that of the strongest ICU method producing the equivalent
product. The lower bound of the paired 95% confidence interval for the speedup
must exceed 1.8 on each primary corpus, and correctness mismatches must be zero.

Equivalent product matters:

- bounded prefix compares against ICU partial-key generation or the engine's
  collation-plus-prefix path;
- complete key compares against correctly buffered ICU sort-key generation;
- equality fingerprint compares against a correct ICU-derived collation key
  hash or the engine's exact collated hash path;
- direct predicate use compares against ICU comparison, not full-key generation
  that the baseline would not perform.

### H2: database value

At least two structurally different operator families improve end-to-end
single-thread latency by at least **15%** over the unmodified ICU-backed engine
on their frozen primary scenarios. For each claimed operator, the upper bound of
the paired 95% confidence interval for the latency ratio
`candidate / baseline` must be below 0.85. Results and collation equivalence must
match exactly, and peak memory must remain within the preregistered budget.

Two sorting variants do not count as two families. Suitable pairs include
`ORDER BY` plus `GROUP BY`, or range filtering plus hash join.

### H3: placement value

Transient Arrow compilation, per-dictionary compilation, complete-key
materialization, and direct ICU have repeatable, explainable winning regions.
On held-out scenarios, a frozen small policy should achieve:

- median runtime regret no greater than **5%**;
- 95th-percentile regret no greater than **20%**; and
- mean regret at least **50% lower** than the best single fixed policy.

Regret for scenario `s` is:

```text
(runtime(chosen, s) - runtime(measured_oracle, s))
-------------------------------------------------
             runtime(measured_oracle, s)
```

If one candidate wins nearly everywhere, that simpler result is preferable and
H3 is rejected.

### H4: semantic portability

The same transducer source, table/key format, fast-domain classification, and
fallback contract passes identical correctness suites and beats the scalar
same-algorithm baseline on at least two materially different vector families.
Any claim spanning fixed and scalable vectors additionally requires one real SVE
or RVV machine. Emulation can establish only build and correctness coverage.

The paper must report per-target results; one geometric mean cannot hide a
target on which the algorithm loses.

## Secondary apparatus question: what did TSL enable?

TSL is evaluated as experimental infrastructure, not promoted into the main
database hypothesis. Record:

- the exact generated dependency closure per target;
- implementation state and verification evidence for every required primitive;
- whether the semantic kernel source and tables are unchanged across profiles;
- compile, binary-size, and performance differences;
- profile-specific configuration and unavoidable target-specific code;
- a limited handwritten-intrinsics oracle on the primary target, if feasible,
  to quantify abstraction overhead rather than to become another maintained
  implementation.

A TSL kernel within 10% of a carefully optimized handwritten primary-target
oracle would be strong artifact evidence, but it is not a substitute for H1 or
H2. Source-line counts alone are not a scientific result.

## Baselines and candidates

### Semantic and system baselines

| ID | Baseline | Role |
| --- | --- | --- |
| **B0** | Binary collation in the target engine | Semantically different upper bound on attainable operator performance. Never the denominator for a correctness-equivalent speedup claim. |
| **B1** | ICU direct comparison with the exact frozen configuration | Strong baseline for filters and comparison-driven operators. |
| **B2** | ICU full sort-key generation with reusable buffers and no redundant size/fill pass | Strong baseline for full-key materialization. |
| **B3** | ICU partial/streaming sort-key generation where the API supports the candidate's bounded product | Strong prefix baseline; avoids comparing a short candidate prefix with unnecessary full-key work. |
| **B4** | Unmodified pinned database engine using its normal ICU collation path | Primary end-to-end baseline. |
| **B5** | Production Arrow/Parquet reader plus unmodified engine behavior | Format-inclusive end-to-end baseline. |

### Algorithmic controls

| ID | Candidate/control | What it isolates |
| --- | --- | --- |
| **C0** | Scalar implementation of the proposed semantic transducer | Algorithm/table effect without SIMD. |
| **C1** | TSL SIMD, no lane refill | Cross-string vectorization without dynamic scheduling. |
| **C2** | TSL SIMD, masked refill | Reuse of holes without state compaction. |
| **C3** | TSL SIMD, compact-and-refill | Central lane-refilled candidate. |
| **C4** | C3 with bounded prefix | Prefix construction, ambiguity, and fallback. |
| **C5** | C3 with streaming fingerprint | Equality/hash consumers. |
| **C6** | C3 with complete keys | Repeated comparisons and dictionary reuse. |
| **C7** | Per-dictionary C4/C5/C6 | Compilation amortized by distinct values. |
| **C8** | Optional handwritten primary-ISA implementation | TSL abstraction-overhead diagnostic only. |

Every candidate must use the same collation identity and exact fallback. A
candidate that silently supports fewer options is a different experiment.

## Correctness evaluation

Correctness is a gate, not a metric traded for throughput. A single unexplained
wrong database result invalidates the corresponding performance evidence.

### 1. Authoritative conformance data

Use the ICU/Unicode collation and normalization tests applicable to each frozen
configuration. Record which tests are in scope, skipped, or unsupported and why.
Unsupported fast-path cases are acceptable only when the exact fallback passes
them.

### 2. Differential comparison

For each string pair `(a, b)`, compare:

- sign of candidate-versus-candidate ordering and ICU `compare(a, b)`;
- equality decision;
- candidate complete-key comparison, when present;
- prefix decision only when the candidate marks it resolved;
- fingerprint compatibility: ICU-equal implies equal fingerprint;
- fallback result and reason.

The test must distinguish “candidate produced no answer” from “candidate
answered equal.” An unresolved prefix is correct only if the consuming path
actually invokes the exact continuation.

### 3. Algebraic properties

On generated samples, test:

- reflexivity of equality;
- antisymmetry of comparison sign;
- transitivity on sampled triples;
- identical key products imply ICU equality/order as required by the product;
- deterministic output for one identity;
- different identities never share a cache entry;
- normalization-equivalent strings compare as required when normalization is
  enabled.

Do not invent invalid metamorphic properties: locale tailoring and contractions
can make apparently simple prefix/suffix transformations non-monotone.

### 4. Hard semantic corpus

The suite must deliberately include:

- empty and very long strings;
- all UTF-8 sequence lengths and boundary code points;
- combining marks in canonical and non-canonical orders;
- precomposed/decomposed canonical equivalents;
- contractions, discontiguous-context cases, and expansions;
- Turkish dotted/dotless case behavior;
- French backwards secondary accents;
- numeric collation with leading zeros and long digit runs;
- variable/punctuation handling and case-level options;
- CJK and at least one right-to-left or Indic-script corpus;
- emoji and supplementary-plane values where the collator defines behavior;
- long common collation prefixes and values equal at primary but different at
  later strengths;
- invalid/truncated UTF-8 according to the frozen input policy;
- nulls and dictionary codes at each integer-width boundary.

ASCII-only correctness and speed are smoke tests, not research evidence.

### 5. Dictionary correctness

Construct dictionaries with:

- duplicate byte strings;
- byte-distinct but collation-equivalent strings;
- values differing only at each strength;
- arbitrary code order;
- several dictionaries containing overlapping values;
- code-width changes and dictionary reset/fallback to plain encoding;
- cache reuse under exact identity and deliberate version/configuration misses.

Verify group counts, join multiplicities, filter results, and order ranks against
decoded strings under ICU. Never compare local ranks across dictionaries without
an explicit remapping.

### 6. Engine equivalence

For every query, compare complete outputs, including duplicates, nulls,
representative values, and stable-order requirements. A checksum is useful for
large results but must be backed by full comparisons on smaller cases and
diagnostic row capture on mismatch.

### 7. Memory safety and determinism

Run address/undefined-behavior sanitizers, fuzz string lengths and tail masks,
guard input/output buffers, and repeat table generation. Test zero lanes at the
batch tail, all lanes exceptional, and output-arena exhaustion. Generated tables
and identity digests must be byte-deterministic.

## Data and corpus design

Use four complementary corpus classes.

### Authoritative corpus

Official conformance and regression inputs establish semantic breadth. They are
not representative performance distributions.

### Real multilingual corpora

Select at least three legally redistributable or reproducibly obtainable
corpora before tuning:

- one Latin-script corpus with accents/case and real names or terms;
- one CJK corpus; and
- one corpus from a materially different script family, such as Arabic or an
  Indic script.

Prefer column-like values—names, locations, products, titles, or categorical
labels—over continuous prose alone. Record provenance, license, extraction,
normalization state, byte/code-point length distributions, distinct count,
script mix, and checksum. If raw data cannot be redistributed, publish a
deterministic transformation/fetch manifest and a small representative fixture.

### Controlled synthetic corpus

Generate values with independently controllable:

- rows and batch size;
- byte and code-point length distributions;
- length skew and lane correlation;
- distinct count and Zipf/uniform frequency;
- dictionary size, code width, and reuse count;
- common binary and collation-prefix length;
- fraction equal at primary/secondary/tertiary levels;
- fast/context/fallback symbol mixture;
- contraction, expansion, normalization, and numeric rates;
- null fraction;
- sort order, filter selectivity, group skew, and join match rate.

Use fixed recorded seeds. Validate generated distributions rather than assuming
parameters produced the intended corpus.

### Adversarial performance corpus

Construct worst cases for each proposed mechanism:

- one very long lane among short strings;
- every lane finishing on a different iteration;
- all rows falling back after substantial partial work;
- lookup indices spanning more than LLC;
- prefixes tying until the last byte;
- full-key expansion much larger than source bytes;
- dictionary cardinality approximately equal to row count;
- tiny dictionaries with extreme reuse;
- alternating dictionaries/pages that defeat caching.

These cases bound behavior; they are not averaged into the primary real-corpus
claim.

## Workloads

### Kernel microbenchmarks

Measure separately and in complete compositions:

1. Arrow offset loading and lane initialization;
2. UTF-8 decode/classification;
3. collation-table lookup;
4. prefix emission;
5. complete-stream fingerprinting;
6. complete-key arena emission;
7. exception compaction and ICU fallback;
8. no-refill, masked-refill, and compact-refill scheduling;
9. dictionary compilation;
10. code-to-semantic-metadata lookup; and
11. identity/cache validation.

Component timings explain a result. Only the complete required path supports a
speedup claim.

### Relational operator workloads

#### Equality/range filtering

Sweep selectivity, constant prefix similarity, batch size, nulls, and fallback
rate. Measure direct ICU, transient prefix/fingerprint, and dictionary products.

#### `GROUP BY` and `DISTINCT`

Sweep cardinality, frequency skew, byte-distinct/collation-equal rates, hash
collisions, dictionary encoding, and number of aggregates. Include exact
collision comparison time.

#### Hash join

Sweep build/probe sizes, match rate, duplicate rate, build-side dictionary
reuse, and collation-equivalent byte-distinct keys. Record key construction,
hashing, collision checks, and materialization separately.

#### `ORDER BY`

Sweep rows, prefix length, common-prefix distribution, string length, number of
sort keys, payload width, cardinality, and spill threshold. The first
confirmatory study should remain in-memory and single-threaded unless baseline
profiling shows that setting is irrelevant. Add spill and parallel execution as
external-validity experiments only after H2 is answered.

### Format-inclusive workloads

Use standard Parquet files from at least two independent writers with:

- plain byte arrays;
- dictionary pages at several cardinalities/code widths;
- dictionary-to-plain fallback;
- multiple row groups and dictionaries;
- nullable values; and
- repeated scans/operators to vary reuse.

Report reader/decode time, dictionary compilation, semantic lookup, operator
time, and total query time. A Parquet result must include all standard reader
work; a predecoded Arrow result is reported separately.

## Staged experiment matrix

A full Cartesian product would be expensive and obscure. Use three stages.

### Stage A: frozen breakthrough scenarios

One primary machine, collator, real corpus, product, and operator-specific
scenario answer `G1`–`G3` and later `G5`. These scenarios are selected before
candidate tuning.

### Stage B: controlled boundary sweeps

Vary one or two interacting factors at a time to identify crossovers:

- length skew x vector width;
- table working set x script mix;
- fallback rate x partial work before fallback;
- prefix length x prefix ambiguity;
- cardinality x dictionary reuse;
- key bytes x downstream comparison count;
- batch size x lane-refill strategy.

Use these sweeps to build explanatory models and define placement-policy
features.

### Stage C: held-out confirmation

Freeze implementation and policy, then evaluate:

- unseen portions of every real corpus;
- at least one entirely held-out corpus;
- held-out parameter combinations;
- a second vector family; and
- where available, one scalable-vector machine.

Tuning on the confirmation data invalidates the confirmatory label.

## Metrics

### Correctness and coverage

- mismatches by semantic operation;
- resolved prefix decisions and unresolved ties;
- rows/bytes/code points completed in the fast domain;
- fallback rows and time by reason;
- key/fingerprint determinism;
- cache/version hit and invalidation counts.

Report both row-weighted and byte/code-point-weighted coverage. A fast path that
handles many tiny values but none of the expensive bytes can otherwise look
misleadingly broad.

### Kernel performance

- strings/s and input bytes/s;
- semantic-key output bytes/s;
- cycles/string, cycles/input byte, and cycles/output byte;
- active-lane fraction by iteration;
- compactions/refills per string;
- time in candidate, fallback, allocation, and output;
- table-cache misses, instructions, branches/mispredictions, and stalled cycles
  where counters are reliable;
- table and executable footprint.

### Database performance

- wall-clock query/operator latency;
- throughput for scan-like consumers;
- CPU time by phase;
- peak and allocated bytes;
- semantic product bytes per input byte/row;
- hash-table probes/collisions/exact comparisons;
- sort prefix ties, full comparisons, and payload movement;
- dictionary compilation amortization and cache reuse;
- chosen-plan regret.

### Portability and TSL evidence

- actual vector length and machine profile;
- emitted/built/executed/value-tested primitive closure;
- implementation-state distribution and required features;
- per-target speedup against ICU and scalar same-algorithm baselines;
- gap to the optional handwritten primary-target oracle;
- target-specific source/configuration changes;
- compiler and generated binary size/time.

## Measurement protocol

### Host control

- use real hardware for every performance claim;
- pin the process/thread to an isolated physical core where possible;
- avoid an active SMT sibling;
- record CPU model, microcode, cache hierarchy, memory, NUMA placement, OS, and
  actual SVE/RVV vector length;
- fix frequency/governor and turbo policy where permitted, otherwise record and
  monitor frequency;
- separate cold-cache, warm-cache, and repeated-reuse experiments;
- stop and rerun samples affected by thermal throttling or documented external
  interference under a predeclared rule.

### Build control

- use release builds with assertions/instrumentation disabled for primary timing;
- keep correctness/sanitizer builds separate;
- record compiler/linker versions and complete flags;
- pin ICU, Arrow/Parquet, DuckDB, Unicode/CLDR, TSL, and table-generator inputs;
- ensure candidates and baselines use compatible optimization and linkage;
- inspect code generation for gross mistakes, but do not tune using the held-out
  test data.

### Timing

- calibrate inner repetitions so one sample is long enough to dominate timer
  resolution;
- use at least 15 independent process-level samples for primary claims unless a
  preregistered power analysis requires more;
- randomize or balance candidate order within blocks;
- pair candidates on the same scenario/data seed;
- include setup if the real use case pays it and report excluded one-time setup
  separately;
- keep raw samples, not only aggregates;
- do not discard outliers without a frozen mechanical rule and an accompanying
  sensitivity report.

### Parallelism

Primary kernel and first-operator results are single-threaded to expose the
semantic transformation. Multithreaded scaling is a later external-validity
test. If parallel execution is studied, report per-thread work balance, memory
bandwidth, NUMA placement, and serial fallback bottlenecks.

## Statistical analysis

- Compute paired ratios per scenario and sample block.
- Report medians and bootstrap 95% confidence intervals for latency/throughput
  ratios; publish the resampling procedure and seed.
- A confirmatory threshold passes only when the relevant confidence bound clears
  it, not when the point estimate does.
- Report every primary scenario individually. Geometric means may summarize but
  may not replace per-corpus/per-machine results.
- Mark all unregistered slices and post-hoc subgroup discoveries exploratory.
- For boundary sweeps, report response surfaces or crossover regions with
  uncertainty rather than dozens of isolated significance tests.
- Use effect size and confidence intervals as primary evidence; p-values, if
  reported, are secondary and corrected for the declared family of tests.

## Placement-policy evaluation

### Data split

Split by corpus and parameter region, not by randomly shuffling duplicate rows.
Use:

- training scenarios for threshold/tree fitting;
- validation scenarios for selecting model complexity; and
- held-out corpora, factor combinations, and at least one machine for final
  regret.

### Candidate oracle

The oracle is the fastest **measured semantically valid complete plan** for a
scenario. It is not a cost-model prediction and not a component-only timing.
Plans that exceed the memory budget or fail correctness are ineligible.

### Policy baselines

- always direct ICU;
- always transient bounded prefix/fingerprint;
- always complete per-row key;
- always per-dictionary compilation when a dictionary exists;
- the engine's existing choice, if one exists.

Report selection accuracy, median/95th/max regret, memory violations, and the
specific features at each decision. If a one-threshold rule performs as well as
a fitted tree, use the threshold.

## Ablations

The following ablations are required to support causal explanations:

- scalar same algorithm versus TSL SIMD;
- no refill versus masked refill versus compact-and-refill;
- identical input with and without length skew;
- table lookup with hot and deliberately cold working sets;
- prefix lengths including zero/direct ICU and full key;
- prefix only versus prefix plus equality fingerprint;
- fallback disabled on an admitted-only corpus versus exact combined path;
- output stores/hash enabled versus computation-only diagnostic;
- per-row versus per-dictionary compilation at equal logical values;
- dictionary compilation included versus amortized over measured reuse counts;
- fast-domain subsets for simple mapping, contractions/expansions,
  normalization, and additional scripts;
- one fixed-width profile versus wider fixed-width and scalable-vector profiles.

Computation-only and fallback-disabled numbers must be labeled ceilings; they
cannot support the main speedup claim.

## Breakthrough reporting

For each implementation gate, publish a compact decision sheet:

| Gate | Primary evidence | Threshold | Confidence result | Correctness result | Decision | Scope change |
| --- | --- | --- | --- | --- | --- | --- |
| G0 | Prior-art claim matrix | No equivalent central mechanism found | Independent review | N/A | Continue/narrow/stop | Exact surviving claim |
| G1 | Engine profiles and binary headroom | >=25% collation CPU in two families and room for 15% | Repeatability interval | Baseline semantics confirmed | ... | ... |
| G2 | Scalar fast-domain suite | >=80% rows on one non-ASCII corpus | Corpus interval | 0 mismatches in conformance + >=1M pairs | ... | ... |
| G3 | One-ISA kernel | >=1.8x ICU and >=1.5x scalar | Lower 95% CI clears thresholds | 0 mismatches | ... | ... |
| G4 | Three-family suite | H1 on all primary corpora | Per-corpus intervals | 0 mismatches | ... | ... |
| G5 | First engine operator | >=15% lower latency | Upper ratio CI <0.85 | Exact engine output | ... | ... |
| G6 | Placement policy | H3 regret thresholds | Held-out intervals | All chosen plans valid | ... | ... |
| G7 | Second/scalable target | Same semantics; beats scalar | Per-target intervals | Identical suite passes | ... | ... |
| G8 | Full result | H1 + two H2 operators + scoped H3/H4 | Confirmatory report | All advertised identities exact | ... | ... |

This sheet prevents an attractive microbenchmark from being mistaken for a
database result.

## Threats to validity and mitigations

### Novelty uncertainty

Proprietary engines and patents may contain similar techniques. Maintain the
living prior-art ledger through submission and phrase claims as measured deltas,
not universal “firsts.”

### ICU-version dependence

Performance, keys, and fast paths can change across ICU versions. Pin one
version for primary claims, test at least one additional current version for
sensitivity, and never compare cached products across identities.

### Corpus representativeness

Public text may not resemble database columns. Use several column-like real
corpora, report their distributions, include synthetic boundary sweeps, and do
not generalize beyond the measured scripts/options.

### Engine dependence

A result in one DuckDB revision may not transfer to other engines. Isolate
kernel, operator model, and engine integration; add a second execution framework
or Arrow-native consumer only after the main gates, and state the external
validity limit.

### Baseline quality

Incorrect ICU buffer use or missing engine optimizations can create a straw man.
Follow ICU's documented key-generation guidance, inspect profiles/source, ask an
experienced reviewer to audit baseline code, and report direct compare as well
as key materialization where each is appropriate.

### TSL implementation maturity

A slow composed/fallback primitive could make the algorithm look bad, while a
target-specific tuning gap could make portability look worse than necessary.
Record transitive implementation facts, compare with a limited native oracle,
and separate algorithm failure from a clearly identified primitive-quality gap.
Do not silently replace the TSL path for the primary claim.

### Hardware availability

Scalable-vector machines may be unavailable. In that case, run correctness under
emulation but remove scalable performance claims. Do not extrapolate from
AVX-512 width to SVE/RVV behavior.

### Fallback selection bias

Tuning the fast domain to the evaluation corpus inflates coverage. Freeze
classification before held-out data, report reason-specific coverage, and
include rows that fall back after partial work.

### Materialization accounting

Ignoring allocation, output writes, cache validation, dictionary compilation,
or destruction exaggerates gains. Primary results include all costs paid by the
query; component-excluded numbers are labeled diagnostics.

## Artifact and result publication

Publish or preserve:

- source and exact dependency locks;
- generated table recipes and identities;
- small legal correctness fixtures and corpus manifests/checksums;
- scenario definitions and seeds;
- raw per-sample measurements and counter records;
- host/build/TSL/ICU provenance;
- scripts that reproduce summaries and figures without rerunning benchmarks;
- every gate decision, including failed pilots;
- the minimal engine integration patch; and
- an explicit unsupported-feature matrix.

Generated/build trees and large raw corpora remain outside Git under
`tslctmp/collation/` during development. Publication packaging may archive them
separately with checksums.

## Evaluation success condition

The proposal earns the intended paper claim only if:

1. all primary semantic tests have zero mismatches;
2. H1 holds independently on three preregistered language/script families;
3. H2 holds for two distinct real relational operator families;
4. H3 either passes on held-out data or is explicitly removed from the paper;
5. H4 is worded only for real machines and unchanged semantic implementations;
6. the result explains the observed boundaries through counters and ablations;
7. the prior-art audit still supports the narrowed claim; and
8. all thresholds, failures, exclusions, and exploratory analyses are reported.

If only the microkernel wins, the result is not yet a database-systems paper. If
the operator wins only for ASCII or one target-specific implementation, it is
not the broad semantic-portability result proposed here. Those outcomes should
be reported honestly and used to decide whether a narrower contribution remains.
