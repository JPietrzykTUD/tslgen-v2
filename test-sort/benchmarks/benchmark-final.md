# Multi-column co-sort: benchmark plan

Authoritative plan for measuring the lexicographic multi-column co-sort. Every
decision here is settled and, where marked, implemented in `cosort_bench`.
[`benchmark.md`](benchmark.md) is the working draft this was distilled from and is
kept only for the reasoning behind these decisions.

## Settled decisions

| decision | rationale | state |
|---|---|---|
| Data comes from `TslDatasetSource` | the nine documented dataset shapes with measured descriptors ($D_j$, $G_j$, $R_j$, $W$), generated in memory and shared across cases, nothing on disk | implemented |
| Correctness is `memcmp` against the reference image | with every column a sort key the sorted image is unique however an unstable sort breaks ties, so the comparison is exact and names the first differing row | implemented |
| Registration goes through per-family predicates, selected by `COSORT_STAGE` | the full product is unrunnable and mostly redundant; each stage answers one question and reports what it dropped | implemented |
| clang 22 for everything | required by the generated clang profile header (`__builtin_elementwise_clzg`); the intrinsic families build with it too | implemented |
| Generated TSL release `v0.2.9` | `v0.2.8` gave the clang families a native `compress`/`expand`; `v0.2.9` adds the native runtime-index `permute_lanes` the bitonic leaf needs. Below either, the style axis measures TSL's scalar fallbacks rather than the styles | implemented |
| Register width and implementation style are *variant* dimensions | both are template parameters of the sorter, not conditions it runs under | implemented |
| `rle=` is an axis of the one binary, with per-machine backends | the detector parameterizes a sort call; a host has DSA or IAA, and `rle=` records which produced a row | implemented |
| Row movement is a *variant* dimension, `move=` | the direct sorter permutes every column; the indirect one permutes a row index and materializes the active column per level. Same datasets, same discovery, same detectors -- so the question "does moving indices beat moving rows" is one axis rather than a second benchmark | implemented |
| The indirect family is checked against the value image, not the permutation | its output is a permutation, and ties make that non-unique because the partition is not stable. The values it selects are unique, since every column is a sort key | implemented |

## Variant space

A variant is one compiled sorter configuration. For the direct sorter the
algorithmic part is `execution × discovery × partition × leaf` = 3 × 2 × 2 × 3 =
**36**, and every cell is implemented and registered. The indirect sorter shares
`discovery × partition × leaf` = 12 and has the serial and parallel executions but
not `deep_parallel_`, so it adds 24 rather than 36:

```text
direct    36 algorithm configurations
indirect  24 algorithm configurations (no deep_parallel_)
          60 x 3 styles (intr, clang, clang_bool) x 3 widths (128, 256, 512)
           = 540 sorter configurations, plus the width- and style-independent
             baseline
           = 541
```

