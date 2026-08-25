# Benchmark plan

What each published number answers, which binary produces it, and under what
method. One question per file; one CSV schema across all of them, so a figure is
a query over `results/` rather than a re-run.

Settled with the author: the paper is about **sorting on modern hardware**, with
two specific angles — **accelerator-offloaded cluster detection** and **TSL
portability for a real algorithm**. Statistics are **median of at least nine
with the IQR reported**, resampled where the spread is wide, and *paired* wherever
two costs differ by less than the machine's drift. The samplesort stays a separate binary but shares the grid. External
baselines come from adapted libraries rather than only `std::sort`.

## The questions

| # | question | binary | status |
| --- | --- | --- | --- |
| Q0 | what configuration should every other number use? | `bench_q0_tune` | built |
| Q1 | How do we compare to the best available implementations? | `bench_q1_baselines` | built |
| Q2 | Quicksort or samplesort — which, where, and why? | `bench_q2_algorithms` | built |
| Q3 | What does cluster detection cost, and does offloading it pay? | `bench_q3_detection` | built |
| Q4 | How does it scale in threads, rows, columns and element width? | `bench_q4_scaling` | built |
| Q5 | Which variant wins where? | `cosort_bench --stage screen` | exists, staged |
| Q6 | What do the native primitives and the mask representation buy? | `cosort_bench --stage attribute` | built, both algorithms |

**Why Q5 and Q6 have no `bench_q5_*.cpp`.** They are stages of the corpus rather
than binaries of their own. A `bench_q5_variants.cpp` would have to re-implement
`cosort_bench`'s registration — the staged plan, the variant enumeration, the drop
accounting, the per-leaf template dispatch — to produce numbers it already
produces. What the paper needs from those two questions is the shared *schema*, so
a figure can be one query across all six, and
`benchmarks/visualization/gbench_to_paper.py` supplies that by converting the
corpus's Google Benchmark JSON. `run_paper.sh` runs both stages at
`--benchmark_repetitions=9` and converts them.

Supporting evidence, cited as mechanism and not as headline: `bench_hybrid_leaf`
(why the leaf is a per-leaf decision), `bench_samplesort_streams` (why K is not
set by the write-stream cliff), `bench_iaa_frequency_min_offload` (where an
offload starts to pay).

## Which dimensions are actually swept

Worth stating plainly, because the answer is not uniform:

| dimension | swept by |
| --- | --- |
| register width, 128/256/512 | Q0 (all cells), Q6, `probe_lane_curves` |
| style, `intr`/`clang`/`clang_bool` | Q0 (all cells), Q6, `probe_paired_styles` |
| element width, 4 and 8 bytes | Q0, Q1, Q2, Q3, Q4 |
| lanes = bits / (8 x bytes) | derived, not swept: it is the ratio of the two above |
| algorithmic knobs (K, leaf, base case, fill, ids, movement, partition, discovery) | Q0 |
| threads | Q4, 1 up to the physical cores of one NUMA node |
| rows, columns | Q2 (rows in *and* out of cache), Q4 |
| detector backend | Q3, this host's hardware only |
| dataset shape | Q1, Q2, Q4, and Q0's tuning set |

Nothing in that table is a literal about one machine. Row counts come from the
probed last-level cache, worker counts from the physical cores of one NUMA node, and
the measurement cell from Q0 -- see
[benchmark-workflow.md](benchmark-workflow.md).

Two notes on reading a width sweep. First, `--element-bytes` in Q2/Q3/Q4 is the
*element* width; it was called `--widths`, which read as register width and misled
exactly as you would expect. Second, `tsl::sse` and `tsl::avx2` in this profile
mean 128-bit and 256-bit, not the SSE and AVX2 instruction sets: on a host with
AVX-512VL the narrower scatters resolve to VL-encoded AVX-512 instructions. So a
width sweep here compares register widths on one ISA and says nothing about a
machine that genuinely lacks AVX-512.

## Method

Fixed for every driver, and implemented once in `benchmarks/paper_harness.hpp`
rather than per file:

* **Verify, then time.** Every configuration is checked against the reference
  image from `datagen` before its first timed run. A configuration that sorts
  wrongly reports `INCORRECT` and no number.
