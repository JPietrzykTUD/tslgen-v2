# Benchmark plan

What each published number answers, which binary produces it, and under what
method. One question per file; one CSV schema across all of them, so a figure is
a query over `results/` rather than a re-run.

Settled with the author: the paper is about **sorting on modern hardware**, with
two specific angles — **accelerator-offloaded cluster detection** and **TSL
portability for a real algorithm**. Statistics are **median of nine with the IQR
reported**. The samplesort stays a separate binary but shares the grid. External
baselines come from adapted libraries rather than only `std::sort`.

## The questions

| # | question | binary | status |
| --- | --- | --- | --- |
| Q1 | How do we compare to the best available implementations? | `bench_q1_baseline` | **outstanding**, see below |
| Q2 | Quicksort or samplesort — which, where, and why? | `bench_q2_algorithms` | built |
| Q3 | What does cluster detection cost, and does offloading it pay? | `bench_q3_detection` | built |
| Q4 | How does it scale in threads, rows, columns and element width? | `bench_q4_scaling` | built |
| Q5 | Which variant wins where? | `cosort_bench --stage screen` | exists, staged |
| Q6 | What do the native primitives and the mask representation buy? | `cosort_bench --stage attribute` | exists, staged |

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

## Method

Fixed for every driver, and implemented once in `benchmarks/paper_harness.hpp`
rather than per file:

* **Verify, then time.** Every configuration is checked against the reference
  image from `datagen` before its first timed run. A configuration that sorts
  wrongly reports `INCORRECT` and no number.
* **Median of nine, IQR reported.** The mean is the wrong centre here: the
  distribution is skewed by scheduler outliers rather than symmetric around them,
  so the median is what survives and the quartiles say how wide the bulk is.

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

**Semantically equal.** Arrow's `SortIndices` with several sort keys performs
literally this operation and produces the same artifact. Strongest optics,
heaviest dependency; added only if the paper needs a system-level baseline.

Both would be fetched under `TSL_COSORT_ENABLE_BASELINES`, off by default,
following the pattern QPL and DML already use — so the default build stays
dependency-free and no test acquires a hidden network requirement.

**This is the one question still unbuilt.** Everything else here runs; Q1 needs
the dependency gate and an adapter per library, and until it exists the only
external number in the results is `std::sort` over row indices, which is the weak
baseline this section exists to replace.

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

**First results, and they are a split rather than a sweep.** ns/element,
`rle=scalar`:

| key | ss w=1 | qs w=1 | ss w=24 | qs w=24 | `std::sort` |
| --- | --- | --- | --- | --- | --- |
| q064 | **188.3** | 447.0 | **22.3** | 183.9 | 310.3 |
| q067 | **130.2** | 280.8 | **17.1** | 87.7 | 317.6 |
| q010 | **56.6** | 79.8 | **14.3** | 18.1 | 212.3 |
| q050 | 30.5 | **11.1** | 19.4 | **5.7** | 67.6 |
| q081 | 23.7 | **14.1** | 32.1 | **24.2** | 63.2 |

Three to two, with a mechanism for each side. Samplesort takes the keys whose
leading column is wide enough to split. The quicksort takes q050, whose ten
columns hold one to five distinct values each — one is constant — so a three-way
partition's equal band swallows whole columns at once and a 16-way split has
almost nothing to divide. It also takes q081, which at 100 k rows is too small to
feed 24 threads: samplesort is *slower* there at 24 workers than at 1.

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

## Q3 — cluster detection## Q3 — cluster detection

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

**Hardware paths only.** `--paths hw` is the default: the software paths are QPL's
and DML's own CPU implementations, so a published figure including them compares
our scalar scan against somebody else's. They stay available for correctness
(`--paths sw`, `--paths all`).

**Which hardware exists is per machine, and no machine has both.** This host has a
DSA and no `/dev/iax`; the IAA host has the reverse. So the accelerator table is
assembled from two runs and every row records its host. `run_paper.sh` reports
which devices it can see, and warns when `libaccel-config` is missing — without it
DML cannot enumerate work queues and every hardware submission fails identically,
which is what made `dsa_hw` look broken for months.

## Q4 — scaling

Threads {1,2,4,8,16,24} x rows {2^18 .. 2^24} x columns {1,2,4,8,16} x {u32,u64},
on three shapes chosen for opposite range structure. Reports speedup against its
own single-thread row, so the axis is self-normalising, plus the phase profile so
a plateau can be attributed rather than noted.

## Running it

```bash
./run_paper.sh <build-dir> <results-dir>            # everything
./run_paper.sh <build-dir> <results-dir> --quick    # one cell per question
```

`--quick` proves the pipeline in a couple of minutes and proves nothing about the
paper. The full run is hours, and the accelerator rows need the machine with the
devices.

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