The `leaf` axis has three values: `ins`, `net`, and `hyb` — the network leaf with a
per-leaf diversion of leaves too sparse to be worth its fixed cost. See
[Choosing the leaf per leaf](#choosing-the-leaf-per-leaf); the algorithm IDs for
`hyb` are appended as 25 to 36 so no published ID moves.

The 37 algorithm names `cosort_bench` registers, at one (style, width). The
indirect family reuses the twelve serial names and is distinguished by `move=`
rather than by a name of its own, so a `move=direct`/`move=index` pair is the same
algorithm on both sides of the comparison:

```text
post_2way_ins                       post_2way_net                       post_2way_hyb
post_3way_ins                       post_3way_net                       post_3way_hyb
incremental_2way_ins                incremental_2way_net                incremental_2way_hyb
incremental_3way_ins                incremental_3way_net                incremental_3way_hyb
parallel_post_2way_ins              parallel_post_2way_net              parallel_post_2way_hyb
parallel_post_3way_ins              parallel_post_3way_net              parallel_post_3way_hyb
parallel_incremental_2way_ins       parallel_incremental_2way_net       parallel_incremental_2way_hyb
parallel_incremental_3way_ins       parallel_incremental_3way_net       parallel_incremental_3way_hyb
deep_parallel_post_2way_ins         deep_parallel_post_2way_net         deep_parallel_post_2way_hyb
deep_parallel_post_3way_ins         deep_parallel_post_3way_net         deep_parallel_post_3way_hyb
deep_parallel_incremental_2way_ins  deep_parallel_incremental_2way_net  deep_parallel_incremental_2way_hyb
deep_parallel_incremental_3way_ins  deep_parallel_incremental_3way_net  deep_parallel_incremental_3way_hyb
std_lex_argsort                     (scalar baseline, the normalizer)
```

## The indirect family

`multicolumn_index_sort.hpp` sorts a row-index permutation and leaves the columns
`const`. Per level it gathers the active column through the index into a
contiguous scratch buffer, sorts `(scratch, index)` with the shared stitch
partition -- the index is the sorter's single payload column -- and discovers the
equal runs that the next column has to break. Only rows inside a surviving range
are materialized, so the gather work per level shrinks the way the direct
sorter's payload set does; the `materialized_per_row` counter reports it.

Three things it deliberately does not do, each dropped with a reason rather than
omitted:

* **No `deep_parallel_` form.** The driver is bulk-synchronous: it fans a level's
  ranges out and barriers between levels. Splitting a *single* partition across
  workers needs the task tree the direct sorter has, so `deep_parallel_` drops
  with `no indirect form of this execution`.
* **Synchronous detectors only.** Nothing polls, so an asynchronous backend would
  never complete; a `static_assert` says so and registration excludes them.
* **Index element type equals the data type**, because the stitch replays a key
  mask on payload registers of the same style. A narrower index needs the mask
  re-spacing that `TMP/tsl_sort`'s `compress_store_index_array` does.

Its detector seam sits in a different place from the direct sorter's, and
`detector_applies` encodes that: discovery runs between levels on the
materialized key buffer, so `rle=` applies to the indirect **serial** path, where
the direct serial path has no seam at all and only ever runs `rle=scalar`.

### What the first measurements say

The governing variable is not the column count -- it is **how early ties
resolve**. At 8 columns, u32, L2, `post_3way_net`, `rle=scalar`:

| shape | direct | index | ratio | materialized/row | levels |
|---|---|---|---|---|---|
| `unique_first` | 27.12 ms | **10.67 ms** | **0.39** | 1.0 | 1 |
| `unique_last_g64` | 23.21 ms | 25.85 ms | 1.11 | 8.0 | 8 |
| `low_cardinality_d4` | 28.20 ms | 33.86 ms | 1.20 | 8.0 | 8 |
| `skewed_zipf_s1` | 324.99 ms | 366.06 ms | 1.13 | 7.9 | 8 |

When column 0 is all-distinct the sort finishes in one level and never touches the
other seven columns, where the direct sorter permutes all of them: 2.6x. When ties
persist to the last column, the indirect form pays a materialize pass per level
and gains nothing, losing 11-20%. A column-count sweep narrowed the ratio from
1.42 at 2 columns to 1.02 at 8, but the catalog generates a different dataset per
column count, so that is not a scaling curve and is not reported as one.

`algo` IDs match the previous benchmark's enum so old JSON stays comparable, and
everything that enum lacked is **appended** rather than inserted: the two two-way
deep-parallel variants as 17 and 18, the six incremental two-way variants as 19 to
24. Inserting would renumber existing IDs and invalidate recorded results.

### Parallelising the indirect sorter

The parallel form is a **task tree**, the same shape `sort_columns_parallel` uses.
A task is one `(column, range)`: it fetches the range's column values into the
scratch buffer, sorts it, and submits a child task per tied sub-range it
discovers. Children run as soon as they exist, so there is no barrier between
columns and a worker that finishes a small range never waits for the largest one
beside it.

Two consequences the caller carries:

* **Discovery runs on worker threads**, so a detector must be safe for concurrent
  use -- a fleet (`TslIaaDetectorFleet`, `TslDsaDetectorFleet`) or a stateless one.
  This is the contract `sort_columns_parallel` already has, for the same reason.
* **Asynchronous detectors are still excluded**, now for a different reason than
  before: an asynchronous backend retains the emitting callable past the task that
  produced it, and the child-submitting emitters here are not self-contained. A
  `static_assert` says so.

Column 0 is the exception the tree cannot help: while the root is the only task
there is nothing to spread. Its fetch is a copy of the whole table, done by a
one-shot fan-out before the tree starts, and its sort is split inside its own
partitions through `TslMultiColumnQuickSorter::sort_key_parallel` -- a public entry
that sorts one key range with its payloads across an executor and reports
completion events, driving no column recursion of its own. It may offload
partitions unconditionally, where `process_parallel_task` may not, precisely
because it promises nothing about scanning the whole range: the caller scans
afterwards, over the range as a whole.

Medians of five, 4 Mi u32 rows over 8 columns, `post_3way_net`:

| shape | 1 worker | 8 | 16 |
|---|---|---|---|
| one huge tie per level | 938 ms | 3.09x | 2.95x |
| many small ties | 113 ms | 4.18x | 4.77x |

In the harness, `low_cardinality_d4` at 8 columns and `halfLLC` goes from 193 ms
serial to 49 ms on 8 workers -- **3.92x**.

Three things were measured rather than assumed, and two of them overturned a
design that looked obviously right.

**Chunking the fetch pays only for the copy.** Splitting the per-level fetch
across workers measured 1.00-1.01x on its own: the fetch is about 5% of the
runtime, so Amdahl caps it there. It survives only as the one-shot pre-pass for
column 0's copy, which is bandwidth-bound and scales. Chunking a *gather* -- what a
deeper level does -- is latency-bound, was never faster than leaving it serial,
and cost about 4% on the shape that has a huge tied range to fetch.

**Splitting partitions helps at column 0 and nowhere else.** Applied to every
level that happens to hold one range, it made one shape better and the other
worse (2.52x to 2.22x). A deeper single-range level exists only under a maximal
tie: its partition tree offers less to split, and a second executor's threads run
while the tree's own workers sit idle. Column 0 alone was best on both shapes.

**The inline threshold decides whether a level is parallel at all.** A discovered
range below `tsl_index_inline_task` is finished by the worker that found it instead
of being queued. Every child of a range is discovered by the *one* thread that
sorted that range, so a threshold above the typical child size silently serialises
the entire next level. On a shape whose second level holds ranges of about a
thousand rows:

| threshold | many small ties, 8 workers |
|---|---|
| 1024 | 1.99x |
| 256 | 4.18x |
| 64 | 4.31x |

The two failure modes are not symmetric -- queueing a range that was too small
costs a constant, inlining one that was large enough costs a level's parallelism --
so the value is deliberately small at 256.

Superseded on the way: an earlier bulk-synchronous form, with a parallel-for over
each level's ranges and a barrier between levels, reached 2.76x and 4.30x on the
same two shapes. The task tree beats it on both and deletes the mechanism, so the
`TslIndexParallelFor` it needed is gone.

### How incremental two-way works

An earlier draft claimed a two-way fragment "cannot report self-contained runs".
That was wrong, and the variant is now implemented. The two-way partition produces

```text
[ strictly before pivot ] [ pivot ] [ not before pivot ]
 lo               p-1        p       p+1            hi-1
```

so the boundary status of every fragment is known exactly:

| fragment | left boundary | right boundary |
|---|---|---|
| root range of a column sort | closed — the enclosing equal-prefix group | closed |
| left part `[lo, p)` | inherits the parent's left boundary | **closed** — the pivot at `p` is strictly greater |
| the pivot at `p` | **closed** — the left part is strictly smaller | **open** — the right part may begin with equal values |
| right part `[p+1, hi)` | **open** — merges with the pivot | inherits the parent's right boundary |

A completed left part can therefore be scanned immediately, and the only place a
run can cross is the pivot into the head of its right part.

One bit of state per range is *not* enough, though, and that is the part worth
knowing. On duplicate-heavy input two-way peels one copy of a value per level with
an **empty left part**, so a run of `k` equal values becomes a chain of `k`
consecutive pivots; widening a fragment by one element covers only the nearest.
What `sort_impl` threads instead is the **start position of the run overlapping the
open edge**: everything in `[open_begin, range_begin)` is equal and already final,
so a fragment reports from there and the runs found inside are maximal. Three cases
complete it:

- a fragment reports `[open_begin, end)`, closed on both sides;
- an empty fragment reports nothing — its open run either continues into the
  sibling pivot, whose range covers it, or was reported where the chain ended;
- when a chain ends at a pivot that differs, the frame reports the chain itself,
  because no fragment below would cover it.

A range handed to another worker is *offered* from `open_begin` too, so it re-enters
as a root with a closed left edge. Those extra elements are final, no other worker
writes them, and a range beginning with its own minimum keeps it there — so
partition offload stays available for two-way incremental, and
`deep_parallel_incremental_2way_*` is a real variant rather than a relabelled
`parallel_` one.

**Validated** by comparing the emitted span set against a full-range scan of the
sorted output: no missed and no duplicated spans across both partition kinds, both
leaves, both directions, at row counts from 2 to 200,000 and cardinalities from 1
to 200,000 — and separately through the benchmark's `memcmp` oracle over 378 cases
at 1, 4 and 24 workers. A `memcmp` alone would not have been enough: a missed run
shows up as a wrong image, but a duplicated one only wastes work.

**And it does not pay.** At L2, `unique_last_g64`, u32, three columns:

| variant | time | `rle_values_per_row` |
|---|---|---|
| `post_2way_ins` | 94.63 ms | 2.00 |
| `incremental_2way_ins` | 98.64 ms | 2.00 |
| `post_3way_ins` | 16.53 ms | 2.00 |
| `incremental_3way_ins` | 16.43 ms | **0.37** |

The scan-volume win of incremental discovery comes entirely from three-way's
pivot-equal bands, which are emitted with **no scan at all**. Two-way has no bands,
so every element still has to be scanned by some fragment: incrementality alone
changes only *when* the scan happens and how early next-column work is exposed. Here
that cost about 4% in time. Keeping the variant is still worth it — it makes the
product complete, and it means "incremental" can be compared against "post" without
the partition kind confounding the answer.

## Axes

These are the axes of `cosort_bench`. The dataset shape replaces the eight inline
`dist=` distributions of the legacy `benchmark_multicolumn_gbench`, which is a
different binary and is not part of this plan.

| axis | name component | values | selected by |
|---|---|---|---|
| dataset shape | `shape=`, `sparams=` | any dataset id prefix from the generator catalog: `unique_first`, `unique_last_g64`, `independent_uniform_c1024`, `skewed_zipf_s1`, `low_cardinality_d4`, … | `COSORT_SHAPES` |
| element width | the `u32`/`u64` component | 4, 8 bytes | `COSORT_ELEMENTS` |
| sort columns | `cols=` | every column is a sort key | `COSORT_COLUMNS` |
| working set | `size=` | L1, L2, halfLLC, LLC, 2xLLC, 16xLLC — bytes **per column** | `COSORT_SIZE_LEVELS` |
| direction pattern | `order=` | asc, desc, alternating | `COSORT_DIRECTIONS` |
| detector | `rle=` | scalar, plus whatever the build has: `dml_sw`/`dsa_hw` and `iaa_sw`/`iaa_hw`, each with an asynchronous form | `COSORT_RLE` |
| workers | `workers=` | scalar per process | `COSORT_WORKERS` |
| task threshold | `threshold=` | scalar per process | `COSORT_TASK_THRESHOLD` |
| partition threshold | `partitions=` | scalar per process, `deep_parallel_` only | `COSORT_PARTITION_THRESHOLD` |

Style, width and movement appear in a name as `style=`, `lanes=` and `move=` but
are variant dimensions, not axes. `style=` is mandatory because `avx512`,
`clang_v512` and `clang_v512_bool` have the same lane count and would otherwise
produce identical names; `move=` is mandatory because the indirect family reuses
the direct algorithm names. `COSORT_MOVEMENTS=direct,index` selects which
movements a run registers, and `COSORT_VARIANTS` keeps filtering on the algorithm
name alone, so it selects a `move=` pair rather than one side of it.

A full benchmark name:

```text
deep_parallel_incremental_3way_net/u32/move=direct/style=intr/lanes=16/
shape=unique_last_g64/sparams=g=64/order=asc/cols=3/size=LLC/stage=screen/
rle=scalar/workers=12/threshold=4096/partitions=16384/real_time
```

Worker count and both thresholds are scalar per process, so a scaling curve over
them needs one process per value, merged by `sweep_multicolumn_bench.py`.

## The staged programme

Each stage pins the axes its question does not need. Counts are measured with
`--benchmark_list_tests` on a 12-core host with the clang family available.

| stage | question | registered | drops reported |
|---|---|---|---|
| `screen` | which variants are viable at all? | 452 | 8 no indirect form, 40 quadratic two-way |
| `tune` | what worker count and thresholds make the survivors fastest? | 86 | 8 out of variant set, 16 quadratic two-way |
| `characterize` | the numbers that get published | 5,712 unrestricted | 288 quadratic two-way |
| `attribute` | what do the native SIMD primitives and the mask representation buy? | 186 | 180 out of variant set, 36 quadratic two-way |

**`screen`** — all 25 direct names plus the sixteen indirect ones, at one point
per axis: u32, 512-bit intrinsics, `asc`, `cols=3`, L2 and LLC, six representative
shapes. (25 + 16) × 6 × 2 = 492 less the 40 two-way cases on a low-cardinality key.
The 8 further drops are the indirect `deep_parallel_` cells, which do not exist.
Minutes, one process. Output: a dominance ranking, and the first `move=` pairing.

**`tune`** — the parallel survivors only, and **coordinate descent** over the three
per-process axes rather than a grid, because they interact weakly: the thresholds
decide what is worth queueing, the worker count decides how many consumers exist.

```text
workers   {1,2,4,8,16,24} at default thresholds     6 processes
task      {512,4096,32768} at the best worker count 3 processes
partition {0,4096,16384,65536} at the best of both  4 processes
                                                   13 processes
```

A full grid over the same values is 72 processes for information coordinate
descent recovers.

**`characterize`** — set `COSORT_VARIANTS` to the finalists from `screen`; the
binary warns when it is unset, because unrestricted it registers every variant.
With four algorithms: 40 dataset parameter sets × 3 sizes × 2 element widths ≈ 960
cases, plus targeted slices for lanes (72), direction (36) and column count (96).

**`attribute`** — the style experiment, deliberately separate: 4 algorithm
configurations (2way|3way × ins|net, serial post-sort) × 3 styles × 3 widths × 3
shapes × 2 sizes. It answers two questions that the other stages hold fixed.

*What does a native primitive buy?* As of `v0.2.8` the clang families reach the
hardware `compress`/`expand`, so what remains emulated on that path is
`permute_lanes`, a per-lane scalar loop used only by the bitonic leaf. The stage
therefore separates cleanly: on the `ins` leaf the clang families land within a few
percent of the intrinsic one, and the `net` leaf isolates the cost of one emulated
primitive. That is also the portability result, because on a target whose profile
lacks a native permute the fallback is what you get.

*What does the mask representation buy?* `clang_v*` and `clang_v*_bool` differ only
in the type of a mask — a lane-wide compare result versus a packed boolean vector
that lowers to a k-register — so the pair is a controlled experiment, and the answer
turns out to depend on width rather than being uniform. Two effects compete: the
bitonic leaf keeps one recorded exchange mask per comparator, 80 of them, which is
5,120 B of stack for `clang_v512` against 160 B for `clang_v512_bool`; against that,
a packed mask on a narrow vector has to be converted to and from the compare result
the 128-bit instructions produce.

Whole programme: roughly 2,200 measured cases, one to two hours, against ~168,000
for the full Cartesian product. Completeness of the *questions* is the goal, not
completeness of the product.

## Tuning the frequency detector

`rle=iaa_freq_sw` / `rle=iaa_freq_hw` do not scan at all. They count the values of
a range *before* it is sorted -- order does not affect a multiset -- and afterwards
the multiplicity of a value is the length of its run, so discovery becomes one step
per distinct value with no comparison. The counts come from
`iaa_distinct_frequencies.hpp` and the walk from `iaa_frequency_run_detector.hpp`,
reached through a `prepare` hook the sorter offers before sorting a range.

Only `move=index` with `post` discovery can offer that hook: incremental reporting
happens *during* partitioning, so there is no moment at which the range is known
and unsorted. `detector_applies` encodes that, and everything else drops.

The one parameter that matters is `COSORT_MIN_OFFLOAD`, the range size below which
the detector declines and the scalar scan runs. It matters more than it looks,
because the walk's cost scales with the *distinct count* while the scan's scales
with the range: there is a crossover, it moves with cardinality, and above some
cardinality it does not exist at all.

`bench_iaa_frequency_min_offload` finds it. It times the sequence a sorter
performs, twice over the same range -- `sort + scan` against
`prepare + sort + walk` -- so the difference is exactly the part of the walk the
sort failed to hide, less the scan it replaced. Nothing is modelled and the
overlap is real:

```bash
cmake --preset iaa && cmake --build --preset iaa --target bench_iaa_frequency_min_offload
./bench_iaa_frequency_min_offload            # hardware, the default
./bench_iaa_frequency_min_offload sw         # QPL software path
./bench_iaa_frequency_min_offload --csv min_offload.csv
```

It prints a delta per (distinct values, range size) and then the crossover per
cardinality. Take the largest crossover among the cardinalities that matter: below
a threshold the detector declines, which is the safe direction to be wrong in.

On the software path, which is all a DSA host can run, the answer is a harness
check rather than a result -- QPL executes each scan on the calling thread there,
so the walk consumes a core instead of a device:

```text
distinct=4        COSORT_MIN_OFFLOAD=16384
distinct=64       never -- the scan is cheaper at every size measured
distinct=1024     never
distinct=16384    never
distinct=1048576  never
```

That is the expected shape and it says the tool works, not that the idea does not.

**Read `rle_coverage` before believing any ratio on a frequency row.** It is the
share of discovered elements the counts resolved rather than a fallback scan, and
a row can look near-parity purely because the fast path barely ran -- an early
measurement here reported 1.04-1.21x that turned out to be 5 prepared ranges
against a million fallbacks. At full coverage and with the snapshot eliminated the
software path costs 1.16-1.19x, essentially all of it the walk executing on a
core, which is the component hardware replaces.

One cost the idea does *not* pay, since it caused some confusion: there is no
snapshot. `TslIaaDistinctFrequencies::start` keeps a pointer and needs its input
unchanged, and a sort rewrites exactly that range -- but the indirect sorter never
writes its source columns, so at level 0 `prepare` reads the column directly, and
below it the materialize pass mirrors the gathered keys into a second buffer for
one extra store rather than a second pass. `rle_snapshot_elements` reports zero on
every row above.

## Choosing the leaf per leaf

`leaf=ins` and `leaf=net` were a configuration axis in the corpus and the sweep
picked whichever won per case. `leaf=hyb` makes the choice per leaf instead, and
`bench_hybrid_leaf` is the standalone sweep that found its threshold. The two fixed
configurations differ in more than which leaf runs:

| | leaf | partitioning stops at | cost per leaf |
| --- | --- | --- | --- |
| `net` | one full-capacity bitonic sort | capacity (256 for u32/AVX-512) | constant |
| `ins` | insertion | 64 | quadratic |

A constant cost is a good trade for a full leaf and a bad one for a sparse leaf, so
the right choice follows the leaf's *fill ratio* — which the data and the row count
decide, not the configuration. Eight columns, u32/AVX-512, three-way, post-sort,
best of five:

| shape | rows | `ins` | `net` | diverted | hybrid |
| --- | --- | --- | --- | --- | --- |
| `low_cardinality_d4` | 2^18 | 12.20 ms | 20.08 ms | 74% | 13.74 ms |
| `low_cardinality_d4` | 2^20 | 40.04 ms | 39.19 ms | 0% | 39.43 ms |
| `skewed_zipf_s1` | 2^18 | 20.04 ms | 197.86 ms | 98% | 29.33 ms |
| `unique_first` | 2^20 | 70.75 ms | 57.23 ms | 2% | 55.80 ms |

Four distinct values per column put 4^7 groups under eight columns, so at 2^20 rows
the leaves hold exactly 64 elements and at 2^18 only 16 — the same shape and the
same column count with opposite winners. `skewed_zipf_s1`'s 9.9x is the fixed cost
paid on leaves of a handful of elements.

The knob is `HybridFillPercent` on `TslMultiColumnQuickSorter`: with `leaf=net`, a
leaf below that share of capacity goes to the insertion leaf instead, and a range
too sparse for the network but longer than insertion's own threshold keeps
partitioning. The sweep therefore reaches both fixed configurations by
construction, so it cannot miss a winner by not extending far enough — `P=100`
leaves only exactly-full leaves to the network and measured 83.98 ms where `ins`
measured 80.14. Its other end does *not* reduce to `net`: `P=1` diverts only
two-element leaves, and on `skewed_zipf_s1` those are already 30% of all leaves, so
it measured 454.89 ms against `net`'s 551.77 — an 18% saving from the cheapest
possible diversion.

Read `P=100` against `ins` as the noise floor too: the same pair measured 0.6%
apart in one run and 4.8% apart in another, best-of-five each time. Nothing below
about 5% is claimed as a per-configuration difference here, which is why the result
below is stated over 24 configurations rather than on any one of them.

**No setting beats the better fixed configuration by more than that noise.** What it
buys is not having to know the shape. Against the per-configuration oracle over
{`ins`, `net`}, four shapes x {2^18, 2^20} rows x {2, 4, 8} columns:

| policy | geomean | worst case |
| --- | --- | --- |
| `ins` | 1.195 | 1.91x |
| `net` | 1.313 | 9.87x |
| `P = auto` | 1.044 | 1.46x |
| `P = 50` | 1.103 | 1.30x |

`auto` is parameter-free: divert exactly the leaves the insertion configuration
would have handled itself, i.e. run the network only where it is at least as full
as insertion's threshold. That is 64 of 256 for u32/AVX-512 (25%) and 64 of 128 for
u64 (50%), so it is derived from the capacity rather than tuned —
`tsl_hybrid_auto_percent`. The residual 1.46x is the network's own threshold: under
`auto` a leaf of 64..256 elements still goes to the network as one full-capacity
sort where `ins` would have partitioned it further, and `P=50` trades average for
worst case by raising that bar.

Read as a corpus result: fixing one leaf for the whole sweep costs 20% (`ins`) or
31% (`net`) on average, so `leaf` has to stay an axis — but a per-leaf rule with no
parameter gets within 4% of knowing the answer in advance, which is what a
production sorter would want.

`HybridFillPercent` defaults to 0, and every other instantiation in the tree uses
that default, so `leaf_accepts` reduces to the previous `count > leaf_threshold`
loop condition and the corpus is unaffected. `test_multicolumn_sort` and
`test_multicolumn_index_sort` pass unchanged.

```bash
./bench_hybrid_leaf                                  # the default sweep
./bench_hybrid_leaf --shapes skewed_zipf_s1 --cols 8 --rows 1048576
./bench_hybrid_leaf --csv hybrid.csv
```

### In the corpus

`leaf=hyb` is a value of the corpus axis, so it registers across every execution,
discovery, movement and detector without further wiring, and `hybrid_fill_percent`
is published per case. The direct family goes 24 -> 36 algorithm configurations and
the indirect 16 -> 24; `cosort_bench` takes 200s to build rather than 137s.

Measured with real discovery rather than in the standalone driver — u32, LLC, eight
columns, `rle=scalar`, the two shapes where the fixed leaves disagree most, so this
is the *unfavourable* selection for the hybrid rather than a representative one:

| shape | move | family | `ins` | `net` | `hyb` | vs better fixed |
| --- | --- | --- | --- | --- | --- | --- |
| `skewed_zipf_s1` | direct | `incremental_3way` | 610.7 ms | 3036.6 ms | 718.2 ms | -17.6% |
| `skewed_zipf_s1` | direct | `post_3way` | 650.2 ms | 2557.9 ms | 730.9 ms | -12.4% |
| `skewed_zipf_s1` | index | `post_3way` | 816.7 ms | 3853.4 ms | 978.6 ms | -19.8% |
| `skewed_zipf_s1` | index | `parallel_incremental_3way` | 1231.7 ms | 1320.6 ms | 1150.2 ms | +6.6% |
| `low_cardinality_d4` | direct | `parallel_incremental_3way` | 62.3 ms | 62.2 ms | 60.9 ms | +2.1% |
| `low_cardinality_d4` | direct | `post_3way` | 225.4 ms | 233.8 ms | 231.7 ms | -2.8% |
| `low_cardinality_d4` | index | `post_3way` | 397.9 ms | 420.3 ms | 441.5 ms | -10.9% |

Consistent with the standalone sweep rather than in tension with it: `hyb` trails
`ins` by 12-20% on zipf, which is the same 1.46x-worst-case shape, while `net`
trails it by 370-470% and the hybrid removes nearly all of that. The one family
where the hybrid wins outright is the indirect parallel one.

### With the detector axis

The leaf axis and the discovery axis were expected to interact: the hybrid keeps
partitioning below the network's threshold, so `incremental` reports more and
smaller fragments, and a fragment under `min_offload` declines and falls back to
the scalar scan. Measured, that interaction does not appear. Four columns, halfLLC,
u32, medians of five, `hyb/ins` per detector — the ratio is what matters, since a
detector changes both variants alike:

| shape | family | `scalar` | `dml_sw` |
| --- | --- | --- | --- |
| `independent_uniform_c1024` | `parallel_post_3way` | 0.847 | 0.760 |
| `independent_uniform_c1024` | `parallel_incremental_3way` | 0.816 | 0.808 |
| `unique_last_g64` | `parallel_post_3way` | 0.975 | 0.872 |
| `unique_last_g64` | `parallel_incremental_3way` | 0.994 | 0.984 |
| `low_cardinality_d4` | `parallel_post_3way` | 0.978 | 0.963 |
| `low_cardinality_d4` | `parallel_incremental_3way` | 1.000 | 0.999 |

`move=index`, `post_3way`, the same sizes, against all three IAA-side backends:

| shape | `scalar` | `iaa_sw` | `iaa_freq_sw` |
| --- | --- | --- | --- |
| `independent_uniform_c1024` | 0.890 | 0.910 | 0.871 |
| `low_cardinality_d4` | 1.004 | 0.993 | 1.015 |
| `unique_last_g64` | 1.154 | 1.110 | 1.151 |

The ratio is set by the shape, not by the backend: it moves by at most 4 points
across three IAA backends and never against the hybrid on the DSA side, where
offload in fact widens the margin slightly. The reason the predicted interaction is
harmless is that it is bounded on the wrong side — a fragment below `min_offload`
falls back to the scalar scan, which is what the scalar detector would have cost
anyway, so smaller fragments can cost the hybrid the *offload* but not more than
running without one. **The leaf choice and the discovery backend can be tuned
independently.**

This pass also produced the hybrid's clearest win, on a shape the standalone sweep
did not cover. `independent_uniform_c1024`, `parallel_post_3way`, `rle=scalar`:
`ins` 224.69 ms, `net` 1126.79 ms, `hyb` 190.27 ms — 15% better than the better
fixed leaf and 5.9x better than the worse one. A thousand distinct values over four
columns puts almost every leaf in the sparse range where the network's fixed cost
is wasted but the ranges are still long enough that insertion's threshold of 64
partitions more than it needs to.

Serial, post-sort, `move=direct`, `rle=scalar` only — the driver has no detector
seam at all, just `tsl_for_each_equal_run` — and every policy comes out of one
driver in `multicolumn_qs_hybrid_leaf.hpp`, so a comparison between them changes
exactly one template argument.

Deliberately not an axis in the corpus, and one interaction argues against making
it one naively. `leaf_sink` fires once per leaf, after the partition loop exits, so
changing when that loop exits changes what `incremental` discovery is handed: a
range of 64..256 elements that `net` would have leafed keeps partitioning under the
hybrid, and the same data therefore yields **more reported fragments, each
smaller**. That is a wash for `rle=scalar` but the wrong direction for every
accelerator backend, because a fragment below `min_offload` (4096 by default)
declines and falls back to the scalar scan anyway. Under `move=index` with `post`
the effect is different rather than absent: `prepare` is per range and not per
leaf, so fragment size does not move, but the extra partitioning below 256 adds key
movement to the window `prepare` is trying to hide behind.

So the rule is measured where it is cleanest and its interaction with the
discovery and execution axes is untested in both directions.

## Builds

```bash
cmake --preset clang && cmake --build --preset clang          # any host
cmake --preset dsa   && cmake --build --preset dsa            # a DSA host
QPL_ROOT=<prefix> cmake --preset iaa && cmake --build --preset iaa   # an IAA host
```

The presets pin **both** `CMAKE_C_COMPILER` and `CMAKE_CXX_COMPILER`. That is not
cosmetic: DML calls `enable_language(C)`, and CMake takes the C compiler from the
environment, so a `CC` naming something unexpected breaks DML's AVX-512 kernels
deep inside the fetched tree. Prerequisites are checked at configure time and name
what is missing: `<uuid/uuid.h>` for DML's hardware dispatcher, and a C compiler
that accepts `-march=skylake-avx512`.

Adding the IAA backend on the IAA host means providing
`test-sort/iaa_run_detector.hpp` with `TslIaaRunDetector<T>` and
`TslIaaAsyncRunDetector<T>` satisfying the contract documented at the top of
`cosort_detectors.hpp`; configuring `TSL_COSORT_ENABLE_IAA=ON` without it fails at
configure time naming the file.

## Reporting conventions

- **Normalize by $W$ across shapes.** Raw ns/row between `unique_first` and
  `unique_last` is meaningless — they differ in intrinsic work by orders of
  magnitude. Within one shape, ns/row is fine. `COSORT_DESCRIBE=1` publishes
  `work_per_row`, `scan_per_row`, `distinct_first` and `duplicate_tuple_frac`.
- **Compare measured discovery volume against predicted $\sum R_j$.** A gap means
  discovery is scanning ranges it should not.
- **State the element-width convention.** Size levels hold bytes per column
  constant, so a u64 case has half the rows of the u32 case at the same level. A
  cross-width plot at fixed footprint conflates narrower keys with more rows.
- **Across machines, compare ratios, never absolute times.** A DSA host and an IAA
  host are different hardware; what transfers is each host's ratio of a backend to
  its own `rle=scalar` row at the same dataset, size and worker count.
  `sweep_multicolumn_bench.py` refuses to merge runs from different hosts, and that
  refusal should stay.
- **Every drop is reported.** A silently narrowed run reads as full coverage.

## Open items

1. **Element-width convention** — keep bytes-per-column constant, or add a
   fixed-row mode? Only affects how cross-width results are read.
2. **`16xLLC`** — a 5-column u64 case there is ~19 GiB after the working copy.
   Keep in the default range or require it explicitly?
3. **Incremental two-way costs about 4% and saves no scanning** — kept for
   completeness, but a candidate to drop from `screen` if the sweep needs
   trimming. Whether the earlier task exposure helps at higher worker counts or on
   the skewed shapes is unmeasured.
4. **`dsa_hw` fails on this host** with `DML_STATUS_BATCH_LIMITS_ERROR`, and so
   does the pre-existing `test_dsa_run_detector hw`, so the fault predates this
   harness. Until it is diagnosed a DSA host measures `scalar` and `dml_sw`.
   `dml_sw` itself only started working while measuring the hybrid leaf: its fleet
   gave each new thread a permanent slot, and the executor starts fresh workers per
   sort, so it threw `fewer slots than calling threads` on the second gbench
   iteration of any parallel case. `TslDsaDetectorFleet` is now the same
   borrow-and-return pool as the IAA one. Any earlier `dml_sw` figure in this
   document predates the executor change that broke it.
5. **IAA is unverified on hardware.** `iaa_sw`/`iaa_hw` and their asynchronous
   forms are implemented and the software path passes its differential test, but
   this host has `/dev/dsa` and no `/dev/iax`. `test_iaa_run_detector hw` and
   `COSORT_RLE=iaa_hw,iaa_hw_async` still have to run on the IAA machine.
   `iaa_sw` numbers are QPL's own CPU scan, not an accelerator, and the
   asynchronous form is *structurally* meaningless there because
   `qpl_submit_job` executes the scan on the calling thread.
6. **The indirect family has no `deep_parallel_` form.** Column 0 is split inside
   its partitions, but a *deeper* single-range level -- one under a maximal tie --
   still runs on one thread, because splitting it measured worse. Making that case
   pay needs the nested executor removed, i.e. the partition split expressed as
   tasks in the same tree rather than a tree of its own.
7. **Asynchronous detectors are unreachable from the indirect family.** The
   blocker is now narrow and fixable: the child-submitting emitters must own what
   they need, the way `process_parallel_task`'s `make_emit` does, before an
   `rle=iaa_hw_async` row can exist for `move=index`.
8. **`gather` is still scalar-emulated for the clang families** in `v0.2.9`, so
   `move=index` with `style=clang` measures that emulation: 34.92 ms against
   19.14 ms for `intr` at 4 columns. It is the same class of gap the `net` leaf
   had before `v0.2.9` fixed `permute_lanes`.
9. **The hybrid leaf's shape dependence is not predictable yet.** It is now
   measured across executions, both movements, both discoveries and four detector
   backends, and the detector turns out not to matter. What decides it is the
   shape: +15% on `independent_uniform_c1024`, neutral on `low_cardinality_d4`,
   -15% on `unique_last_g64`, -12 to -20% on `skewed_zipf_s1`. Promoting it to a
   default needs a leaf-size distribution that predicts the sign, which
   `bench_hybrid_leaf` can report but does not yet.
10. **`dml_sw` on `skewed_zipf_s1` does not finish.** One case
   (`parallel_post_3way_ins`, four columns, halfLLC) takes 115 ms with `rle=scalar`
   and had not completed after 240 s with `rle=dml_sw`. It reproduces on `ins`, so
   it is a property of the DSA detector on a heavy-tailed key, not of the leaf
   axis, and it is why the accelerator tables above use
   `independent_uniform_c1024` in zipf's place. Undiagnosed.
11. **The dangling IAA plan** — `multi-column-sort-plan.md` defers Slice 9 to
   `iaa-rle-offload-plan.md`, which does not exist. Write it or restate Slice 9 as
   the DSA work that shipped.