* **Median of at least nine, IQR reported, more samples where it is wide.** The
  mean is the wrong centre here: the distribution is skewed by scheduler outliers
  rather than symmetric around them, so the median is what survives and the
  quartiles say how wide the bulk is.

  Nine is a floor rather than the answer. Across 335 rows measured on this host the
  relative IQR is 1.81% at the median and 5.80% at the ninetieth percentile, but
  3.6% exceed 10% and the worst reached 40.8%, all parallel. A wide measurement is
  resampled in batches of four until its relative IQR falls under 5% or it reaches
  33, and the row records how many it took. In a representative run 246 rows
  settled at nine, 17 needed 13 to 25, and 11 reached the ceiling still wide -- the
  summary names that last group, because a row that would not settle cannot be
  distinguished from its neighbours.

  Google Benchmark would not fix this. Its contribution is auto-tuning the
  *iteration count* so a sub-millisecond kernel clears the timer's resolution;
  these sorts run tens to hundreds of milliseconds, where one iteration per
  repetition is already right and gbench would choose the same. Its aggregates are
  mean and standard deviation where the median and quartiles are the more robust
  pair. And neither addresses the dominant term, below.

  Two variances are in play and a figure has to say which it reports. Repeating
  *inside* one process, on warm data, the IQR is **1–5%**. Re-running the whole
  binary, which `snapshot.py` does, the same numbers move by **21% serial and 40%
  parallel** — cold caches, fresh allocations, a different scheduler state. The
  drivers here report the intra-process spread, which is the right one for
  comparing two algorithms in the same run; a claim about absolute throughput
  needs the inter-process figure and does not get it from this harness.
* **Machine state recorded per run.** Governor, achieved clock, core count, load
  average and compiler go in the CSV header, because a figure without them is not
  reproducible and this host's clock moves.
* **Parallel runs unpinned.** Pinning changes what is being measured; the
  scheduler is part of the system under test.
* **Drops reported.** Any configuration the grid asks for and does not run —
  unavailable backend, missing device, footprint cap — is emitted with a reason.
  A silently narrowed sweep reads as full coverage.
* **ns per element, never speedup.** Ratios go in the prose, where the
  denominator can be named.
* **Nothing is collected while a number is measured.** Phase timers are a template
  parameter and off by default; the element and range counters are compiled out by
  `TSL_COSORT_NO_INSTRUMENTATION`, which every `bench*` preset sets. Verified in
  the object code rather than by timing, which was too noisy to settle it: 51
  locked atomic instructions become 19, and those 19 belong to the task executor's
  queue and latches. On the parallel index-sort path the counters are twenty atomic
  increments per task and tpcds_q064 produces 986,867 tasks. Every driver prints
  `instrumentation=off`, and `run_paper.sh` refuses to write a results directory
  from a build that does not.
* **One configuration per driver, taken from Q0, never typed in.** Every reporting
  driver reads `best_config.tsv` and selects the entry for the key width it is
  about to measure. This is not hygiene for its own sake: a hard-coded network leaf
  once made the quicksort look 6.6x slower than it is, Q4's thread-scaling
  crossover was measured against a mis-configured quicksort, Q3 built its
  samplesort out of literals while reporting detection's *share* of that sorter's
  runtime, and the samplesort dispatch silently replaced a tuned `fill=75` with
  `fill=50` while still labelling the row `(tuned)`. A configuration the driver
  cannot instantiate is now a drop naming it, never a substitution.

## Q0 — the design-space exploration

Every other number depends on a configuration, so this runs first and the others
read what it chose. Without it, the tuned values live in each driver's source:
re-tuning on new hardware becomes a code change, the figures stop being
reproducible from one command, and — as the corrected table above shows — a
comparison can rest on a knob nobody examined.

**The candidate set.** A cross over the axes measured to interact (bucket count,
base-case leaf, fill threshold) and one-factor-at-a-time around the default for the
rest: fifteen samplesort points and six quicksort points per cell. Not a full grid,
because almost every knob is a template parameter, so a candidate is an
instantiation and a grid is 400-odd per cell.

**Interleaved, not sequential.** Each point contributes a callable rather than a
measurement; every candidate's sorter stays live and one pass of each runs per
round. Measuring A to completion and then B charges whatever drifted between the two
blocks to their difference, and that drift is 1.0% at the median and 3.5% at the
worst -- larger than the differences being resolved, since the leading candidates sit
within 0.2% of each other. The cost is identical: the same passes in a different
order.

**Out of cache, by construction.** The row count is derived from the probed last
level: four times it in live data, so keys, index and scratch together miss. A
literal size had it tuning inside a 30 MiB LLC while Q2 and Q4 applied the result at
134 MB, and the answers differ -- in cache the samplesort preferred `K=8`, out of
cache the `K=16` default is at least tied. Bucket count is precisely the knob that
trades fewer passes against more concurrent output streams, and stream pressure does
not exist until the streams miss.

**Every compiled cell, both key widths.** Eighteen here: three styles by three
register widths by two key widths, one translation unit per (style, width) compiled
in parallel. A configuration found on 32-bit keys is not a tuned configuration for
64-bit keys -- the samplesort takes `K=8/fill50` at four bytes and `K=16/fill75` at
eight -- and until the tuner covered both, every 8-byte row in Q1, Q2 and Q4 applied
the 4-byte configuration and still called itself `(tuned)`. Q0 says so out loud if it
finishes without a configuration for the cell the reporting drivers were built for.

**What ships is the default unless something resolvably beats it.** Not the fastest
number: the fastest number is unstable. Running the identical candidate set twice
moves scores enough to swap the samplesort winner when four candidates sit within
0.2%. The rule is a paired test -- pooled per-round ratio against the default, upper
quartile below 1.0 -- and among challengers that clear it, the first in the fixed
candidate order within the margin. The tied set is printed either way.

The claim this supports is weaker and true: not "these knobs are optimal" but
"nothing we measured beats the default by more than the measurement's own drift".

**Two guards on cost, both learned the hard way.** Two-way partitioning is
quadratic in the equal-run length on a duplicate-heavy tuning set, and a full run
sat on that one candidate for over an hour; it is skipped above a working-set cap,
reported as `SKIPPED` with the reason, exactly as the corpus driver has always
gated it. And any candidate whose calibration pass -- the correctness check, timed,
which costs nothing extra -- exceeds five times the best is abandoned before its
rounds rather than after them.

**The limitation, stated.** One descent round. A second needs the base moved to the
winner, which is a rebuild rather than a flag, and the driver says when it would be
worth it. And at a small sample the shipped configuration can still vary for the
8-byte key, where `base_case` at 64, 128 and 256 differ by under a percent: any rule
that must emit one choice flips when the tie structure does. That is a statement
about the sample rather than the rule, and tied configurations perform identically by
construction -- what matters is that the tie is reported, which it is.


The mechanism -- what is built when, what each stage measures, and where each
measurement goes -- is [benchmark-workflow.md](benchmark-workflow.md). This file is
the reasoning behind the axes.

## What each axis is for

The suite kept producing indefensible answers -- a four-lane cell chosen to
measure the paper, a "best" configuration that changed between two runs of the
same binary -- and the cause was one confusion repeated in three places: axes of
different *kinds* were being optimised over as though they were commensurable.
There are four kinds, and only one of them is a thing to choose.

**Input shape.** Rows, columns, distinct-value count and skew, and key width.
These are properties of the data, not decisions: they are swept, and every result
is reported per shape. A single number averaged over shapes is a summary, never a
finding -- the whole project's result is that cost is shape-dependent.

**Degree of parallelism.** `lanes = register bits / (8 x value bytes)`. This is the
axis the algorithm's structure depends on: a sorting network holds `lanes * rows`,
and the base case, bucket count and leaf capacity all scale with it. Register width
and value width are therefore *not* two independent axes -- their ratio is the
axis. 256-bit over 4-byte keys is the same eight lanes as 512-bit over 8-byte keys,
which the old output hid behind two unrelated-looking numbers. Q0 now prints lanes.

**Resolved, and the answer is no.** Comparing each cell's *winner* could never
settle it: the curve is flat near its minimum, so the argmin is the least stable
statistic it has. What is measurable is the curve. Sweeping the bucket count within
each cell, interleaved and normalised to that cell's own K=16 so absolute cost
divides out, at 2^21 rows over four columns:

| cell | lanes | K=8 | K=16 | K=32 |
| --- | --- | --- | --- | --- |
| u32 @ 256-bit | 8 | 0.9795 [0.9585..0.9975] | 1.0000 | 0.9879 [0.9700..0.9941] |
| u64 @ 512-bit | 8 | **1.0193** [1.0084..1.0292] | 1.0000 | 1.0047 [0.9998..1.0088] |
| u32 @ 512-bit | 16 | 1.0012 [0.9863..1.0169] | 1.0000 | 1.0129 [0.9934..1.0177] |
| u64 @ 256-bit | 4 | 1.0121 [1.0023..1.0163] | 1.0000 | 0.9947 [0.9891..1.0018] |

The two eight-lane cells point in opposite directions -- K=8 is faster than K=16 in
one and slower in the other -- and their quartile bands do not overlap. So the knobs
are not a function of lanes alone.

That is mechanistically sensible rather than surprising. The bucket count trades
fewer passes against more concurrent output streams, and stream pressure on cache
and TLB is set by *bytes*, not by lanes: an eight-lane u64 cell moves twice the
bytes of an eight-lane u32 cell. So the tuning key has to carry both the cell and
the key width -- which is what `best_config.tsv` has always done, now for a reason
rather than by accident.

The effects are small, 2-5%, and only visible because of how they are measured.
`tsl_paper_compare` in paper_harness.hpp interleaves entrants and reduces per-round
ratios, which removes drift slow relative to a round. Sequentially -- all
repetitions of A, then all of B -- the same differences are invisible: that is the
method that named a different winner on two runs of one binary.

**Implementation style.** Intrinsics, clang vector builtins, clang builtins with
packed boolean masks. Same lanes, three ways of expressing them. This axis exists
to be *compared*, never selected: it is the portability claim, and a style that
costs nothing is the result.

**Measured, paired, at a fixed sixteen lanes** (512-bit over 4-byte keys, quicksort
3way/hyb/post, one worker, 2^21 rows, ratios against intrinsics):

| shape | intrinsics | clang vector builtins | clang packed boolean masks |
| --- | --- | --- | --- |
| low_cardinality_d4 | 1.0000 | 0.9957 (tied) | **0.9449** |
| skewed_zipf_s1 | 1.0000 | 1.2552 | **0.9832** |
| independent_uniform_c1024 | 1.0000 | 1.1485 | **0.9801** |
| unique_first | 1.0000 | 1.4569 | 0.9803 (tied) |

The packed-boolean-mask overlay is at least as fast as hand-written intrinsics on
every shape and 2-5% faster on three; the lane-mask overlay is never faster and
costs up to 46%. On AVX-512 that is what one would predict -- a packed boolean mask
is a `k` register, while a lane-wide compare result has to be converted to one for
every masked operation -- and it is a strong result for TSL: the portable
expression is not a tax, it is a small win, provided the mask representation
matches the target's.

It also shows how badly the sequential ranking was misleading: it had
ClangBuiltin/128-bit -- four lanes, and the slowest style -- tied with
Intrinsics/512. Ranking styles by runtime and building the reporting
drivers for the fastest was a category error -- it optimised over the axis whose
purpose is the comparison, and on a 0.3% margin it chose ClangBuiltin/128-bit, a
four-lane cell, to measure an AVX-512 paper with.

So the cell is chosen once, deliberately, and defended by the paired measurement
below rather than by a ranking: **`ClangBoolMask` at the widest register width**,
because packed boolean masks are at least as fast as hand-written intrinsics on
every shape tried. A challenger still has to clear a 5% margin to displace the
widest-width incumbent, and Q6 reports what the other styles cost at equal lanes.
Q0 measures every compiled cell regardless, because the comparison is the result;
what it never does is *choose* on style.

**Algorithmic knobs.** Bucket count, base case, base-case leaf and its fill
threshold, discovery, partition kind, movement. Their optimum is a function of the
two axes above, so they are tuned per (cell, key width) and nowhere else.

And they are reported as a *tied set*. Running the identical candidate set twice on
a quiet, pinned machine moves individual scores by 1.0% at the median and 3.5% at
the worst -- enough to swap which samplesort configuration wins, when the top four
sit within 0.2% of each other. So Q0 reports everything within the drift of the
fastest and ships the documented default whenever the default is in that set. The
claim that survives is not "these knobs are optimal" but "nothing we measured beats
the default by more than the measurement's own drift", which is both defensible and
stable across machines.

**Thread count** is not a design axis at all: it is one thread per physical core of
one NUMA node, pinned with `numactl`. See the note in run_all.sh.

**So Q0 against Q2-Q4 is a division of labour, not a duplication.** Q0 explores
the knob space per cell and per key width and emits one file. Q2, Q3 and Q4 are
built for one cell, read that file for the key width they are measuring, and sweep
the *shape* axes. Nothing is tuned twice, and every reported row names the
configuration it used and whether it came from the file.

## Q1 — external baselines

The objection a single comparator-based baseline invites is that it is a straw
man, and it is a fair one: `std::sort` over row indices is 4–15x slower than
either of ours on every shape measured. Two tiers instead.

**Kernel-fair.** IPS⁴o and Intel's x86-simd-sort (`avx512_qsort_kv`, a key plus
index) are dropped in as the *inner* single-column sort inside our own multi-column
loop. Same loop, same detection, same oracle, so what is compared is the
partitioning kernel and nothing else. This is the comparison that answers "is our
SIMD partition worth writing", and it is the one a reviewer of a sorting paper
will look for.

**Semantically equal.** Arrow's `SortIndices` over a table with one sort key per
column performs literally this operation and produces the same artifact. It is
built. Nothing about it is adapted or restricted, and its table wraps our buffers
without copying and is built outside the timed region -- a system builds a table
once and sorts many times, so charging Arrow for construction would be the straw
man this section exists to remove. At 2^20 rows, one worker, our quicksort against
it: 11.92 vs 122.65 ns/element on low_cardinality_d4 at four columns, 44.08 vs
155.43 on skewed_zipf_s1, 50.59 vs 249.69 at eight columns, 86.36 vs 260.66. So
three to ten times, against the one baseline that solves exactly our problem.

Two notes. `SortIndices` runs on the calling thread -- Arrow parallelises across
ExecPlan nodes, not inside this kernel -- so it appears in the serial table only,
as a stated drop rather than an omission. And Arrow 23 keeps its compute kernels
in `libarrow_compute` and registers them on demand: without
`arrow::compute::Initialize()` the registry has no `sort_indices` at all, and the
failure surfaces as a wrong permutation rather than a missing function, which is
how it was first observed here.

**Not Google Highway's VQSort.** It sorts keys in place and yields a sorted array,
not a permutation, so it does not perform this operation. Its packed key-value
form is one column with an interleaved payload, which is a different layout and
strictly narrower than `avx512_argsort` -- already present, and producing the
artifact we produce.

Both would be fetched under `TSL_COSORT_ENABLE_BASELINES`, off by default,
following the pattern QPL and DML already use — so the default build stays
dependency-free and no test acquires a hidden network requirement.

**Built, and it changed the story.** `bench_q1_baselines` runs every entrant over
the same datasets, through the same verify-then-time harness, against the same
oracle, and nothing is timed unless it first produced a permutation whose image
matches the reference. Serial and parallel are matched: a parallel row of ours is
never compared against a serial baseline.

At 2^22 rows, u32, one worker, our quicksort wins all nine measured cells --
1.15x to 8.5x over IPS4o, 2.8x to 13x over `std::sort`. On the single-column
kernel it also beats Intel's own `avx512_argsort`, 6.68 against 9.79 ns/element
at 2^20 rows, which is the kernel-fair comparison this section was written for.

At twenty-four workers `std::sort(std::execution::par)` wins all five measured
keys. Measured with the sorters' phase instrumentation *off*, which matters: the
first version of this table was taken from a profiled build and overstated the gap
by 8-24%.

| key | ours, 1w | best other, 1w | ours, 24w | best other, 24w |
| --- | --- | --- | --- | --- |
| tpcds_q010 | **53.22** | 137.61 | 14.37 | **11.09** |
| tpcds_q050 | 13.20 | **12.34** | 5.23 | **2.73** |
| tpcds_q064 | **109.88** | 238.74 | 20.05 | **18.27** |
| tpcds_q067 | **76.78** | 226.50 | 16.30 | **16.17** |
| tpcds_q081 | **17.67** | 28.88 | 25.68 | **5.07** |

Serially we win four of five, by 1.6x to 2.9x; tpcds_q050 goes to IPS4o by 7%. In
parallel we lose all five, but three of the five margins are 1.01x, 1.10x and
1.30x -- tpcds_q067 is a dead heat -- and only tpcds_q081 is a rout at 5.07x. That
key is 100,000 rows over fifteen columns, so per-column overhead dominates and
there is little for a task tree to spread.

The quicksort's parallel path is the specific problem, not the approach. On
tpcds_q064 it goes from 109.88 to 112.16 ns/element between one and twenty-four
workers; on tpcds_q067, 76.78 to 77.95. It does not scale at all, so above two
workers the samplesort carries every parallel number. Measured without
instrumentation, end to end: 102.17 at one worker, 88.29 at two, 98.20 at four,
128.24 at eight, 131.20 at twenty-four. The best point is two workers and it
degrades from four.

Two consequences for the paper. The serial claim is strong and rests on a real
baseline rather than a straw man. The parallel claim is not currently supportable
and the quicksort's parallel path is the first thing to fix; until then, a
parallel figure that omits `execution::par` would be the straw man this section
exists to remove.

Fairness notes that belong beside the numbers. `avx512_argsort` writes 8-byte
indices where ours are 4-byte, so a one-column row is not a pure instruction-level
comparison; its parallel path exists but needs `XSS_COMPILE_OPENMP`, absent here.
IPS4o and `std::sort` see the columns only through a comparator, so they cannot
exploit equal runs the way the detector seam does -- which is the structural claim,
and reporting the one-column rows beside the multi-column ones is what keeps that
from being read as a faster inner loop. `execution::par` picks its own thread
count; the row records what we asked *ours* for.

## Q2 — quicksort against samplesort

One grid, both algorithms, so the numbers are comparable for the first time: the
existing samplesort sweeps use their own sizes and shapes while the corpus uses
cache-derived size levels, and nothing has driven both over one grid.

Grid: the 24-shape catalog x {2, 4, 8} columns x {u32, u64} x {1, 24} workers, at
two size levels. Each row carries the phase profile that explains it —
materialise, sort, detect — because the interesting result is not which wins but
why, and the phase split is what makes "better where the data punishes a binary
partition" a measurement rather than a story.

## Data: real TPC-DS / DSB sort keys

The synthetic catalog covers structure classes. These cover what queries actually
ask for, and they are **measured, not modelled**: DSB's `dsdgen` generates all
tables, DuckDB performs the joins each query's sort key needs, every column is
order-preserving dictionary-encoded, and the result is written as a `TSLDSET1`
container the drivers read through `external_path`.
`benchmarks/datagen/tpcds/README.md` has the pipeline and what it does not
reproduce.

**Why DSB rather than TPC-DS.** DSB (Microsoft, MIT, VLDB 2021) is TPC-DS with
deliberately skewed and cross-table-correlated data, and its templates keep
TPC-DS's numbering. Since every result in these documents says co-sort cost is
shape-dependent, more realistic shapes are the point. The official TPC-DS toolkit
is not used: it needs a licence accepted through TPC's website rather than being
fetchable.

**Which queries, chosen on evidence.** The templates were surveyed by `ORDER BY`
width rather than `GROUP BY` width, because `ORDER BY` is what a sort operator
compiles to while a `GROUP BY` may be hashed. Five keys span the axis that decides
everything else — the leading column's cardinality:

| key | columns | rows at sf=1 | leading column | leading cardinality |
| --- | --- | --- | --- | --- |
| q010 | 8 | 2.66 M | `cd_gender` | **2** |
| q050 | 10 | 2.75 M | `s_store_name` | 4 |
| q067 | 8 | 2.69 M | `i_category` | 10 |
| q064 | 9 | 2.65 M | `i_product_name` | ~18 000 |
| q081 | 15 | 100 k | `c_customer_id` | near-unique |

**First results — and the first version of this table was wrong.** It reported
the quicksort with a network leaf, because that was hard-coded in the driver. The
descent in Q0 then found the insertion leaf is up to **6.6x faster** on exactly
these keys, and with it the verdict inverts. Both are below, because the size of
the error is the argument for Q0 existing:

| key | samplesort | quicksort, `net` (as first published) | quicksort, tuned `ins` |
| --- | --- | --- | --- |
| q064 | 188.3 | 447.0 | **68.2** |
| q067 | 130.2 | 280.8 | **51.6** |
| q010 | 56.6 | 79.8 | **31.5** |
| q050 | 30.5 | 11.1 | **10.9** |
| q081 | 23.7 | **14.1** | 25.2 |

At one thread the tuned quicksort wins **all five**; the "three to two favouring
samplesort" in the first version of this document was an artefact of one
unexamined knob. In parallel the samplesort still wins several
keys, so the honest summary is that the quicksort is the better serial sorter on
real keys and the samplesort scales better, not that either dominates. The
parallel half of that comparison was taken at twenty-four workers, which on this
host oversubscribes a six-core node twice over, and needs re-measuring pinned
before it is quoted.

That is also the answer to "why tune at all": a comparison between two algorithms
is a comparison between two *configurations* of them, and picking one by hand is
picking the result.

**What skew is worth, isolated.** The synthetic `tpcds_q67` shape is calibrated to
the cardinalities measured above, so it and the real key differ only in
distribution and correlation. Same 2 685 687 rows, same eight columns:

| | ss w=1 | qs w=1 | ss w=24 | qs w=24 | samplesort ÷ quicksort |
| --- | --- | --- | --- | --- | --- |
| uniform, calibrated | 207.9 | 462.3 | 24.0 | 147.3 | 2.22x |
| real, skewed | 130.2 | 280.8 | 17.1 | 87.7 | 2.16x |
| ratio | 0.63 | 0.61 | 0.71 | 0.60 | |

Real skew is about 1.6x **faster** than uniform data at the same cardinalities --
concentration means fewer distinct tuples to separate and more runs that resolve
whole blocks. But the ratio between the two algorithms barely moves. So uniform
synthetic data at correct cardinalities predicts the *ranking* to within about
five percent while overstating absolute cost by roughly half again. That is worth
saying explicitly in the paper: it is the justification for every synthetic number
in it, and the limit on them.

## Q3 — cluster detection

The centrepiece, and it has to be built to *look for* the regime where offload
pays rather than to confirm that it does. What is already measured says it mostly
does not: detection is 0.5–10.4% of the multi-column samplesort and about 1.7% of
the direct quicksort, `iaa_sw` and `iaa_freq_sw` land inside scalar's noise, and
`dml_sw` is up to 23x worse. A benchmark that only reports those numbers argues
against its own paper; one that maps where the share becomes large is a result
either way.

So the sweep is over what makes detection expensive rather than over backends
alone: distinct-value count, element width, column count, discovery mode
(`post` against `incremental`, which changes fragment size), and range size
against `min_offload`. Backends are the inner loop, not the outer one.

**This host's hardware only.** `run_all.sh` probes `/dev/dsa` and `/dev/iax` and
passes `--detectors` naming exactly what exists, so a run cannot fill the
accelerator table with drops from the wrong machine. `--paths hw|sw|all` remains as
a coarser switch; the software paths are QPL's and DML's own CPU implementations, so
a published figure including them compares our scalar scan against somebody
else's.

**Which hardware exists is per machine, and no machine has both.** This host has a
DSA and no `/dev/iax`; the IAA host has the reverse. So the accelerator table is
assembled from two runs and every row records its host. `run_paper.sh` derives the
detector list from the devices it can actually see -- `--detectors scalar,dsa_hw`
here, `scalar,iaa_hw,iaa_freq_hw` there, overridable with `COSORT_Q3_DETECTORS` --
rather than asking for every compiled backend and dropping the absent ones, which
filled the table with rows from the wrong machine. It also warns when
`libaccel-config` is missing: without it DML cannot enumerate work queues and every
hardware submission fails identically, which is what made `dsa_hw` look broken for
months.

**Two things about this driver's numbers.** It reads Q0's configuration like the
others, which it did not until recently -- it built its samplesort from literals,
and since its headline is detection's *share* of the runtime, and a share is a
ratio against the sort, measuring it around a slower sorter understated every
offload decision resting on it. And its phase timers stay *on*, unlike every other
driver, because here the phase split is the measurement. So Q3's absolute
ns/element are not comparable with Q2's or Q4's -- they carry the timers' 1.08x to
1.28x -- while the share and the between-detector comparison, both taken within one
build, are unaffected.

## Q4 — scaling

Threads 1 up to the physical cores of one NUMA node -- six here, and derived rather
than written down -- x rows x columns {1,2,4,8,16} x {u32,u64},
on three shapes chosen for opposite range structure, plus the measured keys on the
thread axis. Reports speedup against its own single-thread row, so the axis is
self-normalising.

**The thread axis is where the algorithm crossover lives, and it is only visible on
real keys.** The synthetic shapes are won by the quicksort at every thread count.
On `tpcds_q064` the crossover sits between two and four workers: samplesort 187.43
against quicksort 83.28 at one worker, 66.13 against 97.03 at four, 21.31 against
119.73 at twenty-four. A measured dataset arrives with its own row and column
count, so it is passed in rather than looked up by size -- usable on the thread
axis, and correctly unavailable on the row and column axes, which would have to
invent data the query never produced.

**The "quicksort does not scale" finding was an artefact of oversubscription, and
is withdrawn.** It rested on a sweep to twenty-four workers on a host with twelve
physical cores across two NUMA nodes -- so four of the sweep's six points ran SMT
siblings against each other on a shared L1 while gathering across a node boundary.
Pinned to one node's six physical cores with `numactl`, both algorithms improve
monotonically: `low_cardinality_d4` at four columns runs 12.13, 8.09, 5.57, 5.12
ns/element at 1, 2, 4 and 6 workers, and `skewed_zipf_s1` at eight columns 675.6 to
252.7. What survives is the much smaller claim that the quicksort does not scale
*past the local node's physical cores*, which is unremarkable.

Every parallel number in this plan predating that fix is suspect for the same
reason, including Q1's twenty-four-worker comparison against
`std::sort(execution::par)` -- TBB was equally free to spread across both nodes.
Re-measuring those pinned is the outstanding item.

## Q5 and Q6 — variant screening and what the primitives buy

Both are stages of `cosort_bench` rather than binaries of their own, for the
reason given at the top: they would have to re-implement its registration to
produce numbers it already produces. `run_paper.sh` runs them at nine repetitions
and converts the Google Benchmark JSON into the shared schema.

**Q5, the `screen` stage.** Every implementable variant at one point per axis --
execution, discovery, partition kind, leaf, movement -- over six shapes at two
size levels. The question is viability, not tuning: which cells are worth carrying
at all. Two-way partitioning is registered only below a size cap, because it is
quadratic in the equal-run length and a low-cardinality key above that cap is a
several-minute row that tells you nothing you did not already know.

**Q6, the `attribute` stage.** Three implementation styles by three register
widths by both key widths, serial and post-sort so nothing but the primitives
differs. This is the portability claim, and until recently it enumerated the
quicksort's variant space only -- so a claim about TSL rested on one of the two
algorithms. The samplesort is now registered alongside it: not its own product,
because the question here is the cell rather than the configuration, but one fixed
configuration per cell, which is also what keeps the comparison about portability
instead of tuning. Eighteen cases, verified through the same index check the
quicksort cases use, published under algorithm ids 200 and 201 so no existing id
moves.

First numbers, samplesort on `low_cardinality_d4` at L2, three columns:

| lanes | intr | clang | clang_bool |
| --- | --- | --- | --- |
| 4 (128-bit) | 8.94 ms | 8.24 | 9.27 |
| 8 (256-bit) | 6.90 | 7.18 | 7.48 |
| 16 (512-bit) | 5.03 | 4.98 | **4.68** |

Register width is worth 1.8x from four lanes to sixteen. At sixteen the three
styles sit within 7% of each other, which is the portability result stated
positively: the abstraction costs nothing at the width that matters.

**And one asymmetry worth its own paragraph.** Q0's per-cell comparison puts
`intr/128` at 1.89x the best cell on 4-byte keys and 1.73x on 8-byte, while
`clang/128` is within 1.02x -- 40.11 against 21.24 ns/element for the same
algorithm at the same width. That gap survived the 128-bit hybrid-leaf fix, so it
is not a bug: clang's `ext_vector_type` at 128 bits generates materially better
code than explicit SSE intrinsics, because the compiler is free to schedule what
the intrinsics pin. It is the clearest single argument in the suite for generating
through an abstraction rather than writing intrinsics by hand, and it appears only
because the style axis is swept.

## Running it

One command, from a clean checkout to a results directory:

```bash
./run_all.sh                                  # results/$(hostname)
./run_all.sh results/<host> --quick           # prove the pipeline
./run_all.sh results/<host> --scale 10        # a larger scale factor
./run_all.sh results/<host> --no-baselines    # skip Q1's external libraries
```

It configures, generates the data, builds and runs, skipping any step already
done, so a re-run after a failure does not repeat `dsdgen`. Extracted keys go to
`TMP/tpcds_keys/sf<N>/` with a `manifest.txt` naming the scale factor: the earlier
version checked only whether keys existed, so `--scale 10` with scale-1 keys
present measured scale 1 and logged 10 -- every number real, every label wrong. The preset is chosen
from what `/dev` actually has -- `bench-dsa-baselines` on a DSA host,
`bench-iaa-baselines` on an IAA one, `bench` on neither -- and is always a
*measurement* preset.

The compiler is pinned to `clang++-22` and overridden only through
`TSL_COSORT_CXX`, deliberately not `CXX`: the generated TSL selects its profile
and its capability defines from the compiler it is configured with, so a different
compiler is a different library and two results are not comparable. (`CXX` was
already set to `zig c++` in the development container, and the first version of
the script used it.)

The stages underneath, if a step needs running by hand:

```bash
cmake -S . --preset bench-dsa-baselines       # or bench, bench-iaa, ...
cmake --build --preset bench-dsa-baselines
benchmarks/datagen/tpcds/build_generator.sh   # once
benchmarks/datagen/tpcds/generate.sh 1
benchmarks/datagen/tpcds/extract_keys.py --data ... --out TMP/tpcds_keys/sf1
TPCDS_KEYS=TMP/tpcds_keys ./run_paper.sh <build-dir> <results-dir>
```

`run_paper.sh` refuses a build with instrumentation compiled in, so the `dev` and
`phases` presets cannot produce a results directory. `--quick` proves the pipeline
in about ten minutes and proves nothing about the paper; the full run is six to
seven hours, and the accelerator rows need the machine with the devices.

## Exploring the results

```bash
pip install streamlit pandas altair
streamlit run benchmarks/visualization/explore.py -- --results <results-dir>
```

Reads every CSV the directory holds — one schema, so questions compare directly.
It shows the interquartile range on every point, gives drops their own tab rather
than letting them look like gaps, and says so when two hosts' numbers are mixed.

## Output

`results/qN_<name>.csv`, one schema:

```
question,binary,shape,shape_params,rows,columns,element_bytes,algorithm,variant,
detector,workers,repetitions,ns_per_element_median,ns_per_element_p25,
ns_per_element_p75,ns_materialize,ns_sort,ns_detect,verified,drop_reason,
host,governor,clock_mhz,compiler
```

Empty fields where a driver has nothing to say. `run_paper.sh` runs all of them,
records machine state once, and refuses to overwrite a results directory that
already holds a different host's numbers — the same refusal
`sweep_multicolumn_bench.py` already makes, for the same reason.

## Not in scope

* Descending and mixed-direction columns for the samplesort: it compares keys
  directly, so that needs the comparison inverted in the kernels.
* Asynchronous detectors for either index driver: neither polls.
* In-place block permutation: measured as a footprint decision, not a throughput
  one.
